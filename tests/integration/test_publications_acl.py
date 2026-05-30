from tests.conftest import auth_header


def test_public_list_without_auth(client, seed_users):
    teacher_h = auth_header(client, "teacher")
    client.post(
        "/api/v1/publications",
        headers=teacher_h,
        json={
            "nom": "Guide",
            "status": "published",
            "user_id": seed_users["teacher"].id,
        },
    )
    r = client.get("/api/v1/publications/public")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_student_cannot_create_publication(client, seed_users):
    headers = auth_header(client, "student")
    r = client.post(
        "/api/v1/publications",
        headers=headers,
        json={
            "nom": "Hack",
            "user_id": seed_users["student"].id,
        },
    )
    assert r.status_code == 403
