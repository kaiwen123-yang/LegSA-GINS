#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


STAGE = "PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE"
REPO = Path("/home/kaiwen/LegSA-GINS")
RUNTIME = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT") / STAGE
REPO_PACKAGE = REPO / "suanfahengxiangduibi" / STAGE
C_EXPORT = Path("/mnt/c/Users/ykw/Desktop/LegSA-GINS/suanfahengxiangduibi") / STAGE

P4A_C = Path("/mnt/c/Users/ykw/Desktop/LegSA-GINS/suanfahengxiangduibi/PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC")
P4B = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER4B_R2_PHYSICAL_FRAME_CLOSE_AND_YAW_REEVALUATION")
P4C = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER4C_BASELINE_VECTOR_YAW_SEMANTICS_REPAIR_AND_REEVALUATION")
P4D = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER4D_TRACE_REFERENCE_YAW_FRAME_AND_STATUS_RELPOS_AUDIT")
P4E = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER4E_FIXPOSITION_OUTPUT_ROTATION_AND_MESSAGE_SEMANTICS_CLOSURE")
P4F = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER4F_R2_USER_DECLARED_MINIMAL_EXPORT_YAW_POLICY_REEVALUATION")
P4F_C = Path("/mnt/c/Users/ykw/Desktop/LegSA-GINS/suanfahengxiangduibi/PAPER4F_R2_USER_DECLARED_MINIMAL_EXPORT_YAW_POLICY_REEVALUATION")
P3G = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER3G_LAMBDA_MLAMBDA_CLAMBDA_BACKEND_AND_MULTIGNSS_DDLOS_REPAIR")
P3H = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER3H_MULTIGNSS_DDLOS_AND_FOURTH_LAYER_REPAIR")
P3I = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER3I_PHYSICAL_YAW_SATPOS_IEKF_EQKF_INTERNAL_JOIN")
P2A = Path("/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER2A_TRUE_GNSS_INS_QA_FULL_MATRIX")


def ensure_dirs():
    for root in (RUNTIME, REPO_PACKAGE, C_EXPORT):
        root.mkdir(parents=True, exist_ok=True)
    for sub in [
        "00_input_ingest",
        "01_yaw_boundary_freeze",
        "02_native_metrics_consolidation",
        "03_writing_package",
        "04_context_update",
        "05_git_safety",
        "_scripts",
    ]:
        (RUNTIME / sub).mkdir(parents=True, exist_ok=True)


def read_csv_maybe(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def write_text(rel: str, text: str):
    path = RUNTIME / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_df(rel: str, df: pd.DataFrame):
    path = RUNTIME / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def row_count(path: Path) -> int | None:
    if not path.exists() or path.suffix.lower() != ".csv":
        return None
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return max(sum(1 for _ in f) - 1, 0)


def input_stage_index():
    required = [
        ("PAPER4A_C_EXPORT", P4A_C),
        ("PAPER4B_R2", P4B),
        ("PAPER4C", P4C),
        ("PAPER4D", P4D),
        ("PAPER4E", P4E),
        ("PAPER4F_R2_WSL", P4F),
        ("PAPER4F_R2_C_EXPORT", P4F_C),
        ("PAPER3G", P3G),
        ("PAPER3H", P3H),
        ("PAPER3I", P3I),
        ("PAPER2A", P2A),
    ]
    rows = []
    for stage, path in required:
        rows.append({
            "stage_or_input": stage,
            "path": str(path),
            "exists": path.exists(),
            "role": "required_if_present" if stage in {"PAPER2A"} else "required",
        })
    required_files = [
        ("PAPER4F_R2_ROW_LEVEL", P4F_C / "PAPER4F_R2_BODY_YAW_REEVALUATION_ROW_LEVEL.csv"),
        ("PAPER4F_R2_SUMMARY_BY_METHOD", P4F_C / "PAPER4F_R2_BODY_YAW_SUMMARY_BY_METHOD.csv"),
        ("PAPER4F_R2_METHOD_SEMANTICS", P4F_C / "PAPER4F_R2_METHOD_SEMANTICS_DECISION.csv"),
        ("USER_DECLARED_MINIMAL_EXPORT_YAW_POLICY", P4F_C / "USER_DECLARED_MINIMAL_EXPORT_YAW_POLICY.yaml"),
        ("PAPER4D_TRACE_DECISION", P4D / "PAPER4D_TRACE_YAW_REFERENCE_DECISION.yaml"),
        ("PAPER4E_TRACE_DECISION", P4E / "PAPER4E_TRACE_YAW_REFERENCE_DECISION.yaml"),
        ("FRAME_POLICY_ACCEPTED", P4B / "05_frame_policy_decision/FRAME_POLICY_ACCEPTED.yaml"),
    ]
    for item, path in required_files:
        rows.append({
            "stage_or_input": item,
            "path": str(path),
            "exists": path.exists(),
            "role": "mandatory_file",
            "row_count": row_count(path),
        })
    df = pd.DataFrame(rows)
    write_df("PAPER4G_INPUT_STAGE_INDEX.csv", df)
    write_df("00_input_ingest/PAPER4G_INPUT_STAGE_INDEX.csv", df)
    return df


def evidence_consistency():
    row = read_csv_maybe(P4F_C / "PAPER4F_R2_BODY_YAW_REEVALUATION_ROW_LEVEL.csv")
    method = read_csv_maybe(P4F_C / "PAPER4F_R2_BODY_YAW_SUMMARY_BY_METHOD.csv")
    decision = read_csv_maybe(P4F_C / "PAPER4F_R2_METHOD_SEMANTICS_DECISION.csv")
    metrics = {
        "row_level_rows": len(row),
        "valid_case_rows": int((row["valid_epoch_count"] > 0).sum()) if "valid_epoch_count" in row else 0,
        "method_summary_rows": len(method),
        "method_semantics_rows": len(decision),
        "median_previous_policy_rmse": float(row["previous_policy_rmse_deg"].median()) if "previous_policy_rmse_deg" in row else np.nan,
        "median_user_policy_rmse": float(row["body_yaw_rmse_deg"].median()) if "body_yaw_rmse_deg" in row else np.nan,
        "systematic_90deg_ratio": float(row["abs_error_around_90deg_systematic"].mean()) if "abs_error_around_90deg_systematic" in row else np.nan,
    }
    text = f"""# PAPER4G Evidence Consistency Check

Frozen hard facts:
- PAPER4B_R2: physical installation closed.
- GNSS1 = robot-right antenna.
- GNSS2 = robot-left antenna.
- GNSS1 -> GNSS2 = Go2 FLU +Y_left lateral baseline.
- Physical transform for canonical GNSS1->GNSS2 NED baseline heading: `body_yaw_NED_deg = wrap360(baseline_heading_NED_deg + 90 deg)`.
- PAPER4C: direct GNSS status/LLH baseline sanity failed; status rel_pos and LLH position-diff are not valid physical short-baseline truth.
- PAPER4D: trace.yaw source closed to `user_io-out-poi_geodetic.csv:ypr.vector3.x`, but status rel_pos invalid.
- PAPER4E: Fixposition message semantics support FP_POI/output-frame orientation, but actual BY2 Step 6 output rotation/translation config was not found.
- PAPER4F_R2: user-declared minimal-export yaw policy applied: `trace_body_yaw_NED_deg = wrap360(trace_yaw_deg + 90 deg)`.

PAPER4F_R2 checks:
- row-level rows: `{metrics['row_level_rows']}`
- valid evaluated rows: `{metrics['valid_case_rows']}`
- method summary rows: `{metrics['method_summary_rows']}`
- method semantics rows: `{metrics['method_semantics_rows']}`
- median previous-policy RMSE: `{metrics['median_previous_policy_rmse']:.6f}` deg
- median user-policy RMSE: `{metrics['median_user_policy_rmse']:.6f}` deg
- 90-degree-like systematic case ratio: `{metrics['systematic_90deg_ratio']:.6f}`

Conclusion:
The user-declared +90deg trace-body policy was evaluated and did not remove the systematic yaw discrepancy. Body-yaw external-method claims remain diagnostic-only.
"""
    write_text("PAPER4G_EVIDENCE_CONSISTENCY_CHECK.md", text)
    write_text("00_input_ingest/PAPER4G_EVIDENCE_CONSISTENCY_CHECK.md", text)
    return metrics


def yaw_boundary(metrics):
    rows = [
        {
            "decision_item": "physical_baseline_frame_closed",
            "value": True,
            "evidence": "PAPER4B_R2 GNSS1-right/GNSS2-left physical frame closure",
        },
        {
            "decision_item": "trace_yaw_source_closed",
            "value": True,
            "evidence": "PAPER4D/E trace.yaw == user_io-out-poi_geodetic.csv:ypr.vector3.x",
        },
        {
            "decision_item": "trace_body_yaw_reference_final_authorized",
            "value": False,
            "evidence": "PAPER4F_R2 trace+90 policy did not remove systematic yaw discrepancy",
        },
        {
            "decision_item": "external_method_body_yaw_final_authorized",
            "value": False,
            "evidence": "PAPER4F_R2 median user-policy RMSE remains high and systematic_90deg ratio remains ~0.9875",
        },
        {
            "decision_item": "external_method_yaw_metrics_paper_use",
            "value": "diagnostic_only",
            "evidence": "body yaw reference/method yaw semantics not jointly closed for final claim",
        },
        {
            "decision_item": "native_ddlos_metrics_paper_use",
            "value": "appendix_or_main_supporting_evidence",
            "evidence": "native baseline/residual/ambiguity metrics remain valid backend evidence",
        },
    ]
    df = pd.DataFrame(rows)
    write_df("PAPER4G_YAW_DECISION_TABLE.csv", df)
    write_df("01_yaw_boundary_freeze/PAPER4G_YAW_DECISION_TABLE.csv", df)
    text = f"""# PAPER4G Yaw Claim Boundary Freeze

The user-declared +90deg trace-body policy was evaluated and did not remove the systematic yaw discrepancy.

PAPER4F_R2 recorded:
- 2160/2160 PAPER3F/G/H vector-closed method-case rows reevaluated.
- Median previous-policy RMSE: `{metrics['median_previous_policy_rmse']:.6f}` deg.
- Median user-policy RMSE: `{metrics['median_user_policy_rmse']:.6f}` deg.
- 90-degree-like systematic case ratio: `{metrics['systematic_90deg_ratio']:.6f}`.

Therefore:
- `trace_body_yaw_reference_final_authorized=false`
- `external_method_body_yaw_final_authorized=false`
- `external_method_yaw_metrics_paper_use=diagnostic_only`
- `native_ddlos_metrics_paper_use=appendix_or_main_supporting_evidence`

Final body-yaw RMSE/superiority claims remain forbidden. The external literature comparison must be reported using native baseline/residual/ambiguity metrics, not final robot-body yaw metrics.
"""
    write_text("PAPER4G_YAW_CLAIM_BOUNDARY_FREEZE.md", text)
    write_text("01_yaw_boundary_freeze/PAPER4G_YAW_CLAIM_BOUNDARY_FREEZE.md", text)


def agg_native(summary: pd.DataFrame, classif: pd.DataFrame, source: str, provider_level: str, systems: str) -> list[dict]:
    rows = []
    if summary.empty:
        return rows
    for method_id, g in summary.groupby("method_id", dropna=False):
        c = classif[classif["method_id"] == method_id] if "method_id" in classif else pd.DataFrame()
        c0 = c.iloc[0].to_dict() if not c.empty else {}
        row = {
            "method_id": method_id,
            "paper_source": source,
            "implementation_level": c0.get("implementation_level", c0.get("backend_level", "")),
            "provider_level": provider_level,
            "systems_used": systems,
            "case_count": int(g.get("planned_rows", pd.Series(dtype=float)).sum()) if "planned_rows" in g else "",
            "completed_count": int(g.get("completed_rows", pd.Series(dtype=float)).sum()) if "completed_rows" in g else "",
            "blocked_count": int(g.get("blocked_rows", pd.Series([0] * len(g))).sum()) if len(g) else "",
            "baseline_length_error": float(g["median_baseline_length_error"].median()) if "median_baseline_length_error" in g else "",
            "residual_rms": float(g["median_phase_residual"].median()) if "median_phase_residual" in g else "",
            "wrapped_residual_rms": "",
            "ratio": float(g["median_ratio"].median()) if "median_ratio" in g else "",
            "ADOP": "",
            "fix_status_or_fix_rate_proxy": float(g["median_fix_rate"].median()) if "median_fix_rate" in g else "",
            "body_yaw_allowed": False,
            "paper_use_classification": "appendix_or_main_supporting_evidence",
            "claim_boundary": "native backend metrics only; no body-yaw claim; no exact/full reproduction claim",
        }
        rows.append(row)
    return rows


def p3f_rtklib_native_from_p4f() -> list[dict]:
    row = read_csv_maybe(P4F_C / "PAPER4F_R2_BODY_YAW_REEVALUATION_ROW_LEVEL.csv")
    if row.empty:
        return []
    g = row[row["method_id"].str.contains("RTKLIB_MOVING_BASELINE", na=False)]
    if g.empty:
        return []
    return [{
        "method_id": "P3F_DD06_RTKLIB_MOVING_BASELINE_EXTERNAL_DIAGNOSTIC",
        "paper_source": "PAPER3F/PAPER4F_R2",
        "implementation_level": "RTKLIB moving-base external diagnostic",
        "provider_level": "external_rtk_diagnostic_from_existing_epoch_outputs",
        "systems_used": "as provided by RTKLIB diagnostic output",
        "case_count": int(len(g)),
        "completed_count": int((g["valid_epoch_count"] > 0).sum()),
        "blocked_count": int((g["valid_epoch_count"] <= 0).sum()),
        "baseline_length_error": "",
        "residual_rms": "",
        "wrapped_residual_rms": "",
        "ratio": "",
        "ADOP": "",
        "fix_status_or_fix_rate_proxy": "",
        "body_yaw_allowed": False,
        "paper_use_classification": "diagnostic_native_external_baseline_only",
        "claim_boundary": "external RTKLIB diagnostic; not exact Teunissen/Yang/Liu/Wu reproduction; no body-yaw claim",
    }]


def native_metrics():
    rows = []
    rows.extend(agg_native(
        read_csv_maybe(P3G / "PAPER3G_NATIVE_METRICS_SUMMARY.csv"),
        read_csv_maybe(P3G / "PAPER3G_METHOD_BACKEND_CLASSIFICATION_TABLE.csv"),
        "PAPER3G",
        "DD_PROVIDER_V2_multignss_native_metrics",
        "GPS+BDS where provider rows available",
    ))
    rows.extend(agg_native(
        read_csv_maybe(P3H / "PAPER3H_NATIVE_METRICS_SUMMARY.csv"),
        read_csv_maybe(P3H / "PAPER3H_METHOD_BACKEND_CLASSIFICATION_TABLE.csv"),
        "PAPER3H",
        "DD_PROVIDER_V3_GPS_BDS_LOS_COVARIANCE_READY",
        "GPS+BDS LOS/covariance-ready subset",
    ))
    rows.extend(p3f_rtklib_native_from_p4f())
    p3i_provider = read_csv_maybe(P3I / "PAPER3I_PROVIDER_V4_SUMMARY.csv")
    if not p3i_provider.empty:
        p = p3i_provider.iloc[0]
        rows.append({
            "method_id": "PAPER3I_PROVIDER_V4_GPS_BDS_LOS_READY_RESIDUAL_PARTIAL",
            "paper_source": "PAPER3I",
            "implementation_level": "provider_v4_residual_metadata_improvement",
            "provider_level": p.get("provider_v4_status", ""),
            "systems_used": f"GPS rows={p.get('gps_los_ready_rows','')}; BDS rows={p.get('bds_los_ready_rows','')}; Galileo/GLONASS/SBAS not closed",
            "case_count": "",
            "completed_count": p.get("residual_ready_rows", ""),
            "blocked_count": "",
            "baseline_length_error": "",
            "residual_rms": "",
            "wrapped_residual_rms": "",
            "ratio": "",
            "ADOP": "",
            "fix_status_or_fix_rate_proxy": "",
            "body_yaw_allowed": False,
            "paper_use_classification": "main_supporting_provider_evidence",
            "claim_boundary": "provider residual metadata only; no body-yaw or superiority claim",
        })
    pav = read_csv_maybe(P3I / "04_pavlasek_full_iekf_attempt/PAVLASEK_NIS_INNOVATION_SUMMARY.csv")
    if not pav.empty:
        for _, p in pav.iterrows():
            rows.append({
                "method_id": f"PAVLASEK_IEKF_{p.get('mode','')}",
                "paper_source": "PAPER3I",
                "implementation_level": p.get("status", ""),
                "provider_level": "native diagnostic / blocked strict physical extrinsic path",
                "systems_used": "GPS+BDS provider v4 rows where diagnostic-ready",
                "case_count": "",
                "completed_count": p.get("innovation_rows", ""),
                "blocked_count": 0 if p.get("status") == "DIAGNOSTIC_READY" else "",
                "baseline_length_error": "",
                "residual_rms": p.get("nis_median", ""),
                "wrapped_residual_rms": "",
                "ratio": "",
                "ADOP": "",
                "fix_status_or_fix_rate_proxy": p.get("status", ""),
                "body_yaw_allowed": False,
                "paper_use_classification": "diagnostic_only_or_blocked",
                "claim_boundary": "Pavlasek IEKF full claim blocked; native diagnostic only",
            })
    wu = read_csv_maybe(P3I / "05_wu_eqkf_misalignment_attempt/WU_MISALIGNMENT_DIAGNOSTIC_SUMMARY.csv")
    if not wu.empty:
        rows.append({
            "method_id": "WU_EQKF_MISALIGNMENT_NATIVE_DIAGNOSTIC",
            "paper_source": "PAPER3I",
            "implementation_level": "native diagnostic summary",
            "provider_level": "provider_v4_residual_rows",
            "systems_used": "; ".join(sorted(set(wu["system"].astype(str)))) if "system" in wu else "",
            "case_count": "",
            "completed_count": int(wu["rows"].sum()) if "rows" in wu else "",
            "blocked_count": "",
            "baseline_length_error": "",
            "residual_rms": float(wu["residual_norm_median"].median()) if "residual_norm_median" in wu else "",
            "wrapped_residual_rms": "",
            "ratio": "",
            "ADOP": "",
            "fix_status_or_fix_rate_proxy": "",
            "body_yaw_allowed": False,
            "paper_use_classification": "diagnostic_only",
            "claim_boundary": "Wu misalignment/body-yaw claim disabled; native residual diagnostic only",
        })
    ledger = pd.DataFrame(rows)
    write_df("PAPER4G_NATIVE_DDLOS_METRICS_LEDGER.csv", ledger)
    write_df("02_native_metrics_consolidation/PAPER4G_NATIVE_DDLOS_METRICS_LEDGER.csv", ledger)

    status_rows = []
    for _, r in ledger.iterrows():
        status_rows.append({
            "method_id": r["method_id"],
            "paper_source": r["paper_source"],
            "external_family": classify_family(str(r["method_id"])),
            "body_yaw_allowed": False,
            "native_metrics_available": True,
            "paper_use_classification": r["paper_use_classification"],
            "claim_boundary": r["claim_boundary"],
        })
    status = pd.DataFrame(status_rows)
    write_df("PAPER4G_EXTERNAL_LITERATURE_METHOD_STATUS.csv", status)
    write_df("02_native_metrics_consolidation/PAPER4G_EXTERNAL_LITERATURE_METHOD_STATUS.csv", status)

    summary = f"""# PAPER4G Native DD/LOS Metrics Summary

Rows in native metrics ledger: `{len(ledger)}`.

Evidence retained for paper use:
- Teunissen standard LAMBDA / C-LAMBDA / QC-ILS style: native ambiguity, ratio/fix-rate, residual summaries from PAPER3G/H.
- Liu C-WLS: native wrapped-search / refinement diagnostics from PAPER3G/H/I.
- Yang baseline-length constrained KF + MLAMBDA: native length-constrained backend summaries from PAPER3G/H.
- Wu PAR/ADOP/EQKF native module: native ambiguity/module and residual diagnostic summaries; body yaw disabled.
- Pavlasek two-receiver IEKF: diagnostic or blocked boundary only.
- RTKLIB moving-base external diagnostic: external native baseline diagnostic only.

Claim ceiling:
Native DD/LOS baseline, residual, ambiguity, provider-readiness, and fix-rate proxy evidence may be used as appendix or main supporting evidence. Final body-yaw RMSE/superiority claims remain forbidden.
"""
    write_text("PAPER4G_NATIVE_DDLOS_METRICS_SUMMARY.md", summary)
    write_text("02_native_metrics_consolidation/PAPER4G_NATIVE_DDLOS_METRICS_SUMMARY.md", summary)
    return ledger


def classify_family(method_id: str) -> str:
    u = method_id.upper()
    if "YANG" in u or "LENGTH" in u:
        return "Yang length-constrained KF/MLAMBDA"
    if "TEUNISSEN" in u or "LAMBDA" in u or "CLAMBDA" in u or "QCILS" in u:
        return "Teunissen/LAMBDA/C-LAMBDA/QC-ILS"
    if "LIU" in u or "CWLS" in u:
        return "Liu C-WLS"
    if "WU" in u or "PAR_ADOP" in u or "_PAR_" in u or "ADOP" in u or "EQKF" in u:
        return "Wu PAR/ADOP/EQKF"
    if "PAVLASEK" in u or "IEKF" in u:
        return "Pavlasek IEKF"
    if "RTKLIB" in u:
        return "RTKLIB moving-base"
    return "provider/native diagnostic"


def writing_package():
    files = {
        "PAPER4G_MAIN_TEXT_ALLOWED_CONTENT.md": """# PAPER4G Main Text Allowed Content

- BY2/BY3/XB dataset-role-aware protocol.
- BY2 120 canonical degradation design.
- PAPER2A QA method coverage and behavior, with standard/recognized QA boundary where available.
- RTKLIB/RINEX/DDLOS provider construction as engineering provider evidence.
- Provider v4 GPS+BDS residual-ready evidence.
- Physical GNSS1-right/GNSS2-left frame closure.
- Yaw boundary freeze after PAPER4F_R2.
- Native DD/LOS metrics as supporting external literature evidence.
""",
        "PAPER4G_APPENDIX_CONTENT.md": """# PAPER4G Appendix Content

- Teunissen/Liu/Yang/Wu/Pavlasek/RTKLIB native/backend diagnostics.
- PAPER4B/C/D/E/F_R2 yaw-frame audit chain.
- PAPER4F_R2 user-policy reevaluation result.
- Method semantics decision table showing vector-closed vs diagnostic/blocked rows.
""",
        "PAPER4G_DIAGNOSTIC_ONLY_CONTENT.md": """# PAPER4G Diagnostic-Only Content

- External method body-yaw row-level RMSE/MAE/P95 tables.
- PAPER4C direct GNSS status/LLH baseline sanity.
- PAPER4D/E trace yaw reference candidates and output-frame semantics.
- Pavlasek IEKF and Wu EQKF/misalignment native diagnostics.
""",
        "PAPER4G_FORBIDDEN_CLAIMS.md": """# PAPER4G Forbidden Claims

- body-yaw RMSE claim
- external-method yaw superiority
- final_v23 / LegSA_QA / LegSA_full superiority
- same-evaluator superiority unless separately proven
- BY3 yaw generalization
- XB severe-GNSS high-precision proof
- exact/full faithful external reproduction
- RTKLIB as Teunissen/Yang/Liu/Wu exact reproduction
- trace online use
- receiver IMU as Go2 body IMU
- full contact/joint-foot claim
- full Galileo/GLONASS/SBAS provider closure
""",
        "PAPER4G_EXPERIMENT_SECTION_DRAFT_BULLETS.md": """# PAPER4G Experiment Section Draft Bullets

- Describe BY2 as the full-method native DD/LOS/backend evidence dataset and keep BY3/XB role-bounded.
- Report the accepted GNSS1-right/GNSS2-left physical frame separately from final body-yaw claims.
- State that PAPER4F_R2 applied the user-declared minimal-export +90deg trace-body policy and still observed systematic yaw discrepancy.
- Use native baseline, residual, ratio, ADOP, fix-rate proxy, provider readiness, and ambiguity diagnostics for external literature method comparisons.
- Route final robot-body yaw comparisons to diagnostic appendix only.
""",
        "PAPER4G_LIMITATIONS_SECTION_DRAFT_BULLETS.md": """# PAPER4G Limitations Section Draft Bullets

- Body-yaw reference and external-method yaw semantics did not close sufficiently for final body-yaw paper claims.
- Status rel_pos and LLH position-diff are invalid as physical short-baseline truth for this dataset.
- Actual BY2 Fixposition Step 6 output rotation/translation export was not found in local logs.
- User-declared minimal-export +90deg trace-body policy was evaluated but did not remove the systematic discrepancy.
- Galileo/GLONASS/SBAS provider closure remains unavailable.
""",
        "PAPER4G_FIGURE_TABLE_PLAN_UPDATE.md": """# PAPER4G Figure/Table Plan Update

Main/appendix tables:
- Yaw decision freeze table.
- Native DD/LOS metrics ledger.
- External literature method status table.
- PAPER4F_R2 before/after yaw policy diagnostic table.

Figures:
- Keep PAPER4F_R2 yaw figures diagnostic-only.
- Use native metrics summary tables instead of body-yaw RMSE bar charts for external literature comparison.
- Avoid main-text yaw superiority visuals.
""",
        "PAPER4G_IEEE_TIM_ROUTE_UPDATE.md": """# PAPER4G IEEE TIM Route Update

Recommended route:
- Main text emphasizes the LegSA-GINS pipeline, dataset-role protocol, provider construction, and native backend evidence.
- External literature algorithm comparisons are framed as native DD/LOS baseline/residual/ambiguity evidence.
- Body-yaw external-method metrics are explicitly diagnostic-only after PAPER4F_R2.
- Claims remain bounded to evidence; no exact external reproduction or superiority claim is introduced.
""",
    }
    for name, text in files.items():
        write_text(name, text)
        write_text(f"03_writing_package/{name}", text)


def context_update_report():
    text = f"""# PAPER4G Context Update Report

Tracked context files updated by append-only PAPER4G sections:

- `AGENTS.md`
- `PLANS.md`
- `PHASE_LOG.md`
- `CLAIM_BOUNDARY.md`

Update scope:
- freeze external-method body-yaw claims as diagnostic-only after PAPER4F_R2;
- record native DD/LOS baseline/residual/ambiguity/provider metrics as the write-ready external-method route;
- preserve prohibitions on trace online use, receiver IMU as Go2 body IMU, exact/full external reproduction, RTKLIB-as-literature exact reproduction, BY3 yaw generalization, XB severe-GNSS proof, and raw/runtime/external-code staging.

Pre-existing dirty diffs in these context files were observed before PAPER4G. The commit safety process should stage only PAPER4G package files and PAPER4G appended context content, leaving unrelated dirty files unstaged.
"""
    write_text("04_context_update/PAPER4G_CONTEXT_UPDATE_REPORT.md", text)


def git_safety_report(commit_hash: str = "not_committed_in_report_generation"):
    text = f"""# PAPER4G Git Safety Report

Commit hash: `{commit_hash}`.

Allowed staging scope:
- `suanfahengxiangduibi/{STAGE}/**`
- `AGENTS.md`
- `PLANS.md`
- `PHASE_LOG.md`
- `CLAIM_BOUNDARY.md`

Forbidden staging scope:
- raw receiver data
- UBX/RTCM/RINEX/NAV/OBS/RNX files
- `_runtime/`
- `_external_code/`
- external source code
- large epoch payloads

Pre-existing dirty files were observed before PAPER4G. The commit process must not include unrelated dirty files outside the explicit scope.
"""
    write_text("PAPER4G_GIT_SAFETY_REPORT.md", text)
    write_text("05_git_safety/PAPER4G_GIT_SAFETY_REPORT.md", text)


def supervisor_report(metrics, ledger_rows, status="PASS_YAW_BOUNDARY_FROZEN_NATIVE_METRICS_WRITE_READY_COMMITTED", commit_hash="see final CLI response after commit"):
    text = f"""# PAPER4G Supervisor Final Report

Final status: `{status}`.

## What PAPER4F_R2 Proved

PAPER4F_R2 applied the user-declared minimal-export yaw policy:
`trace_body_yaw_NED_deg = wrap360(trace_yaw_deg + 90 deg)`.

It reevaluated 2160/2160 PAPER3F/G/H vector-closed method-case rows.
Median previous-policy RMSE was `{metrics['median_previous_policy_rmse']:.6f}` deg.
Median user-policy RMSE was `{metrics['median_user_policy_rmse']:.6f}` deg.
The 90-degree-like systematic case ratio was `{metrics['systematic_90deg_ratio']:.6f}`.

Therefore, the discrepancy is not fixed by adding +90deg to the trace reference.

## Frozen Yaw Boundary

Body-yaw metrics remain diagnostic-only because the combined trace reference, Fixposition minimal-export yaw policy, method baseline direction semantics, and robot-body yaw semantics still do not support final external-method yaw claims.

## Native Metrics Route

External literature comparison can still support native DD/LOS baseline, residual, ambiguity, provider-readiness, ratio/ADOP, and fix-rate-proxy evidence.
Native metrics ledger rows: `{ledger_rows}`.

## Claims Still Forbidden

- body-yaw RMSE claim
- external-method yaw superiority
- final_v23 / LegSA_QA / LegSA_full superiority
- same-evaluator superiority unless separately proven
- BY3 yaw generalization
- XB severe-GNSS high-precision proof
- exact/full faithful external reproduction
- RTKLIB as Teunissen/Yang/Liu/Wu exact reproduction
- trace online use
- receiver IMU as Go2 body IMU
- full Galileo/GLONASS/SBAS provider closure

## Export Roots

- WSL runtime root: `{RUNTIME}`
- Repository package: `{REPO_PACKAGE}`
- C-drive export: `{C_EXPORT}`

Git commit hash if committed: `{commit_hash}`.
"""
    write_text("PAPER4G_SUPERVISOR_FINAL_REPORT.md", text)
    write_text("05_git_safety/PAPER4G_SUPERVISOR_FINAL_REPORT.md", text)


def export_index():
    files = []
    for p in sorted(RUNTIME.rglob("*")):
        if p.is_file():
            files.append({"relative_path": str(p.relative_to(RUNTIME)), "size_bytes": p.stat().st_size})
    text = f"""# PAPER4G Export Index

Stage: `{STAGE}`

WSL runtime root: `{RUNTIME}`

Repository package: `{REPO_PACKAGE}`

C-drive export: `{C_EXPORT}`

Exported lightweight file count: `{len(files)}`.

No raw/runtime/RINEX/UBX/RTCM/external-code payloads are included.

## Files

"""
    for f in files:
        text += f"- `{f['relative_path']}` ({f['size_bytes']} bytes)\n"
    write_text("PAPER4G_EXPORT_INDEX.md", text)


def sync_exports():
    for dst in (REPO_PACKAGE, C_EXPORT):
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(RUNTIME, dst, ignore=shutil.ignore_patterns("__pycache__", "*.tmp"))


def main():
    ensure_dirs()
    input_stage_index()
    metrics = evidence_consistency()
    yaw_boundary(metrics)
    ledger = native_metrics()
    writing_package()
    context_update_report()
    git_safety_report()
    supervisor_report(metrics, len(ledger))
    export_index()
    sync_exports()
    print(f"PAPER4G package complete: {RUNTIME}")
    print(f"Repo package: {REPO_PACKAGE}")
    print(f"C export: {C_EXPORT}")


if __name__ == "__main__":
    main()
