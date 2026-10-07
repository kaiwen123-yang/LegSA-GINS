#!/usr/bin/env python3
"""Conditional paired position-ranking sensitivity from saved errors; no new evaluation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np


def pin(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def table(path, records):
    with path.open("x", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--doc-dir", type=Path)
    a = p.parse_args()
    prior_path = a.base / "SDK_JOINT_NMB1_READOUT_01/READOUT.json"
    prior = json.loads(prior_path.read_text())
    known = {x["path"]: x["sha256"] for x in prior["input_pins"]}
    paths = {
        "OFF_NULL": "SUPPORT_POSE_NATIVE_NMB1_01/EVALUATION/REPLACE_NULL_ERRORS.csv",
        "OFF_XYZ": "SUPPORT_POSE_XYZ_NMB1_01/EVALUATION/REPLACE_SUPPORT_XYZ_ERRORS.csv",
        "JOINT_NULL": "SUPPORT_SDK_JOINT_NMB1_01/EVALUATION/REPLACE_NULL_ERRORS.csv",
        "JOINT_XYZ": "SUPPORT_SDK_JOINT_NMB1_01/EVALUATION/REPLACE_SUPPORT_XYZ_ERRORS.csv",
    }
    data, pins = {}, [pin(prior_path)]
    for label, rel in paths.items():
        path = a.base / rel
        item = pin(path)
        assert item["sha256"] == known[str(path)], label
        pins.append(item)
        data[label] = np.genfromtxt(path, names=True, delimiter=",")
    t = data["OFF_NULL"]["time"]
    assert all(np.array_equal(t, x["time"]) for x in data.values())
    g0, g1 = prior["gap"]
    fc = prior["first_carrier_s"]
    masks = {
        "FULL_WINDOW": np.ones(len(t), bool),
        "BEFORE_POSITION_GAP": t < g0,
        "POSITION_GAP": (t >= g0) & (t < g1),
        "RECOVERY_BEFORE_FIRST_CARRIER": (t >= g1) & (t < fc),
        "FROM_FIRST_CARRIER": t >= fc,
    }
    pairs = [("OFF_XYZ", "OFF_NULL"), ("JOINT_XYZ", "JOINT_NULL"),
             ("JOINT_NULL", "OFF_NULL"), ("JOINT_XYZ", "OFF_XYZ")]
    rows = []
    for variant, control in pairs:
        for phase, mask in masks.items():
            for component, fields in [("H", ["err_n_m", "err_e_m"]), ("Up", ["err_u_m"])]:
                ea = np.column_stack([data[variant][k][mask] for k in fields])
                eb = np.column_stack([data[control][k][mask] for k in fields])
                d = ea - eb
                ma = float(np.mean(np.sum(ea * ea, axis=1)))
                mb = float(np.mean(np.sum(eb * eb, axis=1)))
                margin = ma - mb
                separation2 = float(np.mean(np.sum(d * d, axis=1)))
                mean_norm = float(np.linalg.norm(np.mean(d, axis=0)))
                separation = np.sqrt(separation2)
                threshold = abs(margin) / (2 * separation) if separation > 0 else None
                constant = abs(margin) / (2 * mean_norm) if mean_norm > 0 else None
                # Check the scalar Cauchy equality without generating a candidate truth trajectory.
                tie_margin = margin - 2 * (margin / (2 * separation2)) * separation2 if separation2 > 0 else margin
                rows.append(dict(variant=variant, control=control, stratum=phase,
                    component=component, epochs=int(mask.sum()),
                    variant_reference_RMSE_m=np.sqrt(ma), control_reference_RMSE_m=np.sqrt(mb),
                    MSE_margin_variant_minus_control_m2=margin,
                    position_pair_RMS_m=separation, mean_pair_displacement_norm_m=mean_norm,
                    arbitrary_common_reference_shift_RMS_tie_m=threshold,
                    constant_common_reference_shift_norm_tie_m=constant,
                    scalar_tie_identity_residual_m2=tie_margin,
                    reference_relative_winner=variant if margin < 0 else control if margin > 0 else "TIE"))
    assert max(abs(x["scalar_tie_identity_residual_m2"]) for x in rows) < 1e-10
    sigma_path = a.base / "REFERENCE_TRACE_QUALITY_NMB1_01/REPORTED_SIGMA_RMS.csv"
    with sigma_path.open() as f:
        sigma = list(csv.DictReader(f))
    pins.append(pin(sigma_path))
    result = dict(schema="conditional_reference_position_rank_sensitivity_v1", runner=pin(Path(__file__).resolve()),
        input_pins=pins, all_four_saved_error_pins_match_prior_readout=True,
        common_epochs=len(t), time_range_s=[float(t[0]), float(t[-1])],
        gap_s=[g0, g1], first_carrier_s=fc, rows=rows, reported_reference_sigma_scale=sigma,
        derivation={"errors": "eA=a-r, eB=b-r, d=eA-eB, u=x-r",
                    "true_margin": "D_true=D-2*mean(d dot u)",
                    "conditional_bound": "RMS(u)<=B implies abs(D_true-D)<=2*RMS(d)*B",
                    "arbitrary_shift_tie": "abs(D)/(2*RMS(d))",
                    "constant_shift_tie": "abs(D)/(2*norm(mean(d)))"},
        limits=["Common additive reference position change on original matched epochs, same frozen NEU axes, interpolation and point transform.",
                "The arbitrary-shift threshold is adversarial and unconstrained in temporal structure; not an estimate or likelihood of actual reference error.",
                "Below the threshold ranking is invariant CONDITIONAL on the asserted RMS bound; no calibrated hard bound is available here.",
                "Constant offset sensitivity is a separate restricted model, not a claim that actual error is constant.",
                "Reported sigma is an uncalibrated model-uncertainty scale over 10 Hz unique source epochs; sensitivity uses existing native output epochs. It is not substituted for B.",
                "No independent-sample confidence interval, covariance subtraction, reference correction, sample deletion or yaw-ranking conclusion.",
                "Does not certify clock, coordinate or physical comparison-point calibration; changing the algorithm point transform itself is outside this additive shift calculation."],
        native_calls=0, evaluator_calls=0, raw_reads=0, reference_payload_reads=0,
        new_reference_or_trajectory_generated=False)
    a.output.mkdir(parents=True, exist_ok=False)
    table(a.output / "PAIRED_RANKING_SENSITIVITY.csv", rows)
    (a.output / "SUMMARY.json").write_text(json.dumps(result, indent=2) + "\n")
    if a.doc_dir:
        shutil.copy2(a.output / "PAIRED_RANKING_SENSITIVITY.csv", a.doc_dir / "REFERENCE_PAIRED_RANKING_SENSITIVITY.csv")
    print(json.dumps({"output": str(a.output), "rows": len(rows), "gap": [r for r in rows if r["stratum"] == "POSITION_GAP"]}, indent=2))


if __name__ == "__main__":
    main()
