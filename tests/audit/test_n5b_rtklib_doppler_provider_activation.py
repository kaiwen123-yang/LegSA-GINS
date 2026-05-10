import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


# 中文说明：测试 N5B provider audit 静态边界和 toy factor 构建。


def test_n5b_provider_audit_static_and_toy():
    path = ROOT / "scripts/audit_n5b_rtklib_doppler_provider_activation.py"
    spec = importlib.util.spec_from_file_location("audit_n5b", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.audit_repository()
