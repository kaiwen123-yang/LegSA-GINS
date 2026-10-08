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


def read_rows(path):
    """Read the emitted state log without re-estimating or re-evaluating it."""
    rows = []
    with path.open(encoding="utf-8", newline="") as file:
        for saved in csv.DictReader(file):
            row = dict(time_s=float(saved["time_s"]),
                       p=np.array([float(saved[f"p_{axis}_m"]) for axis in "NED"]),
                       v=np.array([float(saved[f"v_{axis}_mps"]) for axis in "NED"]),
                       rpy_rad=np.array([float(saved[key]) for key in ("roll_rad", "pitch_rad", "yaw_rad")]),
                       bias=np.array([float(saved[f"bias_{i}"]) for i in range(6)]),
                       direction_status=saved["direction_status"],
                       candidate_support_complete={"True": True, "False": False, "": None}[saved["candidate_support_complete"]])
            for key in ("candidate_yaws_rad", "candidate_costs", "support_ids"):
                row[key] = json.loads(saved[key])
            row.update(json.loads(saved["extra_fields"]))
            rows.append(row)
    return rows


def input_timeline(events):
    return [dict(time_s=event["time_s"],
                 feet=[dict(foot_id=foot["foot_id"], arc_id=foot["arc_id"]) for foot in event["feet"]],
                 phase_relations=len(event["carrier"].ambiguity_labels) if event["carrier"] is not None else None,
                 gnss_position_available=event["gnss_position"] is not None)
            for event in events]


def write_input_timeline(path, timeline):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["time_s", "feet", "phase_relations", "gnss_position_available"])
        writer.writeheader()
        for row in timeline:
            writer.writerow(dict(row, feet=json.dumps(row["feet"])))


def read_saved_plot_inputs(output_root, modes):
    results, evaluated = {}, {}
    for mode in modes:
        results[mode] = dict(rows=read_rows(output_root / mode / "navigation.csv"))
        with np.load(output_root / mode / "offline_error_series.npz", allow_pickle=False) as archive:
            evaluated[mode] = {key: archive[key].copy() for key in archive.files}
    timeline_path = output_root / "input_timeline.csv"
    if timeline_path.exists():
        with timeline_path.open(encoding="utf-8", newline="") as file:
            timeline = [dict(time_s=float(row["time_s"]), feet=json.loads(row["feet"]),
                             phase_relations=int(row["phase_relations"]) if row["phase_relations"] else None,
                             gnss_position_available={"True": True, "False": False, "": None}[row["gnss_position_available"]])
                        for row in csv.DictReader(file)]
        source = "saved_input_timeline"
    else:
        # Earlier runs saved observed arc IDs and consumed phase counts in each
        # output, but not every GNSS arrival. Recover only those recorded fields.
        mode = next(mode for mode in ("U3", "U2", "U1", "U0") if mode in results)
        timeline = [dict(time_s=row["time_s"],
                         feet=[dict(foot_id=int(arc.split("_")[1]), arc_id=arc) for arc in row["support_ids"]],
                         phase_relations=row["consumed_phase_relations"], gnss_position_available=None)
                    for row in results[mode]["rows"]]
        source = f"saved_{mode}_observed_support_ids_and_consumed_phase_relations_GNSS_arrivals_not_saved"
    return timeline, results, evaluated, source


def plot_process(output_root, timeline, results, evaluated, *, stem="joint_process", input_source="observed_input_events"):
    """One figure asks whether retained direction improves the common navigation state.

    Input availability establishes the perturbation; candidate support shows the
    interpretation; yaw, true velocity and position errors show its consequence.
    Every mark comes from actual input events or emitted estimator rows.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FormatStrFormatter

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.labelsize": 8,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": .65,
                         "legend.frameon": False, "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(7, 1, sharex=True, figsize=(174 / 25.4, 245 / 25.4),
                             gridspec_kw={"height_ratios": [1., .6, 1.5, .55, 1.7, 1.1, 1.1]})
    fig.subplots_adjust(left=.15, right=.98, top=.91, bottom=.06, hspace=.29)
    duration = float(timeline[-1]["time_s"])
    support_arcs = {}
    for i, event in enumerate(timeline[:-1]):
        end = timeline[i + 1]["time_s"]
        for foot in event["feet"]:
            identity = (foot["foot_id"], foot["arc_id"])
            if identity in support_arcs:
                support_arcs[identity][1] = end
            else:
                support_arcs[identity] = [event["time_s"], end]
    for (foot, _), (start, end) in support_arcs.items():
        axes[0].broken_barh([(start, end-start)], (3-foot-.27, .54), facecolors="#777777", linewidth=0)
    gnss_arrivals_saved = any(event["gnss_position_available"] is not None for event in timeline)
    if gnss_arrivals_saved:
        fix_times = [event["time_s"] for event in timeline if event["gnss_position_available"]]
        axes[0].scatter(fix_times, np.full(len(fix_times), -1), marker="|", s=16, c="#444444", linewidths=.6)
        axes[0].set_yticks([-1, 0, 1, 2, 3], ["GNSS", "RL", "RR", "FL", "FR"])
        axes[0].set_ylabel("Observed\ninputs")
    else:
        axes[0].set_yticks([0, 1, 2, 3], ["RL", "RR", "FL", "FR"])
        axes[0].set_ylabel("Logged\nsupport")
    carrier_events = [event for event in timeline if event["phase_relations"] is not None]
    axes[1].step([event["time_s"] for event in carrier_events],
                 [event["phase_relations"] for event in carrier_events], where="post", color="#444444", linewidth=.9)
    axes[1].set_yticks([0, 2, 5])
    axes[1].set_ylim(-.3, 5.5)
    axes[1].set_ylabel("Phase\nrelations")
    mode_order = list(results)
    axes[3].set_yticks(range(len(mode_order)), mode_order)
    axes[3].set_ylim(len(mode_order)-.5, -.5)
    axes[3].set_ylabel("Set\nstatus")
    axes[3].text(1., 1.22, "Filled = incomplete", transform=axes[3].transAxes,
                 ha="right", va="bottom", fontsize=6.5)
    axes[3].tick_params(axis="y", length=0, labelsize=6.5)
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
        # Status has its own categorical axis, so it cannot be mistaken for yaw.
        for i, row in enumerate(rows[:-1]):
            complete = row.get("candidate_support_complete")
            if complete is not True:
                interval = [(row["time_s"], rows[i+1]["time_s"]-row["time_s"])]
                axes[3].broken_barh(interval, (mode_order.index(mode)-.3, .6),
                                    facecolors=COLORS[mode] if complete is False else "none",
                                    edgecolors=COLORS[mode] if complete is None else "none",
                                    hatch="////" if complete is None else None, linewidth=.3)
        for axis, field in zip(axes[4:], ("yaw_deg", "velocity_3d_mps", "position_3d_m")):
            axis.plot(data["time_s"], data[field], color=COLORS[mode], linestyle=STYLES[mode], linewidth=.9)
        if mode == "U3" and all("yaw_conditional_std_rad" in row for row in rows):
            std_deg = np.degrees([row["yaw_conditional_std_rad"] for row in rows])
            axes[4].fill_between(data["time_s"], data["yaw_deg"]-1.96*std_deg,
                                 data["yaw_deg"]+1.96*std_deg, color=COLORS[mode], alpha=.12, linewidth=0)
    if evaluated:
        data = next(iter(evaluated.values()))
        axes[2].plot(data["time_s"], np.degrees(wrap_radians(data["truth_yaw_rad"])), color="black", linewidth=.7, linestyle="--")
    if not all_candidates:
        axes[2].text(.5, .5, "No active direction candidates emitted", transform=axes[2].transAxes, ha="center")
    axes[2].set_ylabel("Candidate\nyaw (deg)")
    axes[4].set_yscale("symlog", linthresh=.1, linscale=1., base=10)
    axes[4].set_yticks([-100., -10., -1., -.1, 0., .1, 1., 10., 100.])
    axes[4].yaxis.set_major_formatter(FormatStrFormatter("%g"))
    axes[4].set_ylabel("Yaw error (deg)\nsymlog")
    axes[5].set_ylabel("Velocity error\n(m/s)")
    axes[6].set_ylabel("Position error\n(m)")
    axes[6].set_xlabel("Time (s)")
    for i, axis in enumerate(axes):
        axis.annotate(f"({chr(97+i)})", xy=(0, 1), xycoords="axes fraction", xytext=(-37, 3),
                      textcoords="offset points", fontsize=8.5, fontweight="bold", ha="left", va="bottom")
        axis.set_xlim(0., duration)
        axis.tick_params(axis="both", length=2.5, width=.6)
        if i >= 2 and i != 3:
            axis.grid(axis="y", color="#dddddd", linewidth=.4)
        for t in sorted(set(revocation_times)):
            axis.axvline(t, color="#AA3377", linewidth=.65, linestyle=":", alpha=.7)
    handles = [Line2D([], [], color=COLORS[mode], linestyle=STYLES[mode], label=f"{mode}: {LABELS[mode]}", linewidth=1.2) for mode in results]
    handles += [Line2D([], [], color="black", linestyle="--", label="Truth (candidate panel)", linewidth=.7)]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.55, .99), ncol=3, fontsize=7, handlelength=2.1, columnspacing=1.3)
    fig.canvas.draw()
    # All seven axes share one column. Record final physical rectangles so visual
    # review can inspect the actual result without another plotting pipeline.
    rectangles = [dict(panel=chr(97+i), bounds_pt=(axis.get_position().bounds * np.array([fig.get_figwidth()*72, fig.get_figheight()*72]*2)).tolist())
                  for i, axis in enumerate(axes)]
    write_json(output_root / f"{stem}_geometry.json", rectangles)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(output_root / f"{stem}.{suffix}", dpi=600)
    plt.close(fig)
    (output_root / f"{stem}_caption.md").write_text(
        "First-round diagnostic process figure; this figure does not mark completion of the research deliverable. "
        "(a) Logged force-support arcs"
        + (" and received GNSS navigation epochs. " if gnss_arrivals_saved else ". GNSS arrival times were not saved and are omitted. ") +
        "(b) Actually available carrier-phase relations. "
        "(c) Active direction candidates for each configuration; the dashed black curve is Truth. "
        "Only branches inside the declared conditional profile-cost support are shown; "
        "budget-omitted raw support remains unresolved. Candidate branches are not averaged "
        "into one precise heading. (d) Separate categorical candidate-set status: filled "
        "bands mean incomplete, empty means complete, and hatching means unreported. "
        "These marks are not angles. The green band in (e) is U3's selected-branch local 1.96 sigma, "
        "not a calibrated bound on the unresolved direction union. "
        "(e) Signed wrapped yaw error on a symmetric-logarithmic axis, linear from -0.1 to +0.1 deg. "
        "The full initialization spike and every subsequent timestamp are retained. "
        "(f) True three-dimensional velocity-vector error. (g) Three-dimensional position error. Purple dotted lines, when "
        "present, mark reported dependency revocations or replay events. All states "
        "are outputs published with the information available at their timestamps; "
        "repaired historical estimates do not replace them. Curves show one noise "
        "instance, not an uncertainty interval across instances.\n", encoding="utf-8")
    write_json(output_root / f"{stem}_plot_metadata.json", dict(
        plot_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_timeline_source=input_source, source_result_modes=list(results),
        rows_per_mode={mode: len(result["rows"]) for mode, result in results.items()},
        full_time_interval_s=[timeline[0]["time_s"], duration],
        yaw_axis=dict(scale="symlog", linear_threshold_deg=.1),
        data_or_metric_recomputed=False, research_deliverable_complete=False,
    ))
    return [f"{stem}.{suffix}" for suffix in ("png", "pdf", "svg")]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=6100801)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--duration", type=float, default=90.)
    parser.add_argument("--support-inference", choices=("full_nonlinear", "shared_linearization"),
                        default="full_nonlinear")
    parser.add_argument("--plot-only", action="store_true", help="redraw saved navigation CSV/NPZ only; never run a navigator or regenerate the scene")
    parser.add_argument("--plot-stem", default="joint_process_review", help="filename stem for --plot-only output; the original plot is preserved by default")
    args = parser.parse_args(argv)
    output_root = args.output_root.resolve()
    if args.plot_only:
        timeline, results, evaluated, source = read_saved_plot_inputs(output_root, args.modes)
        files = plot_process(output_root, timeline, results, evaluated, stem=args.plot_stem, input_source=source)
        print(json.dumps(dict(status="PLOT_ONLY_COMPLETE", plot_files=files, navigator_calls=0,
                              scene_generation_calls=0, research_deliverable_complete=False)), flush=True)
        return
    from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator
    from legsa_gins.paper_rebuild.joint_navigation.synthetic import generate_scene

    output_root.mkdir(parents=True, exist_ok=True)
    scene = generate_scene(duration_s=args.duration, seed=args.seed)
    scene["metadata"]["support_inference"] = args.support_inference
    purpose = "full_90_second_process" if args.duration >= 90 else "internal_short_debug_not_scientific_milestone"
    run_record = dict(seed=args.seed, duration_s=args.duration, modes=args.modes, purpose=purpose,
                      data_mode="synthetic", estimator_truth_input=False,
                      support_inference=args.support_inference,
                      scenario_kind=scene["metadata"]["scenario_kind"], completed_modes=[], status="RUNNING")
    repository = Path(__file__).resolve().parents[2]
    sources = sorted((repository / "src/legsa_gins/paper_rebuild/joint_navigation").glob("*.py")) + [Path(__file__).resolve()]
    run_record["source_sha256"] = {str(path.relative_to(repository)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    run_record["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    run_record["runtime"] = dict(python=platform.python_version(), platform=platform.platform(),
                                  packages={name: importlib.metadata.version(name) for name in ("gtsam", "numpy", "scipy", "matplotlib")})
    # A long research run can overlap later source edits. Keep the exact text
    # corresponding to its recorded hashes, not only the previous commit id.
    repository = Path(__file__).resolve().parents[2]
    for relative in run_record["source_sha256"]:
        target = output_root / "SOURCE_SNAPSHOT" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repository / relative).read_bytes())
    write_json(output_root / "run_status.json", run_record)
    write_json(output_root / "sensor_metadata.json", scene["metadata"])
    write_json(output_root / "evaluation_metadata.json", scene["evaluation_metadata"])
    timeline = input_timeline(scene["events"])
    write_input_timeline(output_root / "input_timeline.csv", timeline)
    results, evaluated, metrics = {}, {}, {}
    for mode in args.modes:
        print(f"{mode}: starting {args.duration:g} s {purpose}", flush=True)
        started = time.monotonic()
        navigator = JointNavigator(scene["metadata"], mode=mode)
        try:
            result = navigator.run(scene["events"])
        except (Exception, KeyboardInterrupt) as error:
            run_record.update(status="INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "FAILED",
                              failed_mode=mode, error_type=type(error).__name__, error=str(error),
                              failed_mode_published_rows=len(navigator.rows))
            write_json(output_root / "run_status.json", run_record)
            arm_root = output_root / mode
            arm_root.mkdir(exist_ok=True)
            write_rows(arm_root / "navigation.csv", navigator.rows)
            write_json(arm_root / "decisions.json", navigator.decisions)
            write_json(arm_root / "estimator_summary.json", dict(status=run_record["status"],
                causal_output_rows=len(navigator.rows), partial_output=True,
                complete_research_goal=False))
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
    plot_files = plot_process(output_root, timeline, results, evaluated)
    run_record.update(status="COMPLETED", plot_files=plot_files)
    write_json(output_root / "run_status.json", run_record)
    print(json.dumps(dict(status="COMPLETED", output_root=str(output_root), purpose=purpose, modes=args.modes)), flush=True)


if __name__ == "__main__":
    main()
