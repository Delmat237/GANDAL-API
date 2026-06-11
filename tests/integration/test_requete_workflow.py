from app.infrastructure.proxmox.proxmox_client import ProxmoxIntegrationError
from tests.conftest import auth_header


def test_create_and_approve_vm_request(client, seed_users, mock_proxmox):
    users = seed_users
    student_headers = auth_header(client, "student")
    teacher_headers = auth_header(client, "teacher")

    r = client.post(
        "/api/v1/requetes/create-vm",
        headers=student_headers,
        json={
            "object": "VM projet",
            "teacher_id": users["teacher"].id,
            "size_rom": 20,
            "size_ram": 2,
            "os": "Ubuntu 22.04",
        },
    )
    assert r.status_code == 201
    requete_id = r.json()["id"]

    r = client.post(
        f"/api/v1/requetes/{requete_id}/approve",
        headers=teacher_headers,
        json={"ssh_public_key": "ssh-rsa AAAAB3"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "validated"
    assert len(mock_proxmox.vms) >= 1

    r = client.get("/api/v1/vms", headers=student_headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    vm = r.json()["items"][0]
    assert vm["name"] == "VM projet"
    assert vm["ip_address"] == "10.0.0.42"


def test_approve_vm_request_survives_proxmox_failure(
    client, seed_users, mock_proxmox, monkeypatch
):
    """Si Proxmox est injoignable, l'approbation ne doit pas renvoyer 500 :
    la VM est enregistrée en base avec le statut 'waiting'."""

    def boom(*_args, **_kwargs):
        raise ProxmoxIntegrationError("Proxmox injoignable", 502)

    monkeypatch.setattr(mock_proxmox, "provision_new_vm", boom)

    users = seed_users
    student_headers = auth_header(client, "student")
    teacher_headers = auth_header(client, "teacher")

    r = client.post(
        "/api/v1/requetes/create-vm",
        headers=student_headers,
        json={
            "object": "VM projet",
            "teacher_id": users["teacher"].id,
            "size_rom": 20,
            "size_ram": 2,
            "n_cpu": 4,
            "os": "Ubuntu 22.04",
        },
    )
    assert r.status_code == 201
    requete_id = r.json()["id"]

    r = client.post(
        f"/api/v1/requetes/{requete_id}/approve",
        headers=teacher_headers,
        json={"ssh_public_key": ""},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "validated"

    r = client.get("/api/v1/vms", headers=student_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "waiting"
    assert items[0]["n_cpu"] == 4
    assert items[0]["id_proxmox"] is None
