import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


# 中文说明：有 C++ build 时，audit 必须跑 toy EKF update；无 build 时跳过。


def test_raw_doppler_real_ekf_activation_audit():
    if not (ROOT / "build/cpp/legsa_v23_port_core_demo").exists():
        pytest.skip("C++ demo is not built")
    path = ROOT / "scripts/audit_raw_doppler_real_ekf_activation.py"
    spec = importlib.util.spec_from_file_location("audit_real_ekf", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.audit_repository()
