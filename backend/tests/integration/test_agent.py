"""
Integration tests — Agent Reasoning Engine API (Phase 4).

Tests:
  1. Successful agent run with Mock LLM — verifies all output fields.
  2. Org isolation — Org A cannot run agent on Org B's ticket.
  3. Insufficient evidence — when mock RAG returns empty (fresh org with no docs).
  4. Persistence — ai_runs row is correctly populated with latency, confidence, etc.
  5. History endpoints — GET /agents/runs and GET /agents/runs/{id} work correctly.
  6. Confidence filtering on GET /agents/runs?min_confidence=0.9 returns empty.
  7. 404 for non-existent or cross-org run ID.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_run import AIRun

# ─── URLs ──────────────────────────────────────────────────────────────────────

BASE = "/api/v1"
REGISTER_URL = f"{BASE}/auth/register"
LOGIN_URL    = f"{BASE}/auth/login"
TICKETS_URL  = f"{BASE}/tickets"
AGENTS_URL   = f"{BASE}/agents"


# ─── Test org definitions ─────────────────────────────────────────────────────

ORG_A = {
    "org_name": "Alpha Corp",
    "org_slug": "alpha-corp-agent",
    "full_name": "Alice Alpha",
    "email": "alice@alpha-agent.io",
    "password": "AgentPass1",
}

ORG_B = {
    "org_name": "Beta Corp",
    "org_slug": "beta-corp-agent",
    "full_name": "Bob Beta",
    "email": "bob@beta-agent.io",
    "password": "AgentPass1",
}

SAMPLE_TICKET = {
    "title": "Database connection pool exhausted",
    "description": (
        "All API requests are failing with DB connection timeout. "
        "Pool size is 10, current connections: 10/10. Error: too many clients."
    ),
    "priority": "critical",
    "severity": "s1",
    "category": "database",
    "affected_service": "postgres-primary",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, payload: dict) -> str:
    """Register (idempotent) and return a JWT access token."""
    await client.post(REGISTER_URL, json=payload)
    r = await client.post(
        LOGIN_URL,
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_ticket(client: AsyncClient, token: str) -> str:
    """Create a ticket and return its ID."""
    r = await client.post(TICKETS_URL, json=SAMPLE_TICKET, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAgentRun:
    """Successful agent run and field verification."""

    async def test_run_agent_returns_structured_result(self, client: AsyncClient):
        """Mock LLM returns valid Pydantic output for all three structured nodes."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()

        # Required top-level fields
        assert uuid.UUID(data["ai_run_id"])          # valid UUID
        assert data["ticket_id"] == ticket_id
        assert data["confidence"] is not None
        assert 0.0 <= data["confidence"] <= 1.0
        assert data["risk_level"] in ("low", "medium", "high", "blocked")
        assert isinstance(data["requires_approval"], bool)
        assert isinstance(data["insufficient_evidence"], bool)
        assert isinstance(data["errors"], list)
        assert data["latency_ms"] is not None and data["latency_ms"] > 0

        # Classification must be structured
        cls = data["classification"]
        assert cls is not None
        assert cls["category"]
        assert cls["priority"] in ("low", "medium", "high", "critical")
        assert cls["severity"] in ("s1", "s2", "s3", "s4")
        assert 0.0 <= cls["confidence"] <= 1.0

        # Diagnosis must be structured
        diag = data["diagnosis"]
        assert diag is not None
        assert diag["root_cause"]
        assert isinstance(diag["affected_components"], list)
        assert diag["impact_summary"]
        assert isinstance(diag["evidence"], list)

        # Recommendation must be structured
        rec = data["recommendation"]
        assert rec is not None
        assert rec["action"]
        assert isinstance(rec["steps"], list) and len(rec["steps"]) > 0
        assert rec["risk_level"] in ("low", "medium", "high", "blocked")
        assert rec["estimated_resolution_time"]

    async def test_run_agent_no_raw_json_parse_errors(self, client: AsyncClient):
        """Agent should complete with zero errors in mock mode (no LLM parse failures)."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json()["errors"] == [], "Mock LLM must produce zero parse errors"

    async def test_run_agent_requires_auth(self, client: AsyncClient):
        """Unauthenticated requests must be rejected."""
        r = await client.post(f"{TICKETS_URL}/{uuid.uuid4()}/run-agent")
        assert r.status_code == 403


@pytest.mark.asyncio
class TestAgentOrgIsolation:
    """Org A cannot trigger or view agent results from Org B's tickets."""

    async def test_org_a_cannot_run_on_org_b_ticket(self, client: AsyncClient):
        """Running agent on another org's ticket returns 404."""
        token_a = await _register_and_login(client, ORG_A)
        token_b = await _register_and_login(client, ORG_B)

        # Org B creates a ticket
        ticket_id = await _create_ticket(client, token_b)

        # Org A tries to run agent on Org B's ticket
        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token_a),
            timeout=30,
        )
        # Must be 404 (not 403) to prevent ticket ID enumeration
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    async def test_org_a_cannot_view_org_b_run(self, client: AsyncClient):
        """GET /agents/runs/{id} returns 404 for a run belonging to another org."""
        token_a = await _register_and_login(client, ORG_A)
        token_b = await _register_and_login(client, ORG_B)

        # Org B runs agent
        ticket_id_b = await _create_ticket(client, token_b)
        r = await client.post(
            f"{TICKETS_URL}/{ticket_id_b}/run-agent",
            headers=_auth(token_b),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        run_id = r.json()["ai_run_id"]

        # Org A tries to fetch Org B's run
        r = await client.get(
            f"{AGENTS_URL}/runs/{run_id}",
            headers=_auth(token_a),
        )
        assert r.status_code == 404, f"Cross-org run exposure: {r.status_code}"

    async def test_list_runs_only_returns_own_org(self, client: AsyncClient):
        """GET /agents/runs must only return runs for the authenticated org."""
        token_a = await _register_and_login(client, ORG_A)
        token_b = await _register_and_login(client, ORG_B)

        # Org A runs agent
        ticket_a = await _create_ticket(client, token_a)
        r = await client.post(
            f"{TICKETS_URL}/{ticket_a}/run-agent",
            headers=_auth(token_a),
            timeout=30,
        )
        assert r.status_code == 200
        run_id_a = r.json()["ai_run_id"]

        # Org B lists runs — must NOT see Org A's run
        r = await client.get(f"{AGENTS_URL}/runs", headers=_auth(token_b))
        assert r.status_code == 200
        run_ids = [item["id"] for item in r.json()["items"]]
        assert run_id_a not in run_ids, "Org A's run leaked into Org B's history"


@pytest.mark.asyncio
class TestAgentInsufficientEvidence:
    """
    Insufficient evidence is flagged when confidence is below threshold.

    In mock mode the confidence is always ~0.83, so we test the API contract:
    the field must be present and boolean.
    """

    async def test_insufficient_evidence_field_present(self, client: AsyncClient):
        """Response always contains the insufficient_evidence boolean."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "insufficient_evidence" in data
        assert isinstance(data["insufficient_evidence"], bool)

    async def test_high_confidence_mock_not_flagged_insufficient(self, client: AsyncClient):
        """Mock LLM returns 0.83 confidence which should NOT trigger insufficient_evidence."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token),
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        # Mock confidence ≈ 0.827 > 0.4 threshold
        assert data["insufficient_evidence"] is False


@pytest.mark.asyncio
class TestAgentPersistence:
    """Verify the ai_runs row is correctly populated after a run."""

    async def test_ai_run_persisted_to_database(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """After a run, the ai_runs table must contain the correct record."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        run_id = uuid.UUID(r.json()["ai_run_id"])

        # Fetch from DB
        result = await db_session.execute(
            select(AIRun).where(AIRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        assert run is not None, "ai_run record not found in database"

        # Field assertions
        assert run.ticket_id == uuid.UUID(ticket_id)
        assert run.confidence is not None and 0.0 <= run.confidence <= 1.0
        assert run.risk_level is not None
        assert run.latency_ms is not None and run.latency_ms > 0
        assert run.model_used is not None
        assert run.decision is not None          # Recommendation action
        assert run.reasoning is not None         # Root cause + impact
        assert isinstance(run.evidence, list)    # Diagnosis evidence
        assert run.agent_trace is not None       # Full trace stored
        assert "nodes_executed" in run.agent_trace
        assert "classification" in run.agent_trace
        assert "diagnosis" in run.agent_trace
        assert "recommendation" in run.agent_trace

    async def test_ticket_ai_fields_updated_after_run(
        self, client: AsyncClient
    ):
        """After a run, the ticket's ai_confidence and ai_diagnosis fields are populated."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        # Run agent
        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token),
            timeout=30,
        )
        assert r.status_code == 200

        # Fetch the ticket and check AI fields
        r = await client.get(f"{TICKETS_URL}/{ticket_id}", headers=_auth(token))
        assert r.status_code == 200
        ticket = r.json()
        assert ticket["ai_confidence"] is not None
        assert 0.0 <= ticket["ai_confidence"] <= 1.0
        assert ticket["ai_diagnosis"] is not None
        assert "root_cause" in ticket["ai_diagnosis"]


@pytest.mark.asyncio
class TestAgentHistory:
    """History endpoint tests."""

    async def test_list_runs_paginated(self, client: AsyncClient):
        """GET /agents/runs returns the correct pagination shape."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        # Create two runs
        for _ in range(2):
            r = await client.post(
                f"{TICKETS_URL}/{ticket_id}/run-agent",
                headers=_auth(token),
                timeout=30,
            )
            assert r.status_code == 200

        r = await client.get(f"{AGENTS_URL}/runs", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        assert data["total"] >= 2
        assert data["page"] == 1

    async def test_filter_runs_by_ticket(self, client: AsyncClient):
        """GET /agents/runs?ticket_id=... filters correctly."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token),
            timeout=30,
        )
        assert r.status_code == 200

        r = await client.get(
            f"{AGENTS_URL}/runs?ticket_id={ticket_id}",
            headers=_auth(token),
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(item["ticket_id"] == ticket_id for item in items)

    async def test_filter_runs_by_high_confidence_returns_empty(self, client: AsyncClient):
        """min_confidence=0.99 should return empty for mock runs (confidence ≈ 0.83)."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token),
            timeout=30,
        )
        assert r.status_code == 200

        r = await client.get(
            f"{AGENTS_URL}/runs?min_confidence=0.99",
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_get_run_detail(self, client: AsyncClient):
        """GET /agents/runs/{id} returns full structured output."""
        token = await _register_and_login(client, ORG_A)
        ticket_id = await _create_ticket(client, token)

        r = await client.post(
            f"{TICKETS_URL}/{ticket_id}/run-agent",
            headers=_auth(token),
            timeout=30,
        )
        assert r.status_code == 200
        run_id = r.json()["ai_run_id"]

        r = await client.get(f"{AGENTS_URL}/runs/{run_id}", headers=_auth(token))
        assert r.status_code == 200
        detail = r.json()
        assert detail["id"] == run_id
        assert detail["ticket_id"] == ticket_id
        assert detail["classification"] is not None
        assert detail["diagnosis"] is not None
        assert detail["recommendation"] is not None
        assert detail["agent_trace"] is not None

    async def test_get_nonexistent_run_returns_404(self, client: AsyncClient):
        """Fetching a run with a random UUID returns 404."""
        token = await _register_and_login(client, ORG_A)
        r = await client.get(
            f"{AGENTS_URL}/runs/{uuid.uuid4()}",
            headers=_auth(token),
        )
        assert r.status_code == 404
