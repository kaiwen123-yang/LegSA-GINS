"""Synthetic in-memory figure guard tests; never real-data evidence."""
import hashlib

import pytest

from legsa_gins.paper_rebuild.hext.readonly_figures import (
    AMENDMENT_REASON, LC01_WORDING, MAIN_METHODS, METRICS, SEGMENT_METHODS, STARTS,
    _pinned_bytes, caption, frozen_snapshot, make_fig02s, make_fig02sb, select_rows,
    select_segment_rows,
)


def fixture_rows():
    rows = []
    for sequence, start in STARTS.items():
        for index, method in enumerate((*MAIN_METHODS, "LC01-S")):
            rows.append(dict(sequence_id=sequence, method_id=method,
                             config="S" if method == "LC01-S" else "LIT",
                             start_convention=start, evaluator_contract="evaluator_contract_v3",
                             manuscript_row=method != "LC01-S", evaluation_status="AVAILABLE",
                             **{metric: index+1. for metric, _ in METRICS}))
    selection = dict(selected_config="LIT", selected_method_id="LC01",
                     amended_after_results_seen=True, paper_primary_starts=STARTS)
    return rows, selection


def test_literature_selection_rejects_s_main_row_and_wrong_by2h_start():
    rows, selection = fixture_rows()
    assert len(select_rows(rows, selection)) == 15
    rows[9]["manuscript_row"] = True
    with pytest.raises(ValueError, match="supplementary"):
        select_rows(rows, selection)
    rows[9]["manuscript_row"] = False
    rows[5]["start_convention"] = "FILE_START"
    with pytest.raises(ValueError, match="Missing"):
        select_rows(rows, selection)


def test_s_markers_are_hollow_and_share_literature_bar_centres():
    from matplotlib import pyplot as plt
    rows, selection = fixture_rows()
    fig, projection = make_fig02s(rows, selection)
    try:
        assert len(projection["markers"]) == 18
        for ax in fig.axes:
            assert len(ax.patches) == 12 and len(ax.lines) == 3
            for bar, marker in zip(ax.patches[:3], ax.lines):
                assert marker.get_xdata()[0] == pytest.approx(bar.get_x() + bar.get_width()/2)
                assert marker.get_markerfacecolor() == "none"
            assert ax.get_ylim()[1] > 5  # includes S even when above every literature bar
    finally:
        plt.close(fig)


def test_segment_selection_keeps_only_v3_and_shared_metric_scales():
    from matplotlib import pyplot as plt
    rows = [dict(sequence_id="BY2O", method_id=method, segment_id=segment,
                 evaluator_contract=evaluator, status="AVAILABLE", h_rmse_m=value,
                 yaw_rmse_deg=value*10)
            for segment, value in (("occlusion_primary", 1.), ("occlusion_secondary", 2.))
            for method in SEGMENT_METHODS
            for evaluator in ("evaluator_contract_v2", "evaluator_contract_v3")]
    assert len(select_segment_rows(rows)) == 10
    fig, _ = make_fig02sb(rows)
    try:
        assert fig.axes[0].get_ylim() == fig.axes[2].get_ylim()
        assert fig.axes[1].get_ylim() == fig.axes[3].get_ylim()
    finally:
        plt.close(fig)
    rows.append(dict(rows[1]))
    with pytest.raises(ValueError, match="duplicate"):
        select_segment_rows(rows)


def test_pinned_inputs_reject_changed_bytes_and_symlinks(tmp_path):
    source = tmp_path / "input.csv"
    source.write_bytes(b"a,b\n1,2\n")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    assert _pinned_bytes(source, expected) == source.read_bytes()
    source.write_bytes(b"a,b\n3,4\n")
    with pytest.raises(ValueError, match="identity"):
        _pinned_bytes(source, expected)
    link = tmp_path / "link.csv"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="symlinks"):
        _pinned_bytes(link, expected)


def test_original_snapshot_excludes_exactly_authorized_extensions(tmp_path):
    manifest = tmp_path / "RENDER_MANIFEST.json"
    manifest.write_bytes(b"frozen")
    original = tmp_path / "FIG01"
    original.mkdir()
    (original / "FIG01.png").write_bytes(b"original")
    kwargs = dict(expected_render_sha256=hashlib.sha256(b"frozen").hexdigest(), expected_figure_count=1)
    before = frozen_snapshot(tmp_path, **kwargs)
    for name in ("FIG02S", "FIG02S-b"):
        extension = tmp_path / name
        extension.mkdir()
        (extension / "data").write_bytes(b"extension")
    (tmp_path / "HEXT_RENDER_MANIFEST.json").write_bytes(b"extension")
    assert frozen_snapshot(tmp_path, **kwargs) == before
    (original / "FIG01.png").write_bytes(b"changed")
    assert frozen_snapshot(tmp_path, **kwargs) != before
    (tmp_path / "unauthorized_extension").mkdir()
    with pytest.raises(ValueError, match="directory count"):
        frozen_snapshot(tmp_path, **kwargs)


def test_captions_disclose_exact_amendment_and_lc01_noise_wording():
    for figure_id in ("FIG02S", "FIG02S-b"):
        text = caption(figure_id)
        assert AMENDMENT_REASON in text and LC01_WORDING in text
        assert "amended_after_results_seen=true" in text
        assert "S has mixed effects" in text and "CONTRACT_START" in text
