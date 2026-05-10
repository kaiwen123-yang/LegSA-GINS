import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# 中文说明：测试 NAV-PVT 非 raw Doppler 审计脚本。

def test_raw_doppler_not_pvt_velocity_audit():
    path = ROOT / "scripts/audit_raw_doppler_not_pvt_velocity.py"
    spec = importlib.util.spec_from_file_location("audit_raw_doppler_not_pvt_velocity", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.audit_repository()
