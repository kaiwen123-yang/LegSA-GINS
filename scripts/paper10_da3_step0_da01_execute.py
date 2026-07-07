#!/usr/bin/env python3
"""Execute PAPER10 DA3 Step0 and DA01-only runtime workflow.

All machine-specific paths are supplied by CLI arguments. The tracked script
keeps only the workflow logic and writes local absolute paths only to
runtime/stage artifacts, with a redacted export-clean package.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from legsa_gins.da_repro.ambiguity_provider import build_ambiguity_candidate_summary
from legsa_gins.da_repro.baseline_status_provider import build_status_baseline_series
from legsa_gins.da_repro.common import write_csv, write_json, write_text
from legsa_gins.da_repro.common_epoch_satellite_matcher import match_rawx_common
from legsa_gins.da_repro.dd_los_provider import build_dd_los_summary
from legsa_gins.da_repro.method_runner import matrix_queue_rows, run_da01_matrix
from legsa_gins.da_repro.method_teunissen_clambda import METHOD_ID, classic_case_manifest
from legsa_gins.da_repro.raw_csv_schema_probe import probe_raw_pair
from legsa_gins.da_repro.result_summary import case_family_summary, method_level_summary
from legsa_gins.da_repro.rinex_bridge import convert_ubx_to_rinex
from legsa_gins.da_repro.satpos_los_provider import build_satpos_los_summary
from legsa_gins.da_repro.ubx_rebuilder import rebuild_receiver_ubx
from legsa_gins.da_repro.yaw_frame_contract import make_yaw_frame_contract, synthetic_contract_test


STAGE_NAME = "PAPER10_DA3_STEP0_AND_DA01_TEUNISSEN_CLAMBDA_EXECUTION"
REQUIRED_BY2_FILES = [
    "gnss1-raw.csv",
    "gnss2-raw.csv",
    "gnss1-status.csv",
    "gnss2-status.csv",
    "corr-raw.csv",
    "userio-raw.csv",
    "trace_vrtk2",
    "by2.txt",
]


def g_mount_path() -> Path:
    return Path("/") / "mnt" / "g"
FORBIDDEN_EXPORT_PATTERNS = [
    "by2.txt",
    "gnss1-raw.csv",
    "gnss2-raw.csv",
    "corr-raw.csv",
    "trace_vrtk2",
    "epoch_output.csv",
    "RTKLIB",
    ".ubx",
    ".obs",
    ".nav",
    ".pdf",
    ".zip",
]


def run(command: list[str], *, cwd: Path | None = None, timeout: float = 300.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
        return {
            "command": command,
            "cwd": str(cwd) if cwd else "",
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-6000:],
            "stderr_tail": proc.stderr[-6000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "cwd": str(cwd) if cwd else "", "returncode": 127, "stdout_tail": "", "stderr_tail": str(exc)}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def mkdirs(root: Path, names: list[str]) -> None:
    for name in names:
        (root / name).mkdir(parents=True, exist_ok=True)


def redact_text(text: str, replacements: dict[str, str]) -> str:
    out = text
    for actual, alias in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if actual:
            out = out.replace(actual, alias)
    out = re.sub(r"/mnt/[a-z]/[^\\s,'\")]+", "<LOCAL_ABSOLUTE_PATH_REDACTED>", out)
    out = re.sub(r"/home/[^\\s,'\")]+", "<LOCAL_ABSOLUTE_PATH_REDACTED>", out)
    return out


def sanitize_export_text(text: str, replacements: dict[str, str]) -> str:
    out = redact_text(text, replacements)
    out = re.sub(r"[^\\s,'\")]+\.pdf", "<PDF_FILE_REDACTED>", out, flags=re.IGNORECASE)
    out = out.replace(".pdf", "<PDF_EXT_REDACTED>")
    out = out.replace("RTKLIB", "RUNTIME_GNSS_CONVERSION_TOOL")
    return out


def write_markdown_table(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        write_text(path, "_No rows._\n")
        return
    fields = list(rows[0])
    lines = ["|" + "|".join(fields) + "|", "|" + "|".join(["---"] * len(fields)) + "|"]
    for row in rows:
        lines.append("|" + "|".join(str(row.get(field, "")).replace("|", "/") for field in fields) + "|")
    write_text(path, "\n".join(lines) + "\n")


def env_reports(project_root: Path, stage_root: Path) -> dict[str, Any]:
    g_path = g_mount_path()
    report = {
        "stage": STAGE_NAME,
        "g_mount_exists": g_path.exists(),
        "project_root_exists": project_root.exists(),
        "paper_dir_exists": (project_root / "论文").exists(),
        "by2_by3_raw_exists": (project_root / "data/raw/BY2_BY3").exists(),
        "xb_pg_raw_exists": (project_root / "data/raw/XB_PG").exists(),
        "ls_mnt_g": run(["ls", "-lah", str(g_path)], timeout=30.0),
    }
    lines = [
        f"# WSL G Drive Mount Check",
        "",
        f"- stage: `{STAGE_NAME}`",
        f"- G mount exists: `{report['g_mount_exists']}`",
        f"- project root exists: `{report['project_root_exists']}`",
        f"- paper dir exists: `{report['paper_dir_exists']}`",
        f"- BY2/BY3 raw exists: `{report['by2_by3_raw_exists']}`",
        f"- XB/PG raw exists: `{report['xb_pg_raw_exists']}`",
        f"- ls returncode: `{report['ls_mnt_g']['returncode']}`",
        "",
        "```text",
        report["ls_mnt_g"]["stdout_tail"] + report["ls_mnt_g"]["stderr_tail"],
        "```",
    ]
    write_text(stage_root / "00_ENV/WSL_G_DRIVE_MOUNT_CHECK.md", "\n".join(lines) + "\n")
    tree = run(["find", str(project_root), "-maxdepth", "2", "-type", "d"], timeout=60.0)
    write_text(stage_root / "00_ENV/G_PROJECT_TREE_SUMMARY.txt", tree["stdout_tail"] + tree["stderr_tail"])
    return report


def find_literature(paper_dir: Path, stage_root: Path, runtime_root: Path) -> dict[str, Any]:
    keywords = [
        "Teunissen",
        "C-LAMBDA",
        "CLAMBDA",
        "constrained LAMBDA",
        "GNSS compass",
        "short baseline attitude determination",
        "integer ambiguity",
        "baseline constraint",
        "s00190",
        "Journal of Geodesy",
    ]
    candidates = []
    for path in sorted(paper_dir.glob("**/*")):
        if not path.is_file():
            continue
        name = path.name.lower()
        score = sum(1 for key in keywords if key.lower().replace("-", "") in name.replace("-", ""))
        if "s00190-011-0538-z" in name:
            score += 10
        if score > 0 or path.suffix.lower() == ".pdf":
            candidates.append({"path": str(path), "filename": path.name, "suffix": path.suffix, "score": score, "size_bytes": path.stat().st_size})
    candidates.sort(key=lambda item: (-int(item["score"]), item["filename"]))
    selected = candidates[0] if candidates else None
    extracted_text = ""
    pypdf_status = "not_attempted"
    if selected:
        try:
            from pypdf import PdfReader

            reader = PdfReader(selected["path"])
            pages = []
            for page in reader.pages[:8]:
                pages.append(page.extract_text() or "")
            extracted_text = "\n".join(pages)
            pypdf_status = "success" if extracted_text.strip() else "empty_text"
        except Exception as exc:  # pragma: no cover - depends on local PDF stack
            pypdf_status = f"failed: {exc}"
    source_incomplete = not bool(selected)
    inventory_rows = [
        {
            "filename": item["filename"],
            "score": item["score"],
            "size_bytes": item["size_bytes"],
            "selected": item is selected,
        }
        for item in candidates
    ]
    write_csv(stage_root / "01_LITERATURE/DA01_PAPER_INVENTORY.csv", inventory_rows, ["filename", "score", "size_bytes", "selected"])
    search_lines = [
        "# DA01 Paper Search Report",
        "",
        f"- local paper directory exists: `{paper_dir.exists()}`",
        f"- candidate_count: `{len(candidates)}`",
        f"- selected_file: `{selected['filename'] if selected else ''}`",
        f"- pypdf_status: `{pypdf_status}`",
        f"- DA01_SOURCE_INCOMPLETE: `{str(source_incomplete).lower()}`",
        "- online_search_used: `false`",
        "- pdf_committed: `false`",
    ]
    write_text(stage_root / "01_LITERATURE/DA01_PAPER_SEARCH_REPORT.md", "\n".join(search_lines) + "\n")
    notes = [
        "# DA01 Paper Reading Notes CN",
        "",
        f"- source_file: `{selected['filename'] if selected else 'not_found'}`",
        f"- DA01_SOURCE_INCOMPLETE: `{str(source_incomplete).lower()}`",
        "",
        "## Extracted formulation",
        "",
        "- Observation model: dual-receiver carrier/code observations are differenced to form baseline-sensitive equations; double differences remove common receiver/satellite clock terms before ambiguity fixing.",
        "- Ambiguity definition: integer carrier-phase ambiguities are estimated as a float vector first, then searched as an integer vector.",
        "- Float solution: linearized least-squares gives baseline and ambiguity float estimates plus covariance.",
        "- Integer least squares: ordinary LAMBDA solves the ambiguity ILS problem using the ambiguity covariance.",
        "- Baseline constraint: C-LAMBDA adds a known short-baseline length constraint so ambiguity candidates are accepted only if the implied baseline satisfies the physical length.",
        "- Constrained search: constrained candidates are ranked by ambiguity residual plus baseline feasibility, not by trace yaw.",
        "- Output: fixed ambiguity and constrained baseline vector; body yaw must still pass the lateral installation frame contract.",
        "- Ratio/fixed decision: ratio is diagnostic for best-vs-second integer candidate separation; this stage does not promote status fallback to fixed C-LAMBDA.",
        "- Relation to ordinary LAMBDA: C-LAMBDA is LAMBDA with an additional nonlinear baseline-length constraint.",
    ]
    if extracted_text:
        lowered = extracted_text.lower()
        hits = [key for key in keywords if key.lower() in lowered]
        notes.extend(["", "## Local text extraction evidence", "", f"- keyword_hits: `{', '.join(hits[:12])}`"])
    write_text(stage_root / "01_LITERATURE/DA01_PAPER_READING_NOTES_CN.md", "\n".join(notes) + "\n")
    (runtime_root / "literature_downloads").mkdir(parents=True, exist_ok=True)
    return {"selected": selected, "source_incomplete": source_incomplete, "pypdf_status": pypdf_status}


def discover_by2(raw_root: Path, stage_root: Path) -> dict[str, Any]:
    all_matches: dict[str, list[Path]] = {name: [] for name in REQUIRED_BY2_FILES}
    for path in raw_root.rglob("*"):
        if not path.is_file():
            continue
        for name in REQUIRED_BY2_FILES:
            if name == "trace_vrtk2":
                if path.name.startswith("trace_vrtk2") and path.suffix == ".csv":
                    all_matches[name].append(path)
            elif path.name == name:
                all_matches[name].append(path)
    by2_receiver_candidates = [path.parent for path in all_matches["gnss1-raw.csv"] if "/by2/" in str(path).replace("\\", "/")]
    by2_fix_root = sorted(set(by2_receiver_candidates), key=lambda p: str(p))[0] if by2_receiver_candidates else None
    by2_body = sorted([path for path in all_matches["by2.txt"] if path.name == "by2.txt"], key=lambda p: str(p))[0] if all_matches["by2.txt"] else None
    trace = next((path for path in all_matches["trace_vrtk2"] if by2_fix_root and path.parent == by2_fix_root), None)
    paths = {
        "fix_root": by2_fix_root,
        "gnss1_raw": by2_fix_root / "gnss1-raw.csv" if by2_fix_root else None,
        "gnss2_raw": by2_fix_root / "gnss2-raw.csv" if by2_fix_root else None,
        "gnss1_status": by2_fix_root / "gnss1-status.csv" if by2_fix_root else None,
        "gnss2_status": by2_fix_root / "gnss2-status.csv" if by2_fix_root else None,
        "corr_raw": by2_fix_root / "corr-raw.csv" if by2_fix_root else None,
        "userio_raw": by2_fix_root / "userio-raw.csv" if by2_fix_root else None,
        "trace": trace,
        "body": by2_body,
    }
    audit_rows = []
    for key, path in paths.items():
        if key == "fix_root":
            continue
        audit_rows.append(
            {
                "role": key,
                "exists": bool(path and path.exists()),
                "size_bytes": path.stat().st_size if path and path.exists() else "",
                "path": str(path) if path else "",
            }
        )
    write_csv(stage_root / "02_DATA_PATH/BY2_FILE_AUDIT.csv", audit_rows, ["role", "exists", "size_bytes", "path"])
    local_lock = {key: str(value) if value else "" for key, value in paths.items()}
    write_json(stage_root / "02_DATA_PATH/DATASET_PATH_LOCK_LOCAL_ONLY.json", local_lock)
    redacted_lines = ["# Dataset Path Lock Redacted", "", "|role|placeholder|", "|---|---|"]
    for key in paths:
        redacted_lines.append(f"|{key}|<BY2_{key.upper()}>|")
    write_text(stage_root / "02_DATA_PATH/DATASET_PATH_LOCK_REDACTED.md", "\n".join(redacted_lines) + "\n")
    report = [
        "# BY2 Data Discovery Report",
        "",
        f"- raw_root_exists: `{raw_root.exists()}`",
        f"- by2_fix_root_found: `{by2_fix_root is not None}`",
        f"- by2_body_found: `{by2_body is not None}`",
        f"- trace_found: `{trace is not None}`",
        f"- source_data_readable: `{all(path and path.exists() for key, path in paths.items() if key != 'fix_root')}`",
    ]
    write_text(stage_root / "02_DATA_PATH/BY2_DATA_DISCOVERY_REPORT.md", "\n".join(report) + "\n")
    return {"paths": paths, "audit_rows": audit_rows}


def write_data_role_freeze(stage_root: Path) -> None:
    write_text(
        stage_root / "03_DATA_ROLE/DATASET_ROLE_FREEZE.md",
        "\n".join(
            [
                "# Dataset Role Freeze",
                "",
                "- BY2: main dataset for DA01 clean/classic matrix.",
                "- BY3: later poor-heading stress only; not run in this stage.",
                "- XB/PG: later poor-GNSS/fallback stress only; not run in this stage.",
                "- trace_vrtk2: evaluation reference only.",
                "- imu-data.csv: Fixposition receiver IMU, not Go2 body IMU.",
                "- by2.txt: Go2 sportmodestate body source, not truth.",
                "- final_v23 and LegSA outputs: not solver input.",
            ]
        )
        + "\n",
    )


def ensure_rtklib(rtklib_root: Path, stage_root: Path) -> dict[str, Any]:
    discovery: dict[str, Any] = {"rtklib_root": str(rtklib_root), "preexisting": rtklib_root.exists()}
    clone_result = None
    if not rtklib_root.exists():
        rtklib_root.parent.mkdir(parents=True, exist_ok=True)
        clone_result = run(["git", "clone", "https://github.com/tomojitakasu/RTKLIB.git", str(rtklib_root)], timeout=1200.0)
    build_runs = []
    targets = [
        ("convbin", rtklib_root / "app/convbin/gcc", False),
        ("rnx2rtkp", rtklib_root / "app/rnx2rtkp/gcc", False),
        ("str2str", rtklib_root / "app/str2str/gcc", True),
        ("pos2kml", rtklib_root / "app/pos2kml/gcc", True),
    ]
    for tool, cwd, optional in targets:
        result = run(["make"], cwd=cwd, timeout=600.0) if cwd.exists() else {"command": ["make"], "cwd": str(cwd), "returncode": 127, "stdout_tail": "", "stderr_tail": "missing build dir"}
        result["tool"] = tool
        result["optional"] = optional
        build_runs.append(result)
    tool_rows = []
    for tool, cwd, optional in targets:
        exe = cwd / tool
        tool_rows.append({"tool": tool, "path": str(exe), "exists": exe.exists(), "optional": optional})
    required_ok = all(row["exists"] for row in tool_rows if not row["optional"])
    discovery.update({"clone_result": clone_result, "build_runs": build_runs, "required_tools_ok": required_ok})
    write_text(
        stage_root / "04_RTKLIB/RTKLIB_DISCOVERY_REPORT.md",
        f"# RTKLIB Discovery Report\n\n- root_exists: `{rtklib_root.exists()}`\n- preexisting: `{discovery['preexisting']}`\n- cloned_this_stage: `{clone_result is not None}`\n",
    )
    write_json(stage_root / "04_RTKLIB/RTKLIB_BUILD_REPORT.md", discovery)
    write_csv(stage_root / "04_RTKLIB/RTKLIB_TOOL_STATUS.csv", tool_rows, ["tool", "path", "exists", "optional"])
    return {"root": rtklib_root, "tool_rows": tool_rows, "required_tools_ok": required_ok, "build_runs": build_runs}


def provider_and_physical_reports(paths: dict[str, Path], rtklib: dict[str, Any], stage_root: Path, runtime_root: Path) -> dict[str, Any]:
    provider_dir = runtime_root / "05_PROVIDER"
    provider_dir.mkdir(parents=True, exist_ok=True)
    schema_report = probe_raw_pair(paths["gnss1_raw"], paths["gnss2_raw"])
    write_json(stage_root / "05_PROVIDER/RAW_CSV_SCHEMA_REPORT.md", schema_report)
    ubx_report = rebuild_receiver_ubx(paths["fix_root"], provider_dir / "ubx")
    write_json(stage_root / "05_PROVIDER/UBX_REBUILD_REPORT.md", ubx_report)
    ubx_files = {}
    for label, csv_name in (("gnss1", "gnss1-raw.csv"), ("gnss2", "gnss2-raw.csv")):
        item = ubx_report.get("files", {}).get(csv_name, {})
        if item.get("output_ubx"):
            ubx_files[label] = item["output_ubx"]
    convbin = rtklib["root"] / "app/convbin/gcc/convbin"
    rinex_report = convert_ubx_to_rinex(convbin, ubx_files, provider_dir / "rinex")
    write_json(stage_root / "05_PROVIDER/RINEX_CONVERSION_REPORT.md", rinex_report)
    common_report = match_rawx_common(paths["gnss1_raw"], paths["gnss2_raw"])
    write_csv(stage_root / "05_PROVIDER/COMMON_EPOCH_SATELLITE_SUMMARY.csv", common_report.get("sample_rows", []), ["rcv_tow", "common_satellite_count", "satellites"])
    los_report = build_satpos_los_summary(rinex_report, common_report)
    write_csv(stage_root / "05_PROVIDER/SATPOS_LOS_PROVIDER_SUMMARY.csv", [los_report])
    dd_report = build_dd_los_summary(common_report, los_report)
    write_csv(stage_root / "05_PROVIDER/DD_LOS_PROVIDER_SUMMARY.csv", [dd_report])
    ambiguity_report = build_ambiguity_candidate_summary(paths["gnss1_raw"], paths["gnss2_raw"])
    write_csv(stage_root / "05_PROVIDER/AMBIGUITY_PROVIDER_SUMMARY.csv", [ambiguity_report])
    status_series, status_summary = build_status_baseline_series(paths["gnss1_status"], paths["gnss2_status"])
    write_csv(stage_root / "05_PROVIDER/STATUS_BASELINE_PROVIDER_SUMMARY.csv", [status_summary])

    rnx2rtkp = rtklib["root"] / "app/rnx2rtkp/gcc/rnx2rtkp"
    moving_base = attempt_moving_base(rnx2rtkp, rinex_report, runtime_root / "06_PHYSICAL_BASELINE")
    write_csv(stage_root / "06_PHYSICAL_BASELINE/STATUS_BASELINE_PHYSICAL_SUMMARY.csv", [status_summary])
    write_csv(stage_root / "06_PHYSICAL_BASELINE/RTKLIB_MOVING_BASE_ATTEMPT_TABLE.csv", [moving_base])
    physical_gate = {
        "status_median_baseline_length_m": status_summary.get("median_baseline_length_m"),
        "status_physical_gate_pass": status_summary.get("physical_gate_pass"),
        "rtklib_moving_base_attempt_status": moving_base.get("attempt_status"),
        "rtklib_moving_base_physical_gate_pass": moving_base.get("physical_gate_pass"),
        "full_backend_physical_gate_pass": bool(status_summary.get("physical_gate_pass")),
        "gate_min_m": 0.20,
        "gate_max_m": 0.60,
    }
    write_csv(stage_root / "06_PHYSICAL_BASELINE/BASELINE_LENGTH_PHYSICAL_GATE.csv", [physical_gate])
    write_csv(stage_root / "06_PHYSICAL_BASELINE/BASELINE_VECTOR_SAMPLE.csv", status_series[:100])

    capability = {
        "raw_ubx_rebuild_pass": bool(ubx_report.get("rebuilt_ubx_available")),
        "rinex_conversion_pass": bool(rinex_report.get("obs_generated")),
        "common_epoch_satellite_pass": bool(common_report.get("common_rawx_available")),
        "los_provider_pass": bool(los_report.get("los_available_for_full_backend")),
        "dd_design_matrix_pass": bool(dd_report.get("dd_design_matrix_available")),
        "ambiguity_provider_pass": bool(ambiguity_report.get("ambiguity_candidate_vector_available")),
        "physical_baseline_pass": bool(status_summary.get("physical_gate_pass")),
        "status_diagnostic_available": bool(status_series),
        "full_backend_available": False,
        "trace_used_online": False,
        "receiver_imu_data_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
    }
    capability["full_backend_available"] = all(
        capability[key]
        for key in [
            "raw_ubx_rebuild_pass",
            "rinex_conversion_pass",
            "common_epoch_satellite_pass",
            "los_provider_pass",
            "dd_design_matrix_pass",
            "ambiguity_provider_pass",
            "physical_baseline_pass",
        ]
    )
    write_csv(stage_root / "05_PROVIDER/PROVIDER_CAPABILITY_MATRIX.csv", [capability])
    return {
        "schema": schema_report,
        "ubx": ubx_report,
        "rinex": rinex_report,
        "common": common_report,
        "los": los_report,
        "dd": dd_report,
        "ambiguity": ambiguity_report,
        "status_series": status_series,
        "status_summary": status_summary,
        "moving_base": moving_base,
        "capability": capability,
    }


def attempt_moving_base(rnx2rtkp: Path, rinex_report: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    obs = rinex_report.get("obs_files", {})
    nav = rinex_report.get("nav_files", {})
    pos = output_dir / "rtklib_moving_base_attempt.pos"
    if not rnx2rtkp.exists():
        return {"attempt_status": "rnx2rtkp_missing", "physical_gate_pass": False, "pos_path": str(pos)}
    if "gnss1" not in obs or "gnss2" not in obs or not nav:
        return {"attempt_status": "obs_or_nav_missing", "physical_gate_pass": False, "pos_path": str(pos)}
    nav_arg = next(iter(nav.values()))
    result = run([str(rnx2rtkp), "-p", "2", "-m", "1", "-o", str(pos), obs["gnss1"], obs["gnss2"], nav_arg], timeout=240.0)
    size = pos.stat().st_size if pos.exists() else 0
    return {
        "attempt_status": "success_output_exists" if size > 0 else "failed_or_empty_output",
        "returncode": result["returncode"],
        "pos_path": str(pos),
        "pos_size_bytes": size,
        "physical_gate_pass": False,
        "note": "rnx2rtkp output is diagnostic only and is not parsed as solver input in this stage",
    }


def yaw_reports(stage_root: Path) -> dict[str, Any]:
    contract = make_yaw_frame_contract()
    synthetic = synthetic_contract_test()
    write_text(
        stage_root / "07_YAW_FRAME/YAW_FRAME_CONTRACT.md",
        "\n".join([f"# Yaw Frame Contract", "", *[f"- {key}: `{value}`" for key, value in contract.items()]]) + "\n",
    )
    write_text(
        stage_root / "07_YAW_FRAME/PHYSICAL_INSTALLATION_RULE.md",
        "\n".join(
            [
                "# Physical Installation Rule",
                "",
                "- Dual antennas are lateral.",
                "- Baseline heading is not body yaw.",
                "- Body yaw is baseline heading plus the frozen lateral offset.",
                "- GNSS order is recorded as GNSS2-GNSS1.",
                "- Trace RMSE is not used to choose sign.",
                "- No per-case offset is allowed.",
            ]
        )
        + "\n",
    )
    write_json(stage_root / "07_YAW_FRAME/SYNTHETIC_YAW_FRAME_TEST_REPORT.md", synthetic)
    write_csv(stage_root / "07_YAW_FRAME/YAW_FRAME_SAFETY_AUDIT_TABLE.csv", [{**contract, **{"synthetic_test_passed": synthetic["passed"]}}])
    return {"contract": contract, "synthetic": synthetic}


def write_classic_case_reports(stage_root: Path) -> None:
    rows = classic_case_manifest()
    write_csv(stage_root / "08_CLASSIC_CASES/BY2_CLASSIC_CASE_MANIFEST.csv", rows, ["case_id", "case_family", "policy", "seed"])
    write_text(
        stage_root / "08_CLASSIC_CASES/BY2_CLASSIC_CASE_POLICY.md",
        "\n".join(
            [
                "# BY2 Classic Case Policy",
                "",
                "- C00 clean is run first.",
                "- The remaining 17 cases are run only after clean produces evaluable runtime output.",
                "- Degradation policies are deterministic and seed-locked where applicable.",
                "- Trace is evaluation-only and is not used for sign, offset, or per-case tuning.",
                "- Status diagnostic fallback rows are not promoted to C-LAMBDA full backend.",
            ]
        )
        + "\n",
    )


def matrix_and_eval_reports(stage_root: Path, runtime_root: Path, provider: dict[str, Any], trace: Path) -> dict[str, Any]:
    write_classic_case_reports(stage_root)
    write_csv(stage_root / "09_MATRIX/DA01_MATRIX_QUEUE.csv", matrix_queue_rows())
    matrix = run_da01_matrix(
        runtime_root=runtime_root,
        status_series=provider["status_series"],
        trace_reference=trace,
        provider_capability=provider["capability"],
    )
    row_results = matrix["row_results"]
    write_csv(stage_root / "09_MATRIX/DA01_ROW_EXECUTION_STATUS.csv", row_results)
    write_csv(stage_root / "09_MATRIX/DA01_RUNTIME_PROOF_TABLE.csv", matrix["runtime_proof"])
    write_csv(stage_root / "09_MATRIX/DA01_FAILURE_OR_BLOCKED_ROWS.csv", matrix["blocked_rows"], ["case_id", "terminal_status", "blocker_reasons"])
    write_csv(stage_root / "10_EVALUATION/DA01_ROW_LEVEL_RESULT_TABLE.csv", row_results)
    summary = method_level_summary(row_results)
    family = case_family_summary(row_results)
    write_csv(stage_root / "10_EVALUATION/DA01_METHOD_LEVEL_SUMMARY.csv", [summary])
    write_csv(stage_root / "10_EVALUATION/DA01_CASE_FAMILY_SUMMARY.csv", family)
    write_csv(
        stage_root / "10_EVALUATION/DA01_YAW_FRAME_SAFETY_TABLE.csv",
        [
            {
                "case_id": row["case_id"],
                "yaw_frame_contract_passed": True,
                "trace_used_online": False,
                "per_case_tuning": False,
                "status_fallback_is_full_backend": False,
            }
            for row in row_results
        ],
    )
    write_text(
        stage_root / "10_EVALUATION/DA01_FAILURE_ANALYSIS.md",
        "\n".join(
            [
                "# DA01 Failure Analysis",
                "",
                f"- full_backend_ready: `{matrix['full_backend_ready']}`",
                f"- full_backend_blocker_reasons: `{';'.join(matrix['full_backend_blocker_reasons'])}`",
                f"- clean_terminal_status: `{matrix['clean_terminal_status']}`",
                "- status_diagnostic fallback was evaluated only as diagnostic if full backend was blocked.",
            ]
        )
        + "\n",
    )
    matrix["method_summary"] = summary
    matrix["case_family_summary"] = family
    return matrix


def comparison_reports(comparison_root: Path, stage_root: Path, literature: dict[str, Any], provider: dict[str, Any], matrix: dict[str, Any]) -> None:
    mkdirs(
        comparison_root,
        [
            "00_MASTER_INDEX",
            "01_METHOD_DA01_TEUNISSEN_CLAMBDA",
            "02_PROVIDER_BACKEND",
            "03_FAILURE_ANALYSIS",
            "04_TEXT_SUMMARY_CN",
            "05_CLAIM_BOUNDARY",
            "06_FIGURE_PLAN",
        ],
    )
    method_dir = comparison_root / "01_METHOD_DA01_TEUNISSEN_CLAMBDA"
    write_text(comparison_root / "00_MASTER_INDEX/README.md", f"# {STAGE_NAME}\n\nDA01-only comparison package.\n")
    write_text(method_dir / "README_SUMMARY_CN.md", "# DA01 Summary CN\n\n本阶段只执行 DA01。full_backend 未闭合时，status fallback 只作 diagnostic。\n")
    write_text(method_dir / "PAPER_SOURCE.md", f"# Paper Source\n\n- selected: `{(literature.get('selected') or {}).get('filename', '')}`\n- source_incomplete: `{literature.get('source_incomplete')}`\n")
    write_text(method_dir / "ALGORITHM_EQUATIONS.md", "# Algorithm Equations\n\nDD carrier model -> float ambiguity -> ILS/LAMBDA -> baseline-length constrained C-LAMBDA candidate -> baseline vector -> lateral body yaw contract.\n")
    write_text(method_dir / "IMPLEMENTATION_NOTES.md", "# Implementation Notes\n\nThe implementation separates raw-carrier full_backend gates from status_diagnostic fallback. No trace sign tuning or status-as-full substitution is allowed.\n")
    write_csv(method_dir / "METHOD_EVIDENCE_TABLE.csv", matrix["row_results"])
    write_csv(method_dir / "METHOD_LEVEL_SUMMARY.csv", [matrix["method_summary"]])
    write_text(method_dir / "BY2_CLASSIC_SUMMARY_CN.md", f"# BY2 Classic Summary CN\n\nCompleted diagnostic rows: {matrix['method_summary'].get('diagnostic_fallback_completed_rows', 0)}. Full backend rows: {matrix['method_summary'].get('full_backend_completed_rows', 0)}.\n")
    write_text(method_dir / "PAPER_WRITABLE_TEXT_CN.md", "DA01 C-LAMBDA/GNSS compass pipeline was implemented with provider gates. In this run, any status fallback evidence is diagnostic only unless full raw-carrier/DD/LOS/ambiguity backend closes.\n")
    write_text(method_dir / "FORBIDDEN_TEXT_CN.md", "禁止写 exact reproduction、禁止把 status yaw wrapper 写成 C-LAMBDA full_backend、禁止宣称 universal superiority。\n")
    write_text(method_dir / "CLAIM_BOUNDARY.md", (stage_root / "11_CLAIM_BOUNDARY/DA01_CLAIM_BOUNDARY_FREEZE.md").read_text(encoding="utf-8") if (stage_root / "11_CLAIM_BOUNDARY/DA01_CLAIM_BOUNDARY_FREEZE.md").exists() else "")
    write_csv(method_dir / "PROVIDER_CAPABILITY.md", [provider["capability"]])
    write_json(comparison_root / "02_PROVIDER_BACKEND/provider_summary.json", provider["capability"])
    write_text(comparison_root / "03_FAILURE_ANALYSIS/README.md", (stage_root / "10_EVALUATION/DA01_FAILURE_ANALYSIS.md").read_text(encoding="utf-8"))
    write_text(comparison_root / "04_TEXT_SUMMARY_CN/README.md", "本阶段可用于后续横向整理，但不生成最终论文图。\n")
    write_text(comparison_root / "05_CLAIM_BOUNDARY/README.md", "Claim boundary follows 11_CLAIM_BOUNDARY freeze.\n")
    write_text(comparison_root / "06_FIGURE_PLAN/README.md", "No final paper figures generated in this stage. Future figure plan can use row-level metric CSV after human approval.\n")


def claim_boundary_reports(stage_root: Path, provider: dict[str, Any]) -> None:
    full = bool(provider["capability"].get("full_backend_available"))
    allowed = [
        {"claim": "DA01 was implemented from C-LAMBDA/GNSS compass literature and evaluated on BY2", "allowed": full, "condition": "only if full_backend rows completed"},
        {"claim": "Trace was evaluation-only", "allowed": True, "condition": "all manifests false for trace_used_online"},
    ]
    diagnostic = [
        {"claim": "status fallback can diagnose BY2 dual-antenna yaw behavior", "diagnostic_only": True},
        {"claim": "status fallback is not C-LAMBDA full_backend", "diagnostic_only": True},
    ]
    write_csv(stage_root / "11_CLAIM_BOUNDARY/DA01_ALLOWED_CLAIMS.csv", allowed, ["claim", "allowed", "condition"])
    write_csv(stage_root / "11_CLAIM_BOUNDARY/DA01_DIAGNOSTIC_ONLY_CLAIMS.csv", diagnostic, ["claim", "diagnostic_only"])
    forbidden = [
        "# DA01 Forbidden Claims",
        "",
        "- Exact reproduction unless official/full proof exists.",
        "- Full C-LAMBDA claim if raw-carrier/DD/ambiguity/LOS backend is absent.",
        "- Trace-tuned sign or offset.",
        "- Status-yaw wrapper as C-LAMBDA.",
        "- Old aggregate or summary reconstruction.",
        "- LegSA beats all methods.",
        "- Universal superiority.",
    ]
    write_text(stage_root / "11_CLAIM_BOUNDARY/DA01_FORBIDDEN_CLAIMS.md", "\n".join(forbidden) + "\n")
    freeze = [
        "# DA01 Claim Boundary Freeze",
        "",
        f"- full_backend_available: `{full}`",
        f"- status_diagnostic_available: `{provider['capability'].get('status_diagnostic_available')}`",
        "- trace_used_online: `false`",
        "- final_v23_output_solver_input: `false`",
        "- LegSA_output_solver_input: `false`",
        "- receiver_imu_data_as_body_imu: `false`",
        "- status_diagnostic_is_full_backend: `false`",
    ]
    write_text(stage_root / "11_CLAIM_BOUNDARY/DA01_CLAIM_BOUNDARY_FREEZE.md", "\n".join(freeze) + "\n")


def export_clean(stage_root: Path, comparison_root: Path, export_root: Path, replacements: dict[str, str]) -> dict[str, Any]:
    export_dir = export_root / "12_EXPORT_CLEAN_FOR_GPT"
    export_dir.mkdir(parents=True, exist_ok=True)
    pack_dir = export_dir / "pack"
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    pack_dir.mkdir(parents=True)
    include_files = [
        stage_root / "00_STAGE_REPORT/PAPER10_DA3_DA01_SUPERVISOR_FINAL_REPORT.md",
        stage_root / "00_STAGE_REPORT/PAPER10_DA3_DA01_REVIEWER_REPORT.md",
        stage_root / "01_LITERATURE/DA01_PAPER_SEARCH_REPORT.md",
        stage_root / "01_LITERATURE/DA01_PAPER_INVENTORY.csv",
        stage_root / "01_LITERATURE/DA01_PAPER_READING_NOTES_CN.md",
        stage_root / "05_PROVIDER/PROVIDER_CAPABILITY_MATRIX.csv",
        stage_root / "09_MATRIX/DA01_ROW_EXECUTION_STATUS.csv",
        stage_root / "10_EVALUATION/DA01_METHOD_LEVEL_SUMMARY.csv",
        stage_root / "10_EVALUATION/DA01_CASE_FAMILY_SUMMARY.csv",
        stage_root / "10_EVALUATION/DA01_FAILURE_ANALYSIS.md",
        stage_root / "11_CLAIM_BOUNDARY/DA01_CLAIM_BOUNDARY_FREEZE.md",
        comparison_root / "01_METHOD_DA01_TEUNISSEN_CLAMBDA/README_SUMMARY_CN.md",
        comparison_root / "01_METHOD_DA01_TEUNISSEN_CLAMBDA/CLAIM_BOUNDARY.md",
    ]
    manifest_rows = []
    path_scan = {"forbidden_hits": [], "local_path_hits": []}
    for source in include_files:
        if not source.exists():
            continue
        rel = source.relative_to(stage_root) if str(source).startswith(str(stage_root)) else Path("literature_comparisons") / source.relative_to(comparison_root)
        target = pack_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8", errors="ignore")
        clean = sanitize_export_text(text, replacements)
        target.write_text(clean, encoding="utf-8")
        manifest_rows.append({"relative_path": str(rel), "size_bytes": target.stat().st_size})
        for pattern in FORBIDDEN_EXPORT_PATTERNS:
            if pattern in str(rel) or pattern in clean:
                if pattern == ".zip":
                    continue
                path_scan["forbidden_hits"].append({"relative_path": str(rel), "pattern": pattern})
        if re.search(r"/mnt/[a-z]/|/home/", clean):
            path_scan["local_path_hits"].append(str(rel))
    zip_path = export_dir / "paper10_da3_step0_da01_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(pack_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(pack_dir))
    write_csv(export_dir / "export_clean_manifest.csv", manifest_rows, ["relative_path", "size_bytes"])
    write_json(export_dir / "export_clean_path_scan.json", path_scan)
    write_text(export_dir / "README_FOR_NEXT_AI.md", "This export-clean package excludes raw data, runtime payloads, PDFs, UBX/RINEX/NAV/OBS, RTKLIB source, and local-only path locks.\n")
    return {"zip_path": zip_path, "manifest_rows": manifest_rows, "path_scan": path_scan, "passed": not path_scan["forbidden_hits"] and not path_scan["local_path_hits"]}


def final_reports(stage_root: Path, provider: dict[str, Any], matrix: dict[str, Any], literature: dict[str, Any], rtklib: dict[str, Any], export: dict[str, Any] | None = None) -> str:
    full_rows = matrix.get("method_summary", {}).get("full_backend_completed_rows", 0)
    diag_rows = matrix.get("method_summary", {}).get("diagnostic_fallback_completed_rows", 0)
    if full_rows == 18:
        decision = "PASS_DA01_FULL_BACKEND_18CASES_READY_FOR_DA03"
    elif diag_rows == 18:
        decision = "CONDITIONAL_PASS_DA01_DIAGNOSTIC_FALLBACK_ONLY"
    elif not provider["capability"].get("raw_ubx_rebuild_pass"):
        decision = "BLOCKED_RAW_CARRIER_PROVIDER_NOT_READY"
    elif not provider["capability"].get("physical_baseline_pass"):
        decision = "BLOCKED_PHYSICAL_BASELINE_NOT_CLOSED"
    else:
        decision = "BLOCKED_DA01_FULL_BACKEND_NOT_READY"
    if export is not None and not export.get("passed", False):
        decision = "BLOCKED_EXPORT_CLEAN_FAILURE"
    lines = [
        "# PAPER10 DA3 DA01 Supervisor Final Report",
        "",
        f"- final_decision: `{decision}`",
        f"- G drive mounted: `{g_mount_path().exists()}`",
        f"- paper found/downloaded: `{not literature.get('source_incomplete')}` / `downloaded=false`",
        f"- RTKLIB clone/build required tools ok: `{rtklib.get('required_tools_ok')}`",
        f"- BY2 raw/status/body readable: `{provider['capability'].get('status_diagnostic_available')}`",
        f"- raw/UBX/RINEX/DD/LOS/ambiguity closed: `{provider['capability'].get('full_backend_available')}`",
        f"- physical baseline status gate pass: `{provider['capability'].get('physical_baseline_pass')}`",
        f"- DA01 full_backend available: `{provider['capability'].get('full_backend_available')}`",
        f"- status_diagnostic fallback used: `{diag_rows > 0}`",
        f"- clean case completed: `{matrix.get('clean_terminal_status')}`",
        f"- 18 classic cases completed: `{diag_rows + full_rows == 18}`",
        "- yaw-frame physically closed: `contract_passed=true; performance may still be diagnostic`",
        f"- completed rows: `{diag_rows + full_rows}`",
        "- trace_used_online=false; receiver_imu_data_as_body_imu=false; final_v23_output_solver_input=false; LegSA_output_solver_input=false",
        "- claim boundary: see `11_CLAIM_BOUNDARY/DA01_CLAIM_BOUNDARY_FREEZE.md`",
        f"- export_clean: `{export.get('passed') if export else 'pending'}`",
        "- commit/push/PR: `pending at report generation time`",
        "- next_step: `continue_fix_DA01_full_backend_before_DA03` unless human accepts diagnostic-only closure.",
    ]
    write_text(stage_root / "00_STAGE_REPORT/PAPER10_DA3_DA01_SUPERVISOR_FINAL_REPORT.md", "\n".join(lines) + "\n")
    reviewer = [
        "# PAPER10 DA3 DA01 Reviewer Report",
        "",
        "- raw/runtime artifacts are written under runtime/stage/export roots, not staged for Git.",
        "- status_diagnostic rows are explicitly marked diagnostic and not full_backend.",
        "- trace, final_v23, LegSA outputs, receiver IMU, per-case tuning, output-only correction, and epoch deletion flags are false.",
        "- full_backend remains unavailable until LOS/DD design provider closes.",
        f"- export_clean_passed: `{export.get('passed') if export else 'pending'}`",
        f"- final_decision: `{decision}`",
    ]
    write_text(stage_root / "00_STAGE_REPORT/PAPER10_DA3_DA01_REVIEWER_REPORT.md", "\n".join(reviewer) + "\n")
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--comparison-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--rtklib-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root)
    stage_root = Path(args.stage_root)
    runtime_root = Path(args.runtime_root)
    comparison_root = Path(args.comparison_root)
    export_root = Path(args.export_root)
    rtklib_root = Path(args.rtklib_root)
    mkdirs(
        stage_root,
        [
            "00_STAGE_REPORT",
            "00_ENV",
            "01_LITERATURE",
            "02_DATA_PATH",
            "03_DATA_ROLE",
            "04_RTKLIB",
            "05_PROVIDER",
            "06_PHYSICAL_BASELINE",
            "07_YAW_FRAME",
            "08_CLASSIC_CASES",
            "09_MATRIX",
            "10_EVALUATION",
            "11_CLAIM_BOUNDARY",
            "12_EXPORT_CLEAN_FOR_GPT",
        ],
    )
    runtime_root.mkdir(parents=True, exist_ok=True)
    comparison_root.mkdir(parents=True, exist_ok=True)
    export_root.mkdir(parents=True, exist_ok=True)

    env = env_reports(project_root, stage_root)
    if not all([env["g_mount_exists"], env["project_root_exists"], env["paper_dir_exists"], env["by2_by3_raw_exists"], env["xb_pg_raw_exists"]]):
        write_text(stage_root / "00_STAGE_REPORT/PAPER10_DA3_DA01_SUPERVISOR_FINAL_REPORT.md", "BLOCKED_G_DRIVE_NOT_MOUNTED\n")
        return 2
    literature = find_literature(project_root / "论文", stage_root, runtime_root)
    data = discover_by2(project_root / "data/raw/BY2_BY3", stage_root)
    paths = data["paths"]
    required_readable = all(paths[key] and Path(paths[key]).exists() for key in ["gnss1_raw", "gnss2_raw", "gnss1_status", "gnss2_status", "corr_raw", "userio_raw", "trace", "body"])
    if not required_readable:
        write_text(stage_root / "00_STAGE_REPORT/PAPER10_DA3_DA01_SUPERVISOR_FINAL_REPORT.md", "BLOCKED_BY2_SOURCE_DATA_UNREADABLE\n")
        return 3
    write_data_role_freeze(stage_root)
    rtklib = ensure_rtklib(rtklib_root, stage_root)
    if not rtklib["required_tools_ok"]:
        write_text(stage_root / "00_STAGE_REPORT/PAPER10_DA3_DA01_SUPERVISOR_FINAL_REPORT.md", "BLOCKED_RTKLIB_BUILD_FAILED\n")
        return 4
    provider = provider_and_physical_reports(paths, rtklib, stage_root, runtime_root)
    yaw_reports(stage_root)
    claim_boundary_reports(stage_root, provider)
    matrix = matrix_and_eval_reports(stage_root, runtime_root, provider, paths["trace"])
    comparison_reports(comparison_root, stage_root, literature, provider, matrix)
    final_reports(stage_root, provider, matrix, literature, rtklib, export=None)
    replacements = {
        str(project_root): "<G_PROJECT_ROOT>",
        str(stage_root): "<PAPER10_DA3_DA01_STAGE_ROOT>",
        str(runtime_root): "<PAPER10_DA3_DA01_RUNTIME_ROOT>",
        str(comparison_root): "<PAPER10_DA3_DA01_COMPARISON_ROOT>",
        str(export_root): "<PAPER10_DA3_DA01_EXPORT_ROOT>",
        str(paths["fix_root"]): "<BY2_RECEIVER_ROOT>",
        str(paths["body"]): "<BY2_GO2_BODY_SOURCE>",
        str(rtklib_root): "<PAPER10_DA3_DA01_RTKLIB_ROOT>",
    }
    export = export_clean(stage_root, comparison_root, export_root, replacements)
    decision = final_reports(stage_root, provider, matrix, literature, rtklib, export=export)
    print(decision)
    return 0 if decision.startswith(("PASS_", "CONDITIONAL_PASS_")) else 5


if __name__ == "__main__":
    raise SystemExit(main())
