import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# 中文说明：测试 N5A activation audit 的静态路径，不重复跑 C++ toy。

def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_n5a_activation_audit_static_path():
    module = load_script("audit_n5a_raw_doppler_factor_activation.py")
    module.audit_repository(run_toy=False)
