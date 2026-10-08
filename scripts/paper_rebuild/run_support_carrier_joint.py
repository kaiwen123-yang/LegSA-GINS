#!/usr/bin/env python3
"""Run the integrated navigator, evaluate emitted states, and draw its process.

The estimator receives metadata/events only. Truth is used afterwards for offline
evaluation. A short invocation is an internal debug run, not the 90 s deliverable.
"""
from __future__ import annotations

import argparse
import csv
import json
import hashlib
import importlib.metadata
import platform
import subprocess
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.joint_navigation.synthetic import generate_scene


MODES = ("U0", "U1", "U2", "U3")
LABELS = {"U0": "Carrier + IMU", "U1": "+ Support arcs", "U2": "+ Partial retention", "U3": "+ Dependency replay"}
COLORS = {"U0": "#666666", "U1": "#0072B2", "U2": "#E69F00", "U3": "#009E73"}
STYLES = {"U0": "--", "U1": "-.", "U2": ":", "U3": "-"}


def json_value(value):
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def write_json(path, value):
    path.write_text(json.dumps(json_value(value), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def wrap_radians(value):
    return (np.asarray(value) + np.pi) % (2 * np.pi) - np.pi


def series_metrics(times, errors, interval, pair_available=None):
    """RMSE over emitted samples and finite adjacent time intervals, without gap filling."""
    selected = (times >= interval[0]) & (times <= interval[1])
    t, error = times[selected], errors[selected]
    finite = np.isfinite(error)
    dt = np.diff(t)
    pairs = finite[:-1] & finite[1:] & (dt > 0)
    if pair_available is not None:
        indices = np.flatnonzero(selected)
        pairs &= pair_available[indices[:-1]] & (np.diff(indices) == 1)
    duration = float(np.sum(dt[pairs]))
    weighted = None
    if duration:
        weighted = float(np.sqrt(np.sum(.5 * (error[:-1][pairs]**2 + error[1:][pairs]**2) * dt[pairs]) / duration))
    return dict(
        samples=int(len(t)), finite_samples=int(np.sum(finite)), nonfinite_samples=int(np.sum(~finite)),
        finite_pair_duration_s=duration,
        time_weighted_rmse=weighted,
        sample_rmse=float(np.sqrt(np.mean(error[finite]**2))) if np.any(finite) else None,
        absolute_max=float(np.max(np.abs(error[finite]))) if np.any(finite) else None,
        final_sample_error=float(error[-1]) if len(error) and finite[-1] else None,
    )


def evaluate_rows(rows, truth, evaluation_metadata):
    """Evaluate causal published rows; never replace them with replayed history."""
    t = np.array([row["time_s"] for row in rows], float)
    if len(t) > 1 and np.any(np.diff(t) <= 0):
        raise ValueError("published navigation times must be strictly increasing")
    p = np.array([row["p"] for row in rows], float).reshape((-1, 3))
    v = np.array([row["v"] for row in rows], float).reshape((-1, 3))
    rpy = np.array([row["rpy_rad"] for row in rows], float).reshape((-1, 3))
    true_t = np.array([row["time_s"] for row in truth], float)
    true_p = np.array([row["p"] for row in truth], float)
    true_v = np.array([row["v"] for row in truth], float)
    true_yaw = np.unwrap([np.arctan2(row["R"][1, 0], row["R"][0, 0]) for row in truth])
    p_ref = np.column_stack([np.interp(t, true_t, true_p[:, j]) for j in range(3)])
    v_ref = np.column_stack([np.interp(t, true_t, true_v[:, j]) for j in range(3)])
    yaw_ref = np.interp(t, true_t, true_yaw)
    supported = (t >= true_t[0]) & (t <= true_t[-1])
    # Do not integrate through omitted output events as if they were available.
    pair_available = (np.searchsorted(true_t, t[1:], side="left")
                      - np.searchsorted(true_t, t[:-1], side="right")) == 0
    errors = dict(
        position_3d_m=np.linalg.norm(p - p_ref, axis=1),
        position_horizontal_m=np.linalg.norm(p[:, :2] - p_ref[:, :2], axis=1),
        velocity_3d_mps=np.linalg.norm(v - v_ref, axis=1),
        speed_mps=np.linalg.norm(v, axis=1) - np.linalg.norm(v_ref, axis=1),
        yaw_deg=np.degrees(wrap_radians(rpy[:, 2] - yaw_ref)),
    )
    for error in errors.values():
        error[~supported] = np.nan
    intervals = {"whole": (float(true_t[0]), float(true_t[-1]))}
    intervals.update({stage["description"]: (max(float(true_t[0]), stage["interval_s"][0]), min(float(true_t[-1]), stage["interval_s"][1]))
                      for stage in evaluation_metadata["stages"] if stage["interval_s"][0] <= true_t[-1]})
    metrics = {name: dict(interval_s=interval, errors={key: series_metrics(t, error, interval, pair_available) for key, error in errors.items()})
               for name, interval in intervals.items()}
    finite_state = np.all(np.isfinite(np.column_stack([p, v, rpy])), axis=1) & supported
    status_counts = {}
    for row in rows:
        status = row["direction_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    metrics["coverage"] = dict(
        published_rows=len(rows), truth_event_count=len(truth), finite_state_rows=int(np.sum(finite_state)),
        nonfinite_or_unsupported_state_rows=int(np.sum(~finite_state)),
        no_published_state=len(rows) == 0,
        unmatched_event_count=len({round(float(x), 10) for x in true_t} - {round(float(x), 10) for x in t}),
        direction_status_counts=status_counts,
        incomplete_candidate_support_rows=sum(row.get("candidate_support_complete") is False for row in rows),
        unknown_candidate_completeness_rows=sum(row.get("candidate_support_complete") is None for row in rows),
    )
    metrics["evaluation"] = dict(reference="synthetic_true_state", output="causal_emitted_navigation_rows",
                                  primary_rmse="time_weighted_rmse", historical_revisions_scored=False)
    return metrics, dict(time_s=t, p=p, v=v, rpy_rad=rpy, truth_yaw_rad=yaw_ref, **errors)


def shared_state_differences(rows, baseline_rows):
    reference = {round(float(row["time_s"]), 10): row for row in baseline_rows}
    times, position, velocity, yaw = [], [], [], []
    for row in rows:
        other = reference.get(round(float(row["time_s"]), 10))
        if other is None:
            continue
        times.append(row["time_s"])
        position.append(np.linalg.norm(np.asarray(row["p"]) - other["p"]))
        velocity.append(np.linalg.norm(np.asarray(row["v"]) - other["v"]))
        yaw.append(np.degrees(wrap_radians(row["rpy_rad"][2] - other["rpy_rad"][2])))
    t = np.asarray(times)
    interval = (t[0], t[-1]) if len(t) else (0., 0.)
    return dict(common_rows=len(t), position_change_m=series_metrics(t, np.asarray(position), interval),
                velocity_change_mps=series_metrics(t, np.asarray(velocity), interval),
                yaw_change_deg=series_metrics(t, np.asarray(yaw), interval),
                interpretation="state changes only; accuracy gains are evaluated separately")


def write_rows(path, rows):
    fields = ["time_s", *[f"p_{axis}_m" for axis in "NED"], *[f"v_{axis}_mps" for axis in "NED"],
              "roll_rad", "pitch_rad", "yaw_rad", *[f"bias_{i}" for i in range(6)],
              "candidate_yaws_rad", "candidate_costs", "support_ids", "direction_status",
              "candidate_support_complete", "gnss_innovation_nis", "extra_fields"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            data = dict(time_s=row["time_s"], direction_status=row["direction_status"],
                        candidate_support_complete=row.get("candidate_support_complete"),
                        gnss_innovation_nis=json_value(row.get("gnss_innovation_nis")))
            data.update(zip(fields[1:4], row["p"]))
            data.update(zip(fields[4:7], row["v"]))
            data.update(zip(fields[7:10], row["rpy_rad"]))
            data.update(zip(fields[10:16], row["bias"]))
            for key in ("candidate_yaws_rad", "candidate_costs", "support_ids"):
                data[key] = json.dumps(json_value(row[key]), allow_nan=False)
            standard = {"time_s", "p", "v", "rpy_rad", "bias", "candidate_yaws_rad", "candidate_costs",
                        "support_ids", "direction_status", "candidate_support_complete", "gnss_innovation_nis"}
            data["extra_fields"] = json.dumps(json_value({key: value for key, value in row.items() if key not in standard}), allow_nan=False)
            writer.writerow(data)


def plot_process(output_root, events, results, evaluated):
    """One figure asks whether retained direction improves the common navigation state.

    Input availability establishes the perturbation; candidate support shows the
    interpretation; yaw, true velocity and position errors show its consequence.
    Every mark comes from actual input events or emitted estimator rows.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.labelsize": 8,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": .65,
                         "legend.frameon": False, "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(6, 1, sharex=True, figsize=(174 / 25.4, 225 / 25.4),
                             gridspec_kw={"height_ratios": [1., .7, 1.6, 1.2, 1.1, 1.1]})
    fig.subplots_adjust(left=.14, right=.98, top=.91, bottom=.065, hspace=.24)
    duration = float(events[-1]["time_s"])
    support_arcs = {}
    for i, event in enumerate(events[:-1]):
        end = events[i + 1]["time_s"]
        for foot in event["feet"]:
            identity = (foot["foot_id"], foot["arc_id"])
            if identity in support_arcs:
                support_arcs[identity][1] = end
            else:
                support_arcs[identity] = [event["time_s"], end]
    for (foot, _), (start, end) in support_arcs.items():
        axes[0].broken_barh([(start, end-start)], (3-foot-.27, .54), facecolors="#777777", linewidth=0)
    fix_times = [event["time_s"] for event in events if event["gnss_position"] is not None]
    axes[0].scatter(fix_times, np.full(len(fix_times), -1), marker="|", s=16, c="#444444", linewidths=.6)
    axes[0].set_yticks([-1, 0, 1, 2, 3], ["GNSS", "RL", "RR", "FL", "FR"])
    axes[0].set_ylabel("Observed\ninputs")
    carrier_events = [event for event in events if event["carrier"] is not None]
    axes[1].step([event["time_s"] for event in carrier_events],
                 [len(event["carrier"].ambiguity_labels) for event in carrier_events], where="post", color="#444444", linewidth=.9)
    axes[1].set_yticks([0, 2, 5])
    axes[1].set_ylim(-.3, 5.5)
    axes[1].set_ylabel("Phase\nrelations")
    all_candidates = []
    revocation_times = []
    for mode, result in results.items():
        rows, data = result["rows"], evaluated[mode]
        candidate_t, candidate_yaw = [], []
        revoked_seen = set()
        for row in rows:
            supported = row.get("candidate_supported", [True]*len(row["candidate_yaws_rad"]))
            for angle, has_support in zip(row["candidate_yaws_rad"], supported):
                if not has_support:
                    continue
                candidate_t.append(row["time_s"])
                candidate_yaw.append(float(np.degrees(wrap_radians(angle))))
            revoked = set(row.get("revoked_support_ids", []))
            if revoked - revoked_seen or row.get("replay_performed"):
                revocation_times.append(row["time_s"])
            revoked_seen |= revoked
        all_candidates.extend(candidate_yaw)
        axes[2].scatter(candidate_t, candidate_yaw, s=2.4, color=COLORS[mode], alpha=.55, linewidths=0, rasterized=True)
        incomplete_t = [row["time_s"] for row in rows if row.get("candidate_support_complete") is False]
        axes[2].scatter(incomplete_t, np.full(len(incomplete_t), 1.0 - .05 * MODES.index(mode)), marker="x", s=5,
                        color=COLORS[mode], linewidths=.4, transform=axes[2].get_xaxis_transform(), clip_on=False)
        for axis, field in zip(axes[3:], ("yaw_deg", "velocity_3d_mps", "position_3d_m")):
            axis.plot(data["time_s"], data[field], color=COLORS[mode], linestyle=STYLES[mode], linewidth=.9)
        if mode == "U3" and all("yaw_conditional_std_rad" in row for row in rows):
            std_deg = np.degrees([row["yaw_conditional_std_rad"] for row in rows])
            axes[3].fill_between(data["time_s"], data["yaw_deg"]-1.96*std_deg,
                                 data["yaw_deg"]+1.96*std_deg, color=COLORS[mode], alpha=.12, linewidth=0)
    if evaluated:
        data = next(iter(evaluated.values()))
        axes[2].plot(data["time_s"], np.degrees(wrap_radians(data["truth_yaw_rad"])), color="black", linewidth=.7, linestyle="--")
    if not all_candidates:
        axes[2].text(.5, .5, "No active direction candidates emitted", transform=axes[2].transAxes, ha="center")
    axes[2].set_ylabel("Candidate\nyaw (deg)")
    axes[3].set_ylabel("Yaw error\n(deg)")
    axes[4].set_ylabel("Velocity error\n(m/s)")
    axes[5].set_ylabel("Position error\n(m)")
    axes[5].set_xlabel("Time (s)")
    for i, axis in enumerate(axes):
        axis.annotate(f"({chr(97+i)})", xy=(0, 1), xycoords="axes fraction", xytext=(-37, 3),
                      textcoords="offset points", fontsize=8.5, fontweight="bold", ha="left", va="bottom")
        axis.set_xlim(0., duration)
        axis.tick_params(axis="both", length=2.5, width=.6)
        if i >= 2:
            axis.grid(axis="y", color="#dddddd", linewidth=.4)
        for t in sorted(set(revocation_times)):
            axis.axvline(t, color="#AA3377", linewidth=.65, linestyle=":", alpha=.7)
    handles = [Line2D([], [], color=COLORS[mode], linestyle=STYLES[mode], label=LABELS[mode], linewidth=1.2) for mode in results]
    handles += [Line2D([], [], color="black", linestyle="--", label="Truth (candidate panel)", linewidth=.7),
                Line2D([], [], color="#777777", marker="x", linestyle="none", markersize=3, label="Incomplete candidate support")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.55, .99), ncol=3, fontsize=7, handlelength=2.1, columnspacing=1.3)
    fig.canvas.draw()
    # All six axes share one column. Record final physical rectangles so visual
    # review can inspect the actual result without another plotting pipeline.
    rectangles = [dict(panel=chr(97+i), bounds_pt=(axis.get_position().bounds * np.array([fig.get_figwidth()*72, fig.get_figheight()*72]*2)).tolist())
                  for i, axis in enumerate(axes)]
    write_json(output_root / "process_plot_geometry.json", rectangles)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(output_root / f"joint_process.{suffix}", dpi=600)
    plt.close(fig)
    (output_root / "joint_process_caption.md").write_text(
        "(a) Observed force-support arcs and received GNSS navigation epochs. "
        "(b) Actually available carrier-phase relations. "
        "(c) Active direction candidates for each configuration; crosses indicate "
        "explicitly incomplete candidate support and the dashed black curve is Truth. "
        "Only branches inside the declared conditional profile-cost support are shown; "
        "budget-omitted raw support remains unresolved. Candidate branches are not averaged "
        "into one precise heading. The green band is U3's selected-branch local 1.96 sigma, "
        "not a calibrated bound on the unresolved direction union. "
        "(d) Signed wrapped yaw error. (e) True three-dimensional velocity-vector "
        "error. (f) Three-dimensional position error. Purple dotted lines, when "
        "present, mark reported dependency revocations or replay events. All states "
        "are outputs published with the information available at their timestamps; "
        "repaired historical estimates do not replace them. Curves show one noise "
        "instance, not an uncertainty interval across instances.\n", encoding="utf-8")
    return [f"joint_process.{suffix}" for suffix in ("png", "pdf", "svg")]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=6100801)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--duration", type=float, default=90.)
    args = parser.parse_args(argv)
    from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator

    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    scene = generate_scene(duration_s=args.duration, seed=args.seed)
    purpose = "full_90_second_process" if args.duration >= 90 else "internal_short_debug_not_scientific_milestone"
    run_record = dict(seed=args.seed, duration_s=args.duration, modes=args.modes, purpose=purpose,
                      data_mode="synthetic", estimator_truth_input=False,
                      scenario_kind=scene["metadata"]["scenario_kind"], completed_modes=[], status="RUNNING")
    repository = Path(__file__).resolve().parents[2]
    sources = sorted((repository / "src/legsa_gins/paper_rebuild/joint_navigation").glob("*.py")) + [Path(__file__).resolve()]
    run_record["source_sha256"] = {str(path.relative_to(repository)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    run_record["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    run_record["runtime"] = dict(python=platform.python_version(), platform=platform.platform(),
                                  packages={name: importlib.metadata.version(name) for name in ("gtsam", "numpy", "scipy", "matplotlib")})
    write_json(output_root / "run_status.json", run_record)
    write_json(output_root / "sensor_metadata.json", scene["metadata"])
    write_json(output_root / "evaluation_metadata.json", scene["evaluation_metadata"])
    results, evaluated, metrics = {}, {}, {}
    for mode in args.modes:
        print(f"{mode}: starting {args.duration:g} s {purpose}", flush=True)
        started = time.monotonic()
        try:
            result = JointNavigator(scene["metadata"], mode=mode).run(scene["events"])
        except (Exception, KeyboardInterrupt) as error:
            run_record.update(status="INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "FAILED",
                              failed_mode=mode, error_type=type(error).__name__, error=str(error))
            write_json(output_root / "run_status.json", run_record)
            raise
        arm_root = output_root / mode
        arm_root.mkdir(exist_ok=True)
        write_rows(arm_root / "navigation.csv", result["rows"])
        write_json(arm_root / "decisions.json", result["decisions"])
        write_json(arm_root / "estimator_summary.json", result["summary"])
        arm_metrics, arrays = evaluate_rows(result["rows"], scene["truth"], scene["evaluation_metadata"])
        arm_metrics["runtime_wall_s"] = time.monotonic() - started
        write_json(arm_root / "metrics.json", arm_metrics)
        np.savez_compressed(arm_root / "offline_error_series.npz", **arrays)
        results[mode], evaluated[mode], metrics[mode] = result, arrays, arm_metrics
        run_record["completed_modes"].append(mode)
        write_json(output_root / "run_status.json", run_record)
        print(f"{mode}: {len(result['rows'])} rows; {arm_metrics['runtime_wall_s']:.2f} s wall time", flush=True)
    if "U0" in results:
        for mode in results:
            if mode != "U0":
                metrics[mode]["shared_state_difference_vs_U0"] = shared_state_differences(results[mode]["rows"], results["U0"]["rows"])
                write_json(output_root / mode / "metrics.json", metrics[mode])
    write_json(output_root / "metrics.json", metrics)
    plot_files = plot_process(output_root, scene["events"], results, evaluated)
    run_record.update(status="COMPLETED", plot_files=plot_files)
    write_json(output_root / "run_status.json", run_record)
    print(json.dumps(dict(status="COMPLETED", output_root=str(output_root), purpose=purpose, modes=args.modes)), flush=True)


if __name__ == "__main__":
    main()
