"""
Integration tests for the Ticket Management API — Phase 2.

Covers:
  1. Valid ticket creation and retrieval
  2. Unauthorized access without token
  3. Invalid status transition (OPEN → CLOSED) → 400
  4. Cross-org prevention: User from Org A cannot access Org B's tickets
  5. Audit log is populated on ticket.created and ticket.comment_added
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog

# ─── Test data ────────────────────────────────────────────────────────────────

ORG_A = {
    "org_name": "Acme Corp",
    "org_slug": "acme-corp-tickets",
    "full_name": "Alice Admin",
    "email": "alice@acme-tickets.com",
    "password": "SecurePass1",
}

ORG_B = {
    "org_name": "Beta Corp",
    "org_slug": "beta-corp-tickets",
    "full_name": "Bob Admin",
    "email": "bob@beta-tickets.com",
    "password": "SecurePass1",
}

VALID_TICKET = {
    "title": "API Gateway returning 500 errors",
    "description": "Customers are seeing 500 errors on /v1/payments endpoint intermittently.",
    "priority": "high",
    "category": "API",
    "affected_service": "payment-api",
}

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
TICKETS_URL = "/api/v1/tickets"


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _register_and_token(client: AsyncClient, payload: dict) -> str:
    """Register a user and return a valid access token."""
    await client.post(REGISTER_URL, json=payload)
    resp = await client.post(LOGIN_URL, json={"email": payload["email"], "password": payload["password"]})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestTicketCRUD:
    """Happy-path ticket creation and retrieval."""

    async def test_create_ticket_success(self, client: AsyncClient):
        token = await _register_and_token(client, ORG_A)

        resp = await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token))

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["title"] == VALID_TICKET["title"]
        assert data["priority"] == "high"
        assert data["status"] == "open"
        assert "id" in data
        assert "org_id" in data

    async def test_get_ticket_by_id(self, client: AsyncClient):
        token = await _register_and_token(client, {**ORG_A, "email": "alice2@acme.com", "org_slug": "acme-get"})

        create = await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token))
        assert create.status_code == 201
        ticket_id = create.json()["id"]

        resp = await client.get(f"{TICKETS_URL}/{ticket_id}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == ticket_id

    async def test_list_tickets_returns_only_own_org(self, client: AsyncClient):
        """Sanity check — list endpoint returns tickets."""
        token = await _register_and_token(client, {**ORG_A, "email": "alice3@acme.com", "org_slug": "acme-list"})

        await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token))
        await client.post(TICKETS_URL, json={**VALID_TICKET, "title": "Second ticket same org"}, headers=_auth(token))

        resp = await client.get(TICKETS_URL, headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert isinstance(data["items"], list)

    async def test_create_ticket_unauthenticated(self, client: AsyncClient):
        """No token → 403."""
        resp = await client.post(TICKETS_URL, json=VALID_TICKET)
        assert resp.status_code == 403

    async def test_create_ticket_missing_required_fields(self, client: AsyncClient):
        token = await _register_and_token(client, {**ORG_A, "email": "alice4@acme.com", "org_slug": "acme-missing"})

        # Missing description
        resp = await client.post(TICKETS_URL, json={"title": "No description"}, headers=_auth(token))
        assert resp.status_code == 422

    async def test_create_ticket_short_description(self, client: AsyncClient):
        token = await _register_and_token(client, {**ORG_A, "email": "alice5@acme.com", "org_slug": "acme-short"})

        resp = await client.post(
            TICKETS_URL,
            json={**VALID_TICKET, "description": "Short"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    async def test_delete_ticket_returns_204_no_body(self, client: AsyncClient):
        """DELETE must return 204 with no response body."""
        token = await _register_and_token(
            client, {**ORG_A, "email": "alice-del@acme.com", "org_slug": "acme-del"}
        )
        create = await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token))
        assert create.status_code == 201
        ticket_id = create.json()["id"]

        resp = await client.delete(f"{TICKETS_URL}/{ticket_id}", headers=_auth(token))
        assert resp.status_code == 204
        assert resp.content == b"", f"Expected empty body, got: {resp.content!r}"

        # Confirm it's actually gone
        get_resp = await client.get(f"{TICKETS_URL}/{ticket_id}", headers=_auth(token))
        assert get_resp.status_code == 404

    async def test_delete_nonexistent_ticket_returns_404(self, client: AsyncClient):
        token = await _register_and_token(
            client, {**ORG_A, "email": "alice-del2@acme.com", "org_slug": "acme-del2"}
        )
        import uuid as _uuid
        fake_id = str(_uuid.uuid4())
        resp = await client.delete(f"{TICKETS_URL}/{fake_id}", headers=_auth(token))
        assert resp.status_code == 404



@pytest.mark.asyncio
class TestStatusTransitions:
    """Status workflow enforcement."""

    async def _setup(self, client: AsyncClient, slug_suffix: str) -> tuple[str, str]:
        """Returns (token, ticket_id)."""
        token = await _register_and_token(
            client,
            {**ORG_A, "email": f"alice-st-{slug_suffix}@acme.com", "org_slug": f"acme-st-{slug_suffix}"},
        )
        create = await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token))
        assert create.status_code == 201
        return token, create.json()["id"]

    async def test_valid_transition_open_to_investigating(self, client: AsyncClient):
        token, ticket_id = await self._setup(client, "v1")
        resp = await client.patch(
            f"{TICKETS_URL}/{ticket_id}",
            json={"status": "investigating"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "investigating"

    async def test_valid_transition_investigating_to_in_progress(self, client: AsyncClient):
        token, ticket_id = await self._setup(client, "v2")
        # First transition to investigating
        await client.patch(f"{TICKETS_URL}/{ticket_id}", json={"status": "investigating"}, headers=_auth(token))
        # Then to in_progress
        resp = await client.patch(f"{TICKETS_URL}/{ticket_id}", json={"status": "in_progress"}, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    async def test_invalid_transition_open_to_closed(self, client: AsyncClient):
        """OPEN → CLOSED is not in the DAG — must return 400."""
        token, ticket_id = await self._setup(client, "inv1")
        resp = await client.patch(
            f"{TICKETS_URL}/{ticket_id}",
            json={"status": "closed"},
            headers=_auth(token),
        )
        assert resp.status_code == 400
        assert "closed" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()

    async def test_invalid_transition_open_to_resolved(self, client: AsyncClient):
        """OPEN → RESOLVED is also not permitted."""
        token, ticket_id = await self._setup(client, "inv2")
        resp = await client.patch(
            f"{TICKETS_URL}/{ticket_id}",
            json={"status": "resolved"},
            headers=_auth(token),
        )
        assert resp.status_code == 400

    async def test_valid_full_lifecycle(self, client: AsyncClient):
        """OPEN → INVESTIGATING → IN_PROGRESS → RESOLVED → CLOSED."""
        token, ticket_id = await self._setup(client, "lifecycle")
        url = f"{TICKETS_URL}/{ticket_id}"

        for next_status in ["investigating", "in_progress", "resolved", "closed"]:
            r = await client.patch(url, json={"status": next_status}, headers=_auth(token))
            assert r.status_code == 200, f"Transition to {next_status} failed: {r.text}"
            assert r.json()["status"] == next_status


@pytest.mark.asyncio
class TestCrossOrgPrevention:
    """
    Multi-tenant isolation — users must NEVER be able to read or modify
    another organization's tickets, regardless of valid authentication.
    """

    async def test_org_a_cannot_read_org_b_ticket(self, client: AsyncClient):
        """User from Org A gets 404 when requesting Org B's ticket."""
        token_a = await _register_and_token(
            client, {**ORG_A, "email": "alice-iso@acme.com", "org_slug": "acme-iso"}
        )
        token_b = await _register_and_token(
            client, {**ORG_B, "email": "bob-iso@beta.com", "org_slug": "beta-iso"}
        )

        # Org B creates a ticket
        create_b = await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token_b))
        assert create_b.status_code == 201
        ticket_b_id = create_b.json()["id"]

        # Org A tries to read Org B's ticket → must 404 (ticket not found in their org)
        resp = await client.get(f"{TICKETS_URL}/{ticket_b_id}", headers=_auth(token_a))
        assert resp.status_code == 404, (
            f"Cross-org read succeeded! Org A read Org B ticket {ticket_b_id}. "
            f"CRITICAL RBAC FAILURE. Response: {resp.text}"
        )

    async def test_org_a_cannot_update_org_b_ticket(self, client: AsyncClient):
        """Patch on another org's ticket must 404."""
        token_a = await _register_and_token(
            client, {**ORG_A, "email": "alice-upd@acme.com", "org_slug": "acme-upd"}
        )
        token_b = await _register_and_token(
            client, {**ORG_B, "email": "bob-upd@beta.com", "org_slug": "beta-upd"}
        )

        create_b = await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token_b))
        ticket_b_id = create_b.json()["id"]

        resp = await client.patch(
            f"{TICKETS_URL}/{ticket_b_id}",
            json={"title": "Hacked!"},
            headers=_auth(token_a),
        )
        assert resp.status_code == 404

    async def test_list_tickets_does_not_leak_cross_org(self, client: AsyncClient):
        """List endpoint must only return tickets from the authenticated user's org."""
        token_a = await _register_and_token(
            client, {**ORG_A, "email": "alice-list@acme.com", "org_slug": "acme-list2"}
        )
        token_b = await _register_and_token(
            client, {**ORG_B, "email": "bob-list@beta.com", "org_slug": "beta-list2"}
        )

        # Org B creates a uniquely titled ticket
        unique_title = "BETA SECRET TICKET — must not appear in Org A list"
        await client.post(TICKETS_URL, json={**VALID_TICKET, "title": unique_title}, headers=_auth(token_b))

        # Org A lists their tickets
        resp = await client.get(TICKETS_URL, headers=_auth(token_a))
        assert resp.status_code == 200
        titles = [t["title"] for t in resp.json()["items"]]
        assert unique_title not in titles, (
            "Cross-org data leak! Org B ticket appeared in Org A list. CRITICAL RBAC FAILURE."
        )


@pytest.mark.asyncio
class TestAuditLog:
    """Verify the audit trail is correctly written on ticket operations."""

    async def test_audit_created_on_ticket_create(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _register_and_token(
            client, {**ORG_A, "email": "alice-audit@acme.com", "org_slug": "acme-audit"}
        )

        create_resp = await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token))
        assert create_resp.status_code == 201
        ticket_id = create_resp.json()["id"]

        # Query audit log directly
        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "ticket.created",
                AuditLog.resource_id == __import__("uuid").UUID(ticket_id),
            )
        )
        audit_entry = result.scalar_one_or_none()

        assert audit_entry is not None, "No audit log entry created for ticket.created"
        assert audit_entry.event_type == "ticket.created"
        assert audit_entry.resource_type == "ticket"

    async def test_audit_created_on_comment_add(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _register_and_token(
            client, {**ORG_A, "email": "alice-cmt-audit@acme.com", "org_slug": "acme-cmt-audit"}
        )

        create_resp = await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token))
        ticket_id = create_resp.json()["id"]

        comment_resp = await client.post(
            f"{TICKETS_URL}/{ticket_id}/comments",
            json={"body": "This is a test comment for audit verification."},
            headers=_auth(token),
        )
        assert comment_resp.status_code == 201

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "ticket.comment_added",
                AuditLog.resource_id == __import__("uuid").UUID(ticket_id),
            )
        )
        audit_entry = result.scalar_one_or_none()

        assert audit_entry is not None, "No audit log entry created for ticket.comment_added"
        assert audit_entry.resource_type == "ticket"

    async def test_audit_created_on_status_change(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _register_and_token(
            client, {**ORG_A, "email": "alice-sc-audit@acme.com", "org_slug": "acme-sc-audit"}
        )

        create_resp = await client.post(TICKETS_URL, json=VALID_TICKET, headers=_auth(token))
        ticket_id = create_resp.json()["id"]

        await client.patch(
            f"{TICKETS_URL}/{ticket_id}",
            json={"status": "investigating"},
            headers=_auth(token),
        )

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "ticket.status_changed",
                AuditLog.resource_id == __import__("uuid").UUID(ticket_id),
            )
        )
        audit_entry = result.scalar_one_or_none()

        assert audit_entry is not None, "No audit log entry for status change"
        assert audit_entry.details["from"] == "open"
        assert audit_entry.details["to"] == "investigating"
