"""Read-only audit for runtime yaw update equations in external KF-GINS.

中文说明：只记录路径、行号和短摘要，不复制源码长段，不修改外部仓库。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


KEYWORDS = [
    "gnssdata.yaw",
    "yaw_std",
    "yaw update",
    "scheme_C",
    "H_gnssyaw",
    "R_gnssyaw",
    "wrap",
    "atan2",
    "stateFeedback",
    "euler[2]",
    "residual yaw",
    "heading",
]

TEXT_SUFFIXES = {".cpp", ".cc", ".cxx", ".h", ".hpp", ".py", ".md", ".txt"}
SKIP_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "artifacts",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    "extended_degradation_results",
    "log",
    "logs",
    "output",
    "outputs",
    "result",
    "results",
    "ThirdParty",
    "third_party",
    "vendor",
}
MAX_TEXT_BYTES = 2_000_000


def _iter_text_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size <= MAX_TEXT_BYTES:
            files.append(path)
    return sorted(files)


def audit_yaw_update_runtime(source_root: str | Path) -> dict[str, Any]:
    root = Path(source_root)
    hits: list[dict[str, Any]] = []
    found = {keyword: False for keyword in KEYWORDS}
    counts = {keyword: 0 for keyword in KEYWORDS}
    for path in _iter_text_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for keyword in KEYWORDS:
                if counts[keyword] >= 40 or keyword not in line:
                    continue
                found[keyword] = True
                counts[keyword] += 1
                hits.append(
                    {
                        "path": str(path),
                        "line": line_number,
                        "keyword": keyword,
                        "summary": f"{keyword} runtime yaw update evidence",
                    }
                )
    yaw_measurement_loaded = found["gnssdata.yaw"]
    yaw_unit_conversion = found["heading"] or found["atan2"]
    yaw_residual_formula = found["residual yaw"] or found["euler[2]"] or found["gnssdata.yaw"]
    yaw_wrap_formula = found["wrap"]
    yaw_measurement_matrix = found["H_gnssyaw"]
    yaw_noise_used = found["R_gnssyaw"] or found["yaw_std"]
    scheme_gate = found["scheme_C"]
    missing = [
        name
        for name, present in [
            ("yaw_measurement_loaded", yaw_measurement_loaded),
            ("yaw_residual_formula", yaw_residual_formula),
            ("yaw_wrap_formula", yaw_wrap_formula),
            ("yaw_measurement_matrix", yaw_measurement_matrix),
            ("yaw_noise_used", yaw_noise_used),
            ("scheme_C_gate_used", scheme_gate),
        ]
        if not present
    ]
    return {
        "yaw_measurement_loaded": yaw_measurement_loaded,
        "yaw_unit_conversion": yaw_unit_conversion,
        "yaw_residual_formula": yaw_residual_formula,
        "yaw_wrap_formula": yaw_wrap_formula,
        "yaw_measurement_matrix": yaw_measurement_matrix,
        "yaw_noise_used": yaw_noise_used,
        "scheme_C_gate_used": scheme_gate,
        "yaw_update_status": "yaw_runtime_update_evidence_found" if not missing else "yaw_runtime_update_evidence_partial",
        "evidence_missing": missing,
        "source_paths_and_lines": hits,
        "trace_solver_input": False,
        "copied_external_source": False,
        "numerical_performance_claim": False,
    }
