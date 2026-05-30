from tests.conftest import auth_header


def test_login_success(client, db_engine, seed_users):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "student", "password": "changeme123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_failure(client, seed_users):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "student", "password": "wrong"},
    )
    assert r.status_code == 401


def test_me(client, seed_users):
    headers = auth_header(client, "student")
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "student"
