"""Runtime debug trace loaders for N4H4D1.

中文说明：本模块只读取 LegSA-v23-core 诊断输出，不读取 trace 作为 solver input，
不做 output-only correction，也不删除 epoch。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


FORBIDDEN_FALSE_FLAGS = [
    "trace_solver_input",
    "final_v23_output_substitution",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
    "numerical_performance_claim",
]


def read_json(path: str | Path) -> dict[str, Any]:
    """中文说明：读取 runtime-only JSON；缺失时返回 evidence_missing。"""

    file_path = Path(path)
    if not file_path.exists():
        return {"evidence_status": "evidence_missing", "missing_path_name": file_path.name}
    return json.loads(file_path.read_text(encoding="utf-8"))


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    """中文说明：读取 runtime-only CSV，尽量把数字转为 float/bool，便于诊断。"""

    file_path = Path(path)
    if not file_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            converted: dict[str, Any] = {}
            for key, value in row.items():
                if value in {"true", "false"}:
                    converted[key] = value == "true"
                    continue
                try:
                    converted[key] = float(value)
                except (TypeError, ValueError):
                    converted[key] = value
            rows.append(converted)
    return rows


def load_debug_bundle(debug_dir: str | Path) -> dict[str, Any]:
    """中文说明：加载 C++ debug bundle；这些文件只服务诊断，不代表性能输出。"""

    root = Path(debug_dir)
    bundle = {
        "config_snapshot": read_json(root / "CONFIG_INIT_SNAPSHOT.json"),
        "input_snapshot": read_json(root / "INPUT_STREAM_SNAPSHOT.json"),
        "runtime_debug_manifest": read_json(root / "RUNTIME_DEBUG_MANIFEST.json"),
        "first_updates": read_csv_rows(root / "FIRST_UPDATES.csv"),
        "first_propagations": read_csv_rows(root / "FIRST_PROPAGATIONS.csv"),
        "state_trace_1hz": read_csv_rows(root / "STATE_TRACE_1HZ.csv"),
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    return bundle


def assert_forbidden_flags_false(report: dict[str, Any]) -> list[str]:
    """中文说明：返回未保持 false 的 forbidden flags；audit 使用它阻断越界 claim。"""

    return [key for key in FORBIDDEN_FALSE_FLAGS if report.get(key) is not False]

