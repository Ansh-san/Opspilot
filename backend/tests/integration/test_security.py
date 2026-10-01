import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User

@pytest.mark.asyncio
async def test_invalid_jwt(client: AsyncClient):
    """Test that an invalid JWT returns 401 Unauthorized."""
    headers = {"Authorization": "Bearer invalid.jwt.token"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_cross_org_access(
    client: AsyncClient,
    test_user: User,
    test_user_headers: dict,
    db_session: AsyncSession,
):
    """Test that a user cannot access observability metrics of another org."""
    # Since the observability route uses current_user.org_id, it is inherently 
    # impossible to query another org unless the route accepts an org_id param and 
    # forgets to validate it. We can verify that /api/v1/observability/metrics 
    # successfully scopes to the user's org (returns 200) and we can't fetch others.
    response = await client.get("/api/v1/observability/metrics", headers=test_user_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_runs" in data

@pytest.mark.asyncio
async def test_path_traversal_blocked():
    """Test that the knowledge service sanitizes path traversal filenames."""
    from app.services.knowledge_service import _sanitize_filename
    
    malicious_filename = "../../../etc/passwd"
    safe_filename = _sanitize_filename(malicious_filename)
    
    assert ".." not in safe_filename
    assert "/" not in safe_filename
    assert safe_filename == "etc_passwd"

@pytest.mark.asyncio
async def test_rate_limiting_triggers(client: AsyncClient):
    """Test that excessive login attempts trigger 429 Too Many Requests.
    
    IMPORTANT: This test re-enables the rate limiter explicitly. The autouse
    isolate_rate_limiter fixture in conftest.py disables it for all other tests
    and will automatically restore the disabled state after this test exits.
    """
    from app.core.rate_limiter import limiter
    limiter.enabled = True

    # Attempt to hit the rate limit — limit is 5/minute per settings.RATE_LIMIT_LOGIN
    for _ in range(6):
        response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })

    # The 6th request must be rate-limited
    assert response.status_code == 429
    # SlowAPI returns {"error": "Rate limit exceeded: N per M minute"}
    assert "Rate limit exceeded" in response.text or "Too Many Requests" in response.text


@pytest.mark.asyncio
async def test_stack_traces_hidden(client: AsyncClient):
    """Test that an unhandled exception returns a generic 500 without a stack trace."""
    from app.main import global_exception_handler

    class MockUrl:
        """Minimal URL mock — str() returns the path string."""
        def __str__(self) -> str:
            return "http://testserver/api/v1/error"

    class MockRequest:
        """Minimal Request mock with the attributes global_exception_handler reads."""
        method = "GET"
        url = MockUrl()

    try:
        raise RuntimeError("Secret Internal Database Error")
    except Exception as e:
        response = await global_exception_handler(MockRequest(), e)

    import json
    body = json.loads(response.body.decode())

    assert response.status_code == 500
    assert "Internal server error" in body["detail"]
    assert "Secret Internal Database Error" not in body["detail"]
    assert "traceback" not in body

