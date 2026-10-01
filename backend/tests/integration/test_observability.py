"""Integration tests for Observability API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict

from app.db.models.ai_run import AIRun
from app.db.models.ticket import Ticket
from app.db.models.approval import ApprovalRequest


ORG_A = {
    "org_name": "Acme Observability",
    "org_slug": "acme-observability",
    "full_name": "Alice Admin",
    "email": "alice@acme-observability.com",
    "password": "SecurePass1",
}

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


async def _register_and_token(client: AsyncClient, payload: dict) -> str:
    """Register a user and return a valid access token."""
    await client.post(REGISTER_URL, json=payload)
    resp = await client.post(LOGIN_URL, json={"email": payload["email"], "password": payload["password"]})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_metrics_empty(
    client: AsyncClient, db_session: AsyncSession
):
    """Test getting metrics when no AI runs exist."""
    token = await _register_and_token(client, ORG_A)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/observability/metrics", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_runs"] == 0
    assert data["success_rate"] is None
    assert data["total_cost"] == 0.0


@pytest.mark.asyncio
async def test_get_metrics_with_data(
    client: AsyncClient, db_session: AsyncSession
):
    """Test getting metrics with existing AI runs."""
    
    # We need to get the org_id and user_id first
    token = await _register_and_token(client, {**ORG_A, "email": "bob@acme-obs.com", "org_slug": "bob-org"})
    me_resp = await client.get("/api/v1/auth/me", headers=_auth(token))
    user_id = me_resp.json()["id"]
    org_id = me_resp.json()["org_id"]

    # Create ticket
    ticket = Ticket(
        title="Test Observability",
        description="Something is broken",
        requester_id=user_id,
        org_id=org_id
    )
    db_session.add(ticket)
    await db_session.flush()

    # Create successful run
    run1 = AIRun(
        org_id=org_id,
        ticket_id=ticket.id,
        decision="restart service",
        confidence=0.9,
        latency_ms=1000,
        input_tokens=1000,
        output_tokens=500,
        estimated_cost_usd=0.05,
        model_used="gpt-4o-mini"
    )
    # Create failed run (no decision)
    run2 = AIRun(
        org_id=org_id,
        ticket_id=ticket.id,
        decision=None,
        confidence=0.1,
        latency_ms=2000,
        input_tokens=500,
        output_tokens=100,
        estimated_cost_usd=0.01,
        model_used="gpt-4o-mini"
    )
    db_session.add_all([run1, run2])
    await db_session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/observability/metrics", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_runs"] == 2
    assert data["success_rate"] == 0.5  # 1/2 successful
    assert data["avg_latency"] == 1500.0
    assert data["total_tokens"] == 2100
    assert data["total_cost"] == pytest.approx(0.06)
    assert data["p95_latency"] > 0.0


@pytest.mark.asyncio
async def test_get_ai_run_trace(
    client: AsyncClient, db_session: AsyncSession
):
    """Test fetching a full AI run trace."""
    token = await _register_and_token(client, {**ORG_A, "email": "charlie@acme-obs.com", "org_slug": "charlie-org"})
    me_resp = await client.get("/api/v1/auth/me", headers=_auth(token))
    user_id = me_resp.json()["id"]
    org_id = me_resp.json()["org_id"]

    # Create ticket
    ticket = Ticket(
        title="Test Trace",
        description="Trace this",
        requester_id=user_id,
        org_id=org_id
    )
    db_session.add(ticket)
    await db_session.flush()

    run = AIRun(
        org_id=org_id,
        ticket_id=ticket.id,
        decision="test",
    )
    db_session.add(run)
    await db_session.flush()

    from app.db.models.ai_run import RiskLevel
    # Add approval
    approval = ApprovalRequest(
        org_id=org_id,
        ticket_id=ticket.id,
        ai_run_id=run.id,
        proposed_action="test",
        reason="test",
        risk_level=RiskLevel.HIGH,
        requested_by_id=user_id
    )
    db_session.add(approval)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(f"/api/v1/observability/runs/{run.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(run.id)
    assert "ticket" in data
    assert data["ticket"]["id"] == str(ticket.id)
    assert "approval" in data
    assert data["approval"]["id"] == str(approval.id)

@pytest.mark.asyncio
async def test_observability_cost_calculation(client: AsyncClient, db_session: AsyncSession):
    from app.ai.evaluation.pricing import calculate_cost
    
    # Known model
    cost1 = calculate_cost("gpt-4o", 1000, 1000)
    assert cost1 is not None
    assert cost1 > 0
    
    # Unknown model returns null
    cost2 = calculate_cost("unknown-model", 1000, 1000)
    assert cost2 is None

@pytest.mark.asyncio
async def test_observability_sql_aggregation(client: AsyncClient, db_session: AsyncSession):
    # Register org and get token
    token = await _register_and_token(client, {**ORG_A, "email": "dave@acme-obs.com", "org_slug": "dave-org"})
    me_resp = await client.get("/api/v1/auth/me", headers=_auth(token))
    user_id = me_resp.json()["id"]
    org_id = me_resp.json()["org_id"]

    import uuid
    from datetime import datetime
    
    # Insert known dataset with latencies
    latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    for lat in latencies:
        run = AIRun(
            id=uuid.uuid4(),
            org_id=uuid.UUID(org_id),
            model_used="gpt-4o",
            latency_ms=lat,
            created_at=datetime.utcnow(),
            decision="test",
            confidence=0.9
        )
        db_session.add(run)
    await db_session.commit()
    
    response = await client.get("/api/v1/observability/metrics", headers=_auth(token))
    assert response.status_code == 200
    data = response.json()
    
    # Check percentiles
    # For [100..1000], P50 is ~550, P95 is ~955 (percentile_cont interpolates)
    assert 500 <= data["p50_latency"] <= 600
    assert 900 <= data["p95_latency"] <= 1000

@pytest.mark.asyncio
async def test_org_isolation(client: AsyncClient, db_session: AsyncSession):
    import uuid
    from datetime import datetime
    
    # Register Org A
    token_a = await _register_and_token(client, {**ORG_A, "email": "eve@org-a.com", "org_slug": "eve-org-a"})
    me_a = await client.get("/api/v1/auth/me", headers=_auth(token_a))
    org_a_id = me_a.json()["org_id"]
    
    # Register Org B
    token_b = await _register_and_token(client, {**ORG_A, "email": "frank@org-b.com", "org_slug": "frank-org-b"})
    me_b = await client.get("/api/v1/auth/me", headers=_auth(token_b))
    org_b_id = me_b.json()["org_id"]

    # Insert run for Org A
    run_org_a = AIRun(
        id=uuid.uuid4(),
        org_id=uuid.UUID(org_a_id),
        model_used="gpt-4o",
        created_at=datetime.utcnow()
    )
    db_session.add(run_org_a)
    await db_session.commit()
    
    # Org A sees it
    res_a = await client.get("/api/v1/observability/runs", headers=_auth(token_a))
    assert res_a.status_code == 200
    assert len(res_a.json()) >= 1
    
    # Org B does not see it
    res_b = await client.get("/api/v1/observability/runs", headers=_auth(token_b))
    assert res_b.status_code == 200
    assert len(res_b.json()) == 0
