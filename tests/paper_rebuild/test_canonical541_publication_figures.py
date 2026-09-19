"""Tests for the Canonical-541 publication-figure package (AGENTS sections 12b, 13, 14)."""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from legsa_gins.paper_rebuild.publication import canonical541_figures as figs  # noqa: E402
from legsa_gins.paper_rebuild.publication import qa, style  # noqa: E402
from legsa_gins.paper_rebuild.publication.loaders import load_display_names, load_registry  # noqa: E402


def test_registry_and_renderers_agree():
    reg = load_registry()
    assert set(reg["figure_id"]) == set(figs.FIGURES)
    assert set(reg["role"]) <= {"main_candidate", "supplementary"}
    assert reg["figure_id"].is_unique


def test_display_names_cover_registry_methods():
    names = load_display_names()
    assert {"F01", "F02", "F03", "A04", "F04"} <= set(names["methods"])
    assert names["methods"]["F03"]["role"] == "ablation_row"
    assert names["reference_label"] == "Truth"
    verdicts = {c["verdict"] for c in names["representative_cases"]}
    assert verdicts == {"favourable", "unfavourable"}  # both must be shown together


def test_png_dpi_meets_minimum_width():
    fig, _ = style.new_figure(1, 1, 2.0)
    assert style.png_dpi(fig) * fig.get_figwidth() >= style.MIN_PNG_WIDTH_PX
    plt.close(fig)


def test_qa_flags_forbidden_text_and_missing_panel_labels():
    fig, axes = style.new_figure(1, 2, 2.0)
    axes[0][0].plot([0, 1], [0, 1]); axes[0][0].set_ylabel("Yaw RMSE (°)")
    axes[0][1].plot([0, 1], [1, 0]); axes[0][1].set_ylabel("Horizontal RMSE")  # no unit
    fig.suptitle("DIAGNOSTIC ONLY /mnt/g/RUN_00001.csv")
    rows = {r["check"]: r for r in qa.check_figure(fig, "synthetic")}
    assert rows["no_forbidden_text"]["pass"] is False
    assert rows["no_suptitle"]["pass"] is False
    assert rows["panel_labels"]["pass"] is False
    assert rows["axis_units"]["pass"] is False
    plt.close(fig)


def test_qa_passes_a_compliant_figure(tmp_path):
    fig, axes = style.new_figure(1, 2, 2.0)
    for ax, letter in zip(axes[0], "ab"):
        ax.plot([0, 1], [0, 1]); ax.set_ylabel("Yaw RMSE (°)"); ax.set_xlabel("Time (s)")
        style.panel_label(ax, letter)
    assert all(r["pass"] for r in qa.check_figure(fig, "ok"))
    info = style.save_figure(fig, tmp_path, "ok")
    assert info["png_width_px"] >= style.MIN_PNG_WIDTH_PX
    assert all(r["pass"] for r in qa.check_png(Path(info["png"]), "ok"))
    plt.close(fig)


def test_reference_trace_uses_frozen_time_origin_and_yaw_formula(tmp_path):
    from legsa_gins.paper_rebuild.publication.loaders import evaluation_time_origin, load_reference_trace

    origin = evaluation_time_origin()
    assert origin == 1772784000.0
    p = tmp_path / "trace.csv"
    p.write_text("time,lat,lon,height,yaw,pitch,roll\n"
                 "1772784066.0,40.0,116.0,41.0,90.0,0,0\n"
                 "1772784066.0,40.0,116.0,41.0,90.0,0,0\n"
                 "1772784067.0,40.0,116.0,41.0,-135.0,0,0\n")
    tr = load_reference_trace(p, origin)
    assert list(tr["t"]) == [66.0, 67.0]  # duplicate timestamp dropped, relative time = time - origin
    assert list(tr["yaw_ned_deg"]) == [0.0, 225.0]  # wrap360(90 deg - yaw_ENU)


def test_duplicate_detection_uses_perceptual_hash():
    a = np.zeros(256, dtype=np.uint8); b = a.copy(); b[:3] = 1; c = np.ones(256, dtype=np.uint8)
    pairs = qa.duplicate_pairs({"x": a, "y": b, "z": c})
    assert pairs == [("x", "y", 3)]


@pytest.mark.skipif(not (os.environ.get("LEGSA_C541_ATTEMPT_ROOT") and os.environ.get("LEGSA_C541_DERIVED_DIR")),
                    reason="LEGSA_C541_ATTEMPT_ROOT / LEGSA_C541_DERIVED_DIR not set")
def test_smoke_render_from_frozen_tables(tmp_path):
    from legsa_gins.paper_rebuild.publication.loaders import load_bundle

    bundle = load_bundle(Path(os.environ["LEGSA_C541_ATTEMPT_ROOT"]), Path(os.environ["LEGSA_C541_DERIVED_DIR"]),
                         handoff_subset=bool(os.environ.get("LEGSA_C541_HANDOFF_SUBSET")),
                         trace_path=os.environ.get("LEGSA_C541_TRACE_PATH"))
    for fid in ("MFIG00_reference_comparison", "MFIG01_matrix_overview", "MFIG06_mechanism"):
        fig, caption = figs.FIGURES[fid](bundle)
        assert all(r["pass"] for r in qa.check_figure(fig, fid)), fid
        assert any(k in caption for k in ("541", "Source-Aware", "reference"))
        plt.close(fig)
