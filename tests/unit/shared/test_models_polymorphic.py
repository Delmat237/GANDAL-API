"""Polymorphic model smoke tests (migrated from scripts/test_models.py)."""

from app.shared.models import (
    Base,
    Publication,
    RAccount,
    RCreateVM,
    RDeleteVM,
    Student,
    Teacher,
    VM,
)


def test_all_models(db_session):
    student = Student(
        username="jdoe",
        email="jdoe@example.com",
        password="hashed_pw",
        matricule="STU001",
        level="L3",
        departement="Computer Science",
    )
    teacher = Teacher(
        username="prof_smith",
        email="smith@example.com",
        password="hashed_pw",
        role="Supervisor",
    )
    db_session.add_all([student, teacher])
    db_session.flush()

    assert student.type == "student"
    assert teacher.type == "teacher"

    vm = VM(
        size_rom=50,
        size_ram=4,
        n_cpu=2,
        status="stopped",
        user_id=student.id,
    )
    db_session.add(vm)
    db_session.flush()

    r_create = RCreateVM(
        object="Request to create VM",
        size_rom=20,
        size_ram=2,
        os="Ubuntu 22.04",
        student_id=student.id,
        teacher_id=teacher.id,
    )
    r_delete = RDeleteVM(
        object="Request to delete VM",
        vm_id=vm.id,
        student_id=student.id,
        teacher_id=teacher.id,
    )
    r_account = RAccount(
        object="Account creation request",
        nom="Jane Doe",
        email="jane@example.com",
        student_id=student.id,
        teacher_id=teacher.id,
    )
    pub = Publication(nom="Lab Manual", status="published", user_id=teacher.id)
    db_session.add_all([r_create, r_delete, r_account, pub])
    db_session.commit()

    assert r_create.type == "r_create_vm"
    assert len(student.vms) == 1
