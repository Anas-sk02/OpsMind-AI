from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_password_hashing_and_verification():
    plain = "SuperSecretPassword123!"
    hashed = get_password_hash(plain)

    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_access_and_refresh_token_lifecycle():
    user_id = "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"
    role = "ADMIN"

    access_token = create_access_token(subject=user_id, role=role)
    payload = decode_token(access_token)

    assert payload["sub"] == user_id
    assert payload["role"] == role
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload

    refresh_token = create_refresh_token(subject=user_id, role=role)
    r_payload = decode_token(refresh_token)

    assert r_payload["sub"] == user_id
    assert r_payload["role"] == role
    assert r_payload["type"] == "refresh"
