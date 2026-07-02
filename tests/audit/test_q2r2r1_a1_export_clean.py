import importlib.util
from pathlib import Path


def _load_script_module():
    path = Path("scripts/experiments/run_paper10q2r2r1_a1_dual_matrix.py")
    spec = importlib.util.spec_from_file_location("a1_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_a1_export_scan_flags_local_paths(tmp_path: Path):
    module = _load_script_module()
    root = tmp_path / "text_package"
    root.mkdir()
    (root / "bad.md").write_text(("/home/" + "kaiwen/specific-runtime\n"), encoding="utf-8")
    scan = module.scan_export_clean(root)
    assert scan["status"] == "FAIL"


def test_a1_export_redaction_removes_raw_file_names():
    module = _load_script_module()
    text = module.redact_export_text("by2.txt gnss1-raw.csv trace_vrtk2 epoch_output.csv")
    assert "by2.txt" not in text
    assert "gnss1-raw.csv" not in text
    assert "trace_vrtk2" not in text
    assert "epoch_output.csv" not in text
