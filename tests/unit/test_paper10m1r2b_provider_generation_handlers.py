import importlib.util
import sys
from pathlib import Path


def _load_generator():
    script = Path(__file__).resolve().parents[2] / "scripts" / "paper10m1r2b_generate_by2_degraded_providers.py"
    spec = importlib.util.spec_from_file_location("paper10m1r2b_generate_by2_degraded_providers", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_handler_registry_has_clean_and_all_60_degradation_types():
    module = _load_generator()
    assert set(module.HANDLERS) == {"CLEAN", *{f"D{i:02d}" for i in range(1, 61)}}


def test_wrapper_scripts_exist_for_stage_operations():
    root = Path(__file__).resolve().parents[2]
    for name in [
        "paper10m1r2b_effect_validate_providers.py",
        "paper10m1r2b_build_provider_ready_manifest.py",
        "paper10m1r2b_build_next_execution_queues.py",
        "paper10m1r2b_guard_audit.py",
        "paper10m1r2b_export_clean.py",
    ]:
        assert (root / "scripts" / name).exists()
