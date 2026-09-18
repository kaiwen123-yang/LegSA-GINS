"""H-EXT-04L publication projections of pinned, already evaluated result tables.

No native, evaluator, provider, NAV, IMU, status or trace payload is opened here.
The original FIG02S edition is copied and verified before the authorized update.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import shutil

import numpy as np

from .figures import METRICS, RENDER_SHA256, SEQUENCES, _metric, _no_symlink, _sha, _write_json

FIGURE_IDS = ("FIG02S", "FIG02S-b")
MAIN_METHODS = ("LC01", "F02", "A04", "F04")
SEGMENT_METHODS = ("F02", "A04", "F04", "LC01", "LC01-S")
STARTS = {"BY2": "FILE_START", "BY2H": "CONTRACT_START", "BY2O": "FILE_START"}
SEGMENTS = (("occlusion_primary", "Primary: 3369.94–3411.95 s"),
            ("occlusion_secondary", "Secondary: 3495.94–3508.94 s"))
AMENDMENT_REASON = ("预注册规则按 BY2 航向选出 S，三序列结果显示 S 对基线并非一致有利"
                    "（BY2O 航向 4.016 对 2.454，三序列 roll/pitch 均差），改用发表配置")
LC01_WORDING = "IMU 过程噪声取自原文实验设定，未针对本 IMU 标定"


def frozen_snapshot(v21_root, *, expected_render_sha256=RENDER_SHA256,
                    expected_figure_count=28):
    """Hash every frozen v2.1 file; exclude exactly the two authorized extensions."""
    root = Path(v21_root)
    _no_symlink(root)
    if _sha(root / "RENDER_MANIFEST.json") != expected_render_sha256:
        raise ValueError("Frozen v2.1 RENDER_MANIFEST identity mismatch")
    directories, files = [], {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] in FIGURE_IDS or relative.as_posix() == "HEXT_RENDER_MANIFEST.json":
            continue
        _no_symlink(path)
        if path.is_dir() and len(relative.parts) == 1:
            directories.append(relative.as_posix())
        elif path.is_file():
            files[relative.as_posix()] = _sha(path)
    if len(directories) != expected_figure_count:
        raise ValueError("Frozen figure directory count differs from 28")
    return {"render_manifest_sha256": expected_render_sha256,
            "figure_directory_count": len(directories), "figure_directories": directories,
            "file_count": len(files), "files_sha256": files}


def _pinned_bytes(path, expected_sha256):
    import hashlib
    path = Path(path)
    _no_symlink(path)
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("Pinned figure input identity mismatch: " + path.name)
    return payload


def _true(value):
    return value is True or str(value).lower() == "true"


def select_rows(rows, selection):
    """Literature bars and S markers use one declared start per sequence."""
    if (selection.get("selected_config") != "LIT"
            or selection.get("selected_method_id") != "LC01"
            or not _true(selection.get("amended_after_results_seen"))
            or selection.get("paper_primary_starts") != STARTS):
        raise ValueError("H-EXT-04L manuscript amendment must be explicit")
    selected = {}
    for sequence in SEQUENCES:
        for method in (*MAIN_METHODS, "LC01-S"):
            candidates = [r for r in rows if r.get("sequence_id") == sequence
                          and r.get("method_id") == method
                          and r.get("evaluator_contract") == "evaluator_contract_v3"
                          and (method not in {"LC01", "LC01-S"}
                               or r.get("start_convention") == STARTS[sequence])]
            if len(candidates) != 1:
                raise ValueError("Missing or duplicate amended row: " + sequence + "/" + method)
            row = candidates[0]
            if method in MAIN_METHODS and not _true(row.get("manuscript_row")):
                raise ValueError("Literature/main bar lacks manuscript designation")
            if method == "LC01-S" and _true(row.get("manuscript_row")):
                raise ValueError("S must be a supplementary marker")
            if method in {"LC01", "LC01-S"} and row.get("config") != ("LIT" if method == "LC01" else "S"):
                raise ValueError("External method/config disagree")
            selected[(sequence, method)] = row
    return selected


def _colors():
    from ..publication import style
    return {"LC01": "#009E73", "LC01-S": "#009E73", **style.COLORS}


def _hatches():
    return {"LC01": "..", "LC01-S": "", "F02": "\\\\", "A04": "////", "F04": ""}


def make_fig02s(rows, selection):
    from ..publication import style
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    selected = select_rows(rows, selection)
    fig, axes = style.new_figure(2, 3, 4.9)
    fig.subplots_adjust(left=.09, right=.985, top=.86, bottom=.085, wspace=.48, hspace=.46)
    colors, hatches = _colors(), _hatches()
    labels = {"LC01": "LC01 (literature)", "F02": "Dual-basic (F02)",
              "A04": "Core (A04)", "F04": "Full (F04)"}
    centers, width = np.arange(len(SEQUENCES)), .18
    missing, markers = [], []
    for panel, (ax, (metric, label)) in enumerate(zip(axes.flat, METRICS)):
        style.panel_label(ax, chr(ord("a") + panel), x=-.18)
        finite = [_metric(row, metric) for row in selected.values()]
        ymax = max([value for value in finite if value is not None], default=1) * 1.14 or 1
        for mi, method in enumerate(MAIN_METHODS):
            for si, sequence in enumerate(SEQUENCES):
                x = centers[si] + (mi - 1.5) * width
                value = _metric(selected[(sequence, method)], metric)
                if value is None:
                    ax.text(x, .035 * ymax, "n/a", rotation=90, ha="center", va="bottom", fontsize=7)
                    missing.append(dict(sequence_id=sequence, method_id=method, metric=metric))
                else:
                    ax.bar(x, value, width=width*.91, color=colors[method], edgecolor="#333333",
                           linewidth=.45, hatch=hatches[method], zorder=3)
                if method == "LC01":
                    s_value = _metric(selected[(sequence, "LC01-S")], metric)
                    if s_value is None:
                        missing.append(dict(sequence_id=sequence, method_id="LC01-S", metric=metric))
                        ax.text(x, .09*ymax, "S: n/a", rotation=90, ha="center", va="bottom", fontsize=7)
                    else:
                        # Hollow diamond at precisely the literature bar centre; no offset or S bar.
                        ax.plot([x], [s_value], marker="D", markersize=4.5, markerfacecolor="none",
                                markeredgecolor="#111111", markeredgewidth=.95, linestyle="none", zorder=5)
                        markers.append(dict(sequence_id=sequence, metric=metric, x=float(x), y=s_value))
        ax.set_xticks(centers, SEQUENCES)
        ax.set_ylabel(label)
        ax.set_ylim(0, ymax)
        ax.grid(axis="y", alpha=.4, zorder=0)
    handles = [Patch(facecolor=colors[m], edgecolor="#333333", linewidth=.45, hatch=hatches[m])
               for m in MAIN_METHODS]
    handles.append(Line2D([], [], linestyle="none", marker="D", markersize=4.5,
                          markerfacecolor="none", markeredgecolor="#111111"))
    fig.legend(handles, [labels[m] for m in MAIN_METHODS] + ["LC01-S (supplement)"],
               loc="upper center", bbox_to_anchor=(.53,.998), ncol=3,
               columnspacing=1.2, handlelength=1.8, fontsize=7.5)
    return fig, {"methods": list(MAIN_METHODS), "selected_config": "LIT",
                 "supplementary_marker": "LC01-S", "markers": markers,
                 "missing_metrics": missing, "source_rows": list(selected.values())}


def select_segment_rows(rows):
    selected = {}
    for segment, _ in SEGMENTS:
        for method in SEGMENT_METHODS:
            candidates = [row for row in rows if row.get("method_id") == method
                          and row.get("segment_id") == segment
                          and row.get("evaluator_contract") == "evaluator_contract_v3"
                          and row.get("sequence_id", "BY2O") == "BY2O"]
            if len(candidates) != 1:
                raise ValueError("Missing or duplicate segment row: " + segment + "/" + method)
            row = dict(candidates[0])
            row["evaluation_status"] = row.get("evaluation_status", row.get("status"))
            selected[(segment, method)] = row
    return selected


def make_fig02sb(rows):
    from ..publication import style

    selected = select_segment_rows(rows)
    fig, axes = style.new_figure(2, 2, 4.15)
    fig.subplots_adjust(left=.095, right=.985, top=.92, bottom=.08, wspace=.30, hspace=.56)
    colors, hatches = _colors(), _hatches()
    metrics = (("yaw_rmse_deg", "Yaw RMSE (°)"), ("h_rmse_m", "Horizontal RMSE (m)"))
    missing = []
    for col, (metric, label) in enumerate(metrics):
        values = [_metric(row, metric) for row in selected.values()]
        ymax = max([value for value in values if value is not None], default=1) * 1.15 or 1
        for ri, (segment, segment_label) in enumerate(SEGMENTS):
            ax = axes[ri, col]
            style.panel_label(ax, chr(ord("a") + ri*2 + col), x=-.13)
            ax.text(.12, 1.045, segment_label, transform=ax.transAxes, fontsize=7,
                    ha="left", va="bottom")
            for i, method in enumerate(SEGMENT_METHODS):
                value = _metric(selected[(segment, method)], metric)
                if value is None:
                    ax.text(i, .035*ymax, "n/a", ha="center", va="bottom", fontsize=7)
                    missing.append(dict(segment_id=segment, method_id=method, metric=metric))
                else:
                    ax.bar(i, value, width=.65,
                           facecolor="none" if method == "LC01-S" else colors[method],
                           edgecolor=colors[method] if method == "LC01-S" else "#333333",
                           linewidth=.8 if method == "LC01-S" else .45,
                           hatch=hatches[method], zorder=3)
            ax.set_xticks(range(len(SEGMENT_METHODS)), SEGMENT_METHODS)
            ax.set_ylabel(label)
            ax.set_ylim(0, ymax)
            ax.grid(axis="y", alpha=.4, zorder=0)
    return fig, {"methods": list(SEGMENT_METHODS), "segments": [s for s, _ in SEGMENTS],
                 "common_y_limits_by_metric": True, "missing_metrics": missing,
                 "source_rows": list(selected.values())}


def caption(figure_id):
    common = ("LC01 denotes the published literature configuration. " + LC01_WORDING + "。 "
              "The preregistered BY2 yaw rule selected S; the manuscript row was amended after "
              "seeing all three sequences (amended_after_results_seen=true). " + AMENDMENT_REASON + "。 "
              "S has mixed effects and is retained in supplementary results. "
              "BY2 and BY2O use FILE_START; both BY2H LC01 configurations use CONTRACT_START. "
              "BY2H geometric-audit failures remain explicitly flagged in the source tables; "
              "available numerical errors are not removed. "
              "Errors use the frozen evaluation against the fused navigation solution output "
              "directly by the commercial low-cost dual-antenna GNSS/INS receiver "
              "(Fixposition Vision-RTK 2); the estimator under test never reads it (file-access audit). "
              "Different methods retain their own full-rate evaluated epoch support. "
              "No estimator or evaluator is rerun and no trace is read for this figure.")
    if figure_id == "FIG02S":
        return ("FIG02S (v2). Three-sequence horizontal and Up RMSE, yaw RMSE and absolute-error P95, "
                "and roll/pitch RMSE. LC01 literature bars are overlaid by hollow diamonds for "
                "LC01-S at the same bar positions. F04 (Full) is the frozen protocol-v2.1 method; "
                "A04 (Core) is an ablation. " + common)
    return ("FIG02S-b. BY2O primary (3369.94–3411.95 s) and secondary (3495.94–3508.94 s) "
            "closed occlusion intervals: yaw and horizontal RMSE for F02, A04, F04, LC01 and LC01-S. "
            "Axes share limits within each metric. S is shown as an unfilled bar. " + common)


def _copy_verified(source, target):
    _no_symlink(source)
    _no_symlink(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    if _sha(source) != _sha(target):
        raise IOError("Figure copy identity mismatch")


def render_closeout(*, main_table, summary_path, segment_table, main_sha256,
                    summary_sha256, segment_sha256, output_root, publication_root,
                    code_commit, publish=False):
    """Export pinned tables and optionally replace the authorized H-EXT extension.

    All frozen figure files are checked before/after; publication updates start only
    once both newly exported figures pass automatic QA. Visual review is separate.
    """
    from ..publication import style, qa
    from ..publication import protocol_v21_render
    from ..publication.protocol_v21_render import figure_checks
    from matplotlib import pyplot as plt

    main_table, summary_path, segment_table = map(Path, (main_table, summary_path, segment_table))
    summary = json.loads(_pinned_bytes(summary_path, summary_sha256))
    main_payload = _pinned_bytes(main_table, main_sha256)
    segment_payload = _pinned_bytes(segment_table, segment_sha256)
    declared = summary["files_sha256"][main_table.name]
    if isinstance(declared, dict):
        declared = declared["sha256"]
    if declared != main_sha256:
        raise ValueError("Summary/main-table identity disagreement")
    rows = list(csv.DictReader(io.StringIO(main_payload.decode("utf-8"))))
    segments = list(csv.DictReader(io.StringIO(segment_payload.decode("utf-8"))))
    selection = summary["selection"]
    code_root = Path(__file__).resolve().parents[4]
    renderer_files = [Path(__file__), Path(__file__).with_name("figures.py"),
                      Path(style.__file__), Path(qa.__file__), Path(protocol_v21_render.__file__)]
    source_hashes = {"<CODE_ROOT>/" + path.relative_to(code_root).as_posix(): _sha(path)
                     for path in renderer_files}
    v21 = Path(publication_root) / "figures/v21"
    before = frozen_snapshot(v21)
    out = Path(output_root) / "figures"
    _no_symlink(out)
    if out.exists():
        raise FileExistsError("Closeout figure output already exists")
    out.mkdir(parents=True)
    provenance = dict(data_mode="frozen_real_result_visualization", synthetic_data_used=False,
                      semisynthetic_data_used=False, trace_used_online=False, trace_open_count=0,
                      native_invocation_count=0, solver_invocation_count=0,
                      evaluator_invocation_count=0, provider_invocation_count=0,
                      raw_payload_open_count=0, code_commit=code_commit, config_hash=summary_sha256,
                      renderer_source_sha256=source_hashes,
                      main_table_sha256=main_sha256, summary_sha256=summary_sha256,
                      segment_table_sha256=segment_sha256, metric_recomputation_performed=False)
    manifests = {}
    for figure_id, drawer in (("FIG02S", lambda: make_fig02s(rows, selection)),
                               ("FIG02S-b", lambda: make_fig02sb(segments))):
        fig, projection = drawer()
        try:
            checks = qa.check_figure(fig, figure_id) + figure_checks(fig, figure_id)
            if not all(bool(row["pass"]) for row in checks):
                raise ValueError("Figure QA failed: " + json.dumps(checks))
            target = out / figure_id
            saved = style.save_figure(fig, target, figure_id)
            checks += qa.check_png(Path(saved["png"]), figure_id)
            if not all(bool(row["pass"]) for row in checks):
                raise ValueError("Raster QA failed: " + json.dumps(checks))
            text = caption(figure_id)
            (target / "CAPTION.md").write_text(text + "\n", encoding="utf-8")
            manifest = dict(provenance, figure_id=figure_id,
                            status="RENDERED_QA_PASS_PENDING_VISUAL_REVIEW", visual_qa="PENDING",
                            selection=selection, projection=projection, caption=text, qa=checks,
                            outputs={ext: {"path": figure_id + "/" + figure_id + "." + ext,
                                           "sha256": saved[ext + "_sha256"]}
                                     for ext in ("png", "pdf", "svg")},
                            png_width_px=saved["png_width_px"], png_height_px=saved["png_height_px"],
                            canvas_width_mm=174.0, minimum_type_pt=7,
                            layout="2x3" if figure_id == "FIG02S" else "2x2")
            _write_json(target / "FIGURE_MANIFEST.json", manifest)
            # A previous edition's visual PASS must never survive beside new pixels.
            _write_json(target / (figure_id + "_VISUAL_QA.json"),
                        {"task": "H-EXT-04L", "figure_id": figure_id, "status": "PENDING",
                         "png_sha256": saved["png_sha256"], "reviewer": None,
                         "note": "New edition requires independent rendered-image inspection"})
            manifests[figure_id] = manifest
        finally:
            plt.close(fig)
    preservation = {}
    if publish:
        # Preserve the earlier extension byte-for-byte before touching its files.
        preserve = out / "previous_H_EXT_03"
        for name in ("FIG02S", "HEXT_RENDER_MANIFEST.json"):
            source = v21 / name
            _no_symlink(source)
            if not source.exists():
                raise FileNotFoundError("Required original extension is absent: " + name)
            paths = sorted(source.rglob("*")) if source.is_dir() else [source]
            for path in paths:
                _no_symlink(path)
                if path.is_file():
                    relative = path.relative_to(v21)
                    _copy_verified(path, preserve / relative)
                    preservation[relative.as_posix()] = _sha(path)
        if (v21 / "FIG02S-b").exists():
            raise FileExistsError("FIG02S-b already exists; no implicit overwrite")
        for figure_id in FIGURE_IDS:
            publication_target = v21 / figure_id
            publication_target.mkdir(exist_ok=(figure_id == "FIG02S"))
            for source in sorted((out / figure_id).iterdir()):
                target = publication_target / source.name
                _no_symlink(target)
                if target.exists() and target.relative_to(v21).as_posix() not in preservation:
                    raise FileExistsError("Unpreserved publication file would be overwritten")
                with source.open("rb") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                if _sha(source) != _sha(target):
                    raise IOError("Published figure hash mismatch")
    after = frozen_snapshot(v21)
    if before != after:
        raise ValueError("Original v2.1 figure archive changed")
    for path, expected in ((main_table, main_sha256), (summary_path, summary_sha256),
                            (segment_table, segment_sha256)):
        if _sha(path) != expected:
            raise ValueError("Figure input changed during rendering")
    result = dict(provenance, schema_version="hext.render.v2", task="H-EXT-04L",
                  status="RENDERED_QA_PASS_PENDING_VISUAL_REVIEW", visual_qa="PENDING",
                  figures=manifests, publication_updated=publish,
                  selection=selection, frozen_v21_before=before, frozen_v21_after=after,
                  original_v21_files_byte_unchanged=True, preserved_previous_extension=preservation,
                  preserved_previous_location="figures/previous_H_EXT_03")
    _write_json(out / "HEXT_RENDER_MANIFEST.json", result)
    if publish:
        target = v21 / "HEXT_RENDER_MANIFEST.json"
        with (out / "HEXT_RENDER_MANIFEST.json").open("rb") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        if _sha(out / "HEXT_RENDER_MANIFEST.json") != _sha(target):
            raise IOError("Publication render manifest hash mismatch")
    return result
