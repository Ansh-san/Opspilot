"""Integration tests for auth endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
ME_URL = "/api/v1/auth/me"

VALID_REGISTER = {
    "org_name": "Test Corp",
    "org_slug": "test-corp",
    "full_name": "Test Admin",
    "email": "admin@testcorp.com",
    "password": "SecurePass1",
}


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(REGISTER_URL, json=VALID_REGISTER)
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "admin@testcorp.com"
        assert data["role"] == "admin"
        assert "hashed_password" not in data

    async def test_register_duplicate_slug(self, client: AsyncClient):
        await client.post(REGISTER_URL, json=VALID_REGISTER)
        resp2 = await client.post(REGISTER_URL, json={**VALID_REGISTER, "email": "other@testcorp.com"})
        assert resp2.status_code == 409

    async def test_register_duplicate_email(self, client: AsyncClient):
        await client.post(REGISTER_URL, json=VALID_REGISTER)
        resp2 = await client.post(REGISTER_URL, json={**VALID_REGISTER, "org_slug": "other-slug"})
        assert resp2.status_code == 409

    async def test_register_weak_password(self, client: AsyncClient):
        resp = await client.post(REGISTER_URL, json={**VALID_REGISTER, "password": "weakpass"})
        assert resp.status_code == 422

    async def test_register_invalid_slug(self, client: AsyncClient):
        resp = await client.post(REGISTER_URL, json={**VALID_REGISTER, "org_slug": "INVALID SLUG!"})
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client: AsyncClient):
        await client.post(REGISTER_URL, json=VALID_REGISTER)
        resp = await client.post(LOGIN_URL, json={"email": VALID_REGISTER["email"], "password": VALID_REGISTER["password"]})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post(REGISTER_URL, json=VALID_REGISTER)
        resp = await client.post(LOGIN_URL, json={"email": VALID_REGISTER["email"], "password": "WrongPass1"})
        assert resp.status_code == 401

    async def test_login_unknown_email(self, client: AsyncClient):
        resp = await client.post(LOGIN_URL, json={"email": "nobody@nowhere.com", "password": "AnyPass1"})
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestMe:
    async def _get_token(self, client: AsyncClient) -> str:
        await client.post(REGISTER_URL, json=VALID_REGISTER)
        resp = await client.post(LOGIN_URL, json={"email": VALID_REGISTER["email"], "password": VALID_REGISTER["password"]})
        return resp.json()["access_token"]

    async def test_me_authenticated(self, client: AsyncClient):
        token = await self._get_token(client)
        resp = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == VALID_REGISTER["email"]

    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get(ME_URL)
        assert resp.status_code == 403  # HTTPBearer returns 403 when no header


@pytest.mark.asyncio
class TestRefresh:
    async def test_refresh_success(self, client: AsyncClient):
        await client.post(REGISTER_URL, json=VALID_REGISTER)
        login = await client.post(LOGIN_URL, json={"email": VALID_REGISTER["email"], "password": VALID_REGISTER["password"]})
        refresh_token = login.json()["refresh_token"]
        resp = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(REFRESH_URL, json={"refresh_token": "not.a.valid.token"})
        assert resp.status_code == 401

