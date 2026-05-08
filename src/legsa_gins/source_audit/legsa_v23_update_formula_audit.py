"""只读审计 final_v23 / KF-GINS 更新公式证据。

中文说明：
本模块只扫描 reference/final_v23_repo 与 /home/kaiwen/KF-GINS 中的短证据行，
不复制外部源码，不把 reference 输出作为 proposed solver input。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
REFERENCE_ROOTS = [
    REPO_ROOT / "reference/final_v23_repo",
    Path("/home/kaiwen/KF-GINS"),
]

SEARCH_GROUPS = {
    "position_update_formula_evidence": [
        "gnssdata.blh",
        "gnssdata.std",
        "H_gnsspos",
        "R_gnsspos",
        "antlever",
    ],
    "velocity_update_formula_evidence": [
        "gnssdata.vel",
        "gnssdata.vel_std",
        "H_gnssvel",
        "R_gnssvel",
    ],
    "yaw_update_formula_evidence": [
        "gnssdata.yaw",
        "gnssdata.yaw_std",
        "H_gnssyaw",
        "R_gnssyaw",
    ],
    "yaw_residual_sign_evidence": [
        "yaw residual",
        "residual_yaw",
        "YAW-NORMAL",
        "YAW-DOWNWEIGHT",
        "YAW-REJECT",
    ],
    "scheme_C_gate_evidence": [
        "scheme_C",
        "yaw_res_soft",
        "yaw_res_hard",
        "downweight",
    ],
    "ekf_feedback_evidence": [
        "EKFUpdate",
        "stateFeedback",
    ],
}


@dataclass
class EvidenceHit:
    """中文说明：单条证据只保留短行摘要，避免复制外部长源码。"""

    root: str
    path: str
    line: int
    pattern: str
    snippet: str


def _iter_text_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    skipped = {".git", "build", "cmake-build-debug", "__pycache__", ".pytest_cache"}
    suffixes = {".cpp", ".hpp", ".h", ".cc", ".cxx", ".py", ".md", ".txt", ".yaml", ".json"}
    return (
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in suffixes
        and not any(part in skipped for part in path.parts)
    )


def collect_evidence(max_hits_per_group: int = 12) -> dict[str, object]:
    """中文说明：只读收集公式关键词证据；缺失时保留 evidence_missing。"""

    grouped: dict[str, list[EvidenceHit]] = {name: [] for name in SEARCH_GROUPS}
    for root in REFERENCE_ROOTS:
        for path in _iter_text_files(root):
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            relpath = str(path.relative_to(root))
            for line_no, line in enumerate(lines, start=1):
                compact = " ".join(line.strip().split())
                if not compact:
                    continue
                for group, patterns in SEARCH_GROUPS.items():
                    if len(grouped[group]) >= max_hits_per_group:
                        continue
                    for pattern in patterns:
                        if pattern.lower() in compact.lower():
                            grouped[group].append(
                                EvidenceHit(
                                    root=str(root),
                                    path=relpath,
                                    line=line_no,
                                    pattern=pattern,
                                    snippet=compact[:180],
                                )
                            )
                            break

    result: dict[str, object] = {
        "audit_role": "read_only_formula_evidence",
        "reference_roots": [str(root) for root in REFERENCE_ROOTS],
        "external_source_copied": False,
        "final_v23_output_used_as_solver_input": False,
        "yaw_residual_sign": "evidence_missing_default_obs_pred",
        "velocity_lever_correction": "evidence_missing_false",
        "yaw_H_mapping_conservative": True,
    }
    for group, hits in grouped.items():
        result[group] = [asdict(hit) for hit in hits] if hits else "evidence_missing"
    return result


def write_report(output_path: Path) -> Path:
    """中文说明：写 /tmp JSON 证据报告，tracked docs 只引用短摘要和 evidence_missing。"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(collect_evidence(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


if __name__ == "__main__":
    print(json.dumps(collect_evidence(), indent=2, ensure_ascii=False))
