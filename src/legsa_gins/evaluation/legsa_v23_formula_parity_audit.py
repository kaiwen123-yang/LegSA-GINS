"""Formula parity audit helpers for N4H4D2.

中文说明：本模块只读 reference/final_v23_repo 与外部 KF-GINS 源码，
提取短公式证据和 LegSA-v23-core 自身实现特征；不复制长源码，不修改 solver。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REFERENCE_KEYWORDS = {
    "earth_DRi_DR": ["DRi", "DR("],
    "rotation_euler_matrix": ["matrix2euler", "euler2matrix"],
    "ins_vel_update": ["velUpdate", "gravity", "coriolis"],
    "ins_pos_update": ["posUpdate", "DRi", "height"],
    "ins_att_update": ["attUpdate", "qnn", "qbb"],
    "gnss_position_update": ["H_gnsspos", "gnssdata.blh", "antlever"],
    "gnss_velocity_update": ["H_gnssvel", "gnssdata.vel", "vel_std"],
    "gnss_yaw_update": ["H_gnssyaw", "gnssdata.yaw", "yaw_std"],
    "ekf_update": ["EKFUpdate", "Joseph", "K"],
    "state_feedback": ["stateFeedback", "feedback", "dx"],
}


LEGSA_CHECKS = {
    "earth_DRi_DR": ("cpp/legsa_v23_core/src/common/earth.cpp", ["DRi", "DR("]),
    "vel_gravity_sign": ("cpp/legsa_v23_core/src/mechanization/ins_mechanization.cpp", ["gravity", "+"]),
    "pos_height_sign": ("cpp/legsa_v23_core/src/mechanization/ins_mechanization.cpp", ["posUpdate", "height"]),
    "att_qnn_sign_or_order": ("cpp/legsa_v23_core/src/mechanization/ins_mechanization.cpp", ["attUpdate", "qnn", "qbb"]),
    "position_residual_sign": (
        "cpp/legsa_v23_core/src/updates/measurement_update.cpp",
        ["antenna_blh[i] - gnss.blh[i]", "predicted antenna position minus GNSS observed"],
    ),
    "position_H_phi_sign": ("cpp/legsa_v23_core/src/updates/measurement_update.cpp", ["skewSymmetric", "PHI_ID"]),
    "velocity_residual_sign": (
        "cpp/legsa_v23_core/src/updates/measurement_update.cpp",
        ["nav.vel_ned_mps[i] - gnss.vel[i]"],
    ),
    "yaw_residual_sign": ("cpp/legsa_v23_core/src/updates/measurement_update.cpp", ["gnss.yaw_deg - pred_yaw_deg"]),
    "yaw_H_mapping": ("cpp/legsa_v23_core/src/updates/measurement_update.cpp", ["PHI_ID + 2"]),
    "ekf_update_residual_sign": ("cpp/legsa_v23_core/src/filter/ekf_update.cpp", ["meas.residual[row] - predicted"]),
    "state_feedback_pos_vel_sign": (
        "cpp/legsa_v23_core/src/filter/state_feedback.cpp",
        ["pos_blh_rad_m[i] -=", "vel_ned_mps[i] -="],
    ),
    "state_feedback_phi_sign_or_side": (
        "cpp/legsa_v23_core/src/filter/state_feedback.cpp",
        ["multiply(qpn, qbn)", "rotvec2quaternion(delta_phi)"],
    ),
}


def _text_files(root: Path) -> list[Path]:
    skip = {".git", "build", "__pycache__", ".pytest_cache"}
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in skip for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in {".cpp", ".hpp", ".h", ".cc", ".c", ".py", ".md"}:
            files.append(path)
    return files


def _alias(path: Path, root: Path, role: str) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path.name
    return f"{role}:{rel.as_posix()}"


def _line_summary(line: str) -> str:
    clean = " ".join(line.strip().split())
    if len(clean) > 120:
        clean = clean[:117] + "..."
    return clean


def _search_keywords(root: Path, role: str, keywords: list[str], limit: int = 8) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    lowered = [item.lower() for item in keywords]
    for file_path in _text_files(root):
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            haystack = line.lower()
            if any(keyword in haystack for keyword in lowered):
                hits.append(
                    {
                        "source_path_role_alias": _alias(file_path, root, role),
                        "line": lineno,
                        "short_formula_summary": _line_summary(line),
                    }
                )
                if len(hits) >= limit:
                    return hits
    return hits


def audit_reference_formula_snippets(reference_root: str | Path, external_root: str | Path) -> dict[str, Any]:
    """中文说明：只记录短 evidence 摘要和行号，不复制外部源码。"""

    reference = Path(reference_root)
    external = Path(external_root)
    evidence: dict[str, Any] = {}
    for key, keywords in REFERENCE_KEYWORDS.items():
        hits = _search_keywords(reference, "final_v23_reference", keywords)
        hits.extend(_search_keywords(external, "external_kfgins_readonly", keywords))
        evidence[key] = {
            "evidence_status": "found" if hits else "evidence_missing",
            "hits": hits[:10],
        }
    return {
        "phase": "N4H4D2",
        "reference_formula_evidence": evidence,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "diagnostic_only": True,
    }


def audit_legsa_formula_implementation(repo_root: str | Path) -> dict[str, Any]:
    """中文说明：检查 LegSA-v23-core 关键公式文本特征；候选项只表示需要 D3 验证。"""

    root = Path(repo_root)
    checks: dict[str, Any] = {}
    candidates: list[str] = []
    for key, (rel_path, tokens) in LEGSA_CHECKS.items():
        path = root / rel_path
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing = [token for token in tokens if token not in text]
        status = "present" if not missing else "candidate_missing_or_ambiguous"
        checks[key] = {
            "path": rel_path,
            "implementation_status": status,
            "missing_or_ambiguous_tokens": missing,
        }
        if missing:
            candidates.append(key)

    measurement_text = (root / "cpp/legsa_v23_core/src/updates/measurement_update.cpp").read_text(
        encoding="utf-8", errors="ignore"
    )
    if "skewSymmetric(lever_nav)" in measurement_text and "position_H_phi_sign_flip" in measurement_text:
        candidates.append("position_H_phi_sign")
    if "PHI_ID + 2" in measurement_text and "yaw_H_sign_flip" in measurement_text:
        candidates.append("yaw_H_mapping")

    return {
        "phase": "N4H4D2",
        "legsa_formula_checks": checks,
        "formula_mismatch_candidates": sorted(set(candidates)),
        "candidate_meaning": "candidate means needs controlled D3 verification, not confirmed bug",
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "diagnostic_only": True,
    }


def build_formula_parity_report(
    reference_root: str | Path,
    external_root: str | Path,
    repo_root: str | Path,
) -> dict[str, Any]:
    """中文说明：汇总 reference evidence 与 LegSA 实现候选项，输出 D2 JSON report。"""

    reference_report = audit_reference_formula_snippets(reference_root, external_root)
    legsa_report = audit_legsa_formula_implementation(repo_root)
    missing_evidence = [
        key
        for key, value in reference_report["reference_formula_evidence"].items()
        if value.get("evidence_status") == "evidence_missing"
    ]
    report = {
        "phase": "N4H4D2",
        "reference_report": reference_report,
        "legsa_report": legsa_report,
        "formula_mismatch_candidates": legsa_report["formula_mismatch_candidates"],
        "evidence_missing": missing_evidence,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
    }
    return report


def write_formula_report(path: str | Path, report: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
