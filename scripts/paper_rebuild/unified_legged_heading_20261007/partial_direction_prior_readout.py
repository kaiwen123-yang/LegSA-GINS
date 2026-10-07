#!/usr/bin/env python3
"""Read exact pre-carrier priors; bound prior overlap with source direction arcs.

No solver, evaluator, reference, Monte Carlo, branch selection or new likelihood.
The chi-square bound is conditional on the saved Gaussian error chart and fixed
nominal position, not a posterior mode probability or calibrated sensor claim.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

import numpy as np
from scipy.special import log_ndtr
from scipy.spatial.transform import Rotation
from scipy.stats import chi2

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/paper_rebuild/carrier_phase")]
from candidate_lifecycle_pilot import axes

CONFIDENCE = .999
CHI2_RADIUS_SQUARED = float(chi2.ppf(CONFIDENCE, 3))
AXES = ("n", "e", "d")


def pin(path):
    path = Path(path)
    return {"path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def bits(time):
    return format(struct.unpack(">Q", struct.pack(">d", float(time)))[0], "016x")


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def ned_axes(lat, lon):
    """Rows N/E/D expressed in ECEF, matching C_ne transpose."""
    sl, cl, so, co = math.sin(lat), math.cos(lat), math.sin(lon), math.cos(lon)
    return np.array([[-sl*co, -sl*so, cl], [-so, co, 0.],
                     [-cl*co, -cl*so, -sl]])


def matrix(row, prefix, suffix):
    return np.array([[float(row[prefix + a + b + suffix]) for b in AXES]
                     for a in AXES])


def arc_distance(unit_baseline, start, width):
    """Exact spherical distance to an azimuth arc with unrestricted elevation.

    The vertical poles belong to its closure. For an azimuth gap > pi/2 the
    nearest point is a pole; continuing the cos^2 formula would be incorrect.
    """
    theta = math.atan2(unit_baseline[1], unit_baseline[0])
    inside = width >= 2*math.pi or (theta - start) % (2*math.pi) <= width
    delta = 0. if inside else min(
        abs(math.atan2(math.sin(theta-a), math.cos(theta-a)))
        for a in (start, start + width))
    rho = float(np.linalg.norm(unit_baseline[:2]))
    z = abs(float(unit_baseline[2]))
    distance = (math.asin(min(1., rho*math.sin(delta))) if delta <= math.pi/2
                else math.atan2(rho, z))
    return theta, inside, delta, distance


def log_chi3_survival(x):
    """Closed-form log SF, avoiding scipy.logsf underflow for remote arcs."""
    if x == 0.:
        return 0.
    first = math.log(2.) + float(log_ndtr(-math.sqrt(x)))
    second = .5*math.log(2*x/math.pi) - x/2
    return float(np.logaddexp(first, second))


def stats(values):
    values = list(values)
    return None if not values else dict(zip(
        ("min", "median", "max"), map(float, np.quantile(values, [0, .5, 1]))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--provider-details", type=Path, required=True)
    parser.add_argument("--model-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    diagnostic = args.native / "BASELINE3D_DIAGNOSTICS.csv"
    with gzip.open(args.provider_details, "rt") as handle:
        selected = [row for row in map(json.loads, handle)
                    if row["policy"] == "rolling" and row["kind"] == "PARTIAL_GLS_LIKELIHOOD"]
    # This readout's denominator is the frozen BY2O source, not accepted updates.
    if len(selected) != 117:
        raise ValueError("Expected the complete frozen BY2O 117-partial source")
    model_plan = json.loads(args.model_plan.read_text())
    with diagnostic.open() as handle:
        by_time = {}
        for row in csv.DictReader(handle):
            by_time.setdefault(bits(row["time"]), []).append(row)
    rows, component_rows = [], []
    for source in selected:
        index, time = int(source["index"]), float(source["time_s"])
        components = source["consumed_likelihood"]["directed_components"]
        record = model_plan["records"][index]
        if bits(record["time_s"]) != bits(time):
            raise ValueError("Source anchor model does not match the partial epoch")
        anchor = record["anchor_ecef_m"]
        quality = source["consumed_likelihood"]["partial_quality"]
        item = dict(index=index, time_s=time, event_time_bits_hex=bits(time),
                    source_fingerprint=source["source_fingerprint"],
                    component_count=len(components), phase_rank=quality["phase_rank"],
                    baseline_rank=quality["baseline_rank"],
                    source_anchor_ecef_x_m=anchor[0], source_anchor_ecef_y_m=anchor[1],
                    source_anchor_ecef_z_m=anchor[2],
                    source_anchor_status=record["anchor_decision"]["status"],
                    source_anchor_time_s=record["anchor_decision"]["source_time_s"])
        candidates = by_time.get(bits(time), [])
        if len(candidates) != 1:
            item["status"] = "MISSING_OR_AMBIGUOUS_EVENT_PRIOR"
            item["native_event_rows"] = len(candidates)
            rows.append(item)
            continue
        event = candidates[0]
        item.update(native_accepted=int(event["accepted"]), native_reason=event["reason"],
                    native_nis=float(event["nis_actual_innovation"]) if event["nis_actual_innovation"] else None)
        if event.get("prior_available") != "1":
            item["status"] = "PRIOR_UNAVAILABLE"
            rows.append(item)
            continue
        if event["prior_phase"] != "PRE_CURRENT_CARRIER_UPDATE":
            raise ValueError("Posterior or unknown prior phase cannot enter this readout")
        if event["event_time_bits_hex"].lower() != bits(time):
            raise ValueError("Native/source event bits differ")
        # Preserve original nonzero error mean; do not fake a covariance reset.
        cbn = np.array([[float(event[f"prior_nominal_cbn_{i}{j}"]) for j in range(3)] for i in range(3)])
        mu = np.array([float(event[f"prior_dx_phi_{a}_rad"]) for a in AXES])
        covariance = matrix(event, "prior_P_phi_phi_", "_rad2")
        eigenvalues = np.linalg.eigvalsh((covariance + covariance.T)/2)
        if eigenvalues[0] < -1e-14 or eigenvalues[-1] <= 0:
            raise ValueError("Saved attitude prior is not positive semidefinite")
        lam_max = float(eigenvalues[-1])
        body = np.array([float(event[f"prior_body_baseline_{a}_m"]) for a in ("x", "y", "z")])
        nominal_h = cbn @ body
        saved_h = np.array([float(event[f"h_{a}_m"]) for a in AXES])
        h_identity_error = float(np.max(abs(nominal_h - saved_h)))
        if h_identity_error > 1e-10:
            raise ValueError("Dumped nominal frame/body does not reproduce actual factor h")
        native_basis = ned_axes(float(event["prior_nominal_lat_rad"]), float(event["prior_nominal_lon_rad"]))
        source_horizontal = axes(anchor)
        source_basis = np.vstack([source_horizontal, np.cross(*source_horizontal)])
        chart_center_h = Rotation.from_rotvec(mu).apply(nominal_h)
        source_h = source_basis @ native_basis.T @ chart_center_h
        source_unit = source_h / np.linalg.norm(source_h)
        confidence_radius = math.sqrt(CHI2_RADIUS_SQUARED * lam_max)
        item.update(status="PRIOR_AVAILABLE", prior_event_identity=event["prior_event_identity"],
                    baseline_event_sequence=event["baseline_event_sequence"],
                    prior_state_time=float(event["prior_state_time"]),
                    prior_state_minus_event_s=float(event["prior_state_time"])-time,
                    prior_state_event_bits_equal=event["prior_state_time_bits_hex"].lower()==bits(time),
                    prior_state_time_bits_hex=event["prior_state_time_bits_hex"],
                    prior_error_chart=event["prior_error_chart"],
                    nominal_h_identity_max_abs_m=h_identity_error,
                    source_center_azimuth_deg=math.degrees(math.atan2(source_unit[1], source_unit[0])),
                    source_center_elevation_down_deg=math.degrees(math.asin(float(np.clip(source_unit[2], -1, 1)))),
                    error_mean_norm_deg=math.degrees(float(np.linalg.norm(mu))),
                    P_phi_phi_symmetry_max_abs=float(np.max(abs(covariance-covariance.T))),
                    P_phi_phi_min_eigenvalue_rad2=float(eigenvalues[0]),
                    P_phi_phi_max_eigenvalue_rad2=lam_max,
                    worst_axis_std_deg=math.degrees(math.sqrt(lam_max)),
                    confidence_radius_deg=math.degrees(confidence_radius),
                    position_frame="FROZEN_NOMINAL_POSITION_NOT_JOINT_PHI_POSITION_INTEGRAL")
        current_components = []
        for number, component in enumerate(components):
            theta, inside, gap, distance = arc_distance(
                source_unit, float(component["start_rad"]), float(component["width_rad"]))
            x = distance**2 / lam_max
            log_upper = log_chi3_survival(x)
            # A representable upward cap preserves the upper-bound interpretation.
            underflow_capped = log_upper < math.log(np.finfo(float).tiny)
            upper = math.exp(max(log_upper, math.log(np.finfo(float).tiny)))
            excluded = distance > confidence_radius
            comp = dict(index=index, time_s=time, component_index=number,
                        source_fingerprint=source["source_fingerprint"],
                        component_start_rad=component["start_rad"],
                        component_width_rad=component["width_rad"],
                        center_azimuth_inside=inside,
                        minimum_azimuth_gap_deg=math.degrees(gap),
                        minimum_required_rotation_deg=math.degrees(distance),
                        confidence_radius_deg=math.degrees(confidence_radius),
                        chi2_required_radius_squared=x,
                        prior_mass_upper_bound=upper,
                        log_prior_mass_upper_bound=log_upper,
                        upper_bound_capped_at_smallest_normal=underflow_capped,
                        outside_999_confidence_ellipsoid=excluded,
                        bound_scope="GAUSSIAN_ORIGINAL_CHART_FIXED_NOMINAL_P_PRIOR_ONLY")
            current_components.append(comp)
            component_rows.append(comp)
        excluded_count = sum(x["outside_999_confidence_ellipsoid"] for x in current_components)
        item["excluded_components"] = excluded_count
        item["unexcluded_components"] = len(components)-excluded_count
        item["prior_domain_status"] = (
            "ALL_COMPONENTS_OUTSIDE_CONFIDENCE_ELLIPSOID" if excluded_count == len(components)
            else "ONE_COMPONENT_NOT_EXCLUDED" if len(components)-excluded_count == 1
            else "MULTIPLE_COMPONENTS_NOT_EXCLUDED_NOT_A_POSTERIOR_CLAIM")
        if current_components:
            ordered = sorted(current_components, key=lambda x: x["minimum_required_rotation_deg"])
            item.update(nearest_component_index=ordered[0]["component_index"],
                        farther_component_index=ordered[-1]["component_index"],
                        farther_minimum_rotation_deg=ordered[-1]["minimum_required_rotation_deg"],
                        farther_log_prior_mass_upper_bound=ordered[-1]["log_prior_mass_upper_bound"],
                        farther_component_excluded=ordered[-1]["outside_999_confidence_ellipsoid"])
        rows.append(item)

    available = [x for x in rows if x["status"] == "PRIOR_AVAILABLE"]
    double = [x for x in rows if x["component_count"] == 2]
    double_available = [x for x in double if x["status"] == "PRIOR_AVAILABLE"]
    summary = dict(status="COMPLETE" if len(available) == 117 else "INCOMPLETE_PRIOR_COVERAGE",
                   partial_denominator=len(rows), two_component_denominator=len(double),
                   prior_available=len(available), two_component_prior_available=len(double_available),
                   native_accepted=sum(x.get("native_accepted", 0) for x in rows),
                   all_status_counts=dict(Counter(x["status"] for x in rows)),
                   all_prior_domain_status_counts=dict(Counter(x["prior_domain_status"] for x in available)),
                   two_component_status_counts=dict(Counter(x["prior_domain_status"] for x in double_available)),
                   farther_rotation_deg=stats(x["farther_minimum_rotation_deg"] for x in double_available),
                   farther_log_prior_upper=stats(x["farther_log_prior_mass_upper_bound"] for x in double_available),
                   confidence_radius_deg=stats(x["confidence_radius_deg"] for x in available),
                   prior_state_minus_event_s=stats(x["prior_state_minus_event_s"] for x in available),
                   prior_state_event_exact_bits_matches=sum(x["prior_state_event_bits_equal"] for x in available),
                   confidence_level=CONFIDENCE, chi2_degrees_of_freedom=3,
                   chi2_radius_squared=CHI2_RADIUS_SQUARED,
                   native_solver_calls=0, evaluator_calls=0, reference_reads=0, monte_carlo_samples=0,
                   method="Spherical distance to full-elevation arc + global SO3 Exp Lipschitz + largest covariance eigenvalue + chi-square tail",
                   original_error_chart_preserved=True, nominal_position_frozen=True,
                   frontend_RP_gyro_domain_not_multiplied_as_independent_probability=True,
                   not_posterior_mode_probability=True, not_an_algorithm_gate=True,
                   no_candidate_revocation=True,
                   inputs={"native_diagnostic":pin(diagnostic), "provider_details":pin(args.provider_details),
                           "model_plan":pin(args.model_plan), "readout":pin(Path(__file__))})
    args.output.mkdir(parents=True, exist_ok=False)
    write_csv(args.output / "PARTIAL_PRIOR_EVENTS.csv", rows)
    write_csv(args.output / "PARTIAL_PRIOR_COMPONENTS.csv", component_rows)
    (args.output / "SUMMARY.json").write_text(json.dumps(summary, indent=2, allow_nan=False)+"\n")
    outcome = summary["two_component_status_counts"]
    report = f"""# 部分方向域与更新前共同姿态先验

本次读取全部 {len(rows)} 条 partial，包含 {len(double)} 条双分量域；更新前 prior 覆盖 {len(available)}/{len(rows)}。native 已接受 {summary['native_accepted']} 条，但接受结果不参与样本筛选。没有执行 native/evaluator、读取 reference 或进行 Monte Carlo。

## 双分量结果

{json.dumps(outcome, ensure_ascii=False, indent=2)}

prior_state_time−event_time 的 min/median/max 为 {summary['prior_state_minus_event_s']} 秒，精确 bits 相同 {summary['prior_state_event_exact_bits_matches']}/{len(available)}。实际 exact-event 代码先传播到事件，再设 timestamp_=event_time 后 gnssUpdate（gi_engine.cpp:797–823）；这里汇总实际差，不从标签预设为零。

固定 99.9% 置信判据；连续上界保存在每弧表中。弧序号保留原顺序，near/far 只按必要旋转距离排序。若两个弧都远，标为 prior/domain 不相容；不能自动认定近弧正确。没有排除也不证明两个后验模态，不能据此永久撤销候选或新增算法门。

## 计算合同

原误差图表 phi~N(mu,P)；使用 Exp(mu) C_nom r 构造图表中心。未假装把非零 mu reset 后仍沿用原 P。每条源 anchor 来自冻结模型 PLAN 的 anchor_ecef_m（原始 GNSS code anchor，非参考）；先由当前 nominal BLH 的 NED 转 ECEF，再投到源 anchor 北/东/下轴。角是侧向基线 atan2(E,N)，不是机体 Euler yaw。nominal p 固定，未积分位置随机性或 p/phi 相关项，因此不是完整联合状态概率。

每弧允许全部高程，故所得球面最短角 d 是触及原域的必要旋转下界。令 delta 为中心方位至弧的最小环形距离，中心单位基线=(rho*cos(theta),rho*sin(theta),z)。delta<=pi/2 时 d=asin(rho*sin(delta))；否则 d=atan2(rho,abs(z))，最优点在极点闭包。对所有 phi，SO3 的 Exp 映射满足 d_SO3(Exp(phi),Exp(mu))<=||phi-mu||。置信椭球又满足 ||phi-mu||<=sqrt(lambda_max(P))*sqrt(q2)，故弧内先验质量至多 SF_chi2_3(d*d/lambda_max(P))。该界有意忽略椭球方向和 RP 高程限制，保守但无大规模数值积分。log SF 用闭式 logaddexp 稳算；数值列若低于最小 normal double 则向上截断，真实量级仍由 log 列报告，未输出伪精确零概率。

这里对给定域计算原高斯 prior 质量的上界，没有把 RP/重力/gyro 域作为独立 likelihood 相乘。域是使用相关来源获得的几何外覆盖，输出既不校准 prior，也不是 posterior mode probability。足端、SDK 和此前载波对共同状态的作用已包含在实际 P 中，不另叠 foot prior。保留域外质量，不把两个弧归一化为总概率 1。

## 产物

- 事件表：{args.output / 'PARTIAL_PRIOR_EVENTS.csv'}
- 每弧表：{args.output / 'PARTIAL_PRIOR_COMPONENTS.csv'}
- 身份、全分母与汇总：{args.output / 'SUMMARY.json'}

本次仅为是否值得研究多分量后端的诊断；不能作为新的测量、质量门、整数正确性或候选撤销依据。
"""
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report)
    print(json.dumps({k:summary[k] for k in (
        "status", "partial_denominator", "two_component_denominator", "prior_available",
        "two_component_status_counts", "farther_rotation_deg", "farther_log_prior_upper",
        "confidence_radius_deg")}, indent=2))


if __name__ == "__main__":
    main()
