#!/usr/bin/env python3
"""Read four sealed BY2O position-product-gap arms; never run solver/evaluator."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
import yaml
from vector_direction_sa_readout import (
    read, pin, checked, rows, emit, table, val, rotations, ecef_and_ned, nearest)

LO = 3278.598000049591
HI = 3310.3980000019073
RECOVERY_END = HI + 20.
FIRST_AFFECTED = 3279.99799990654
ARMS = ("SDK_GAP_FULL_ONLY", "SDK_GAP_PARTIAL",
        "FOOT_GAP_FULL_ONLY", "FOOT_GAP_PARTIAL")
PAIRS = (
    ("GAP_PARTIAL_WITH_SDK", ARMS[0], ARMS[1]),
    ("GAP_PARTIAL_WITH_FOOT_POLICY", ARMS[2], ARMS[3]),
    ("FOOT_POLICY_WITHOUT_GAP_PARTIAL", ARMS[0], ARMS[2]),
    ("FOOT_POLICY_WITH_GAP_PARTIAL", ARMS[1], ARMS[3]),
)
METRIC_KEYS = ("horizontal_rmse_m", "up_rmse_m", "position_3d_rmse_m",
               "yaw_rmse_deg", "horizontal_p99_m", "up_abs_p99_m", "yaw_abs_p99_deg")


def masks(times):
    t = np.asarray(times)
    gap = (t > LO) & (t < HI)
    recovery = (t >= HI) & (t <= RECOVERY_END)
    return {"full_window": np.ones(len(t), bool), "position_product_gap": gap,
            "recovery_20s": recovery, "remaining": ~(gap | recovery)}


def rms(values):
    x = np.asarray(values)
    return float(np.sqrt(np.mean(x*x))) if len(x) and np.isfinite(x).all() else None


def q(values, level):
    x = np.asarray(values)
    return float(np.quantile(x, level)) if len(x) and np.isfinite(x).all() else None


def mean(values):
    x = np.asarray(values)
    return float(np.mean(x)) if len(x) and np.isfinite(x).all() else None


def histogram(data, key):
    return json.dumps(dict(Counter(x[key] for x in data)), sort_keys=True)


def strata_rows(data, timekey):
    times = np.array([val(x, timekey) for x in data])
    return {name: [x for x, selected in zip(data, mask) if selected]
            for name, mask in masks(times).items()}



def source_aware_summary(data, provider_times, arm):
    """Recover carrier time from its unique frozen slot, not its 10-digit CSV print."""
    normalized, remapped = [], []
    for row in data:
        item = dict(row)
        recorded = val(row, "time")
        exact = recorded
        if row["source_id"] == "dual_antenna_yaw":
            candidates = np.flatnonzero(abs(provider_times-recorded) < 1e-6)
            assert len(candidates) == 1
            exact = float(provider_times[candidates[0]])
            original_masks, exact_masks = masks([recorded]), masks([exact])
            if any(original_masks[k][0] != exact_masks[k][0] for k in original_masks):
                remapped.append(dict(arm=arm, source=row["source_id"],
                    serialized_SA_time_s=recorded, exact_provider_time_s=exact,
                    serialized_minus_exact_s=recorded-exact,
                    original_strata="|".join(k for k,v in original_masks.items() if v[0]),
                    corrected_strata="|".join(k for k,v in exact_masks.items() if v[0])))
        item["stratum_source_time"] = str(exact)
        normalized.append(item)
    result = []
    for name, selected in strata_rows(normalized, "stratum_source_time").items():
        for source in sorted(set(row["source_id"] for row in data)):
            subset = [row for row in selected if row["source_id"] == source]
            result.append(dict(arm=arm, stratum=name, source=source,
                actual_SA_evaluations=len(subset),
                accepted=sum(int(val(x,"accepted")) for x in subset),
                rejected=sum(int(val(x,"rejected")) for x in subset),
                median_nis=q([val(x,"nis") for x in subset],.5),
                R_scale_histogram=histogram(subset,"combined_R_scale"),
                reason_histogram=histogram(subset,"reason_codes")))
    return result, remapped


def state_effect(label, dp, dv, drpy, angle, db, dl, times):
    result = []
    for name, mask in masks(times).items():
        row = dict(comparison=label, stratum=name, native_epochs=int(mask.sum()),
                   position_horizontal_rms_m=rms(np.linalg.norm(dp[mask, :2], axis=1)),
                   position_horizontal_p99_m=q(np.linalg.norm(dp[mask, :2], axis=1), .99),
                   position_3d_rms_m=rms(np.linalg.norm(dp[mask], axis=1)),
                   velocity_horizontal_rms_mps=rms(np.linalg.norm(dv[mask, :2], axis=1)),
                   velocity_horizontal_p99_mps=q(np.linalg.norm(dv[mask, :2], axis=1), .99),
                   velocity_3d_rms_mps=rms(np.linalg.norm(dv[mask], axis=1)),
                   attitude_rotation_rms_deg=rms(angle[mask]),
                   gyro_bias_3d_pair_rms_dph=rms(np.linalg.norm(db[mask, :3], axis=1)),
                   accel_bias_3d_pair_rms_mps2=rms(np.linalg.norm(db[mask, 3:6]*1e-5, axis=1)),
                   evaluation_lever_horizontal_pair_rms_m=rms(np.linalg.norm(dl[mask, :2], axis=1)))
        for k, axis in enumerate(("N", "E", "D")):
            row[f"position_{axis}_mean_m"] = mean(dp[mask, k])
            row[f"velocity_{axis}_mean_mps"] = mean(dv[mask, k])
            row[f"velocity_{axis}_rms_mps"] = rms(dv[mask, k])
        for k, axis in enumerate(("roll", "pitch", "yaw")):
            row[f"{axis}_pair_rms_deg"] = rms(drpy[mask, k])
        for k, axis in enumerate(("x", "y", "z")):
            row[f"gyro_bias_{axis}_mean_dph"] = mean(db[mask, k])
            row[f"accel_bias_{axis}_mean_mps2"] = mean(db[mask, k+3]*1e-5)
        result.append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--docs", type=Path, required=True)
    args = parser.parse_args()
    stage = args.stage.resolve()
    plan_path = stage / "PLAN.json"
    plan = read(plan_path)
    assert plan["schema"] == "position_product_gap_local_partial_support.v1"
    assert plan["semisynthetic_data_used"] and not plan["natural_gnss_outage"]
    intervention = plan["local_carrier_intervention"]
    assert intervention["gap_open_interval"] == [LO, HI]
    assert intervention["first_affected_partial_time"] == FIRST_AFFECTED
    seal = read(stage / "ALL_NATIVE_SEALED.json")
    evaluation_seal = read(stage / "EVALUATION_COMPLETE.json")
    plan_sha = pin(plan_path)["sha256"]
    assert seal["plan_sha256"] == plan_sha
    assert evaluation_seal["run_count"] == 4
    sealed_runs = {x["run_id"]: x for x in seal["records"]}
    runs = {run["arm"]: run for run in plan["runs"]}
    assert set(runs) == set(ARMS)
    inputs = [pin(plan_path), pin(stage / "ALL_NATIVE_SEALED.json"),
              pin(stage / "EVALUATION_COMPLETE.json")]

    # Compare only the frozen local carrier ablation, not an entire FULL algorithm.
    providers = {arm: rows(checked(runs[arm]["carrier"])) for arm in ARMS}
    base, partial = providers[ARMS[0]], providers[ARMS[1]]
    assert providers[ARMS[2]] == base and providers[ARMS[3]] == partial
    provider_times = np.array([val(x, "measurement_time") for x in partial])
    assert np.array_equal(provider_times, [val(x, "measurement_time") for x in base])
    changed = np.array([a != b for a, b in zip(base, partial)])
    assert int(changed.sum()) == 30
    assert float(provider_times[changed][0]) == FIRST_AFFECTED
    assert np.all((provider_times[changed] > LO) & (provider_times[changed] < HI))
    assert all(not val(a, "valid") and val(b, "valid")
               for a, b, flag in zip(base, partial, changed) if flag)
    classes = np.array(["GAP_PARTIAL_ADDED" if flag else "COMMON_VALID"
                        if val(b, "valid") else "COMMON_INVALID"
                        for b, flag in zip(partial, changed)])

    def classify(time):
        i = int(nearest(provider_times, [time])[0])
        return str(classes[i]) if abs(provider_times[i]-time) < 1e-6 else "NO_PROVIDER_SLOT"

    arms, metrics, sa_summary, carrier_summary, aids_summary = {}, [], [], [], []
    sa_time_remaps = []
    common_times = None
    for arm in ARMS:
        run = runs[arm]
        config_path = checked(run["config"])
        config = yaml.safe_load(config_path.read_text())
        native = Path(config["outputpath"])
        rid = run["run_id"]
        evaluation = stage / "EVALUATION" / rid / "FROZEN_EVALUATOR"
        evaluation_result_path = evaluation.parent / "EVALUATION_RESULT.json"
        evaluation_result = read(evaluation_result_path)
        assert evaluation_result["row"]["status"] == "COMPLETED"
        assert evaluation_result["row"]["source_nav_sha256"] == sealed_runs[rid]["nav"]["sha256"]
        checked(evaluation_result["error_series"])
        result = read(native / "RESULT.json")
        assert result["status"] == "COMPLETED" and result["online_reference_opens"] == 0
        nav = np.loadtxt(native / "LegSA_PORT_NAV.nav")
        kf = np.loadtxt(native / "KF_GINS_Navresult.nav")
        bias = np.loadtxt(native / "KF_GINS_IMU_ERR.txt")
        std = np.loadtxt(native / "KF_GINS_STD.txt")
        times = kf[:, 1]
        if common_times is None:
            common_times = times
        assert np.array_equal(times, common_times)
        assert np.array_equal(bias[:, 0], times) and np.array_equal(std[:, 0], times)
        assert len(nav) == len(times)
        errors = np.genfromtxt(evaluation / "error_series.csv", delimiter=",",
                              names=True, encoding="utf-8-sig")
        # No interpolation or matched-point removal in the readout.
        assert np.array_equal(errors["time"], times)
        sa = rows(native / "SOURCE_AWARE_WEIGHT_TRACE.csv")
        carrier = rows(native / "BASELINE3D_DIAGNOSTICS.csv")
        body = rows(native / "BODY_VELOCITY_EVENTS.csv")
        foot = rows(native / "SUPPORT_POSE_EVENTS.csv")
        replay_events = rows(native / "SUPPORT_POSE_REPLAY_EVENTS.csv")
        manifest = read(native / "RUN_MANIFEST.json")
        replay = read(native / "SUPPORT_POSE_REPLAY_SUMMARY.json")
        for row in carrier:
            row["provider_class"] = classify(val(row, "measurement_time", val(row, "time")))
        for name, mask in masks(times).items():
            e = errors[mask]
            horizontal, up, yaw = e["horizontal_err_m"], e["err_u_m"], e["yaw_err_deg"]
            metric = dict(arm=arm, stratum=name, native_epochs=int(mask.sum()),
                          evaluation_epochs=len(e), coverage_ratio=len(e)/int(mask.sum()) if mask.any() else None,
                          nonfinite_error_rows=int(sum(~np.isfinite(horizontal+up+yaw))),
                          horizontal_rmse_m=rms(horizontal), up_rmse_m=rms(up),
                          position_3d_rmse_m=rms(e["position_3d_err_m"]),
                          yaw_rmse_deg=rms(yaw), roll_rmse_deg=rms(e["roll_err_deg"]),
                          pitch_rmse_deg=rms(e["pitch_err_deg"]))
            for label, values in (("horizontal", horizontal), ("up_abs", abs(up)),
                                  ("yaw_abs", abs(yaw))):
                unit = "deg" if label == "yaw_abs" else "m"
                for suffix, level in (("p95", .95), ("p99", .99), ("max", 1)):
                    metric[f"{label}_{suffix}_{unit}"] = q(values, level)
            metric.update(last_matched_time_s=float(e["time"][-1]) if len(e) else None,
                          last_horizontal_error_m=float(horizontal[-1]) if len(e) else None,
                          last_up_error_m=float(up[-1]) if len(e) else None,
                          last_yaw_error_deg=float(yaw[-1]) if len(e) else None)
            metrics.append(metric)

        source_counts, time_remaps = source_aware_summary(sa, provider_times, arm)
        sa_summary.extend(source_counts)
        sa_time_remaps.extend(time_remaps)
        for name, selected in strata_rows(carrier, "time").items():
            provider_mask = masks(provider_times)[name]
            for group in ("GAP_PARTIAL_ADDED", "COMMON_VALID", "COMMON_INVALID", "NO_PROVIDER_SLOT"):
                data = [row for row in selected if row["provider_class"] == group]
                carrier_summary.append(dict(arm=arm, stratum=name, provider_class=group,
                    fixed_source_slots=int(sum(provider_mask & (classes == group))),
                    source_valid_slots=sum(int(val(row, "valid")) for row, yes, label
                        in zip(providers[arm], provider_mask, classes) if yes and label == group),
                    diagnostic_rows=len(data), attempted=sum(int(val(x, "attempt")) for x in data),
                    accepted=sum(int(val(x, "accepted")) for x in data),
                    rejected=sum(int(val(x, "rejected")) for x in data),
                    reason_histogram=histogram(data, "reason")))
        foot_strata, body_strata = strata_rows(foot, "event_time_s"), strata_rows(body, "state_time")
        for name in masks(times):
            fs, bs = foot_strata[name], body_strata[name]
            ends = [x for x in fs if x["event_type"] == "END"]
            aids_summary.append(dict(arm=arm, stratum=name,
                foot_event_rows=len(fs), foot_START=sum(x["event_type"] == "START" for x in fs),
                foot_END=len(ends), foot_END_attempted=sum(int(val(x, "attempted")) for x in ends),
                foot_END_accepted=sum(int(val(x, "accepted")) for x in ends),
                foot_RETIRE=sum(x["event_type"] == "RETIRE" for x in fs),
                foot_REVOKE=sum(x["event_type"] == "REVOKE" for x in fs),
                sdk_event_rows=len(bs), sdk_accepted=sum(int(val(x, "accepted")) for x in bs),
                sdk_suppressed=sum(x["reason"] == "SUPPORT_INTERVAL_SDK_REPLACED" for x in bs),
                sdk_reason_histogram=histogram(bs, "reason"),
                foot_reason_histogram=histogram(fs, "reason")))
        arms[arm] = dict(nav=nav, kf=kf, bias=bias, std=std, errors=errors, manifest=manifest,
                         replay=replay, result=result, replay_events=replay_events,
                         evaluator_summary=read(evaluation / "summary.json"))
        inputs.extend([pin(config_path), run["carrier"]])
        for filename in ("LegSA_PORT_NAV.nav", "KF_GINS_Navresult.nav", "KF_GINS_IMU_ERR.txt",
                         "KF_GINS_STD.txt", "BASELINE3D_DIAGNOSTICS.csv", "SOURCE_AWARE_WEIGHT_TRACE.csv",
                         "BODY_VELOCITY_EVENTS.csv", "SUPPORT_POSE_EVENTS.csv",
                         "SUPPORT_POSE_REPLAY_SUMMARY.json", "SUPPORT_POSE_REPLAY_EVENTS.csv",
                         "RUN_MANIFEST.json", "RESULT.json"):
            inputs.append(pin(native / filename))
        inputs.extend([pin(evaluation / "error_series.csv"), pin(evaluation / "summary.json"), pin(evaluation_result_path)])

    # All pair differences use the instantaneous SDK control NED frame via ECEF.
    ref_xyz, ref_axes = ecef_and_ned(arms[ARMS[0]]["nav"])
    lever = np.array(plan["sequences"][0]["evaluation"]["position_lever_frd_m"])
    for arm, data in arms.items():
        n = data["nav"]
        xyz, axes_native = ecef_and_ned(n)
        rotation_native = rotations(n[:, 7:10])
        rotation_ecef = np.einsum("nji,njk->nik", axes_native, rotation_native)
        data["position_common"] = np.einsum("nij,nj->ni", ref_axes, xyz-ref_xyz)
        data["velocity_common"] = np.einsum("nij,nj->ni", ref_axes,
            np.einsum("nji,nj->ni", axes_native, n[:, 4:7]))
        data["rotation_ecef"] = rotation_ecef
        data["lever_common"] = np.einsum("nij,nj->ni", ref_axes,
            np.einsum("nij,j->ni", rotation_ecef, lever))

    effects, boundary_rows, prefixes, deltas = [], [], [], []
    scalar = {(row["arm"], row["stratum"]): row for row in metrics}
    pair_vectors = {}
    for label, control, treatment in PAIRS:
        a, b = arms[control], arms[treatment]
        dp, dv = b["position_common"]-a["position_common"], b["velocity_common"]-a["velocity_common"]
        drpy = (b["nav"][:, 7:10]-a["nav"][:, 7:10]+180) % 360-180
        relative = np.einsum("nji,njk->nik", a["rotation_ecef"], b["rotation_ecef"])
        angle = np.rad2deg(np.arccos(np.clip((np.trace(relative, axis1=1, axis2=2)-1)/2, -1, 1)))
        db, dl = b["bias"][:, 1:]-a["bias"][:, 1:], b["lever_common"]-a["lever_common"]
        pair_vectors[label] = dict(dp=dp, dv=dv, drpy=drpy, db=db, dl=dl)
        effects += state_effect(label, dp, dv, drpy, angle, db, dl, common_times)
        for name, requested in (("gap_entry", LO), ("gap_exit", HI), ("recovery_end", RECOVERY_END)):
            i = max(0, int(np.searchsorted(common_times, requested, side="right"))-1)
            boundary = dict(comparison=label, boundary=name, requested_time_s=requested,
                            saved_time_s=float(common_times[i]),
                            saved_minus_requested_s=float(common_times[i]-requested))
            for tag, values, names in (
                ("position", dp[i], ("N_m", "E_m", "D_m")),
                ("velocity", dv[i], ("N_mps", "E_mps", "D_mps")),
                ("attitude", drpy[i], ("roll_deg", "pitch_deg", "yaw_deg")),
                ("gyro_bias", db[i, :3], ("x_dph", "y_dph", "z_dph")),
                ("accel_bias", db[i, 3:6]*1e-5, ("x_mps2", "y_mps2", "z_mps2"))):
                boundary.update({tag+"_"+axis: float(value) for axis, value in zip(names, values)})
            boundary_rows.append(boundary)
        for name in masks(common_times):
            before, after = scalar[(control, name)], scalar[(treatment, name)]
            deltas.append(dict(comparison=label, stratum=name, control=control, treatment=treatment,
                **{key: after[key]-before[key] if before[key] is not None and after[key] is not None else None
                   for key in METRIC_KEYS}))
        if label.startswith("GAP_PARTIAL_"):
            prefix = common_times < FIRST_AFFECTED
            changed_state = np.any(a["kf"] != b["kf"], axis=1) | np.any(a["bias"] != b["bias"], axis=1)
            changed_indices = np.flatnonzero(changed_state)
            prefixes.append(dict(comparison=label, prefix_epochs=int(prefix.sum()),
                fixed_first_affected_carrier_time_s=FIRST_AFFECTED,
                exact_prefix_state_equal=bool(np.array_equal(a["kf"][prefix], b["kf"][prefix])),
                exact_prefix_bias_scale_equal=bool(np.array_equal(a["bias"][prefix], b["bias"][prefix])),
                exact_prefix_STD_equal=bool(np.array_equal(a["std"][prefix], b["std"][prefix])),
                first_saved_state_or_bias_difference_time_s=float(common_times[changed_indices[0]]) if len(changed_indices) else None))

    interactions = []
    for name in masks(common_times):
        sdk = next(x for x in deltas if x["comparison"] == PAIRS[0][0] and x["stratum"] == name)
        foot = next(x for x in deltas if x["comparison"] == PAIRS[1][0] and x["stratum"] == name)
        interactions.append(dict(stratum=name,
            **{key: foot[key]-sdk[key] if sdk[key] is not None and foot[key] is not None else None
               for key in METRIC_KEYS},
            meaning="descriptive difference of gap-partial effects across complete SDK/foot-replacement policies"))

    interaction_states = []
    sdk_vectors, foot_vectors = pair_vectors[PAIRS[0][0]], pair_vectors[PAIRS[1][0]]
    for name, mask in masks(common_times).items():
        dp = (foot_vectors["dp"]-sdk_vectors["dp"])[mask]
        dv = (foot_vectors["dv"]-sdk_vectors["dv"])[mask]
        db = (foot_vectors["db"]-sdk_vectors["db"])[mask]
        dl = (foot_vectors["dl"]-sdk_vectors["dl"])[mask]
        interaction_states.append(dict(stratum=name, native_epochs=int(mask.sum()),
            position_horizontal_interaction_rms_m=rms(np.linalg.norm(dp[:, :2], axis=1)),
            position_3d_interaction_rms_m=rms(np.linalg.norm(dp, axis=1)),
            velocity_horizontal_interaction_rms_mps=rms(np.linalg.norm(dv[:, :2], axis=1)),
            velocity_3d_interaction_rms_mps=rms(np.linalg.norm(dv, axis=1)),
            gyro_bias_interaction_rms_dph=rms(np.linalg.norm(db[:, :3], axis=1)),
            accel_bias_interaction_rms_mps2=rms(np.linalg.norm(db[:, 3:6]*1e-5, axis=1)),
            lever_horizontal_interaction_rms_m=rms(np.linalg.norm(dl[:, :2], axis=1)),
            interpretation="native vector difference-of-differences in common frame; not additive causal attribution"))

    out = stage / "READOUT"
    out.mkdir(exist_ok=False)
    products = {
        "METRICS.csv": metrics, "WITHIN_BACKGROUND_DELTAS.csv": deltas,
        "DESCRIPTIVE_INTERACTION.csv": interactions, "NATIVE_STATE_EFFECT.csv": effects,
        "NATIVE_STATE_INTERACTION.csv": interaction_states,
        "BOUNDARY_STATE_DIFFERENCES.csv": boundary_rows, "PREFIX_IDENTITY.csv": prefixes,
        "SOURCE_AWARE_COUNTS.csv": sa_summary, "SA_TIME_BOUNDARY_CORRECTION.csv": sa_time_remaps,
        "CARRIER_COUNTS.csv": carrier_summary,
        "FOOT_SDK_COUNTS.csv": aids_summary}
    for filename, data in products.items():
        table(out / filename, data)
    result = dict(schema="position_product_gap_readout.v1", runner=pin(__file__), input_pins=inputs,
        fixed_gap=dict(lo=LO, hi=HI, interval="open", recovery_end=RECOVERY_END,
                       recovery_interval="[hi,hi+20]", remaining="complement of gap union recovery"),
        fixed_provider_counts=dict(Counter(classes.tolist())), prefix_checks=prefixes,
        fixed_output_epoch_counts={k:int(v.sum()) for k,v in masks(common_times).items()},
        metrics=metrics, within_background_deltas=deltas, descriptive_interaction=interactions,
        state_effects=effects, native_state_interaction=interaction_states, boundary_states=boundary_rows,
        source_aware_counts=sa_summary, sa_time_boundary_corrections=sa_time_remaps,
        carrier_counts=carrier_summary, foot_sdk_counts=aids_summary,
        arm_diagnostics={arm:{key:data[key] for key in ("manifest","replay","result","evaluator_summary","replay_events")}
                         for arm,data in arms.items()},
        native_solver_calls=0, evaluator_calls=0, reference_payload_reads=0,
        semantics=dict(controlled_position_product_outage_not_natural=True,
            carrier_difference="Only 30 partial slots inside the fixed gap differ; outside 87 partial and all common FULL inputs remain",
            support_difference="REPLACE_SUPPORT versus SDK_NULL is a whole SDK-replacement policy, not a pure foot-information causal effect",
            interaction="Descriptive difference of effects; not additive causal decomposition",
            state_differences="Native IMU point, common ECEF-derived local frame; not reference accuracy",
            velocity_reference_RMSE=None, error_metric="Frozen reference-relative evaluator error series",
            source_count="SA only sees updates reaching SA; carrier hard-NIS counts are separate",
            source_time_masks="Carrier SA serialized at 10 decimals is joined uniquely to exact frozen provider time; other SA sources keep recorded source time; BODY uses consumption state_time, FOOT uses event_time; no nearest-IMU assignment",
            boundary_samples="Last saved native row at or before fixed boundary; not exact event update jumps"))
    emit(out / "READOUT.json", result)
    args.docs.mkdir(parents=True, exist_ok=True)
    for name in ("METRICS.csv", "NATIVE_STATE_EFFECT.csv", "DESCRIPTIVE_INTERACTION.csv", "PREFIX_IDENTITY.csv"):
        table(args.docs / ("POSITION_PRODUCT_GAP_"+name), products[name])
    lines = ["# 位置产品缺失：局部 partial × 足式政策四臂", "",
        "本轮为受控半合成位置产品缺失诊断，非自然 GNSS 失效。四臂在缺失区间外保留相同 carrier；局部对照只撤去 gap 内 30 条 partial。不是整窗 FULL 与 ROLLING 算法比较。足式维度为替代 SDK 的完整政策，不解释为纯足端信息贡献。", "",
        f"固定 gap ({LO}, {HI}) s；恢复段 [{HI}, {RECOVERY_END}] s；remaining 与这两段互斥并覆盖其余全窗。全窗另行汇总。四臂均保留全部原生及评价分母，数据没有按误差、接受结果或有无增益删段。", "",
        "| arm | stratum | N | H RMSE m | Up RMSE m | yaw RMSE deg | H p99 m | yaw p99 deg | coverage |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in metrics:
        lines.append("| "+" | ".join(str(row[k]) for k in (
            "arm","stratum","evaluation_epochs","horizontal_rmse_m","up_rmse_m","yaw_rmse_deg",
            "horizontal_p99_m","yaw_abs_p99_deg","coverage_ratio"))+" |")
    lines += ["", "## 差值和实际来源", "",
        "WITHIN_BACKGROUND_DELTAS 逐背景报告 gap-partial 保留减撤去；DESCRIPTIVE_INTERACTION 为两种完整足式政策下该差值之差。原生状态差另列，速度没有参考 RMSE，不能把速度差当精度。评价杆臂作用与原生 IMU 点位置作用分开。", "",
        "SOURCE_AWARE_COUNTS 保留 position、receiver velocity、raw Doppler、RP、body velocity 的实际接受/拒绝与权重；CARRIER_COUNTS 另保留前级 NIS 和供给分母；FOOT_SDK_COUNTS 区分 START/END/RETIRE/REVOKE 及 SDK 抑制。零自然撤销不等于故障撤销验证。", "",
        "## 局部归因资格", "", "首个可能改变 carrier 的时刻固定为 "+str(FIRST_AFFECTED)+
        "；PREFIX_IDENTITY 检查每个足式背景此前全部保存状态、偏置/尺度及 STD 完全相同。若该条件失败，不将结果归因为局部 30 条 partial。BOUNDARY_STATE_DIFFERENCES 保留 gap 入口/出口与恢复末的实际状态差和采样时间偏差。", "",
        "本读出新增 native/evaluator 均为 0，未读取参考 payload；仅读取根任务已封存的 4 次 native 和 4 次冻结评价 error_series。所有数值是当前参考下的相对结果，不是独立真值验证。即使位置产品被撤去，receiver velocity/raw Doppler 等仍可约束运动，不能预期或承诺必有明显位置增益。", "",
        f"完整机器产物：{out / 'READOUT.json'}", ""]
    (args.docs / "POSITION_PRODUCT_GAP_READOUT.md").write_text("\n".join(lines))
    print(json.dumps(dict(output=str(out),prefix_checks=prefixes,
        gap_metrics=[x for x in metrics if x["stratum"]=="position_product_gap"],
        gap_interaction=next(x for x in interactions if x["stratum"]=="position_product_gap")),indent=2))


if __name__ == "__main__":
    main()
