"""Régressions sur les anomalies du module Users relevées dans le rapport de test.

- Matricule dupliqué : doit renvoyer 409 explicite et non 500 (exception non gérée).
- Champ ``role`` d'un enseignant : doit être validé (422) au lieu d'accepter
  n'importe quelle chaîne.
"""

from tests.conftest import auth_header


def _student_payload(**overrides) -> dict:
    payload = {
        "username": "alice",
        "email": "alice@example.com",
        "password": "changeme123",
        "matricule": "MAT-NEW-001",
        "level": "L1",
        "departement": "Computer Science",
    }
    payload.update(overrides)
    return payload


def test_duplicate_matricule_returns_409_not_500(client, seed_users):
    admin_headers = auth_header(client, "admin")

    r = client.post(
        "/api/v1/users/students", headers=admin_headers, json=_student_payload()
    )
    assert r.status_code == 201

    # Même matricule, username/email différents → conflit métier explicite.
    r = client.post(
        "/api/v1/users/students",
        headers=admin_headers,
        json=_student_payload(username="bob", email="bob@example.com"),
    )
    assert r.status_code == 409
    assert "matricule" in r.json()["detail"].lower()


def test_invalid_teacher_role_is_rejected(client, seed_users):
    admin_headers = auth_header(client, "admin")

    r = client.post(
        "/api/v1/users/teachers",
        headers=admin_headers,
        json={
            "username": "prof",
            "email": "prof@example.com",
            "password": "changeme123",
            "role": "n'importe quoi",
        },
    )
    assert r.status_code == 422


def test_valid_teacher_role_is_accepted(client, seed_users):
    admin_headers = auth_header(client, "admin")

    r = client.post(
        "/api/v1/users/teachers",
        headers=admin_headers,
        json={
            "username": "prof2",
            "email": "prof2@example.com",
            "password": "changeme123",
            "role": "Admin",
        },
    )
    assert r.status_code == 201
    assert r.json()["role"] == "Admin"
