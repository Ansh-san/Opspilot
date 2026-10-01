"""Unit tests for security utilities (password hashing and JWT)."""

from __future__ import annotations

import time

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

USER_ID = "12345678-1234-1234-1234-123456789012"
ORG_ID = "87654321-4321-4321-4321-210987654321"


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("MySecret1")
        assert hashed != "MySecret1"

    def test_verify_correct_password(self):
        hashed = hash_password("MySecret1")
        assert verify_password("MySecret1", hashed) is True

    def test_reject_wrong_password(self):
        hashed = hash_password("MySecret1")
        assert verify_password("WrongPass1", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt uses a random salt — same password hashes differently."""
        h1 = hash_password("MySecret1")
        h2 = hash_password("MySecret1")
        assert h1 != h2


class TestAccessToken:
    def test_create_and_decode(self):
        token = create_access_token(USER_ID, ORG_ID)
        payload = decode_access_token(token)
        assert payload["sub"] == USER_ID
        assert payload["org"] == ORG_ID
        assert payload["type"] == "access"

    def test_reject_refresh_token_as_access(self):
        refresh = create_refresh_token(USER_ID, ORG_ID)
        with pytest.raises(JWTError):
            decode_access_token(refresh)

    def test_reject_tampered_token(self):
        token = create_access_token(USER_ID, ORG_ID)
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(JWTError):
            decode_access_token(tampered)


class TestRefreshToken:
    def test_create_and_decode(self):
        token = create_refresh_token(USER_ID, ORG_ID)
        payload = decode_refresh_token(token)
        assert payload["sub"] == USER_ID
        assert payload["type"] == "refresh"

    def test_reject_access_token_as_refresh(self):
        access = create_access_token(USER_ID, ORG_ID)
        with pytest.raises(JWTError):
            decode_refresh_token(access)
