import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.approval import ApprovalRequest, ApprovalStatus
from app.db.models.ticket import Ticket
from app.ai.policy.engine import PolicyEngine
from app.ai.policy.rules import PolicyDecision
from app.ai.tools.registry import tool_registry, ToolExecutionError
import app.ai.tools.simulated  # imported for side effect of registering tools


# ─── URLs ──────────────────────────────────────────────────────────────────────

BASE = "/api/v1"
LOGIN_URL    = f"{BASE}/auth/login"
TICKETS_URL  = f"{BASE}/tickets"

# Seeded credentials
ADMIN_CREDS = {"email": "admin@demo-corp.io", "password": "AdminPass1"}
MANAGER_CREDS = {"email": "manager@demo-corp.io", "password": "ManagerPass1"}
AGENT_CREDS = {"email": "agent@demo-corp.io", "password": "AgentPass1"}

SAMPLE_TICKET = {
    "title": "Database connection pool exhausted",
    "description": "All API requests are failing with DB connection timeout.",
    "priority": "critical",
    "severity": "s1",
    "category": "database",
    "affected_service": "postgres-primary",
}


async def _login(client: AsyncClient, creds: dict) -> str:
    r = await client.post(LOGIN_URL, json=creds)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_policy_engine_classifications():
    # Use tools that are actually registered in the system:
    # "get_service_health" -> LOW
    # "restart_test_service" -> MEDIUM
    # "restart_production_service" -> HIGH
    # "drop_production_database" -> BLOCKED (if registered, wait, is it registered? Actually, if it's NOT registered, it evaluates to BLOCKED anyway!)
    
    # Test BLOCKED (unknown tool)
    res = PolicyEngine.evaluate("unknown_tool", {}, {})
    assert res.decision == PolicyDecision.REJECT
    assert res.risk_level.value == "blocked"

    # Test HIGH risk
    res = PolicyEngine.evaluate("restart_production_service", {"service": "api"}, {})
    assert res.decision == PolicyDecision.REQUIRE_APPROVAL
    assert res.risk_level.value == "high"

    # Test MEDIUM risk
    res = PolicyEngine.evaluate("restart_test_service", {"service": "api"}, {})
    assert res.decision == PolicyDecision.REQUIRE_APPROVAL
    assert res.risk_level.value == "medium"

    # Test LOW risk
    res = PolicyEngine.evaluate("get_service_health", {"service": "api"}, {})
    assert res.decision == PolicyDecision.AUTO_EXECUTE
    assert res.risk_level.value == "low"

@pytest.mark.asyncio
async def test_tool_registry_validation():
    # Unknown tool
    with pytest.raises(ToolExecutionError, match="Unknown tool requested: unknown_tool"):
        await tool_registry.execute_tool("unknown_tool", {})

    # Invalid arguments (missing required 'service' for restart_production_service)
    with pytest.raises(ToolExecutionError, match="Invalid arguments for tool"):
        await tool_registry.execute_tool("restart_production_service", {})
    
    # Extra arguments (extra='forbid')
    with pytest.raises(ToolExecutionError, match="Invalid arguments for tool"):
        await tool_registry.execute_tool("get_service_health", {"service": "api", "extra_arg": "hax0r"})

@pytest.mark.asyncio
async def test_agent_proposes_but_does_not_execute(client: AsyncClient, db_session: AsyncSession):
    token = await _login(client, ADMIN_CREDS)
    
    # Create a fresh ticket to avoid state conflicts
    r = await client.post(TICKETS_URL, json=SAMPLE_TICKET, headers=_auth(token))
    ticket_id = r.json()["id"]

    res = await client.post(f"/api/v1/tickets/{ticket_id}/run-agent", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    
    assert data["proposed_action"] == "restart_production_service" # Mock LLM hardcoded to this
    assert data["approval_status"] == "pending"
    
    app_id = data["approval_id"]
    approval = await db_session.get(ApprovalRequest, uuid.UUID(app_id))
    assert approval is not None
    assert approval.status == ApprovalStatus.PENDING

@pytest.mark.asyncio
async def test_security_self_approval_blocked(client: AsyncClient, db_session: AsyncSession):
    token = await _login(client, ADMIN_CREDS)
    r = await client.post(TICKETS_URL, json=SAMPLE_TICKET, headers=_auth(token))
    ticket_id = r.json()["id"]

    # Admin runs agent
    res = await client.post(f"/api/v1/tickets/{ticket_id}/run-agent", headers=_auth(token))
    app_id = res.json()["approval_id"]

    # Admin tries to approve their own request
    res2 = await client.post(f"/api/v1/approvals/{app_id}/approve", json={"note": "Looks good"}, headers=_auth(token))
    assert res2.status_code == 403
    assert "cannot approve an action that you requested" in res2.json()["detail"]

@pytest.mark.asyncio
async def test_security_cross_org_approval_blocked(client: AsyncClient, db_session: AsyncSession):
    token = await _login(client, ADMIN_CREDS)
    r = await client.post(TICKETS_URL, json=SAMPLE_TICKET, headers=_auth(token))
    ticket_id = r.json()["id"]

    res = await client.post(f"/api/v1/tickets/{ticket_id}/run-agent", headers=_auth(token))
    app_id = res.json()["approval_id"]

    # Simulate cross-org by changing the DB record's org_id
    approval = await db_session.get(ApprovalRequest, uuid.UUID(app_id))
    approval.org_id = uuid.uuid4()
    await db_session.commit()

    # Admin tries to approve (now in different org)
    res2 = await client.post(f"/api/v1/approvals/{app_id}/approve", json={"note": "Approving"}, headers=_auth(token))
    assert res2.status_code == 404

@pytest.mark.asyncio
async def test_stale_approval_double_execution(client: AsyncClient, db_session: AsyncSession):
    token_admin = await _login(client, ADMIN_CREDS)
    token_manager = await _login(client, MANAGER_CREDS)
    
    r = await client.post(TICKETS_URL, json=SAMPLE_TICKET, headers=_auth(token_admin))
    ticket_id = r.json()["id"]

    res = await client.post(f"/api/v1/tickets/{ticket_id}/run-agent", headers=_auth(token_admin))
    app_id = res.json()["approval_id"]

    # Manager approves 1st time
    res_approve1 = await client.post(f"/api/v1/approvals/{app_id}/approve", json={"note": "Approving 1st time"}, headers=_auth(token_manager))
    assert res_approve1.status_code == 200

    # Manager tries to approve again
    res_approve2 = await client.post(f"/api/v1/approvals/{app_id}/approve", json={"note": "Approving 2nd time"}, headers=_auth(token_manager))
    assert res_approve2.status_code == 409
    assert "no longer PENDING" in res_approve2.json()["detail"]
