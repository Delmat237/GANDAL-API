"""
Deprecated: use tests/unit/shared/test_models_polymorphic.py
"""
from tests.unit.shared.test_models_polymorphic import test_all_models as _run
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__.replace(
        "test_models.py", "../tests/unit/shared/test_models_polymorphic.py")]))
