"""Probe whether LSIM/OIM had an existing concrete definition before N6A.

中文说明：只把非 N6A 的可执行/定义性文本算作已有定义；历史 boundary/roadmap 中
的“未实现 LSIM/OIM”不算已有定义。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


KEYWORDS = ("LSIM", "OIM", "source-aware", "source aware", "innovation metric", "integrity metric")


def probe_source_aware_definitions(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root)
    matches: list[dict[str, Any]] = []
    definition_like: list[dict[str, Any]] = []
    for rel_root in ["docs", "src", "cpp", "scripts", "tests"]:
        base = root / rel_root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix in {".pyc", ".png", ".jpg", ".jpeg", ".pdf", ".svg"}:
                continue
            rel = path.relative_to(root).as_posix()
            if "source_aware" in rel.lower() or "n6a_" in rel.lower() or "N6A_" in rel:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if any(keyword.lower() in line.lower() for keyword in KEYWORDS):
                    item = {"path": rel, "line": lineno, "text": line.strip()[:240]}
                    matches.append(item)
                    lowered = line.lower()
                    if any(token in lowered for token in ["lsim definition", "oim definition", "def compute_lsim", "def compute_oim"]):
                        definition_like.append(item)
    return {
        "stage": "N6A_source_aware_LSIM_OIM_weighting",
        "found_existing_definition": bool(definition_like),
        "existing_definition_matches": definition_like,
        "historical_mentions": matches,
        "adopted_auditable_definition": not bool(definition_like),
        "adopted_definition": {
            "LSIM": "Local/Source-Level Integrity Metric based on solver-visible source metadata",
            "OIM": "Observation Innovation Metric based on residual/R/HPH consistency",
        },
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_probe_report(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
