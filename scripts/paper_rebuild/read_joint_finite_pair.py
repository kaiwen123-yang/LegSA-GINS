#!/usr/bin/env python3
"""Read one completed fixed/automatic U3 pair; never run or revise navigation.

The six intervals are declared here before inspecting the automatic result.
Only causal emitted rows and their existing offline error series are scored.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from run_support_carrier_joint import json_value, read_rows, series_metrics


SYNTHETIC_SOURCE = "src/legsa_gins/paper_rebuild/joint_navigation/synthetic.py"
INTERVALS = {"whole": (0., 90.), "pre_slip_65_67": (65., 67.),
             "slip_67_70": (67., 70.), "after_slip_70_77": (70., 77.),
             "recovery_77_90": (77., 90.), "pv_gap_65_77": (65., 77.)}
ERRORS = ("position_3d_m", "velocity_3d_mps", "yaw_deg")
REQUIRED = ("navigation.csv", "metrics.json", "decisions.json",
            "offline_error_series.npz", "estimator_summary.json")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def root_status(path):
    root = path.parent if path.name == "U3" else path
    status_path = root / "run_status.json"
    status = read_json(status_path) if status_path.is_file() else {}
    missing = [str(root / "U3" / name) for name in REQUIRED
               if not (root / "U3" / name).is_file()]
    if not (root / "input_timeline.csv").is_file():
        missing.append(str(root / "input_timeline.csv"))
    return root, status, dict(root=str(root), run_status=status.get("status", "MISSING"),
        completed_modes=status.get("completed_modes", []), missing_files=missing,
        complete=(status.get("status") == "COMPLETED"
                  and "U3" in status.get("completed_modes", []) and not missing))


def runs_of_values(times, values):
    """Consecutive observed-row runs, with no inferred transition between rows."""
    result = []
    for index, (time, value) in enumerate(zip(times, values)):
        if not result or value != result[-1]["value"]:
            if result:
                result[-1]["next_change_at_s"] = float(time)
            result.append(dict(first_sample_s=float(time), last_sample_s=float(time),
                               rows=1, value=value, next_change_at_s=None))
        else:
            result[-1]["last_sample_s"] = float(time)
            result[-1]["rows"] += 1
    return result


def history_readout(rows, decisions, summary):
    times = [row["time_s"] for row in rows]
    expansions = [item for item in decisions
                  if item.get("kind") == "NONLINEAR_CONDITIONAL_HISTORY_EXPANDED"]
    switches = [item for item in decisions
                if item.get("kind") == "COMMON_LINEARIZATION_REFERENCE_CHANGED"]
    by_identity = {}
    for item in expansions:
        by_identity.setdefault(item["support_identity"], []).append(item)
    policies, selected_repair = [], []
    for row in rows:
        descriptor = row.get("selected_support_policy", {})
        source_policy = descriptor.get("source_policy", [])
        identity = row.get("selected_support_model")
        matched = [item for item in by_identity.get(identity, [])
                   if item["time_s"] <= row["time_s"]
                   and item.get("source_policy") == source_policy]
        repaired = (identity not in (None, "fixed")
                    and any(item.get("mode") == "finite_common_motion" for item in source_policy)
                    and row.get("conditional_history_recomputed") is True and bool(matched))
        selected_repair.append(repaired)
        policies.append(dict(selected_support_model=identity,
                             selected_support_policy=descriptor,
                             selected_expanded_finite_history=repaired))
    fixed_support = [None if "supported_contact_models" not in row
                     else "fixed" in row["supported_contact_models"] for row in rows]
    selected_times = [t for t, selected in zip(times, selected_repair) if selected]
    support_decisions = [{key: item.get(key) for key in (
        "time_s", "selected", "supported_models", "selected_source_policy",
        "fixed_contact_in_support", "fixed_minus_best_score", "working_edit_cost",
        "working_support_delta", "comparison_scope")}
        for item in decisions if item.get("kind") == "CONTACT_MODEL_PREDICTIVE_SUPPORT"]
    return dict(
        selected_policy_runs=runs_of_values(times, policies),
        selected_expanded_finite_history_rows=len(selected_times),
        first_selected_expanded_finite_history_s=selected_times[0] if selected_times else None,
        selected_expanded_finite_history_in_pv_gap_rows=sum(65 <= t <= 77 for t in selected_times),
        conditional_history_recomputed_rows=sum(row.get("conditional_history_recomputed") is True for row in rows),
        fixed_contact_published_support_runs=runs_of_values(times, fixed_support),
        first_fixed_excluded_in_published_support_s=next(
            (t for t, supported in zip(times, fixed_support) if supported is False), None),
        predictive_support_decisions=support_decisions,
        predictive_support_decision_selected_is="SCORE_WINNER_NOT_NECESSARILY_PUBLISHED_POLICY",
        nonlinear_conditional_history_expansions=expansions,
        common_linearization_reference_changes=switches,
        legacy_revocation=dict(
            emitted_revocation_rows=sum(row.get("revocation") is True for row in rows),
            emitted_replay_performed_rows=sum(row.get("replay_performed") is True for row in rows),
            emitted_revoked_support_ids=sorted({arc for row in rows for arc in row.get("revoked_support_ids", [])}),
            summary={key: summary.get(key) for key in ("replayed_events", "revoked_arcs",
                "support_model_replayed_events", "nonlinear_support_expansions", "linearization_reference_switches")}),
        direction_status_counts=dict(Counter(row["direction_status"] for row in rows)),
        interpretation="Expansion, reference switching, legacy revocation, and actual published policy selection are distinct events.")


def read_run(root, status):
    rows = read_rows(root / "U3/navigation.csv")
    metrics = read_json(root / "U3/metrics.json")
    decisions = read_json(root / "U3/decisions.json")
    summary = read_json(root / "U3/estimator_summary.json")
    with (root / "input_timeline.csv").open(encoding="utf-8", newline="") as file:
        timeline = np.array([float(row["time_s"]) for row in csv.DictReader(file)])
    times = np.array([row["time_s"] for row in rows])
    with np.load(root / "U3/offline_error_series.npz", allow_pickle=False) as archive:
        series_times = archive["time_s"].copy()
        errors = {key: archive[key].copy() for key in ERRORS}
        saved_states = {key: archive[key].copy() for key in ("p", "v", "rpy_rad")}
    aligned = np.array_equal(times, series_times)
    state_alignment = aligned and all(np.array_equal(
        np.asarray([row[key] for row in rows]), saved_states[key], equal_nan=True)
        for key in saved_states)
    time_coverage = np.array_equal(times, timeline)
    finite_states = int(sum(np.all(np.isfinite(np.concatenate(
        [row["p"], row["v"], row["rpy_rad"]]))) for row in rows))
    if len(series_times) > 1:
        adjacent = (np.searchsorted(timeline, series_times[1:], side="left")
                    - np.searchsorted(timeline, series_times[:-1], side="right")) == 0
    else:
        adjacent = np.empty(0, dtype=bool)
    interval_metrics = {name: {key: series_metrics(series_times, errors[key], interval, adjacent)
                              for key in ERRORS} for name, interval in INTERVALS.items()}
    source_saved = digest(root / "SOURCE_SNAPSHOT" / SYNTHETIC_SOURCE)
    source_declared = status.get("source_sha256", {}).get(SYNTHETIC_SOURCE)
    coverage = dict(navigation_rows=len(rows), input_event_rows=len(timeline),
        error_series_rows=len(series_times), finite_state_rows=finite_states,
        all_errors_finite=all(np.all(np.isfinite(value)) for value in errors.values()),
        navigation_matches_error_series_times=aligned,
        navigation_matches_error_series_states=state_alignment,
        navigation_matches_all_input_times=time_coverage,
        strictly_increasing_times=bool(len(times) > 1 and np.all(np.diff(times) > 0)),
        first_sample_s=float(times[0]) if len(times) else None,
        last_sample_s=float(times[-1]) if len(times) else None,
        saved_metrics_coverage=metrics.get("coverage"))
    coverage["complete_1287_rows_0_90"] = bool(
        len(rows) == len(timeline) == len(series_times) == finite_states == 1287
        and aligned and state_alignment and time_coverage and coverage["all_errors_finite"]
        and coverage["strictly_increasing_times"] and times[0] == 0 and times[-1] == 90)
    return dict(root=str(root), git_commit=status.get("git_commit"),
        support_monitoring=status.get("support_monitoring"),
        support_motion_model=summary.get("support_motion_model"),
        scenario_kind=status.get("scenario_kind"),
        source_identity=dict(seed=status.get("seed"), duration_s=status.get("duration_s"),
            synthetic_declared_sha256=source_declared, synthetic_snapshot_sha256=source_saved,
            snapshot_matches_declared=source_saved is not None and source_saved == source_declared,
            input_timeline_sha256=digest(root / "input_timeline.csv")),
        coverage=coverage, evaluation=metrics.get("evaluation"),
        runtime_wall_s=metrics.get("runtime_wall_s"), interval_metrics=interval_metrics,
        history=history_readout(rows, decisions, summary)), times


def number(value):
    return "未得出" if value is None else f"{value:.6f}"


def markdown(report):
    lines = ["# M1 有限共同运动完整配对读出", "", f"状态：`{report['status']}`。", "",
        "只评价已保存的因果发布行；无重跑、无历史输出替换、无新参数选择。"]
    if report["status"] == "INCOMPLETE_INPUTS":
        for label, item in report["inputs"].items():
            lines.append(f"\n- {label}：{item['run_status']}；U3 完成={item['complete']}；缺少文件={len(item['missing_files'])}。")
        lines.append("\n自动或固定运行尚未完成，未计算配对收益；没有轮询或启动导航。")
        return "\n".join(lines) + "\n"
    lines += ["", f"同源及完整共同时间轴合格：{report['paired_evidence_qualified']}。",
              "", "| 区间 s | p3 固定 → 自动 / m | v3 固定 → 自动 / m/s | yaw 固定 → 自动 / deg | 共同有限时长 s |",
              "|---|---:|---:|---:|---:|"]
    for name, bounds in INTERVALS.items():
        cells = []
        for key in ERRORS:
            fixed = report["fixed"]["interval_metrics"][name][key]
            automatic = report["automatic"]["interval_metrics"][name][key]
            cells.append(f"{number(fixed['time_weighted_rmse'])} → {number(automatic['time_weighted_rmse'])}")
        durations = [report[label]["interval_metrics"][name][key]["finite_pair_duration_s"]
                     for label in ("fixed", "automatic") for key in ERRORS]
        duration = number(durations[0]) if len(set(durations)) == 1 else "不一致，见 JSON"
        lines.append(f"| {name} ({bounds[0]:g}–{bounds[1]:g}) | " + " | ".join(cells) + f" | {duration} |")
    lines += ["", "区间采用现有 series_metrics 的闭区间样本与相邻有限段梯形时间权重；不插值到端点、不填补缺口。"]
    for label in ("fixed", "automatic"):
        item, history = report[label], report[label]["history"]
        legacy = history["legacy_revocation"]
        lines += ["", f"- {label}：发布/有限状态={item['coverage']['navigation_rows']}/{item['coverage']['finite_state_rows']}；"
            f"conditional_history_recomputed={history['conditional_history_recomputed_rows']} 行；"
            f"非线性展开={len(history['nonlinear_conditional_history_expansions'])} 次；"
            f"参考切换={len(history['common_linearization_reference_changes'])} 次。",
            f"- {label}：实际选择已展开的有限运动历史={history['selected_expanded_finite_history_rows']} 行，"
            f"首次={number(history['first_selected_expanded_finite_history_s'])} s，"
            f"65–77 s 内={history['selected_expanded_finite_history_in_pv_gap_rows']} 行；"
            f"固定解释首次不在发布支持内={number(history['first_fixed_excluded_in_published_support_s'])} s。",
            f"- {label}：旧 revocation/replay_performed 行计数="
            f"{legacy['emitted_revocation_rows']}/{legacy['emitted_replay_performed_rows']}。"]
    lines += ["", "实际 selected_support_policy 的完整分段、固定解释进出支持、展开事件和参考切换事件均保存在 JSON。"
        "预测支持决策中的 selected 是分数赢家，不能替代发布行的实际选择。",
        "", f"M1 必要条件：65–77 s 的 p3、v3 都改善={report['m1_necessary_conditions']['gap_position_and_velocity_improve']}；"
        f"自动实际选择已非线性展开的有限运动历史={report['m1_necessary_conditions']['automatic_selected_repaired_history']}。",
        "", "该判定仅覆盖这一个配对的 M1 必要条件，不宣称三个创新完成，也不单凭 p/v 或状态变化宣称航向造成导航收益。"]
    if not report["paired_evidence_qualified"]:
        lines += ["", "配对资格未满足，数值仅作单次结果读出；逐项原因见 JSON 的 identity_checks 和 coverage。"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed-root", type=Path, required=True)
    parser.add_argument("--automatic-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    fixed_root, fixed_status, fixed_input = root_status(args.fixed_root)
    automatic_root, automatic_status, automatic_input = root_status(args.automatic_root)
    report = dict(status="INCOMPLETE_INPUTS", inputs=dict(fixed=fixed_input, automatic=automatic_input),
        declared_intervals_s=INTERVALS, complete_research_goal=False,
        three_innovations_complete=False, navigation_run_performed=False,
        reference_access="EXISTING_OFFLINE_ERROR_SERIES_ONLY")
    if fixed_input["complete"] and automatic_input["complete"]:
        fixed, fixed_times = read_run(fixed_root, fixed_status)
        automatic, automatic_times = read_run(automatic_root, automatic_status)
        a, b = fixed["source_identity"], automatic["source_identity"]
        identity_checks = dict(
            same_seed=a["seed"] is not None and a["seed"] == b["seed"],
            both_duration_90_s=a["duration_s"] == b["duration_s"] == 90,
            same_synthetic_generator=a["snapshot_matches_declared"] and b["snapshot_matches_declared"]
                and a["synthetic_snapshot_sha256"] == b["synthetic_snapshot_sha256"],
            same_input_timeline=a["input_timeline_sha256"] == b["input_timeline_sha256"],
            same_published_times=np.array_equal(fixed_times, automatic_times),
            fixed_monitoring_disabled=fixed["support_monitoring"] is False,
            automatic_monitoring_enabled=automatic["support_monitoring"] is True,
            both_synthetic=all(s.get("data_mode") == "synthetic" for s in (fixed_status, automatic_status)),
            both_u3=all("U3" in s.get("completed_modes", []) for s in (fixed_status, automatic_status)))
        qualified = all(identity_checks.values()) and all(
            item["coverage"]["complete_1287_rows_0_90"] for item in (fixed, automatic))
        gap = [item["interval_metrics"]["pv_gap_65_77"] for item in (fixed, automatic)]
        improves = all(gap[0][key]["time_weighted_rmse"] is not None
            and gap[1][key]["time_weighted_rmse"] is not None
            and gap[1][key]["time_weighted_rmse"] < gap[0][key]["time_weighted_rmse"] for key in ERRORS[:2])
        selected = automatic["history"]["selected_expanded_finite_history_rows"] > 0
        report.update(fixed=fixed, automatic=automatic, identity_checks=identity_checks,
            paired_evidence_qualified=qualified,
            m1_necessary_conditions=dict(gap_position_and_velocity_improve=improves,
                automatic_selected_repaired_history=selected,
                selected_repaired_history_during_gap=automatic["history"]["selected_expanded_finite_history_in_pv_gap_rows"] > 0,
                met=qualified and improves and selected),
            status=("UNQUALIFIED_PAIR" if not qualified else
                    "M1_NECESSARY_CONDITIONS_MET" if improves and selected else "M1_NECESSARY_CONDITIONS_NOT_MET"))
    report = json_value(report)
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "M1_FINITE_PAIR.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    (args.output_root / "M1_FINITE_PAIR.md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps(dict(status=report["status"], output_root=str(args.output_root)), ensure_ascii=False))


if __name__ == "__main__":
    main()
