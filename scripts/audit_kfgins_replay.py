#!/usr/bin/env python3
"""Audit committed N4H2 KF-GINS replay reports.

中文说明：本审计只读取已提交的 N4H2 文档，不读取真实 raw/replay
产物，不修改外部 KF-GINS，也不把诊断指标升级为性能结论。
"""

from __future__ import annotations

from pathlib import Path
import re
import sys


REQUIRED_REPORT = Path("docs/experiments/process_data_kfgins_replay.md")
REQUIRED_DECISION = Path("docs/experiments/n4h2_replay_decision.md")

REQUIRED_REPORT_SNIPPETS = [
    "This is baseline replay evidence only.",
    "not a proposed solver result",
    "`trace_solver_input=false`",
    "`output_only_correction=false`",
    "`formal_performance_claim_allowed=false`",
    "`process_data-compatible runtime inputs can drive an external KF-GINS baseline",
]

REQUIRED_DECISION_SNIPPETS = [
    "- replay_completed: true",
    "- external_run_status: completed",
    "- output_standardization_status: completed",
    "- evaluation_status: completed",
    "- metrics_available: true",
    "- position_replay_gate_pass: true",
    "- yaw_replay_gate_pass: false",
    "- yaw_config_issue: true",
    "- blocking_issue: none",
    "recommended_next_stage = N4H2C_yaw_config_parity_audit",
    "- trace_solver_input: false",
    "- trace_evaluation_only: true",
    "- output_only_correction: false",
    "- bad_epoch_deletion_for_metric: false",
    "- numerical_performance_claim: false",
    "- raw_data_committed: false",
]

METRIC_EXPECTATIONS = {
    "aligned_count": 56566,
    "horizontal_rmse_m": 0.3479654209159466,
    "up_rmse_m": 0.7940101228929531,
    "yaw_rmse_deg": 93.55731196644105,
    "roll_rmse_deg": 1.0674301793679788,
    "pitch_rmse_deg": 1.6712386339103198,
}

FORBIDDEN_LOCAL_PATHS = [
    "/mnt/c/Users/ykw/Desktop",
    "/mnt/c/Users/86187/Desktop",
    "C:\\Users",
]


def _read(path: Path, root: Path) -> str:
    full_path = root / path
    if not full_path.exists():
        raise AssertionError(f"missing required report: {path}")
    return full_path.read_text(encoding="utf-8")


def _require_snippets(text: str, snippets: list[str], label: str) -> None:
    missing = [snippet for snippet in snippets if snippet not in text]
    if missing:
        raise AssertionError(f"{label} missing snippets: {missing}")


def _metric_value(text: str, name: str) -> float:
    pattern = re.compile(rf"- {re.escape(name)}: ([0-9.]+)")
    match = pattern.search(text)
    if not match:
        raise AssertionError(f"missing metric: {name}")
    return float(match.group(1))


def audit(root: Path) -> None:
    report_text = _read(REQUIRED_REPORT, root)
    decision_text = _read(REQUIRED_DECISION, root)
    joined = report_text + "\n" + decision_text

    _require_snippets(report_text, REQUIRED_REPORT_SNIPPETS, str(REQUIRED_REPORT))
    _require_snippets(decision_text, REQUIRED_DECISION_SNIPPETS, str(REQUIRED_DECISION))

    for name, expected in METRIC_EXPECTATIONS.items():
        actual = _metric_value(decision_text, name)
        if abs(actual - expected) > 1.0e-12:
            raise AssertionError(f"{name} expected {expected}, got {actual}")

    leaked = [path for path in FORBIDDEN_LOCAL_PATHS if path in joined]
    if leaked:
        raise AssertionError(f"local BY2 path leak found: {leaked}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        audit(root)
    except AssertionError as exc:
        print(f"N4H2 KF-GINS replay audit failed: {exc}")
        return 1
    print("N4H2 KF-GINS replay audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
