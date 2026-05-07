"""中文说明：audit 测试加固 final_v23/trace true flag 检测，不接触真实数据。"""

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts/audit_cpp_runtime_backbone.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_cpp_runtime_backbone", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cpp_runtime_backbone_audit_passes():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout


def test_forbidden_true_flag_helper_detects_contamination_flags():
    audit = _load_audit_module()
    forbidden_samples = [
        "final_v23_output_substitution: true",
        "final_v23_output_substitution = true",
        '"final_v23_output_substitution": true',
        "proposed_reads_final_v23_output: true",
        "proposed_reads_final_v23_output = true",
        '"proposed_reads_final_v23_output": true',
        "trace_solver_input: true",
        "trace_solver_input = true",
        '"trace_solver_input": true',
        "trace_used_for_tuning: true",
        "trace_used_for_tuning = true",
        '"trace_used_for_tuning": true',
        "output_only_correction: true",
        "output_only_correction = true",
        '"output_only_correction": true',
    ]
    for sample in forbidden_samples:
        assert audit.contains_forbidden_true_flag(sample), sample


def test_forbidden_true_flag_helper_allows_false_boundary_flags():
    audit = _load_audit_module()
    allowed_samples = [
        "final_v23_output_substitution: false",
        "proposed_reads_final_v23_output: false",
        "trace_solver_input: false",
        "trace_used_for_tuning: false",
        "output_only_correction: false",
        '"final_v23_output_substitution": false',
        'stream << "  \\"proposed_reads_final_v23_output\\": false,\\n";',
    ]
    for sample in allowed_samples:
        assert not audit.contains_forbidden_true_flag(sample), sample
