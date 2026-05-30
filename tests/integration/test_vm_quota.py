from tests.conftest import auth_header


def test_vm_quota_on_create_request(client, seed_users, monkeypatch, db_engine):
    monkeypatch.setenv("MAX_VMS_PER_STUDENT", "0")
    from app.core.config import get_settings

    get_settings.cache_clear()

    headers = auth_header(client, "student")
    r = client.post(
        "/api/v1/requetes/create-vm",
        headers=headers,
        json={
            "object": "VM",
            "teacher_id": seed_users["teacher"].id,
            "size_rom": 10,
            "size_ram": 1,
            "os": "Ubuntu 22.04",
        },
    )
    assert r.status_code == 400
    get_settings.cache_clear()
