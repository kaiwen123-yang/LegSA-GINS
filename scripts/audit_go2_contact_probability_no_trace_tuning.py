#!/usr/bin/env python3
"""Audit N7B4 contact probability boundary.

中文说明：contact probability 模型必须只使用 Go2 field distribution / mode/gait
等内部字段；不得出现 trace/final_v23 调阈值或本地路径泄漏。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "src/legsa_gins/go2_prior/go2_contact_confidence_features.py",
    "src/legsa_gins/go2_prior/go2_contact_probability_model.py",
    "src/legsa_gins/go2_prior/go2_probability_weighted_prior_builder.py",
    "scripts/experiments/run_n7b4_go2_literature_contact_velocity.py",
    "docs/experiments/n7b4_contact_probability_model.md",
    "docs/experiments/n7b4_diagnostic_activation_boundary.md",
]
FORBIDDEN = [
    "/mnt/c/" + "Users/ykw/Desktop",
    "/mnt/c/" + "Users/86187/Desktop",
    "C:" + "\\\\Users",
    "/home/kaiwen/" + "legsa_n4h4",
    "/home/kaiwen/" + "legsa_external_artifacts",
    "trace_tuned",
    "final_v23_tuned",
]


def main() -> int:
    for rel in FILES:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"audit_go2_contact_probability_no_trace_tuning failed: missing {rel}")
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in FORBIDDEN:
            if token in text:
                raise SystemExit(f"audit_go2_contact_probability_no_trace_tuning failed: forbidden token {token} in {rel}")
    model_text = (ROOT / "src/legsa_gins/go2_prior/go2_contact_probability_model.py").read_text(encoding="utf-8")
    required = [
        "trace_solver_input\": False",
        "final_v23_output_solver_input\": False",
        "diagnostic_only\": True",
        "diagnostic_contact_probability_not_truth_label",
    ]
    for token in required:
        if token not in model_text:
            raise SystemExit(f"audit_go2_contact_probability_no_trace_tuning failed: required boundary missing {token}")
    print("audit_go2_contact_probability_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
