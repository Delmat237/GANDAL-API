"""Tests de la feature cluster : RBAC topologie + persistance des liens réseau."""
from __future__ import annotations

from app.core.security import hash_password
from app.features.cluster.service import ClusterService
from app.shared.models import NetworkLink, Student, VM


class FakeGateway:
    """Faux ProxmoxGateway/cluster : topologie figée, actions enregistrées."""

    def __init__(self):
        self.calls: list[tuple] = []

    def topology(self):
        return {
            "hosts": ["emilia", "ram"],
            "vms": [
                {"vmid": 3001, "name": "a", "node": "ram", "status": "up",
                 "ip": "10.50.30.102", "internet": False, "maxcpu": 4, "maxmem": 0},
                {"vmid": 3002, "name": "b", "node": "emilia", "status": "stopped",
                 "ip": "10.50.30.103", "internet": True, "maxcpu": 4, "maxmem": 0},
            ],
        }

    def set_internet(self, vmid, enable):
        self.calls.append(("internet", vmid, enable))

    def link_vms(self, vmids, enable, group_name=None):
        self.calls.append(("link", tuple(vmids), enable, group_name))

    def start_vm(self, node, vmid):
        self.calls.append(("start", vmid))

    def stop_vm(self, node, vmid):
        self.calls.append(("stop", vmid))


def _student(db, name="etu") -> Student:
    s = Student(username=name, email=f"{name}@x.cm", password=hash_password("pw"),
                type="student", matricule=f"M{name}", level="GI4", departement="GI")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _vm(db, owner_id, vmid) -> VM:
    v = VM(size_rom=20, size_ram=4096, n_cpu=4, status="up",
           id_proxmox=vmid, node="ram", user_id=owner_id)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def test_topology_admin_sees_all(db_session):
    svc = ClusterService(db_session, FakeGateway())
    topo = svc.topology(only_owner_id=None)
    assert {v.vmid for v in topo.vms} == {3001, 3002}
    assert "emilia" in topo.hosts


def test_topology_student_scoped_to_owned(db_session):
    student = _student(db_session)
    _vm(db_session, student.id, 3001)  # l'étudiant ne possède que 3001
    svc = ClusterService(db_session, FakeGateway())
    topo = svc.topology(only_owner_id=student.id)
    assert {v.vmid for v in topo.vms} == {3001}
    assert topo.vms[0].owner_name == student.username


def test_link_persists_network_edge(db_session):
    student = _student(db_session)
    _vm(db_session, student.id, 3001)
    _vm(db_session, student.id, 3002)
    gw = FakeGateway()
    svc = ClusterService(db_session, gw)
    svc.link(student, [3001, 3002], enable=True, group_name="backend")
    links = db_session.query(NetworkLink).all()
    assert len(links) == 1
    assert ("link", (3001, 3002), True, "backend") in gw.calls
    # La toile voit désormais l'arête.
    topo = svc.topology(only_owner_id=student.id)
    assert len(topo.links) == 1
    # Déconnexion → arête retirée.
    svc.link(student, [3001, 3002], enable=False, group_name="backend")
    assert db_session.query(NetworkLink).count() == 0
