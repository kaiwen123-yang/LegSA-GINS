"""Scientific-identity and literal-unavailability checks for v3 reporting."""
from copy import deepcopy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile
import subprocess
import os

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.hext.aggregate import TABLE_FIELDS
from legsa_gins.paper_rebuild.protocol_v3 import reporting as report
from legsa_gins.paper_rebuild.protocol_v3.packaging import package, verify_zip


def sample(method="F04", case="C00_clean_normal", status="COMPLETED", value="1.000"):
    return dict(dataset_id="BY2", sequence_id="BY2", method_id=method, case_id=case,
        evaluation_status=status, failure_classification="NONE" if status == "COMPLETED" else "ALGORITHM_FAILURE_DIVERGED",
        data_mode="real_clean", synthetic_data_used=False, semisynthetic_data_used=False,
        **{metric: value if status == "COMPLETED" else report.UNAVAILABLE for metric in report.METRICS})


def horizontal_fixture():
    old, new = [], []
    for sequence in report.SEQUENCES:
        for method in report.MAIN:
            row = {name: "UNAVAILABLE" for name in TABLE_FIELDS}
            row.update(sequence_id=sequence, method_id=method, main_row="True", manuscript_row="True")
            old.append(row)
            new.append(dict(sample(method), dataset_id=sequence))
    for i in range(37):
        row = {name: "UNAVAILABLE" for name in TABLE_FIELDS}
        row.update(sequence_id="BY2", method_id="LC01" if i % 2 else "EXT05C", h_rmse_m="0.000000000012300", notes='{"literal": "quoted, source token"}')
        old.append(row)
    return old, new


def test_horizontal_preserves_external_tokens_and_all_rows():
    old, new = horizontal_fixture()
    before = deepcopy(old)
    rows, audit = report.main_table(old, new, "v3")
    assert old == before
    assert len(rows) == 52 and rows[15:] == old[15:]
    assert len([r for r in audit if r["disposition"] == "LEGSA_REPLACED_WITH_V3"]) == 15
    assert all(r["h_rmse_m"] == "1.000" for r in rows[:15])


def test_horizontal_rejects_missing_or_duplicate_legsa_identity():
    old, new = horizontal_fixture()
    with pytest.raises(ValueError, match="Missing/duplicate"):
        report.main_table(old, new[:-1], "v3")
    old[1] = deepcopy(old[0])
    with pytest.raises(ValueError, match="Missing/duplicate"):
        report.main_table(old, new, "v3")


def test_failure_comparison_retains_completed_to_failure_and_unpaired_values():
    frozen = [sample(case="D27_seed_00", value="2.1000000000000001")]
    new = [sample(case="D27_seed_00", status="NOT_RUN_ALGORITHM_FAILURE")]
    row = report.comparison_rows(new, frozen)[0]
    assert row["completed_to_failure"] is True and row["paired_finite"] is False
    assert row["delta_yaw_rmse_deg"] == "UNAVAILABLE"
    assert row["v21_yaw_rmse_deg"] == "2.1000000000000001"


def test_paired_difference_uses_decimal_source_tokens():
    row = report.comparison_rows([sample(value="2.1000000000000002")], [sample(value="2.1000000000000001")])[0]
    assert row["delta_yaw_rmse_deg"] == "1E-16"


def test_no_cross_case_comparison_substitution():
    with pytest.raises(ValueError, match="identical unique"):
        report.comparison_rows([sample(case="D27_seed_00")], [sample(case="D26_seed_00")])


def test_finite_denominators_preserve_algorithm_and_not_applicable_states():
    rows = [sample(value="1"), sample(case="D01", value="9"), sample(case="D02", status="NOT_RUN_ALGORITHM_FAILURE"),
        dict(sample(case="D03", status="NOT_APPLICABLE"), failure_classification="B3_NOT_APPLICABLE_NO_HEADING_EPOCHS")]
    result = report.absolute_summary(rows)[0]
    assert result["registered_count"] == 4 and result["finite_count"] == 2
    assert result["algorithm_failure_count"] == 1 and result["not_applicable_count"] == 1
    assert result["mean"] == 5 and result["failure_rate"] == .25
    assert result["worst_5pct_mean"] == 9 and result["worst_5pct_count"] == 1


def test_completed_nan_is_not_silently_deleted():
    with pytest.raises(ValueError, match="silently remove"):
        report.absolute_summary([sample(value="NaN")])


def test_sensitivity_copy_is_exact_and_d57_not_applicable_survives():
    rows = [dict(case_id=case, variant=variant, evaluation_status="NOT_APPLICABLE" if case.startswith("D57") and variant == "B3" else "COMPLETED",
        failure_classification="B3_NOT_APPLICABLE_NO_HEADING_EPOCHS" if case.startswith("D57") and variant == "B3" else "NONE",
        yaw_rmse_deg="UNAVAILABLE" if case.startswith("D57") and variant == "B3" else "1.234500000")
        for case in report.SUBSET61 for variant in sorted(report.SENSITIVITY_VARIANTS)]
    result = report.copy_sensitivity(rows, subset=True)
    assert result == rows and result is not rows
    assert len(result) == 183
    with pytest.raises(ValueError, match="coverage"):
        report.copy_sensitivity(rows[:-1], subset=True)


def test_by2o_closed_segments_include_outside_and_leave_external_tokens():
    times = np.asarray([3186., 3369.94, 3411.95, 3420., 3495.94, 3508.94, 3563.])
    frame = pd.DataFrame({name: times if name == "time" else np.ones(len(times)) for name in report.ERROR_COLUMNS})
    row = dict(sample(), dataset_id="BY2O")
    external = dict(method_id="LC01", evaluator_contract="evaluator_contract_v3", segment_id="outside", yaw_rmse_deg="7.5000000")
    result = report.by2o_segments([row], lambda _: (frame, "<SEALED>/errors.csv"), [external], "v3", [3186, 3563])
    assert result[0] == external
    index = {r["segment_id"]: r for r in result if r["method_id"] == "F04"}
    assert index["occlusion_primary"]["count"] == 2
    assert index["occlusion_secondary"]["count"] == 2
    assert index["inside_union"]["count"] == 4
    assert index["outside"]["count"] == 3


def test_reporting_refuses_raw_trace_even_with_correct_hash(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    path = raw / "reference.csv"
    path.write_bytes(b"not a real trace")
    with pytest.raises(PermissionError, match="raw data"):
        report.Sources({"raw_root": raw}).read({"path": str(path), "sha256": report.sha256(path)})


def test_reporting_detects_pinned_source_change(tmp_path):
    path = tmp_path / "table.csv"
    path.write_bytes(b"a\n1\n")
    ref = dict(path=str(path), sha256=report.sha256(path))
    path.write_bytes(b"a\n2\n")
    with pytest.raises(RuntimeError, match="HARD_STOP_V3_REPORT_INPUT_HASH"):
        report.Sources({}).read(ref)


def observer_module(monkeypatch):
    monkeypatch.delenv("CLEAN5_EVALUATOR_CAPTURE_CONFIG", raising=False)
    path = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/v3_evaluator_observer/sitecustomize.py"
    spec = importlib.util.spec_from_file_location("v3_test_observer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def truth_locals():
    return dict(t_nav=np.array([1., 2.]), gt_lat=np.array([30., 30.1]), gt_lon=np.array([110., 110.1]),
        gt_alt=np.array([20., 21.]), gt_yaw_for_cmp=np.array([359., 1.]),
        nav=pd.DataFrame(dict(lat=[30.01, 30.11], lon=[110.01, 110.11], alt=[20.01, 21.01], yaw=[359.1, 1.1])),
        err_df=pd.DataFrame(dict(time=[1., 2.], yaw_err_deg=[.1, .1])))


def test_truth_export_observes_existing_arrays_without_mutation(tmp_path, monkeypatch):
    module = observer_module(monkeypatch)
    local = truth_locals()
    originals = {name: value.copy(deep=True) if isinstance(value, pd.DataFrame) else value.copy() for name, value in local.items()}
    module.export_matched_trajectory(local, tmp_path)
    rows = pd.read_csv(tmp_path / "MATCHED_TRAJECTORY.csv")
    assert np.array_equal(rows.truth_yaw_deg, local["gt_yaw_for_cmp"])
    for name, original in originals.items():
        if isinstance(original, pd.DataFrame):
            pd.testing.assert_frame_equal(local[name], original)
        else:
            assert np.array_equal(local[name], original)
    receipt = json.loads((tmp_path / "MATCHED_TRAJECTORY_MANIFEST.json").read_text())
    assert receipt["additional_trace_opens"] == 0 and receipt["new_interpolation"] is False


def test_truth_callback_preserves_original_observer_and_ignores_other_frames(tmp_path, monkeypatch):
    module = observer_module(monkeypatch)
    events = []
    callback = module.wrap_profile(dict(evaluator="synthetic_evaluator.py", outdir=str(tmp_path)), lambda *args: events.append(args[1]))
    frame = SimpleNamespace(f_code=SimpleNamespace(co_filename="synthetic_evaluator.py", co_name="main"), f_locals=truth_locals())
    callback(frame, "call", None)
    assert not (tmp_path / "MATCHED_TRAJECTORY.csv").exists()
    callback(frame, "return", None)
    assert events == ["call", "return"] and (tmp_path / "MATCHED_TRAJECTORY.csv").is_file()


def test_partial_zip_preserves_literal_hard_stop_and_member_bytes(tmp_path):
    scratch, archive, handoff = (tmp_path / name for name in ("scratch", "archive", "handoff"))
    scratch.mkdir(); archive.mkdir()
    stop = scratch / "HARD_STOP.json"
    stop.write_text(json.dumps(dict(status="HARD_STOP", gate="2d", native_calls=1)))
    (archive / "retained.txt").write_bytes(b"literal\x00evidence\n")
    result = package(scratch, archive, handoff, code_freeze="a" * 40, partial=True, stop_path=stop)
    assert result["scientific_status"] == "HARD_STOP_PARTIAL_EVIDENCE"
    with zipfile.ZipFile(result["destination"]) as z:
        assert z.read("V3_ARCHIVE/retained.txt") == b"literal\x00evidence\n"
        summary = json.loads(z.read("V3_SCRATCH/09_HANDOFF/PARTIAL_DELIVERY_SUMMARY.json"))
        assert summary["scientific_completion_claim"] is False and summary["hard_stop"]["gate"] == "2d"
    with pytest.raises(FileExistsError):
        package(scratch, archive, handoff, code_freeze="a" * 40, partial=True, stop_path=stop)


def test_complete_package_cannot_bypass_gates(tmp_path):
    with pytest.raises(ValueError, match="identity gates"):
        package(tmp_path / "scratch", tmp_path / "archive", tmp_path / "handoff", code_freeze="a" * 40)


def test_frozen_representative_windows_use_components_not_anchor_arithmetic():
    from legsa_gins.paper_rebuild.protocol_v3.figures import frozen_plot_intervals
    full = dict(case_meta=dict(duration_s="full_sequence"), components=[])
    assert frozen_plot_intervals(full, [66., 340.]) == [(66., 340.)]  # D27 and D12
    for name, interval in (("D04", [196.2, 216.2]), ("D58", [201.2, 211.2]), ("D60", [196.2, 216.2])):
        bundle = dict(case_meta=dict(anchor_time_s="206.2", duration_s="20"), components=[
            dict(component=name, details=dict(interval=interval)),
            dict(component="clean_recovery_interval", details=dict(interval=[interval[1], interval[1] + 20]))])
        assert frozen_plot_intervals(bundle, [66., 340.]) == [tuple(interval)]
    with pytest.raises(ValueError, match="realized fault interval"):
        frozen_plot_intervals(dict(case_meta=dict(anchor_time_s="206.2", duration_s="20")), [66, 340])


def test_heatmap_preserves_all_failed_type_position():
    from legsa_gins.paper_rebuild.protocol_v3.figures import type_heatmap
    rows = [dict(degradation_id=f"D{i:02}", profile=method, evaluation_status="NOT_RUN_ALGORITHM_FAILURE" if i == 37 else "COMPLETED",
        yaw_rmse_deg=np.nan if i == 37 else i) for i in range(1, 61) for method in report.MAIN]
    frame = type_heatmap(pd.DataFrame(rows), "yaw_rmse_deg")
    assert frame.shape == (60, 5) and frame.index[36] == "D37"
    assert frame.loc["D37"].isna().all() and frame.loc["D38"].eq(38).all()


def test_finalize_direct_invocation_resolves_project_without_pythonpath(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/v3_finalize.py"
    config = tmp_path / "local.yaml"
    config.write_text("paths:\n  protocol_v3_scratch: " + str(tmp_path / "missing") + "\n  clean_root: " + str(tmp_path / "clean") + "\n")
    result = subprocess.run(["/usr/bin/python3", "-B", str(script), "--phase", "figures", "--code-freeze", "a" * 40,
        "--local-config", str(config)], cwd=tmp_path, env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"}, capture_output=True, text=True)
    assert result.returncode != 0 and "FileNotFoundError" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr


def test_all_ten_drawers_accept_synthetic_full_cohort_with_missing_type():
    """Exercise real drawer/adapter APIs; render only in-memory synthetic canvases."""
    from legsa_gins.paper_rebuild.protocol_v3 import figures
    from legsa_gins.paper_rebuild.publication import style
    from legsa_gins.paper_rebuild.publication.protocol_v21_render import figure_checks
    from legsa_gins.paper_rebuild.hext.readonly_figures import make_fig02s, make_fig02sb, STARTS
    records = []
    cases = [("C00_clean_normal", "CLEAN", "clean")] + [(f"D{i:02}_seed_{seed:02}", f"D{i:02}", "dual_yaw" if i >= 30 else "gnss_outage") for i in range(1, 61) for seed in range(9)]
    for case, kind, family in cases:
        for index, method in enumerate(report.CONFIG):
            row = sample(method=method, case=case, status="NOT_RUN_ALGORITHM_FAILURE" if kind == "D37" else "COMPLETED", value=1 + index / 20)
            row.update(profile=method, run_id=case + "__" + method, degradation_id=kind, case_family=family, evaluator_version="v3",
                data_mode="synthetic_test_only", synthetic_data_used=True, semisynthetic_data_used=False,
                source_aware_touch_rate=.2, raw_doppler_update_count=10, scheme_c_reject_count=1, go2_hv_update_count=8)
            records.append(row)
    pairs = pd.DataFrame(report.paired_rows(records))
    pairs.delta_candidate_minus_reference = pd.to_numeric(pairs.delta_candidate_minus_reference)
    summaries = []
    for (comparison, metric), group in pairs.groupby(["comparison", "metric_name"]):
        for scope, family, part in [("overall", "ALL", group), *[("family", family, part) for family, part in group.groupby("case_family")]]:
            median = float(part.delta_candidate_minus_reference.median())
            summaries.append(dict(comparison=comparison, metric_name=metric, scope=scope, family=family,
                paired_sample_count=len(part), median_delta_candidate_minus_reference=median,
                median_ci95_low=median - .01, median_ci95_high=median + .01))
    core = pd.DataFrame(records)
    for metric in report.METRICS:
        core[metric] = pd.to_numeric(core[metric], errors="coerce")
    tables = {"PAIRWISE_CASE_LEVEL_V3.csv": pairs, "PAIRWISE_SUMMARY_V3.csv": pd.DataFrame(summaries)}
    window_bundles = {"D27_seed_00": dict(case_meta=dict(duration_s="full_sequence")),
        "D12_seed_00": dict(case_meta=dict(duration_s="full_sequence"))}
    for kind, interval in (("D04", [196.2, 216.2]), ("D58", [201.2, 211.2]), ("D60", [196.2, 216.2])):
        window_bundles[kind + "_seed_00"] = dict(case_meta=dict(duration_s="20"), components=[dict(component="fault", details=dict(interval=interval))])
    for case, bundle in window_bundles.items():
        bundle["case_id"] = case
    times = np.linspace(66., 340., 17)
    errors = pd.DataFrame({name: times if name == "time" else np.sin(times / 100) for name in report.ERROR_COLUMNS})
    truth = pd.DataFrame(dict(time=times, truth_latitude_deg=30 + np.linspace(0, .0001, len(times)),
        truth_longitude_deg=110 + np.linspace(0, .0001, len(times)), truth_height_m=np.full(len(times), 20.),
        truth_yaw_deg=np.linspace(100, 110, len(times)), estimate_latitude_deg=30.000001 + np.linspace(0, .0001, len(times)),
        estimate_longitude_deg=110.000001 + np.linspace(0, .0001, len(times)), estimate_height_m=np.full(len(times), 20.01),
        estimate_yaw_deg=np.linspace(100.1, 110.1, len(times))))
    bundle = object.__new__(figures.Bundle)
    bundle.unique, bundle.notes = core, []
    bundle.p = SimpleNamespace(table=lambda name: tables[name].copy(), use=lambda frame: frame, used=set())
    bundle.runtime = SimpleNamespace(truth=lambda _: truth.copy(), series=lambda _: (errors.copy(), "<SYNTHETIC_TEST>/errors.csv"),
        sources=SimpleNamespace(read=lambda reference: json.dumps(window_bundles[reference["case_id"]]).encode()))
    bundle.case_sources = {case: {"case_id": case} for case in window_bundles}
    bundle.evaluation_windows = {"BY2": {"window_seconds": [66, 340]}}
    horizontal = []
    for sequence in report.SEQUENCES:
        for method in ("F02", "A04", "F04", "LC01", "LC01-S"):
            row = {name: 1.0 for name in report.METRIC_FIELDS}
            row.update(sequence_id=sequence, method_id=method, evaluator_contract="evaluator_contract_v3", evaluation_status="COMPLETED",
                start_convention=STARTS[sequence], manuscript_row=method != "LC01-S", config="S" if method == "LC01-S" else "LIT" if method == "LC01" else "PROTOCOL_V3")
            horizontal.append(row)
    segments = [dict(sequence_id="BY2O", method_id=method, segment_id=segment, evaluator_contract="evaluator_contract_v3", status="AVAILABLE", yaw_rmse_deg=.3, h_rmse_m=.1)
        for method in ("F02", "A04", "F04", "LC01", "LC01-S") for segment in ("occlusion_primary", "occlusion_secondary")]
    selection = dict(selected_config="LIT", selected_method_id="LC01", amended_after_results_seen=True, paper_primary_starts=STARTS)
    rendered = []
    for figure_id in figures.FIGURE_IDS:
        figure = None
        try:
            if figure_id == "FIG02S":
                figure, _ = make_fig02s(horizontal, selection)
            elif figure_id == "FIG02S-b":
                figure, _ = make_fig02sb(segments)
            else:
                figure, _ = figures.DRAWERS[figure_id](bundle)
            assert all(check["pass"] for check in figure_checks(figure, figure_id))
            rendered.append(figure_id)
        finally:
            style.plt.close(figure)
    assert rendered == list(figures.FIGURE_IDS)
