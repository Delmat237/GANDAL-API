from app.shared.models import Requete, Student, Teacher, VM
from app.shared.policies.permissions import AuthorizationPolicy


def test_is_admin_or_superadmin():
    admin = Teacher(username="a", email="a@x.com", password="p", role="Admin")
    assert AuthorizationPolicy.is_admin_or_superadmin(admin) is True


def test_is_student():
    s = Student(
        username="s",
        email="s@x.com",
        password="p",
        matricule="M1",
        level="L1",
        departement="CS",
    )
    assert AuthorizationPolicy.is_student(s) is True


def test_can_manage_vm_owner():
    s = Student(
        username="s",
        email="s@x.com",
        password="p",
        matricule="M1",
        level="L1",
        departement="CS",
    )
    s.id = 1
    vm = VM(size_rom=1, size_ram=1, n_cpu=1, user_id=1)
    assert AuthorizationPolicy.can_manage_vm(s, vm) is True


def test_can_evaluate_request_assigned_teacher():
    teacher = Teacher(username="t", email="t@x.com",
                      password="p", role="Teacher")
    teacher.id = 5
    req = Requete(object="o", type="requete",
                  status="pending", student_id=1, teacher_id=5)
    assert AuthorizationPolicy.can_evaluate_request(teacher, req) is True


def test_can_view_request_student_own():
    s = Student(
        username="s",
        email="s@x.com",
        password="p",
        matricule="M1",
        level="L1",
        departement="CS",
    )
    s.id = 3
    req = Requete(object="o", type="requete",
                  status="pending", student_id=3, teacher_id=1)
    assert AuthorizationPolicy.can_view_request(s, req) is True
