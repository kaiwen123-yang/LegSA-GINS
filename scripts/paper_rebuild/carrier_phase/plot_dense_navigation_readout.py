"""Plot completed comparison errors only; never call a solver or read raw/reference."""
from pathlib import Path
import argparse
import json
import hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pvt", type=Path, required=True)
    parser.add_argument("--prior-serial", type=Path, required=True)
    parser.add_argument("--dense-serial", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.pvt, args.prior_serial, args.dense_serial]
    labels = ["Dual-PVT vector control", "Carrier: 2 s opportunities",
              "Carrier: 0.2 s opportunities + native kernel"]
    colors = ["#1c5283", "#a86c23", "#287b56"]
    frames = [pd.read_csv(p) for p in paths]
    keys = frames[0]["time"].to_numpy()
    if not all(np.array_equal(keys, frame["time"].to_numpy()) for frame in frames):
        raise ValueError("complete evaluation time support differs")
    columns = ["yaw_err_deg", "horizontal_err_m", "err_u_m"]
    if not all(np.isfinite(frame[["time", *columns]].to_numpy()).all() for frame in frames):
        raise ValueError("nonfinite saved evaluation")
    args.output.mkdir(parents=True, exist_ok=False)
    fig, axes = plt.subplots(3, 1, figsize=(10.6, 8.0), sharex=True)
    records = []
    for ax, column, ylabel in zip(axes, columns,
            ["Heading difference (deg)", "Horizontal difference (m)", "Vertical difference (m)"]):
        for path, frame, label, color in zip(paths, frames, labels, colors):
            values = frame[column].to_numpy()
            rms = float(np.sqrt(np.mean(values * values)))
            ax.plot(keys, values, color=color, linewidth=.75, alpha=.9,
                    label=f"{label} | RMSE {rms:.4f}")
            records.append(dict(variant=label, metric=column, epochs=len(keys),
                                rmse=rms, max_abs=float(np.max(np.abs(values))),
                                source=str(path)))
        ax.set_ylabel(ylabel)
        ax.grid(alpha=.2)
        ax.legend(loc="upper right", fontsize=8, framealpha=.88)
    axes[-1].set_xlabel("Time (s)")
    axes[-1].set_xlim(float(keys[0]), float(keys[-1]))
    fig.suptitle("Carrier integration: full navigation support", fontsize=14)
    fig.text(.08, .015,
             "Receiver-derived comparison reference; not independent truth. "
             "Serial replay charges recorded CILS cost only.",
             fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .97))
    for ext in ("png", "pdf"):
        fig.savefig(args.output / f"carrier_navigation_comparison.{ext}", dpi=170)
    plt.close(fig)
    pd.DataFrame(records).to_csv(args.output / "metrics.csv", index=False)
    (args.output / "PROVENANCE.json").write_text(json.dumps(dict(
        interpretation="saved evaluation differences, not independent-truth errors",
        complete_time_support=True, points_per_curve=len(keys), decimation=False,
        solver_calls=0, evaluator_calls=0, raw_or_reference_reads=0,
        inputs={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        records=records), indent=2) + "\n")


if __name__ == "__main__":
    main()
