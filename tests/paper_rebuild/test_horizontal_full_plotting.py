from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.horizontal_literature.plotting.common import (
    _line_style,
    _semantic_color,
    expected_artifacts,
)
from legsa_gins.paper_rebuild.horizontal_literature.plotting.loaders import (
    MissingSourceField,
    load_frozen_table,
)
from legsa_gins.paper_rebuild.horizontal_literature.plotting.registry import (
    EXPECTED_FAMILY_COUNT,
    PLOT_REGISTRY_ORIGIN,
    load_registry,
    resolve_source,
    validate_registry,
    validate_worker_count,
)
from legsa_gins.paper_rebuild.horizontal_literature.plotting.runner import (
    _write_plot_catalog,
    _write_plot_qa,
    build_parser,
)
from legsa_gins.paper_rebuild.horizontal_literature.plotting.refinements import _short_group
from legsa_gins.paper_rebuild.horizontal_literature.plotting.style import (
    BASELINE_NOTE,
    LAYOUT_PIXELS,
    METHOD_COLORS,
    pixels_for_layout,
)

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "configs/paper_rebuild/horizontal_literature/HORIZONTAL_FULL_PLOT_REGISTRY.csv"


@pytest.fixture(scope="module")
def families():
    return load_registry(REGISTRY)


def test_registry_has_exact_reconstructed_66_family_contract(families):
    assert len(families) == EXPECTED_FAMILY_COUNT == 66
    assert len({family.plot_id for family in families}) == 66
    assert all(family.required for family in families)
    assert {family.registry_origin for family in families} == {PLOT_REGISTRY_ORIGIN}


def test_path_resolution_is_bounded_and_prior_plotting_root_is_forbidden(families, tmp_path):
    family = families[0]
    source = resolve_source(
        family, comparison_root=tmp_path / "comparison", canonical_attempt=tmp_path / "canonical"
    )
    assert source == tmp_path / "comparison" / family.source_file
    forbidden = replace(family, source_file="13_AGGREGATE/../14_FULL_PLOTTING/result.csv")
    with pytest.raises(ValueError):
        validate_registry([forbidden], require_exact_count=False)


def test_primary_method_colors_match_user_contract_and_are_unique():
    expected = {
        "Reference": "#111111",
        "RAW01": "#2F6BFF",
        "RAW02": "#F28E2B",
        "RAW03": "#36A165",
        "EXT04": "#8C8C8C",
        "LC01": "#7B61FF",
        "GINAV": "#D95F02",
        "Hartley": "#009E73",
        "F02": "#7A7A7A",
        "F03": "#4C78A8",
        "A04": "#2CA02C",
        "F04": "#D62728",
    }
    assert {key: METHOD_COLORS[key] for key in expected} == expected
    assert len(set(expected.values())) == len(expected)


def test_4k_and_8k_size_contract():
    assert pixels_for_layout("normal") == (5120, 2880)
    assert pixels_for_layout("dense") == (7680, 4320)
    assert pixels_for_layout("portrait") == (4320, 5760)
    assert pixels_for_layout("square") == (4096, 4096)
    assert min(LAYOUT_PIXELS["panel"]) >= 2304
    assert max(LAYOUT_PIXELS["panel"]) >= 4096


def test_formal_diagnostic_and_canonical_scopes_are_distinct(families):
    by_id = {family.plot_id: family for family in families}
    assert by_id["INT01_FORMAL_C00_RMSE"].scope_label == "FORMAL C00"
    assert by_id["LC10_COMMON_SUPPORT_77_DIAGNOSTIC"].scope_label == "DIAGNOSTIC ONLY"
    assert by_id["C541_01_METHOD_DISTRIBUTION_SUMMARY"].scope_label == "CANONICAL-541"
    assert by_id["HAR08_OBSERVABILITY_RANK_NULLITY"].scope_label == "STRUCTURAL ONLY"


def test_hartley_registry_forbids_absolute_position_and_yaw_rmse(families):
    hartley = [family for family in families if family.plot_id.startswith("HAR")]
    assert len(hartley) == 10
    for family in hartley:
        text = " ".join((family.title, *family.required_fields, *family.y_fields)).lower()
        assert "absolute_position_rmse" not in text
        assert "absolute_yaw_rmse" not in text
    broken = replace(hartley[0], y_fields=("absolute_yaw_rmse_deg",))
    with pytest.raises(ValueError):
        validate_registry([broken], require_exact_count=False)


def test_77_epoch_and_ginav_gap_guards(families):
    by_id = {family.plot_id: family for family in families}
    common = by_id["LC10_COMMON_SUPPORT_77_DIAGNOSTIC"]
    assert common.scope_label == "DIAGNOSTIC ONLY"
    assert "77 epochs" in common.caption
    for family in families:
        if "GINAV" in family.plot_id:
            assert family.allow_gap_fill is False
    broken = replace(by_id["LC07_GINAV_STATUS_TIMELINE"], allow_gap_fill=True)
    with pytest.raises(ValueError):
        validate_registry([broken], require_exact_count=False)


def test_refinement_contract_has_no_forbidden_figure_wording_and_exact_pair_fields(families):
    by_id = {family.plot_id: family for family in families}
    forbidden = (
        "same-source reference",
        "同源参考",
        "fixposition-derived reference",
        "非独立真值",
        "not independent ground truth",
    )
    figure_text = "\n".join(
        family.title + "\n" + family.caption for family in families
    ).lower()
    assert not any(token.lower() in figure_text for token in forbidden)
    for plot_id in (
        "C541_06_A04_F04_PAIRED_DELTA_DISTRIBUTION",
        "C541_07_A04_F04_PAIRED_SCATTER",
    ):
        fields = set(by_id[plot_id].required_fields)
        assert {"comparison", "candidate_method_id", "reference_method_id"} <= fields
    assert by_id["LC08_GINAV_LC_UPDATE_VS_INS_ONLY"].scope_label == "DIAGNOSTIC ONLY"
    assert "diagnostic_group" in by_id["LC08_GINAV_LC_UPDATE_VS_INS_ONLY"].required_fields
    assert all(
        by_id[plot_id].scope_label in {"STRUCTURAL ONLY", "MECHANISM ONLY"}
        for plot_id in (
            "HAR06_GAUGE_EQUIVALENCE_QUANTILES",
            "HAR07_GAUGE_TOLERANCE_NORMALIZED",
            "HAR08_OBSERVABILITY_RANK_NULLITY",
            "HAR09_NONGAUGE_SINGULAR_AND_WEAK_DIRECTIONS",
            "HAR10_TOPOLOGY_NIS_CHI_SQUARE",
        )
    )
    assert "window_id" in by_id["HAR08_OBSERVABILITY_RANK_NULLITY"].required_fields
    label = _short_group({"model": "IDEAL_BIAS_FREE", "window_id": "WIN002", "contact_count": 2})
    assert label == "Ideal W2 C=2"
    assert "?" not in label


def test_ext01_ext02_and_hard_baseline_claim_notes(families):
    by_id = {family.plot_id: family for family in families}
    assert "global optimum certified integer solutions" in by_id["RAW03_STATE_VOCABULARY_SMALL_MULTIPLES"].caption.lower()
    assert "Accepted wrapped solution is not ambiguity correctness" in by_id["RAW07_NATIVE_STATE_TIMELINES"].caption
    assert by_id["RAW09_BASELINE_LENGTH_TIME_SERIES"].caption == BASELINE_NOTE


def test_current_c00_and_541_mean_are_not_same_family_or_source(families):
    internal = [family for family in families if family.plot_id.startswith("INT")]
    canonical = [family for family in families if family.plot_id.startswith("C541")]
    assert all(family.scope_label == "CANONICAL-541" for family in canonical)
    assert not any(family.scope_label == "CANONICAL-541" for family in internal)
    assert all("14_FULL_PLOTTING" not in family.source_file for family in families)
    assert all("HORIZONTAL18_V2" not in family.source_file for family in families)
    assert all("final_v23" not in family.source_file.lower() for family in families)


def test_worker_cap_and_ten_second_progress_parser_contract():
    assert validate_worker_count(1) == 1
    assert validate_worker_count(16) == 16
    assert validate_worker_count(24) == 24
    for value in (0, 25, -1, True):
        with pytest.raises(ValueError):
            validate_worker_count(value)
    defaults = build_parser().parse_args(
        [
            "--input-root", "i",
            "--canonical-attempt", "c",
            "--output-root", "o",
            "--registry", "r",
        ]
    )
    assert defaults.workers == 16
    assert defaults.progress_interval == 10


def test_output_naming_and_formats_are_exact(families, tmp_path):
    family = families[0]
    outputs = expected_artifacts(tmp_path, family, ("png", "pdf", "svg"))
    assert len(outputs) == (1 + family.panel_count) * 3
    names = {path.name for path in outputs}
    assert f"{family.plot_id}_COMPOSITE.png" in names
    assert f"{family.plot_id}_PANEL_A.pdf" in names
    assert f"{family.plot_id}_PANEL_B.svg" in names


def test_method_specific_output_directories_are_populated_and_styles_are_fixed(families):
    required_groups = {
        "02_EXT01_CLAMBDA",
        "03_EXT02_CWLS",
        "04_EXT03_YANG2024",
        "07_LC01_PAVLASEK",
        "08_LC02_GINAV",
    }
    assert required_groups <= {family.output_group for family in families}
    by_id = {family.plot_id: family for family in families}
    assert _semantic_color("F04", by_id["INT01_FORMAL_C00_RMSE"], 0) == "#D62728"
    assert _semantic_color("EXT04", by_id["EXT04_01_FAR_PAR_INVALID_FLOW"], 0) == "#8C8C8C"
    assert _line_style("Reference", 0) == "--"
    assert _line_style("EXT04", 0) == "--"


def test_header_only_and_all_null_required_fields_skip_honestly(tmp_path):
    header_only = tmp_path / "header_only.csv"
    header_only.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(MissingSourceField, match="zero data rows"):
        load_frozen_table(header_only, ("a",))
    all_null = tmp_path / "all_null.csv"
    all_null.write_text("a,b\nNA,1\n,2\n", encoding="utf-8")
    with pytest.raises(MissingSourceField, match="no populated finite value"):
        load_frozen_table(all_null, ("a", "b"))


def test_entrypoint_contains_no_solver_evaluator_or_matlab_execution_imports():
    paths = [
        REPO / "scripts/paper_rebuild/run_horizontal_full_plotting.py",
        REPO / "src/legsa_gins/paper_rebuild/horizontal_literature/plotting/runner.py",
    ]
    forbidden = (
        "import subprocess",
        "matlab.engine",
        "evaluate_nav_trace",
        "run_canonical541",
        "by2_algorithm_runner",
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert not any(token in text for token in forbidden)


def test_catalog_and_png_qa_are_deterministic_lightweight_outputs(tmp_path):
    from PIL import Image
    import csv

    group = tmp_path / "10_INTERNAL_C00"
    group.mkdir()
    assets = []
    plot_id = "RAW11_CONTINUITY_AND_GAP_PANEL"
    for component in ("COMPOSITE", "PANEL_A", "PANEL_B"):
        for suffix in ("png", "pdf", "svg"):
            path = group / f"{plot_id}_{component}.{suffix}"
            assets.append(str(path))
            if suffix == "png":
                Image.new("RGB", (4096, 16), "white").save(path)
    gallery = tmp_path / "99_GALLERY"
    gallery.mkdir()
    Image.new("RGB", (4096, 16), "white").save(gallery / "ALL_PLOTS_CONTACT_SHEET_4K.png")
    records = [{
        "plot_id": plot_id,
        "output_group": "10_INTERNAL_C00",
        "scope_label": "FORMAL C00",
        "title": "Internal formal C00 RMSE",
        "status": "COMPLETE_RESUMED_VALID",
        "source_file": "/frozen/source.csv",
        "artifacts": assets,
    }]
    catalog_path, catalog_rows = _write_plot_catalog(tmp_path, records)
    qa_path, qa_counts = _write_plot_qa(tmp_path, records)
    assert catalog_rows == 1
    catalog = list(csv.DictReader(catalog_path.open()))
    assert catalog[0]["composite_png"].endswith("_COMPOSITE.png")
    assert catalog[0]["panel_png_assets"].count(".png") == 2
    assert "_COMPOSITE.png" not in catalog[0]["panel_png_assets"]
    assert qa_counts == {"png_rows": 4, "failed_rows": 0}
    qa = list(csv.DictReader(qa_path.open()))
    assert all(row["status"] == "PASS" for row in qa)
    assert {row["asset_type"] for row in qa} == {"PLOT_FAMILY", "CONTACT_SHEET"}
