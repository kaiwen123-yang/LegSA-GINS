import hashlib
import json

import pytest

from legsa_gins.paper_rebuild.canonical541.plots import (
    FIGURE_SPECS, FigureQAError, _heatmap_figure, _recovery_figure,
    _source_aware_figure, render_diagnostic_figures,
)


def _tables():
    full = []
    for method_index in range(1, 5):
        method = f"F{method_index:02d}"
        for dtype_index in range(1, 61):
            full.append({
                "method_id": method, "case_id": f"D{dtype_index:02d}_seed_00",
                "degradation_type_id": f"D{dtype_index:02d}",
                "case_family": f"family_{(dtype_index-1)//10}", "evaluable": True,
                "yaw_rmse_deg": dtype_index / 10 + method_index / 100,
                "horizontal_rmse_m": dtype_index / 20 + method_index / 100,
                "up_rmse_m": dtype_index / 30 + method_index / 100,
            })
    ablation = [{"method_id": f"A{method:02d}", "case_id": f"D{dtype:02d}_seed_00"}
                for method in range(1, 10) for dtype in range(1, 61)]
    comparisons = ("F04_vs_F03", "F03_vs_F02", "F02_vs_F01", "A01_vs_A03",
                   "A01_vs_A04", "A01_vs_A05", "A01_vs_A06", "A01_vs_A07")
    paired = [{"comparison": comparison, "metric": "yaw_rmse_deg",
               "degradation_type_id": f"D{dtype:02d}", "case_family": f"family_{(dtype-1)//10}",
               "paired_delta_left_minus_right": (dtype % 5 - 2) / 20}
              for comparison in comparisons for dtype in range(1, 61)]
    recovery = [{"method_id": method, "degradation_type_id": dtype,
                 "post_median": 0.3 + index/100, "time_to_return_s": 2 + index}
                for index, (method, dtype) in enumerate((
                    (method, dtype) for dtype in ("D58", "D60") for method in ("F01", "F02", "F03", "F04")
                ))]
    scheme = [{"method_id": method, "yaw_normal": 100, "yaw_downweight": 5,
               "yaw_reject": 2, "yaw_accept": 105} for method in ("F03", "F04")]
    source = [{"method_id": method, "source": "raw_doppler",
               "mechanism_evaluable": True,
               "perturbed_R_scale_changed_count": 20,
               "unperturbed_R_scale_changed_count": 4,
               "perturbed_reject_count": 3,
               "unperturbed_reject_count": 1,
               "perturbed_R_scale_p95": 2.5,
               "unperturbed_R_scale_p95": 1.2}
              for method in ("F04", "A01", "A04")]
    finite = [{"matrix": matrix, "method_id": f"{prefix}{index:02d}",
               "evaluable_rate": .99, "failure_count": 1}
              for matrix, prefix, methods in (("full", "F", range(1, 5)),
                                               ("ablation", "A", range(1, 10)))
              for index in methods]
    worst = [{"case_id": f"D{dtype:02d}_seed_08", "method_id": "F04",
              "metric_value": 100-dtype} for dtype in range(1, 31)]
    logical = [{"matrix": "full", "logical_row_count": 2164, "unique_execution_count": 2100},
               {"matrix": "ablation", "logical_row_count": 4869, "unique_execution_count": 3800}]
    return {"full_rows": full, "ablation_rows": ablation, "paired_deltas": paired,
            "recovery_metrics": recovery, "source_aware_actions": source,
            "schemec_actions": scheme, "finite_failure": finite,
            "worst_cases": worst, "logical_unique": logical}


def test_all_25_figures_are_semantic_and_sha_bound(tmp_path):
    tables = _tables()
    hashes = {name: hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
              for name, rows in tables.items()}
    report = render_diagnostic_figures(tables=tables, table_hashes=hashes,
                                       output_root=tmp_path / "figures")
    assert report["passed"] and report["figure_count"] == len(FIGURE_SPECS) == 25
    assert report["all_semantic_not_arbitrary_slices"]
    assert report["semantic_source_table_sha256"] == hashes
    for row in report["figures"]:
        assert row["source_table_sha256"]
        assert row["action_labels_present"] is False
        assert row["action_label_overlap_not_applicable"] is True
        assert row["delta_or_independent_secondary_panel"] is True
        assert row["png_pixel_std"] > .005 and row["pdf_header_valid"]


def test_semantic_renderer_fails_on_evaluable_nan(tmp_path):
    tables = _tables(); tables["full_rows"][0]["yaw_rmse_deg"] = float("nan")
    with pytest.raises(FigureQAError, match="NaN/Inf"):
        render_diagnostic_figures(tables=tables, output_root=tmp_path / "figures")


def test_semantic_renderer_requires_named_tables(tmp_path):
    with pytest.raises(FigureQAError, match="inputs missing"):
        render_diagnostic_figures(tables={"full_rows": []}, output_root=tmp_path / "figures")


def test_heatmap_masks_failure_proven_method_type_cell():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = _tables()["full_rows"]
    failed = next(row for row in rows if row["method_id"] == "F04"
                  and row["degradation_type_id"] == "D60")
    failed["evaluable"] = False
    failed["terminal_status"] = "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"
    failed["yaw_rmse_deg"] = None
    fig, axes = plt.subplots(2, 1)
    count, values, _ = _heatmap_figure(fig, axes, rows, "yaw_rmse_deg")
    assert count == 240
    assert values and all(float(value) == float(value) for value in values)
    assert fig._canonical541_semantic_qa["masked_metric_cell_count"] == 1
    assert fig._canonical541_semantic_qa["failure_count_total"] == 1
    assert fig._canonical541_semantic_qa["zero_fill_for_missing_or_failure"] is False
    assert any(text.get_text() == "F1" for text in axes[0].texts)
    plt.close(fig)


def test_recovery_missing_failure_and_no_return_are_not_zero_filled():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = []
    for dtype in ("D58", "D60"):
        for method in ("F01", "F02", "F03", "F04"):
            rows.append({"method_id": method, "degradation_type_id": dtype,
                         "metric": "horizontal", "evaluable": True,
                         "post_median": .4, "time_to_return_s": 3.0})
    failed = next(row for row in rows if row["method_id"] == "F04"
                  and row["degradation_type_id"] == "D60")
    failed.update(evaluable=False, post_median=None, time_to_return_s=None)
    no_return = next(row for row in rows if row["method_id"] == "F03"
                     and row["degradation_type_id"] == "D60")
    no_return["time_to_return_s"] = None
    fig, axes = plt.subplots(2, 1)
    _, values, _ = _recovery_figure(axes, rows)
    assert 20.0 not in values  # the former fallback must never reappear
    qa = fig._canonical541_semantic_qa
    assert qa["recovery_failure_count"] == 1
    assert qa["recovery_not_returned_count"] == 1
    assert qa["zero_fill_for_missing_or_failure"] is False
    assert any("NR1" in text.get_text() for text in axes[1].texts)
    plt.close(fig)


def test_source_aware_exact_nonzero_fields_are_not_silently_zeroed():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = _tables()["source_aware_actions"]
    fig, axes = plt.subplots(2, 1)
    _, values, _ = _source_aware_figure(axes, rows)
    qa = fig._canonical541_semantic_qa
    assert qa["source_aware_exact_field_contract"] is True
    assert qa["source_aware_nonzero_input_action_total"] == 84
    assert qa["source_aware_plotted_action_total"] == 84
    assert max(values) > 0
    plt.close(fig)


def test_source_aware_stale_alias_fields_fail_instead_of_default_zero():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [{"source": "raw_doppler", "mechanism_evaluable": True,
             "r_scale_changed_epochs": 20, "reject_epochs": 3, "r_scale_p95": 2.5}]
    fig, axes = plt.subplots(2, 1)
    with pytest.raises(FigureQAError, match="required numeric fields"):
        _source_aware_figure(axes, rows)
    plt.close(fig)
