#!/usr/bin/env python3
"""Post-hoc availability summaries; no new solver or reference-error evaluation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

PROTOCOL_COMMIT = "2271d5a38a49aa957bbc3539244ec18ad7fa55ff"
METHODS = ("F01", "F02", "F03", "A04", "F04")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def rtk_rows(path):
    with path.open() as stream:
        rows = [list(map(float, row)) for row in csv.reader(stream)
                if row and not row[0].lstrip().startswith("%")]
    return np.asarray(rows, dtype=float).reshape(-1, 15)


def time_support(output_ns, input_ns):
    indices = []
    unmatched = 0
    for t in output_ns:
        p = int(np.searchsorted(input_ns, t))
        candidates = [j for j in (p - 1, p) if 0 <= j < len(input_ns)]
        best = min(candidates, key=lambda j: abs(int(input_ns[j]) - int(t)))
        if abs(int(input_ns[best]) - int(t)) <= 20_000_000:
            indices.append(best)
        else:
            unmatched += 1
    if len(set(indices)) != len(indices):
        raise ValueError("Output reuses a source epoch")
    return len(indices), unmatched


def ecef(lat, lon, height):
    p, l = np.deg2rad(lat), np.deg2rad(lon)
    e2 = 6.6943799901413165e-3
    n = 6378137.0 / np.sqrt(1 - e2 * np.sin(p) ** 2)
    return np.column_stack(((n + height) * np.cos(p) * np.cos(l),
                            (n + height) * np.cos(p) * np.sin(l), (n * (1-e2) + height) * np.sin(p)))


def enu(xyz, origin, lat, lon):
    p, l = np.deg2rad([lat, lon])
    rotation = np.array([[-np.sin(l), np.cos(l), 0], [-np.sin(p)*np.cos(l), -np.sin(p)*np.sin(l), np.cos(p)],
                         [np.cos(p)*np.cos(l), np.cos(p)*np.sin(l), np.sin(p)]])
    return (xyz - origin) @ rotation.T


def gap_plot(ax, t, values, *, threshold, **kwargs):
    t, values = np.asarray(t), np.asarray(values)
    if len(t) == 0:
        return
    boundaries = np.r_[0, np.flatnonzero(np.diff(t) > threshold) + 1, len(t)]
    for k, (lo, hi) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        options = dict(kwargs)
        if k:
            options.pop("label", None)
        ax.plot(t[lo:hi], values[lo:hi], **options)


def gap_threshold(times):
    steps = np.diff(np.asarray(times))
    positive = steps[steps > 0]
    return 3 * float(np.median(positive)) if len(positive) else 0.0


def verify_retained(directory):
    if (directory / "SKIPPED.json").is_file():
        skipped = json.loads((directory / "SKIPPED.json").read_text())
        if (directory / "COMMAND.json").exists() or skipped["native_invocations"] != 0:
            raise RuntimeError("Conflicting skipped and executed identities")
        return dict(skipped, returncode=None, wall_seconds_including_strace=0,
                    source_receipt_name="SKIPPED.json", reference_path_access_lines=[], binary_sha256="NOT_INVOKED"), {
                        "terminal_status":skipped["status"], "recorded_output_hashes_match":"NOT_APPLICABLE_NOT_INVOKED",
                        "validation":{"rows":0,"finite_rows":0,"errors":["NOT_INVOKED"]}}
    receipt = json.loads((directory / "COMMAND.json").read_text())
    validation = json.loads((directory / "OUTPUT_VALIDATION.json").read_text())
    if sha(directory / "COMMAND.json") != validation["original_receipt_sha256"]:
        raise RuntimeError(f"Changed receipt: {directory.name}")
    if not validation["recorded_output_hashes_match"]:
        raise RuntimeError(f"Previously rejected identity: {directory.name}")
    for name, expected in receipt["artifacts"].items():
        if not (directory / name).is_file() or sha(directory / name) != expected:
            raise RuntimeError(f"Changed output: {directory.name}/{name}")
    receipt["source_receipt_name"] = "COMMAND.json"
    return receipt, validation


def figures(seq, data, output, destination, result):
    g1 = np.load(data / "decoded" / seq / "gnss1-raw.npz", allow_pickle=False)
    g2 = np.load(data / "decoded" / seq / "gnss2-raw.npz", allow_pickle=False)
    hp = np.load(data / "decoded" / seq / "paired_hp_observations.npz", allow_pickle=False)
    poi = np.load(data / "decoded" / seq / "user_io-out-poi_geodetic.npz", allow_pickle=False)
    xb = np.load(data / "decoded" / f"xb{seq[1:]}.npz", allow_pickle=False)
    ns0 = int(g1["RXM_RAWX__time_ns"][0])
    tow0 = g1["RXM_RAWX__rcv_tow"][0]
    unique = np.unique(poi["measurement_ns"], return_index=True)[1]
    plat, plon, ph = (poi[k][unique] for k in ("p.vector3.x", "p.vector3.y", "p.vector3.z"))
    origin = ecef(plat[:1], plon[:1], ph[:1])[0]
    fig, axes = plt.subplots(3, 2, figsize=(13, 10.5), constrained_layout=True)
    ax = axes[0, 0]
    penu = enu(ecef(plat, plon, ph), origin, plat[0], plon[0])
    # Common WGS84 origin; no per-trajectory fit, offset removal, or SE(3) alignment.
    for z, name, color in ((g1, "GNSS1 APC", "#2166ac"), (g2, "GNSS2 APC", "#b2182b")):
        values = enu(np.column_stack([z[f"NAV_HPPOSECEF__{c}_m"] for c in "xyz"]), origin, plat[0], plon[0])
        tt = z["NAV_HPPOSECEF__itow_ms"] * .001
        bounds = np.r_[0, np.flatnonzero(np.diff(tt) > gap_threshold(tt))+1, len(tt)]
        for i, (lo, hi) in enumerate(zip(bounds[:-1], bounds[1:])):
            ax.plot(values[lo:hi, 0], values[lo:hi, 1], lw=.7, color=color, label=name if i == 0 else None)
    pt = (poi["measurement_ns"][unique] - ns0) * 1e-9
    bounds = np.r_[0, np.flatnonzero(np.diff(pt) > gap_threshold(pt))+1, len(pt)]
    for i, (lo, hi) in enumerate(zip(bounds[:-1], bounds[1:])):
        ax.plot(penu[lo:hi, 0], penu[lo:hi, 1], color="#238b45", lw=1, label="Commercial POI (different point)" if i == 0 else None)
    ax.set(title="Recorded positions; different physical points", xlabel="East from first POI (m)", ylabel="North (m)")
    ax.axis("equal"); ax.legend(fontsize=8)
    ax = axes[0, 1]
    ht = hp["itow_ms"]*.001-tow0
    gap_plot(ax, ht, hp["length_m"], threshold=gap_threshold(ht), color="#756bb1", lw=.8)
    ax.set(title="Raw HPPOSECEF difference; not a calibrated baseline", xlabel="From first G1 RAWX (s)", ylabel="GNSS2 - GNSS1 length (m)")
    directory = output / f"{seq}_RTK_FULL"
    _, valid = verify_retained(directory)
    rows = rtk_rows(directory / "solution.pos") if not valid["validation"]["errors"] else np.empty((0,15))
    ax = axes[1, 0]
    if len(rows):
        times = rows[:, 1] - tow0
        lengths = np.linalg.norm(rows[:, 2:5], axis=1)
        for q, color in ((1, "#238b45"), (2, "#d95f0e")):
            mask = rows[:, 5] == q
            ax.scatter(times[mask], lengths[mask], c=color, s=23, label=f"Q{q} ({mask.sum()} epochs)")
        ax.legend(fontsize=8)
        inset = ax.inset_axes([.12,.44,.48,.46])
        inset.scatter(times, lengths, c=np.where(rows[:,5]==1,"#238b45","#d95f0e"),s=16)
        inset.set(title=f"All {len(rows)} output epochs ({times[-1]-times[0]:.1f} s)", xlabel="Time (s)")
        inset.tick_params(labelsize=7)
        inset.title.set_fontsize(8); inset.xaxis.label.set_fontsize(8)
    else:
        message = "NO SOLUTION\nHeader-only output retained" if result["status"] == "NO_SOLUTION" else result["status"]
        ax.text(.5, .5, message, ha="center", va="center", transform=ax.transAxes, wrap=True)
    duration = (g1["RXM_RAWX__time_ns"][-1] - ns0)*1e-9
    ax.set(xlim=(0, duration), title=f"Actual RTKLIB output: {result['matched_output_epochs']}/{result['input_epochs']}", xlabel="Time (s)", ylabel="Baseline length (m)")
    ax = axes[1, 1]
    for i, (z, name) in enumerate(((g1, "G1 carrier"), (g2, "G2 carrier"))):
        vt = z["NAV_PVT__itow_ms"]*.001-tow0
        gap_plot(ax, vt, z["NAV_PVT__carrSoln"]+3*i, threshold=gap_threshold(vt), lw=.7, label=name)
    if len(rows):
        ax.scatter(rows[:, 1]-tow0, rows[:, 5]+6, s=16, label="RTKLIB Q (not receiver carrier)")
    ax.set(ylim=(-.5, 9), xlim=(0, duration), yticks=[0,1,2,3,4,5,7,8],
           yticklabels=["G1 none","G1 float","G1 fixed","G2 none","G2 float","G2 fixed","RTK Q1","RTK Q2"],
           title="Input states and actual solver support", xlabel="Time (s)")
    ax = axes[2, 0]
    xt = (xb["time_ns"]-ns0)*1e-9
    ax.scatter(xt[1:], np.diff(xb["time_ns"])*1e-6, s=.2, color="#0571b0", rasterized=True)
    ax.set(title="Go2 complete-message stamp intervals", xlabel="Time (s)", ylabel="dt (ms)")
    ax = axes[2, 1]
    gap_plot(ax, pt, (poi["arrival_ns"][unique]-poi["measurement_ns"][unique])*1e-6, threshold=gap_threshold(pt), lw=.6, label="POI arrival - measurement")
    for z, label in ((g1,"G1 RAWX"),(g2,"G2 RAWX")):
        rt = (z["RXM_RAWX__time_ns"]-ns0)*1e-9
        gap_plot(ax, rt, (z["RXM_RAWX__arrival_ns"]-z["RXM_RAWX__time_ns"])*1e-6, threshold=gap_threshold(rt), lw=.6, label=label)
    ax.set(title="Recorded time differences; not fitted delays", xlabel="Time (s)", ylabel="Arrival - measurement (ms)")
    ax.legend(fontsize=8)
    for ax in axes.flat:
        ax.grid(alpha=.2)
    fig.suptitle(f"{seq} | Full recording diagnostics | RD: no velocity output | Accuracy RMSE: NA", fontsize=14)
    for suffix in ("png", "svg"):
        fig.savefig(destination / f"{seq}_diagnostics.{suffix}", dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", type=Path, required=True)
    paths = yaml.safe_load(parser.parse_args().local.read_text())["paths"]
    root, audit = Path(paths["code_root"]), Path(paths["audit_root"])
    out, data = audit / "gnss_exploration", audit / "data_audit"
    docs = root / "docs/paper_rebuild/audit_xbpg_20261001"
    plots = audit / "figures"
    plots.mkdir(exist_ok=True)
    runs, metrics, identities = [], [], []
    prep = json.loads((out / "PREPARATION.json").read_text())
    for i in range(1, 5):
        seq = f"S{i}"
        for method in METHODS:
            reason = "UNVERIFIED_GO2_IMU_TO_GNSS_APC_GEOMETRY_AND_CLOCK_BINDING"
            if method != "F01":
                reason += ";FORMAL_V3_BOTH_FIXED_HEADING_SUPPORT_ZERO"
            blocked = dict(sequence=seq, method=method, phase="MAIN_FULL_WINDOW", run_id=f"{seq}_{method}_NOT_RUN",
                           status="NOT_RUN_INPUT_UNQUALIFIED", reason=reason, native_invocations=0)
            runs.append(blocked)
            metrics.append(dict(blocked, input_epochs="NA", matched_output_epochs=0, coverage_percent="NA",
                                horizontal_rmse_m="NA", vertical_rmse_m="NA", position_3d_rmse_m="NA", velocity_rmse_mps="NA",
                                roll_rmse_deg="NA", pitch_rmse_deg="NA", yaw_rmse_deg="NA", error_p95="NA", error_max="NA",
                                reference_matched_epochs=0, evaluation_reason="NO_METHOD_OUTPUT;PHYSICAL_POINT_AND_CLOCK_UNVERIFIED"))
        rtk_result = None
        for kind, method, receiver in (("RTK", "EXPLORATORY_RTKLIB_UNCONSTRAINED", 2), ("RD", "EXPLORATORY_CURRENT_RAW_DOPPLER_HELPER", 1)):
            directory = out / f"{seq}_{kind}_FULL"
            receipt, validation = verify_retained(directory)
            z = np.load(data / "decoded" / seq / f"gnss{receiver}-raw.npz", allow_pickle=False)
            input_ns = z["RXM_RAWX__week"].astype(np.int64)*604800_000_000_000 + np.rint(z["RXM_RAWX__rcv_tow"]*1e9).astype(np.int64)
            rows = rtk_rows(directory / "solution.pos") if kind == "RTK" and not validation["validation"]["errors"] else np.empty((0,15))
            n = validation["validation"]["finite_rows"]
            if kind == "RD" and n:
                raise RuntimeError("Nonempty RD requires explicit time-column support parsing; never assume it empty")
            output_ns = rows[:,0].astype(np.int64)*604800_000_000_000 + np.rint(rows[:,1]*1e9).astype(np.int64)
            matched, unmatched = time_support(output_ns, input_ns)
            status = validation["terminal_status"]
            if status == "OUTPUT_REQUIRES_SUPPORT_CHECK":
                status = "PARTIAL_SUPPORT" if matched < len(input_ns) else "FULL_EPOCH_SUPPORT"
            if unmatched:
                status = "OUTPUT_OUTSIDE_INPUT_SUPPORT"
            base = dict(sequence=seq, method=method, phase="EXPLORATORY_FULL_WINDOW", run_id=directory.name, status=status,
                        reason=receipt.get("reason","SEE_GNSS_EXPLORATORY_RESULTS"), native_invocations=receipt.get("native_invocations",1), returncode=receipt["returncode"],
                        wall_seconds_including_strace=receipt["wall_seconds_including_strace"], original_status=receipt["status"],
                        protocol_commit=PROTOCOL_COMMIT, receipt=f"<AUDIT_ROOT>/gnss_exploration/{directory.name}/{receipt['source_receipt_name']}",
                        receipt_sha256=sha(directory/receipt["source_receipt_name"]), output_identity_verified=validation["recorded_output_hashes_match"],
                        reference_access_lines=len(receipt["reference_path_access_lines"]))
            runs.append(base)
            lengths = np.linalg.norm(rows[:,2:5], axis=1)
            measure = dict(base, input_epochs=len(input_ns), output_epochs=validation["validation"]["rows"], finite_output_epochs=n,
                           matched_output_epochs=matched, unmatched_output_epochs=unmatched, missing_solution_epochs=len(input_ns)-matched,
                           coverage_percent=100*matched/len(input_ns), raw_duration_s=(input_ns[-1]-input_ns[0])*1e-9,
                           output_span_s=float((output_ns[-1]-output_ns[0])*1e-9) if len(output_ns) else 0,
                           output_max_gap_s=float(np.diff(output_ns).max()*1e-9) if len(output_ns)>1 else "NA",
                           fixed_output_epochs=int(np.sum(rows[:,5]==1)), float_output_epochs=int(np.sum(rows[:,5]==2)),
                           baseline_length_min_m=float(lengths.min()) if len(lengths) else "NA", baseline_length_median_m=float(np.median(lengths)) if len(lengths) else "NA",
                           baseline_length_max_m=float(lengths.max()) if len(lengths) else "NA", reference_matched_epochs=0,
                           horizontal_rmse_m="NA", vertical_rmse_m="NA", position_3d_rmse_m="NA", velocity_rmse_mps="NA",
                           roll_rmse_deg="NA", pitch_rmse_deg="NA", yaw_rmse_deg="NA", error_p95="NA", error_max="NA",
                           observation_attempts="UNKNOWN_INTERNAL", observation_accepted="UNKNOWN_INTERNAL", observation_rejected="UNKNOWN_INTERNAL",
                           evaluation_reason="UNVERIFIED_PHYSICAL_POINT_REFERENCE;NO_ABSOLUTE_ERROR_EVALUATION")
            metrics.append(measure)
            if kind == "RTK":
                rtk_result = measure
            identities.append(dict(run_id=directory.name, code_commit=PROTOCOL_COMMIT, binary_sha256=receipt["binary_sha256"],
                                   config_hash=prep["config_sha256"] if kind == "RTK" else "RTKLIB_PRCOOPT_DEFAULT_PLUS_HELPER_EMBEDDED_SETTINGS",
                                   source_config_or_helper=sha(out / "UNCONSTRAINED_MOVING_BASE.conf") if kind == "RTK" else sha(root / "src/legsa_gins/raw_gnss/rtklib_doppler_helper_builder.py"),
                                   original_receipt_sha256=sha(directory/receipt["source_receipt_name"]), supplement="PROVENANCE_FROM_FROZEN_PROTOCOL_AND_EXECUTION_COMMAND;ORIGINAL_RECEIPT_UNCHANGED"))
        figures(seq, data, out, plots, rtk_result)
    for directory in sorted(out.iterdir()):
        if not directory.is_dir() or not (directory / "COMMAND.json").is_file() or directory.name.endswith("FULL"):
            continue
        receipt = json.loads((directory / "COMMAND.json").read_text())
        validation = directory / "OUTPUT_VALIDATION.json"
        status = json.loads(validation.read_text())["terminal_status"] if validation.is_file() else receipt["status"]
        runs.append(dict(sequence=directory.name[:2], method=receipt["role"], phase="SMOKE" if "SMOKE" in directory.name else "CONVERSION",
                         run_id=directory.name, status=status, native_invocations=1, returncode=receipt["returncode"],
                         wall_seconds_including_strace=receipt["wall_seconds_including_strace"], receipt_sha256=sha(directory/"COMMAND.json"),
                         receipt=f"<AUDIT_ROOT>/gnss_exploration/{directory.name}/COMMAND.json"))
    write_csv(docs / "RUNS.csv", runs)
    write_csv(docs / "METRICS.csv", metrics)
    write_csv(docs / "EXPLORATORY_IDENTITY.csv", identities)
    write_csv(docs / "FIGURE_INDEX.csv", [dict(path=f"<AUDIT_ROOT>/figures/{p.name}", bytes=p.stat().st_size, sha256=sha(p),
              data_mode="real_xb_pg_raw", synthetic_data_used=False, semisynthetic_data_used=False,
              metrics_recomputed=False, actual_raster_review="PENDING") for p in sorted(plots.iterdir()) if p.suffix in (".png",".svg")])
    count=lambda predicate:sum(int(r["native_invocations"]) for r in runs if predicate(r))
    print(json.dumps({"run_rows":len(runs),"metric_rows":len(metrics),
                      "native_real_rtk":count(lambda r:r['method']=='EXPLORATORY_RTKLIB_UNCONSTRAINED' or r['phase']=='SMOKE'),
                      "native_real_rd":count(lambda r:r['method']=='EXPLORATORY_CURRENT_RAW_DOPPLER_HELPER'),
                      "convbin":count(lambda r:r['phase']=='CONVERSION'),
                      "formal_legsa_real":count(lambda r:r['phase']=='MAIN_FULL_WINDOW'),"reference_evaluators":0,"figures":4}))


if __name__ == "__main__":
    main()
