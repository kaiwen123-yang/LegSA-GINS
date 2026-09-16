"""FIG02S from frozen H-EXT tables, preserving all 28 v2.1 figure trees."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import shutil

import numpy as np

FIGURE_ID = "FIG02S"
RENDER_SHA256 = "800df76ad82b68e3fca7aded30081f6d1ad01241175978baf440c9e0f290dd4e"
SEQUENCES = ("BY2", "BY2H", "BY2O")
METRICS = (("h_rmse_m", "Horizontal RMSE (m)"),
           ("up_rmse_m", "Up RMSE (m)"),
           ("yaw_rmse_deg", "Yaw RMSE (°)"),
           ("yaw_p95_absolute_deg", "Yaw P95 (°)"),
           ("roll_rmse_deg", "Roll RMSE (°)"),
           ("pitch_rmse_deg", "Pitch RMSE (°)"))


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _no_symlink(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Figure evidence/output must not follow symlinks")


def frozen_v21_snapshot(v21_root, *, expected_render_sha256=RENDER_SHA256,
                        expected_figure_count=28):
    """Read/hash the original archive; exclude only the explicitly new extension."""
    root = Path(v21_root)
    _no_symlink(root)
    manifest = root / "RENDER_MANIFEST.json"
    if _sha(manifest) != expected_render_sha256:
        raise ValueError("Frozen v2.1 RENDER_MANIFEST identity mismatch")
    files, directories = {}, []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] == FIGURE_ID or relative.as_posix() == "HEXT_RENDER_MANIFEST.json":
            continue
        if path.is_symlink():
            raise ValueError("Frozen figure archive contains a symlink")
        if path.is_dir() and len(relative.parts) == 1:
            directories.append(relative.as_posix())
        if path.is_file():
            files[relative.as_posix()] = _sha(path)
    if len(directories) != expected_figure_count:
        raise ValueError("Frozen figure directory count differs from 28")
    return {"render_manifest_sha256": expected_render_sha256,
            "figure_directory_count": len(directories), "figure_directories": directories,
            "files_sha256": files, "file_count": len(files)}


def verify_frozen_v21(before, v21_root):
    after = frozen_v21_snapshot(v21_root)
    if after != before:
        raise ValueError("Original v2.1 figure archive changed")
    return after


def _truthy(value):
    return value is True or str(value).lower() == "true"


def select_plot_rows(rows, selection):
    """Keep the globally chosen LC01 version and the three specified internal rows."""
    config = selection["selected_config"]
    if config not in {"LIT", "S"}:
        raise ValueError("Unknown globally selected external version")
    external = "LC01" if config == "LIT" else "LC01-S"
    if selection["selected_method_id"] != external:
        raise ValueError("Selected external method/config disagree")
    methods = (external, "F02", "A04", "F04")
    selected = {}
    for sequence in SEQUENCES:
        for method in methods:
            found = [row for row in rows if row.get("sequence_id") == sequence
                     and row.get("method_id") == method and _truthy(row.get("main_row"))]
            if len(found) != 1:
                raise ValueError("Missing or duplicate main row: " + sequence + "/" + method)
            row = found[0]
            if "v3" not in str(row.get("evaluator_contract", "")):
                raise ValueError("FIG02S requires the v3 evaluation contract")
            if method == external and row.get("config") != config:
                raise ValueError("Per-sequence external version substitution")
            selected[(sequence, method)] = row
    return methods, selected


def _metric(row, key):
    if row.get("evaluation_status") not in {"COMPLETED","AVAILABLE","AVAILABLE_GEOMETRIC_AUDIT_FAIL"}:
        return None
    try:
        value = float(row[key])
    except (ValueError, TypeError, KeyError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def make_fig02s(rows, selection):
    """Construct, but do not export, the prescribed six-panel grouped-bar figure."""
    from ..publication import style
    from matplotlib.patches import Patch

    methods, selected = select_plot_rows(rows, selection)
    fig, axes = style.new_figure(2, 3, 4.9)
    fig.subplots_adjust(left=.09, right=.985, top=.88, bottom=.085, wspace=.48, hspace=.46)
    colors = {methods[0]: "#009E73", "F02": style.COLORS["F02"],
              "A04": style.COLORS["A04"], "F04": style.COLORS["F04"]}
    hatches = {methods[0]: "..", "F02": "\\\\", "A04": "////", "F04": ""}
    labels = {methods[0]: methods[0], "F02": "Dual-basic (F02)",
              "A04": "Core (A04)", "F04": "Full (F04)"}
    width, centers = .18, np.arange(len(SEQUENCES))
    missing = []
    for index, (ax, (key, label)) in enumerate(zip(axes.flat, METRICS)):
        style.panel_label(ax, chr(ord("a")+index), x=-.18)
        finite = [_metric(row, key) for row in selected.values()]
        ymax = max([value for value in finite if value is not None], default=1) * 1.14
        if ymax <= 0:
            ymax = 1
        for mi, method in enumerate(methods):
            for si, sequence in enumerate(SEQUENCES):
                x = centers[si] + (mi - 1.5) * width
                value = _metric(selected[(sequence,method)], key)
                if value is None:
                    # Missing evidence is not a zero-height bar.
                    ax.text(x, .035*ymax, "n/a", rotation=90, ha="center", va="bottom", fontsize=7)
                    missing.append({"sequence_id":sequence,"method_id":method,"metric":key})
                else:
                    ax.bar(x, value, width=width*.91, color=colors[method], edgecolor="#333333",
                           linewidth=.45, hatch=hatches[method], zorder=3)
        ax.set_xticks(centers, SEQUENCES)
        ax.set_ylabel(label)
        ax.set_ylim(0, ymax)
        ax.grid(axis="y", alpha=.4, zorder=0)
    fig.legend([Patch(facecolor=colors[m], edgecolor="#333333", linewidth=.45, hatch=hatches[m])
                for m in methods], [labels[m] for m in methods], loc="upper center",
               bbox_to_anchor=(.53,.998), ncol=2, columnspacing=1.5, handlelength=1.8, fontsize=7.5)
    return fig, {"methods":list(methods), "selected_config":selection["selected_config"],
                 "missing_metrics":missing,
                 "source_rows":[dict(selected[(s,m)]) for s in SEQUENCES for m in methods]}


def caption(selection, source_rows):
    selected = selection["selected_config"]
    alternative = "S" if selected == "LIT" else "LIT"
    return (
        "FIG02S. Three-sequence solution-level comparison: horizontal and Up RMSE, yaw RMSE and "
        "absolute-error P95, and roll/pitch RMSE. LC01 uses the globally selected " + selected +
        " version, selected by the preregistered BY2 C00 v3 yaw-RMSE rule and used unchanged on all "
        "three sequences; every " + alternative + " row and both EXT05C versions remain in the supplementary tables. "
        "F04 (Full) is the frozen protocol-v2.1 proposed method; hatched A04 (Core) is an ablation. "
        "Errors are evaluated against the fused navigation solution output directly by the commercial "
        "low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2); the estimator under test "
        "never reads it (file-access audit). External primary rows use FILE_START unless the "
        "preregistered initial static-calibration criterion fails; BY2H CONTRACT_START rows are "
        "diagnostics unless that registered static failure promotes the fallback to the primary row. "
        "Geometric-audit failures retain available numerical metrics. Native IMU gaps are dropped without "
        "interpolating samples, holding fabricated samples, or inflating covariance; the chosen "
        "gap-drop convention and the retained LegSA convention are reported separately. BY2O has "
        "57 GNSS2 status float epochs; these are distinct from pAcc-inflated HPPOSECEF epochs. "
        "Coverage uses matched_epoch_count/output_epoch_count for each method's own retained NAV "
        "support, not a common timestamp count; differing sample rates therefore remain explicit. "
        "Unavailable metrics are marked n/a, never zero. No estimator or evaluator is rerun for plotting."
    )


def _write_json(path, payload):
    def scalar(value):
        if isinstance(value,np.generic):
            return value.item()
        raise TypeError(type(value).__name__)
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False, default=scalar)
        handle.write("\n")


def render_fig02s(*, main_table, summary_path, runtime_root, publication_root,
                  code_commit, frozen_before=None):
    """Non-overwriting extension export; caller runs this only after aggregate freeze."""
    from ..publication import style, qa
    from ..publication.protocol_v21_render import figure_checks
    from matplotlib import pyplot as plt

    main_table, summary_path = Path(main_table), Path(summary_path)
    runtime_root, publication_root = Path(runtime_root), Path(publication_root)
    v21 = publication_root / "figures/v21"
    before = frozen_before if frozen_before is not None else frozen_v21_snapshot(v21)
    verify_frozen_v21(before, v21)
    summary = json.loads(summary_path.read_text())
    expected = summary["files_sha256"][main_table.name]
    if isinstance(expected, dict):
        expected = expected["sha256"]
    if _sha(main_table) != expected:
        raise ValueError("Aggregate table changed after final summary")
    with main_table.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    out = runtime_root / "10_FIGURES"
    target, publication_target = out / FIGURE_ID, v21 / FIGURE_ID
    for path in (target, publication_target, out / "HEXT_RENDER_MANIFEST.json", v21 / "HEXT_RENDER_MANIFEST.json"):
        _no_symlink(path)
        if path.exists():
            raise FileExistsError("Non-overwriting FIG02S output already exists: " + str(path))
    out.mkdir(parents=True, exist_ok=True)
    fig, projection = make_fig02s(rows, summary["selection"])
    try:
        checks = qa.check_figure(fig, FIGURE_ID) + figure_checks(fig, FIGURE_ID)
        if not all(bool(row["pass"]) for row in checks):
            raise ValueError("FIG02S figure QA failed: " + json.dumps(checks))
        target.mkdir()
        saved = style.save_figure(fig, target, FIGURE_ID)
        checks.extend(qa.check_png(Path(saved["png"]), FIGURE_ID))
        if not all(bool(row["pass"]) for row in checks):
            raise ValueError("FIG02S raster QA failed: " + json.dumps(checks))
        text = caption(summary["selection"], projection["source_rows"])
        (target / "CAPTION.md").write_text(text + "\n")
        outputs = {ext:{"path":FIGURE_ID+"/"+FIGURE_ID+"."+ext,
                        "sha256":saved[ext+"_sha256"]} for ext in ("png","pdf","svg")}
        manifest = {"figure_id":FIGURE_ID,"status":"RENDERED_QA_PASS_PENDING_VISUAL_REVIEW",
                    "data_mode":"frozen_real_result_visualization","synthetic_data_used":False,
                    "semisynthetic_data_used":False,"trace_used_online":False,"trace_open_count":0,
                    "solver_invocation_count":0,"evaluator_invocation_count":0,"provider_invocation_count":0,
                    "code_commit":code_commit,"main_table_sha256":expected,
                    "summary_sha256":_sha(summary_path),"config_hash":_sha(summary_path),
                    "metric_recomputation_performed":False,"selection":summary["selection"],
                    "caption":text,"qa":checks,"outputs":outputs,
                    "png_width_px":saved["png_width_px"],"png_height_px":saved["png_height_px"],
                    "canvas_width_mm":174.0,"minimum_type_pt":7,"layout":"2x3",
                    "projection":projection,"frozen_v21_before":before}
        _write_json(target / "FIGURE_MANIFEST.json", manifest)
        publication_target.mkdir()
        for path in sorted(target.iterdir()):
            with path.open("rb") as source, (publication_target/path.name).open("xb") as dest:
                shutil.copyfileobj(source,dest)
            if _sha(path) != _sha(publication_target/path.name):
                raise IOError("FIG02S publication copy hash mismatch")
        manifest["frozen_v21_after"] = verify_frozen_v21(before,v21)
        manifest["original_v21_files_byte_unchanged"] = True
        _write_json(out / "HEXT_RENDER_MANIFEST.json",manifest)
        _write_json(v21 / "HEXT_RENDER_MANIFEST.json",manifest)
        return manifest
    finally:
        plt.close(fig)
