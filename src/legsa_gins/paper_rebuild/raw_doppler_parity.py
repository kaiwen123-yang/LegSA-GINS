"""CLEAN2R2A1 Raw Doppler minimum-sufficient provider parity.

This module deliberately does *not* canonicalize RINEX files or rebuild a
provider.  It separates the 18 solver-semantic CSV columns from three
attempt-specific provenance columns and records the current full-file bytes as
an audit identity.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from .manifest import sha256_file


RAW_DOPPLER_COLUMNS = (
    "time",
    "source_time",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "sat_count",
    "rtklib_solution_sat_count",
    "doppler_sat_count",
    "gdop_like",
    "provider_status",
    "valid",
    "quality",
    "quality_flag",
    "raw_doppler_backend_id",
    "obs_source_hash",
    "nav_source_hash",
    "conversion_config_hash",
    "covariance_policy",
)
AUDIT_ONLY_PROVENANCE_COLUMNS = (
    "obs_source_hash",
    "nav_source_hash",
    "conversion_config_hash",
)
SOLVER_SEMANTIC_COLUMNS = tuple(
    column for column in RAW_DOPPLER_COLUMNS
    if column not in AUDIT_ONLY_PROVENANCE_COLUMNS
)

EXPECTED_ROW_COUNT = 1248
EXPECTED_SOLVER_SEMANTIC_SHA256 = (
    "235694534abfe2fa15b5469cebbeda220469a0d3da7318fdbbdc39b07548fa33"
)
EXPECTED_ACTUAL_FULL_SHA256 = (
    "847d6c0ed6c28c59c661b07d59707faf76c3a5adb2b45fac9802a190b8b00fc4"
)
HISTORICAL_NONCANONICAL_FULL_SHA256 = (
    "a40b9933295f6c2c989884d67cc674313f2fe03113c8acdf1d02ddf28734d722"
)


class RawDopplerParityError(RuntimeError):
    """The current fresh provider failed the minimum-sufficient parity gate."""


def _semantic_rows(path: str | Path) -> tuple[list[str], list[list[str]]]:
    provider = Path(path).resolve(strict=True)
    if provider.is_symlink():
        raise RawDopplerParityError("Raw Doppler provider must not be a symlink")
    with provider.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or tuple(rows[0]) != RAW_DOPPLER_COLUMNS:
        raise RawDopplerParityError("Raw Doppler CSV must have the exact frozen 21-column header")
    if len(rows) - 1 != EXPECTED_ROW_COUNT:
        raise RawDopplerParityError("Raw Doppler CSV row count differs from 1248")
    if any(len(row) != len(RAW_DOPPLER_COLUMNS) for row in rows[1:]):
        raise RawDopplerParityError("Raw Doppler CSV contains a malformed-width data row")
    indexes = [RAW_DOPPLER_COLUMNS.index(column) for column in SOLVER_SEMANTIC_COLUMNS]
    selected = [[row[index] for index in indexes] for row in rows]
    return list(SOLVER_SEMANTIC_COLUMNS), selected


def compute_raw_doppler_solver_semantic_sha256(path: str | Path) -> str:
    """Hash the exact 18 semantic columns without reformatting cell text.

    中文说明：这里只排除三个 provenance 审计字段。其余列、行顺序和每个
    cell 的原文本均保留，以逗号和 LF 重建，并强制一个末尾 LF。这样任何
    数值、std、validity、quality、卫星数、backend 或 covariance 变化都会
    改变语义哈希。
    """

    _, rows = _semantic_rows(path)
    payload = "\n".join(",".join(row) for row in rows) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_source(path: Path) -> str:
    resolved = path.resolve(strict=True)
    if resolved.is_symlink():
        raise RawDopplerParityError(f"static audit source is a symlink: {path}")
    return resolved.read_text(encoding="utf-8")


def audit_cpp_provenance_consumption(repo_root: str | Path) -> dict[str, Any]:
    """Prove the three provenance cells gate lineage but never enter EKF math."""

    repo = Path(repo_root).resolve(strict=True)
    sources = {
        "loader": repo / "cpp/legsa_v23_port_core/src/factors/raw_doppler_factor_loader.cpp",
        "factor": repo / "cpp/legsa_v23_port_core/src/factors/raw_doppler_factor.cpp",
        "engine": repo / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp",
    }
    texts = {role: _require_source(path) for role, path in sources.items()}
    rows: list[dict[str, Any]] = []
    for column in AUDIT_ONLY_PROVENANCE_COLUMNS:
        assignment = (
            f'measurement.{column} = stringValue(row, "{column}", "");'
        )
        equality = f"measurement.{column} == config.{column}"
        loader_assignment = assignment in texts["loader"]
        loader_lineage_equality = equality in texts["loader"]
        factor_occurrences = texts["factor"].count(column)
        engine_occurrences = texts["engine"].count(column)
        rows.append({
            "column": column,
            "classification": "audit_only_provenance",
            "loader_reads_cell": loader_assignment,
            "loader_uses_for_lineage_equality": loader_lineage_equality,
            "raw_doppler_factor_numeric_occurrences": factor_occurrences,
            "gi_engine_numeric_occurrences": engine_occurrences,
            "used_in_numeric_update": factor_occurrences > 0 or engine_occurrences > 0,
            "passed": loader_assignment and loader_lineage_equality
            and factor_occurrences == 0 and engine_occurrences == 0,
        })
    report = {
        "schema_version": "paper_rebuild.clean2r2a1_cpp_provenance_static_audit.v1",
        "audit_scope": "loader_lineage_gate_and_numeric_update_sources",
        "source_sha256": {role: sha256_file(path) for role, path in sources.items()},
        "rows": rows,
        "provenance_fields_are_audit_only": True,
        "numeric_update_uses_provenance_fields": False,
        "passed": len(rows) == 3 and all(row["passed"] for row in rows),
    }
    if not report["passed"]:
        raise RawDopplerParityError("C++ provenance-field static audit failed")
    return report


def audit_raw_doppler_minimum_sufficient_parity(
    *, provider_path: str | Path, repo_root: str | Path,
) -> dict[str, Any]:
    """Audit the frozen current provider without rewriting or copying it."""

    provider = Path(provider_path).resolve(strict=True)
    semantic_hash = compute_raw_doppler_solver_semantic_sha256(provider)
    actual_hash = sha256_file(provider)
    static_audit = audit_cpp_provenance_consumption(repo_root)
    report = {
        "schema_version": "paper_rebuild.clean2r2a1_raw_doppler_parity.v1",
        "provider_path": str(provider),
        "row_count": EXPECTED_ROW_COUNT,
        "column_count": len(RAW_DOPPLER_COLUMNS),
        "solver_semantic_column_count": len(SOLVER_SEMANTIC_COLUMNS),
        "solver_semantic_columns": list(SOLVER_SEMANTIC_COLUMNS),
        "audit_only_provenance_columns": list(AUDIT_ONLY_PROVENANCE_COLUMNS),
        "all_other_columns_required": True,
        "raw_doppler_solver_semantic_sha256": semantic_hash,
        "expected_solver_semantic_sha256": EXPECTED_SOLVER_SEMANTIC_SHA256,
        "raw_doppler_actual_full_sha256": actual_hash,
        "expected_current_actual_full_sha256": EXPECTED_ACTUAL_FULL_SHA256,
        "historical_noncanonical_attempt_full_sha256": {
            "value": HISTORICAL_NONCANONICAL_FULL_SHA256,
            "role": "audit_only",
            "gate": False,
        },
        "provider_bytes_modified": False,
        "provider_rows_reordered_or_removed": False,
        "cpp_provenance_static_audit": static_audit,
        "passed": semantic_hash == EXPECTED_SOLVER_SEMANTIC_SHA256
        and actual_hash == EXPECTED_ACTUAL_FULL_SHA256
        and static_audit["passed"],
    }
    if not report["passed"]:
        raise RawDopplerParityError("minimum-sufficient Raw Doppler parity failed")
    return report
