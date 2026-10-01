"""Integration tests for Phase 6 Evaluators."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# Seeded credentials (admin@demo-corp.io exists in the test DB after seeding)
ADMIN_CREDS = {"email": "admin@demo-corp.io", "password": "AdminPass1"}
LOGIN_URL = "/api/v1/auth/login"


async def _get_admin_token(client: AsyncClient) -> str:
    """Log in as the seeded admin and return an access token."""
    r = await client.post(LOGIN_URL, json=ADMIN_CREDS)
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_run_evaluations(client: AsyncClient, db_session: AsyncSession):
    """Trigger an evaluation run and verify expected metrics are returned."""
    # 1. Ensure we have an AI run in the seeded test DB
    result = await db_session.execute(text("SELECT id FROM ai_runs LIMIT 1"))
    row = result.first()
    if not row:
        pytest.skip("No AI runs in DB to test evaluation — run seed_data.py first.")

    ai_run_id = str(row[0])

    # 2. Get admin token (uses seeded credentials, not rate-limited in tests)
    admin_token = await _get_admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Trigger evaluation endpoint
    response = await client.post(
        f"/api/v1/evaluations/run/{ai_run_id}",
        headers=headers,
    )
    assert response.status_code == 200, f"Evaluation endpoint failed: {response.text}"

    data = response.json()
    assert "evaluation_results" in data
    evals = data["evaluation_results"]
    assert isinstance(evals, list)
    assert len(evals) > 0

    metric_names = [e["metric_name"] for e in evals]
    assert "evidence_coverage" in metric_names
    assert "confidence_validation" in metric_names
    assert "retrieval_quality" in metric_names
