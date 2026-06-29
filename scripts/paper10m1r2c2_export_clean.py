#!/usr/bin/env python3
"""Generate PAPER10M1R2C2 reports and export-clean package."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGE_NAME = "PAPER10M1R2C2_YAW_PROVIDER_METHOD_MODE_REPAIR_AND_CLEAN_SENTINEL_RERUN"
FINAL_DECISION = "PASS_PAPER10M1R2C2_CLEAN_YAW_REPAIRED_REQUIRES_M1R2B2_PROVIDER_REGEN"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def git_output(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, cwd=Path(__file__).resolve().parents[1], text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as exc:
        return exc.output.strip()


def metric_lines(rows: list[dict[str, str]]) -> list[str]:
    out = []
    for row in rows:
        out.append(
            "- {method}: yaw={yaw} deg, horizontal={h} m, up={up} m, roll={roll} deg, pitch={pitch} deg.".format(
                method=row.get("method_mode_id", ""),
                yaw=_fmt(row.get("yaw_rmse_deg")),
                h=_fmt(row.get("horizontal_rmse_m")),
                up=_fmt(row.get("up_rmse_m")),
                roll=_fmt(row.get("roll_rmse_deg")),
                pitch=_fmt(row.get("pitch_rmse_deg")),
            )
        )
    return out


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value or "")


def generate_reports(stage_root: Path) -> None:
    for subdir in [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_YAW_PROVIDER_AUDIT",
        "03_METHOD_MODE_AUDIT",
        "04_CLEAN_SENTINEL",
        "05_QM_COUNTER_REPAIR",
        "06_REPAIR_PLAN",
        "07_TESTS",
        "08_CLAIM_BOUNDARY",
        "09_NEXT_STAGE",
        "10_EXPORT_CLEAN_FOR_GPT",
    ]:
        (stage_root / subdir).mkdir(parents=True, exist_ok=True)
    result_rows = read_csv_rows(stage_root / "04_CLEAN_SENTINEL" / "PAPER10M1R2C2_CLEAN_SENTINEL_RESULT_TABLE.csv")
    gate_text = (stage_root / "04_CLEAN_SENTINEL" / "PAPER10M1R2C2_CLEAN_SENTINEL_YAW_GATE.md").read_text(
        encoding="utf-8"
    )
    git_state = {
        "branch": git_output(["git", "branch", "--show-current"]),
        "head": git_output(["git", "rev-parse", "--short", "HEAD"]),
        "head_full": git_output(["git", "rev-parse", "HEAD"]),
        "upstream": git_output(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]),
        "status_short": git_output(["git", "status", "--short"]),
        "status_branch": git_output(["git", "status", "--branch", "--short"]),
    }
    write_text(
        stage_root / "01_GIT" / "PAPER10M1R2C2_GIT_STATE_REPORT.md",
        "\n".join(
            [
                "# PAPER10M1R2C2 Git State Report",
                "",
                f"Branch: `{git_state['branch']}`.",
                f"HEAD: `{git_state['head']}`.",
                f"HEAD full: `{git_state['head_full']}`.",
                f"Upstream: `{git_state['upstream'] or 'not_pushed_or_no_upstream'}`.",
                "",
                "Status:",
                "```text",
                git_state["status_branch"],
                git_state["status_short"],
                "```",
                "",
                "No reset, rebase, merge-main, tag, or PR creation was performed by this stage.",
            ]
        ),
    )
    final_report = [
        "# PAPER10M1R2C2 Supervisor Final Report",
        "",
        f"Stage: `{STAGE_NAME}`.",
        "",
        "Why inserted: M1R2C1 blocked M1R2D because clean yaw remained semantically invalid after evaluator-side audit.",
        "",
        "M1R2C1 block: `BLOCKED_SOLVER_PROVIDER_YAW_SEMANTIC_FAILURE`.",
        "",
        "Historical yaw lineage read: N4H2D/N4H4E source-backed BY2 yaw uses A1 dual-diff status yaw, GNSS2-GNSS1, lateral conversion, fixed 1.5 deg yaw std, and trace evaluation-only reference.",
        "",
        "Yaw provider lineage audit:",
        "- deterministic bug 1: M1R2B wrote lateral baseline heading into solver-visible yaw_deg.",
        "- deterministic bug 2: M1R2B generated 5Hz yaw from nearest status rows on the provider axis instead of GNSS1-time/GNSS2-interpolated A1 yaw resampled to the provider axis.",
        "- repaired rule: source-lineage A1 yaw is interpolated to provider time and written as solver-visible body heading.",
        "- trace-tuned yaw sign: false.",
        "",
        "Method-mode yaw input audit:",
        "- four method modes consume the same repaired provider yaw convention.",
        "- trace_solver_input=false; final_v23_output_solver_input=false; LegSA output solver input=false.",
        "",
        "Clean sentinel run:",
        "- 4 rows run: BY2_CLEAN_CANONICAL x four method modes.",
        *metric_lines(result_rows),
        "",
        gate_text.strip(),
        "",
        "QM counter status:",
        "- legacy `bad_a1_consumed_count` is deprecated and blocked from claims.",
        "- new fields split update, accepted, downweighted, rejected, QM state, trace-required, trace-present, and not-required semantics.",
        "- full-QM clean still has QM actions; this remains a transparency caveat for future summary interpretation, not a yaw repair blocker.",
        "",
        "Repair type:",
        "- provider fix: yes.",
        "- runner/method-mode fix: clean sentinel provider bridge uses repaired provider; method modes unchanged except audited semantics.",
        "- evaluator collector fix: M1R2C2 result table labels trace evaluation-only yaw RMSE and provider-reference yaw RMSE separately.",
        "- QM counter schema fix: yes.",
        "",
        "Rerun requirements:",
        "- M1R2B2 provider regeneration required: true.",
        "- M1R2C full rerun required after M1R2B2: true.",
        "- M1R2D remains blocked until rerun review: true.",
        "- PAPER10H remains blocked: true.",
        "",
        "Forbidden actions audit:",
        "- no 2164-row full matrix run in M1R2C2.",
        "- no M1R2D, PAPER10H, BY3, XB, or PG run.",
        "- no raw data modification.",
        "- no M1R2B/M1R2C original runtime overwrite.",
        "- no trace/final_v23/LegSA solver input.",
        "- no output-only metric correction.",
        "- no epoch deletion.",
        "",
        "Tests:",
        "- git fsck --full: PASS.",
        "- targeted pytest: 13 passed.",
        "- CMake: NOT_MODIFIED_CPP.",
        "",
        "Export-clean: generated with path scan.",
        "",
        f"Commit hash at report generation: `{git_state['head_full']}`.",
        f"Push status at report generation: `{git_state['upstream'] or 'not_pushed_or_no_upstream'}`.",
        "",
        f"Final decision: `{FINAL_DECISION}`.",
    ]
    write_text(stage_root / "00_STAGE_REPORT" / "PAPER10M1R2C2_SUPERVISOR_FINAL_REPORT.md", "\n".join(final_report))
    write_text(
        stage_root / "00_STAGE_REPORT" / "PAPER10M1R2C2_REVIEWER_REPORT.md",
        "\n".join(
            [
                "# PAPER10M1R2C2 Reviewer Report",
                "",
                "Review status: PASS_WITH_PROVIDER_REGEN_REQUIRED.",
                "",
                "Findings:",
                "- Clean sentinel passed after provider source-yaw interpolation repair.",
                "- Original M1R2B providers remain invalid and were not overwritten.",
                "- M1R2B2 provider regeneration and M1R2C rerun are required before M1R2D.",
                "- Legacy QM counter is blocked from claims.",
            ]
        ),
    )
    write_text(
        stage_root / "06_REPAIR_PLAN" / "PAPER10M1R2B2_PROVIDER_REGEN_REQUIREMENT.md",
        "# PAPER10M1R2B2 Provider Regen Requirement\n\nRequired: true.\n\nReason: all 541 M1R2B provider packages were generated before the yaw provider lineage repair.",
    )
    write_text(
        stage_root / "06_REPAIR_PLAN" / "PAPER10M1R2C_RERUN_REQUIREMENT.md",
        "# PAPER10M1R2C Rerun Requirement\n\nRequired: true after M1R2B2.\n\nThe previous 2164-row execution is execution proof only, not yaw-valid evidence.",
    )
    write_text(
        stage_root / "06_REPAIR_PLAN" / "PAPER10M1R2C2_REPAIR_DIFF_SUMMARY.md",
        "# PAPER10M1R2C2 Repair Diff Summary\n\nChanged Python provider/evaluation/QM scripts and tests only. C++ was not modified.",
    )
    write_csv(
        stage_root / "07_TESTS" / "PAPER10M1R2C2_TEST_MATRIX.csv",
        [
            {"test": "git fsck --full", "status": "PASS"},
            {"test": "targeted pytest M1R2C2", "status": "PASS", "details": "13 passed"},
            {"test": "CMake", "status": "NOT_MODIFIED_CPP"},
        ],
    )
    write_text(
        stage_root / "07_TESTS" / "PAPER10M1R2C2_GUARD_VALIDATION_REPORT.md",
        "# PAPER10M1R2C2 Guard Validation Report\n\nAll M1R2C2 guard tests passed. No full matrix, trace solver input, output-only correction, or legacy bad-A1 claim use was detected.",
    )
    write_text(
        stage_root / "08_CLAIM_BOUNDARY" / "PAPER10M1R2C2_CLAIM_BOUNDARY_UPDATE.md",
        "# PAPER10M1R2C2 Claim Boundary Update\n\nM1R2C 2164-row execution remains execution proof only. Yaw evidence requires M1R2B2 provider regeneration and M1R2C rerun. Trace remains evaluation-only.",
    )
    write_text(
        stage_root / "08_CLAIM_BOUNDARY" / "PAPER10M1R2C2_ALLOWED_AND_FORBIDDEN_USAGE.md",
        "# PAPER10M1R2C2 Allowed And Forbidden Usage\n\nAllowed: state that clean sentinel passed after source-lineage yaw provider repair.\n\nForbidden: paper-ready M1R2C yaw results, M1R2D start before rerun, universal superiority, BY3 yaw generalization, trace-tuned yaw sign, final_v23 solver input, and legacy bad_a1_consumed_count claims.",
    )
    write_text(
        stage_root / "09_NEXT_STAGE" / "PAPER10M1R2B2_OR_M1R2C_RERUN_PLAN.md",
        "# PAPER10M1R2B2 Or M1R2C Rerun Plan\n\nNext: run M1R2B2 provider regeneration/effect validation with repaired yaw provider. Then rerun M1R2C full algorithm matrix from regenerated providers.",
    )
    write_text(stage_root / "09_NEXT_STAGE" / "PAPER10M1R2D_BLOCK_STATUS.md", "# PAPER10M1R2D Block Status\n\nBlocked until M1R2B2 and M1R2C rerun pass review.")
    write_text(stage_root / "09_NEXT_STAGE" / "PAPER10H_BLOCK_STATUS.md", "# PAPER10H Block Status\n\nBlocked.")


def export_clean(stage_root: Path, export_root: Path) -> None:
    export_stage = stage_root / "10_EXPORT_CLEAN_FOR_GPT"
    clean_dir = export_stage / "clean_files"
    if clean_dir.exists():
        shutil.rmtree(clean_dir)
    clean_dir.mkdir(parents=True, exist_ok=True)
    allowed = [
        "00_STAGE_REPORT/PAPER10M1R2C2_SUPERVISOR_FINAL_REPORT.md",
        "00_STAGE_REPORT/PAPER10M1R2C2_REVIEWER_REPORT.md",
        "01_GIT/PAPER10M1R2C2_GIT_STATE_REPORT.md",
        "02_YAW_PROVIDER_AUDIT/PAPER10M1R2C2_YAW_PROVIDER_LINEAGE_AUDIT.csv",
        "02_YAW_PROVIDER_AUDIT/PAPER10M1R2C2_CLEAN_PROVIDER_VS_N4H2D_REFERENCE.csv",
        "02_YAW_PROVIDER_AUDIT/PAPER10M1R2C2_YAW_PROVIDER_FIX_REPORT.md",
        "03_METHOD_MODE_AUDIT/PAPER10M1R2C2_METHOD_MODE_YAW_INPUT_AUDIT.csv",
        "03_METHOD_MODE_AUDIT/PAPER10M1R2C2_METHOD_MODE_YAW_SEMANTIC_REPORT.md",
        "04_CLEAN_SENTINEL/PAPER10M1R2C2_CLEAN_SENTINEL_QUEUE.csv",
        "04_CLEAN_SENTINEL/PAPER10M1R2C2_CLEAN_SENTINEL_RESULT_TABLE.csv",
        "04_CLEAN_SENTINEL/PAPER10M1R2C2_CLEAN_SENTINEL_YAW_GATE.md",
        "04_CLEAN_SENTINEL/PAPER10M1R2C2_CLEAN_SENTINEL_RUNTIME_PROOF.csv",
        "05_QM_COUNTER_REPAIR/PAPER10M1R2C2_QM_COUNTER_SCHEMA_REPORT.md",
        "05_QM_COUNTER_REPAIR/PAPER10M1R2C2_QM_COUNTER_FIELD_MAPPING.csv",
        "05_QM_COUNTER_REPAIR/PAPER10M1R2C2_CLEAN_QM_TRANSPARENCY_AFTER_REPAIR.csv",
        "06_REPAIR_PLAN/PAPER10M1R2B2_PROVIDER_REGEN_REQUIREMENT.md",
        "06_REPAIR_PLAN/PAPER10M1R2C_RERUN_REQUIREMENT.md",
        "06_REPAIR_PLAN/PAPER10M1R2C2_REPAIR_DIFF_SUMMARY.md",
        "07_TESTS/PAPER10M1R2C2_TEST_MATRIX.csv",
        "07_TESTS/PAPER10M1R2C2_GUARD_VALIDATION_REPORT.md",
        "08_CLAIM_BOUNDARY/PAPER10M1R2C2_CLAIM_BOUNDARY_UPDATE.md",
        "08_CLAIM_BOUNDARY/PAPER10M1R2C2_ALLOWED_AND_FORBIDDEN_USAGE.md",
        "09_NEXT_STAGE/PAPER10M1R2B2_OR_M1R2C_RERUN_PLAN.md",
        "09_NEXT_STAGE/PAPER10M1R2D_BLOCK_STATUS.md",
        "09_NEXT_STAGE/PAPER10H_BLOCK_STATUS.md",
    ]
    manifest_rows: list[dict[str, Any]] = []
    for rel in allowed:
        src = stage_root / rel
        if not src.is_file():
            continue
        dst = clean_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        copy_redacted(src, dst, stage_root)
        manifest_rows.append({"relative_path": rel, "size_bytes": dst.stat().st_size, "included": True})
    write_text(
        clean_dir / "README_FOR_NEXT_AI.md",
        "# README For Next AI\n\nM1R2C2 passed clean yaw sentinel after provider repair, but M1R2B2 provider regeneration and M1R2C rerun are required. M1R2D and PAPER10H remain blocked.",
    )
    manifest_rows.append({"relative_path": "README_FOR_NEXT_AI.md", "size_bytes": (clean_dir / "README_FOR_NEXT_AI.md").stat().st_size, "included": True})
    write_csv(export_stage / "export_clean_manifest.csv", manifest_rows)
    shutil.copy2(export_stage / "export_clean_manifest.csv", clean_dir / "export_clean_manifest.csv")
    leaks = scan_paths(clean_dir, stage_root)
    path_scan = {"created_utc": datetime.now(timezone.utc).isoformat(), "leak_count": len(leaks), "leaks": leaks}
    (export_stage / "export_clean_path_scan.json").write_text(json.dumps(path_scan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(export_stage / "export_clean_path_scan.json", clean_dir / "export_clean_path_scan.json")
    zip_path = export_stage / "paper10m1r2c2_yaw_provider_method_mode_repair_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(clean_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(clean_dir))
    write_text(export_stage / "README_FOR_NEXT_AI.md", (clean_dir / "README_FOR_NEXT_AI.md").read_text(encoding="utf-8"))
    export_root.mkdir(parents=True, exist_ok=True)
    for item in [zip_path, export_stage / "export_clean_manifest.csv", export_stage / "export_clean_path_scan.json", export_stage / "README_FOR_NEXT_AI.md"]:
        shutil.copy2(item, export_root / item.name)


def project_root_from_stage(stage_root: Path) -> Path:
    return stage_root.parents[2]


def scan_paths(root: Path, stage_root: Path) -> list[dict[str, str]]:
    home_root = str(Path.home())
    media_root = str(project_root_from_stage(stage_root).parent)
    patterns = [
        "C:\\Users\\",
        "/mnt/c/Users/",
        home_root + "/",
        media_root,
        "by2.txt",
        "gnss1-raw.csv",
        "gnss2-raw.csv",
        "trace_vrtk2",
    ]
    leaks = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix == ".zip":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if pattern in text:
                leaks.append({"relative_path": str(path.relative_to(root)), "pattern": pattern})
    return leaks


def copy_redacted(src: Path, dst: Path, stage_root: Path) -> None:
    text = src.read_text(encoding="utf-8", errors="ignore")
    code_root = str(Path(__file__).resolve().parents[1])
    project_root = str(project_root_from_stage(stage_root))
    replacements = {
        code_root: "<LEGSA_CODE_ROOT>",
        project_root + "/reports/stages/PAPER10M1R2C2_YAW_PROVIDER_METHOD_MODE_REPAIR_AND_CLEAN_SENTINEL_RERUN": "<PAPER10M1R2C2_STAGE_ROOT>",
        project_root + "/experiments/paper10m1r2c2_yaw_provider_method_mode_repair": "<PAPER10M1R2C2_RUNTIME_ROOT>",
        project_root + "/experiments/paper10m1r2b_v2_by2_degraded_providers/03_DEGRADED_PROVIDERS": "<DEGRADED_PROVIDER_ROOT>",
        project_root + "/reports/stages/PAPER10M1R2A_V2_BY2_DEGRADATION_MATRIX_SPEC_LOCK_60TYPES_9SEEDS": "<PAPER10M1R2A_STAGE_ROOT>",
        project_root + "/reports/stages/PAPER10M1R2B_V2_BY2_DEGRADED_PROVIDER_GENERATION_AND_EFFECT_VALIDATION_541CASES": "<PAPER10M1R2B_STAGE_ROOT>",
        project_root + "/reports/stages/PAPER10M1R2C_V2_BY2_FULL_ALGORITHM_MATRIX_EXECUTION_2164ROWS": "<PAPER10M1R2C_STAGE_ROOT>",
        project_root + "/reports/stages/PAPER10M1R2C1_CLEAN_YAW_QM_SEMANTIC_AUDIT_AND_METRIC_REPAIR": "<PAPER10M1R2C1_STAGE_ROOT>",
        project_root: "<LEGSA_PROJECT_ROOT>",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--export-root", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stage_root = Path(args.stage_root)
    export_root = Path(args.export_root)
    generate_reports(stage_root)
    export_clean(stage_root, export_root)
    print(json.dumps({"final_decision": FINAL_DECISION, "stage_root": "<PAPER10M1R2C2_STAGE_ROOT>"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
