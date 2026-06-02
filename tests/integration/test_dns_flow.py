"""
Tests d'intégration – Package DNS
Teste le flow HTTP complet via TestClient (SQLite en mémoire, MockProxmox).
"""
import pytest
from tests.conftest import auth_header


# ── Helpers ────────────────────────────────────────────────────────────────────

def _create_vm_for_student(client, student_headers, teacher_id: int) -> int:
    """Crée une VM via le flow requête → approbation et retourne son ID."""
    r = client.post(
        "/api/v1/requetes/create-vm",
        headers=student_headers,
        json={
            "object": "VM pour DNS",
            "teacher_id": teacher_id,
            "size_rom": 20,
            "size_ram": 2,
            "os": "Ubuntu 22.04",
        },
    )
    assert r.status_code == 201, r.text
    requete_id = r.json()["id"]

    admin_headers = auth_header(client, "admin")
    r = client.post(
        f"/api/v1/requetes/{requete_id}/approve",
        headers=admin_headers,
        json={"ssh_public_key": "ssh-rsa AAAAB3NzaC1"},
    )
    assert r.status_code == 200, r.text

    r = client.get("/api/v1/vms", headers=student_headers)
    assert r.status_code == 200
    vms = r.json()["items"]
    assert len(vms) >= 1
    return vms[-1]["id"]


# ── Tests CRUD DNS ─────────────────────────────────────────────────────────────

class TestDNSCRUDFlow:
    def test_create_dns_entry(self, client, seed_users, mock_proxmox):
        """L'étudiant propriétaire peut créer une entrée DNS sur sa VM."""
        users = seed_users
        student_headers = auth_header(client, "student")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        r = client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "api.projet.dc.enspy.cm", "vm_id": vm_id},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["hostname"] == "api.projet.dc.enspy.cm"
        assert body["vm_id"] == vm_id
        assert "id" in body

    def test_get_dns_entry(self, client, seed_users, mock_proxmox):
        """L'étudiant peut récupérer une entrée DNS par son ID."""
        users = seed_users
        student_headers = auth_header(client, "student")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        r = client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "get.dc.enspy.cm", "vm_id": vm_id},
        )
        dns_id = r.json()["id"]

        r = client.get(f"/api/v1/dns/{dns_id}", headers=student_headers)
        assert r.status_code == 200
        assert r.json()["hostname"] == "get.dc.enspy.cm"

    def test_list_dns_for_vm(self, client, seed_users, mock_proxmox):
        """La liste par VM retourne toutes les entrées DNS de cette VM."""
        users = seed_users
        student_headers = auth_header(client, "student")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        for i in range(3):
            r = client.post(
                "/api/v1/dns",
                headers=student_headers,
                json={"hostname": f"host{i}.dc.enspy.cm", "vm_id": vm_id},
            )
            assert r.status_code == 201

        r = client.get(f"/api/v1/dns/vms/{vm_id}", headers=student_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    def test_update_dns_hostname(self, client, seed_users, mock_proxmox):
        """L'étudiant peut modifier le hostname d'une entrée DNS."""
        users = seed_users
        student_headers = auth_header(client, "student")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        r = client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "old.dc.enspy.cm", "vm_id": vm_id},
        )
        dns_id = r.json()["id"]

        r = client.patch(
            f"/api/v1/dns/{dns_id}",
            headers=student_headers,
            json={"hostname": "new.dc.enspy.cm"},
        )
        assert r.status_code == 200
        assert r.json()["hostname"] == "new.dc.enspy.cm"

    def test_delete_dns_entry(self, client, seed_users, mock_proxmox):
        """L'étudiant peut supprimer une entrée DNS, puis un GET retourne 404."""
        users = seed_users
        student_headers = auth_header(client, "student")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        r = client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "del.dc.enspy.cm", "vm_id": vm_id},
        )
        dns_id = r.json()["id"]

        r = client.delete(f"/api/v1/dns/{dns_id}", headers=student_headers)
        assert r.status_code == 204

        r = client.get(f"/api/v1/dns/{dns_id}", headers=student_headers)
        assert r.status_code == 404


# ── Tests de contrôle d'accès ──────────────────────────────────────────────────

class TestDNSAccessControl:
    def test_unauthenticated_cannot_create(self, client, seed_users, mock_proxmox):
        """Sans token, la création est refusée (401)."""
        r = client.post(
            "/api/v1/dns",
            json={"hostname": "anon.dc.enspy.cm", "vm_id": 1},
        )
        assert r.status_code == 401

    def test_non_owner_teacher_cannot_create(self, client, seed_users, mock_proxmox):
        """Un enseignant non propriétaire de la VM ne peut pas créer de DNS."""
        users = seed_users
        student_headers = auth_header(client, "student")
        teacher_headers = auth_header(client, "teacher")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        r = client.post(
            "/api/v1/dns",
            headers=teacher_headers,
            json={"hostname": "hack.dc.enspy.cm", "vm_id": vm_id},
        )
        assert r.status_code == 403

    def test_admin_can_create_on_any_vm(self, client, seed_users, mock_proxmox):
        """L'admin peut créer une entrée DNS sur n'importe quelle VM."""
        users = seed_users
        student_headers = auth_header(client, "student")
        admin_headers = auth_header(client, "admin")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        r = client.post(
            "/api/v1/dns",
            headers=admin_headers,
            json={"hostname": "admin.dc.enspy.cm", "vm_id": vm_id},
        )
        assert r.status_code == 201

    def test_admin_list_all_dns(self, client, seed_users, mock_proxmox):
        """L'admin peut lister toutes les entrées DNS via GET /api/v1/dns."""
        users = seed_users
        student_headers = auth_header(client, "student")
        admin_headers = auth_header(client, "admin")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "list.dc.enspy.cm", "vm_id": vm_id},
        )

        r = client.get("/api/v1/dns", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_student_cannot_list_all_dns(self, client, seed_users, mock_proxmox):
        """Un étudiant ne peut pas accéder à la liste globale (403)."""
        student_headers = auth_header(client, "student")
        r = client.get("/api/v1/dns", headers=student_headers)
        assert r.status_code == 403


# ── Tests de validation métier ─────────────────────────────────────────────────

class TestDNSBusinessRules:
    def test_duplicate_hostname_returns_409(self, client, seed_users, mock_proxmox):
        """Créer deux fois le même hostname retourne 409 Conflict."""
        users = seed_users
        student_headers = auth_header(client, "student")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "dup.dc.enspy.cm", "vm_id": vm_id},
        )
        r = client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "dup.dc.enspy.cm", "vm_id": vm_id},
        )
        assert r.status_code == 409

    def test_invalid_hostname_returns_422(self, client, seed_users, mock_proxmox):
        """Un hostname invalide retourne 422 Unprocessable Entity."""
        users = seed_users
        student_headers = auth_header(client, "student")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        r = client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "pas_un_fqdn", "vm_id": vm_id},
        )
        assert r.status_code == 422

    def test_dns_on_nonexistent_vm_returns_404(self, client, seed_users, mock_proxmox):
        """Créer un DNS sur une VM inexistante retourne 404."""
        student_headers = auth_header(client, "student")
        r = client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "ghost.dc.enspy.cm", "vm_id": 99999},
        )
        assert r.status_code == 404

    def test_dns_deleted_when_vm_is_deleted(self, client, seed_users, mock_proxmox):
        """La suppression d'une VM supprime en cascade ses entrées DNS."""
        users = seed_users
        student_headers = auth_header(client, "student")
        admin_headers = auth_header(client, "admin")
        vm_id = _create_vm_for_student(client, student_headers, users["teacher"].id)

        r = client.post(
            "/api/v1/dns",
            headers=student_headers,
            json={"hostname": "cascade.dc.enspy.cm", "vm_id": vm_id},
        )
        dns_id = r.json()["id"]

        # Suppression de la VM
        r = client.delete(f"/api/v1/vms/{vm_id}", headers=student_headers)
        assert r.status_code == 204

        # Le DNS doit avoir été supprimé en cascade
        r = client.get(f"/api/v1/dns/{dns_id}", headers=admin_headers)
        assert r.status_code == 404
