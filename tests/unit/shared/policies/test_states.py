import pytest

from app.shared.models import Requete, VM
from app.shared.policies.states import RequestStatePolicy, StateTransitionError, VMStatePolicy


def test_can_start_when_stopped():
    vm = VM(size_rom=1, size_ram=1, n_cpu=1, status="stopped", user_id=1)
    assert VMStatePolicy.can_start(vm) is True


def test_can_start_when_up_false():
    vm = VM(size_rom=1, size_ram=1, n_cpu=1, status="up", user_id=1)
    assert VMStatePolicy.can_start(vm) is False


def test_can_stop_when_up():
    vm = VM(size_rom=1, size_ram=1, n_cpu=1, status="up", user_id=1)
    assert VMStatePolicy.can_stop(vm) is True


def test_can_pause_when_up():
    vm = VM(size_rom=1, size_ram=1, n_cpu=1, status="up", user_id=1)
    assert VMStatePolicy.can_pause(vm) is True


def test_validate_transition_start_raises():
    vm = VM(size_rom=1, size_ram=1, n_cpu=1, status="up", user_id=1)
    with pytest.raises(StateTransitionError):
        VMStatePolicy.validate_transition(vm, VMStatePolicy.UP)


def test_can_be_evaluated_pending():
    req = Requete(object="o", type="requete",
                  status="pending", student_id=1, teacher_id=2)
    assert RequestStatePolicy.can_be_evaluated(req) is True


def test_validate_approval_rejects_processed():
    req = Requete(object="o", type="requete",
                  status="validated", student_id=1, teacher_id=2)
    with pytest.raises(StateTransitionError):
        RequestStatePolicy.validate_approval(req)
