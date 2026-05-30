from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_returns_hash():
    h = hash_password("secret")
    assert h != "secret"
    assert h.startswith("$argon2")


def test_verify_password_valid():
    h = hash_password("secret")
    assert verify_password("secret", h) is True


def test_verify_password_invalid():
    h = hash_password("secret")
    assert verify_password("wrong", h) is False


def test_create_and_decode_access_token():
    token = create_access_token(42, extra_claims={"type": "student"})
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "student"
