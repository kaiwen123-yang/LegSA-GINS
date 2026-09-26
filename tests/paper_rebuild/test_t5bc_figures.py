"""Synthetic-only figure data, provenance, and output-exclusivity checks."""
import csv
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.hext import t5bc_figures as figures


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _row(sequence="BY2", profile="F02", variant=figures.FROZEN, value="1.00000000"):
    return {"sequence_id": sequence, "configuration_id": profile, "variant": variant,
            "evaluator_contract": "evaluator_contract_v3", "evaluation_status": "COMPLETED",
            "failure_classification": "NONE", **{metric: value for metric, _, _ in figures.METRICS}}


def _sequence_rows():
    rows = []
    for sequence_index, sequence in enumerate(figures.SEQUENCES):
        for profile in figures.PROFILES:
            for variant in figures._variants(profile):
                rows.append(_row(sequence, profile, variant, str(sequence_index + 1.) + "0000000"))
        for method in ("LC01", "LC01-S"):
            rows.append(_row(sequence, method, method, "10000.0"))
    return rows


CASES = ["C00_clean_normal", "D01_seed_00", "D05_seed_00"]


def _subset_rows():
    rows = []
    for case in CASES:
        for variant in (figures.FROZEN, *figures.VARIANTS):
            row = {**_row(profile="F04", variant=variant), "case_id": case}
            for metric, _, _ in figures.METRICS:
                row["delta_vs_frozen_" + metric] = "0.00000000" if variant == figures.FROZEN else "0.12500000"
                if variant != figures.FROZEN:
                    row[metric] = "1.12500000"
            rows.append(row)
    return rows


def test_sequence_cells_match_actual_slots_and_share_metric_domains():
    rows = _sequence_rows()
    rows[1]["evaluation_status"] = "UNAVAILABLE_EVALUATION_FAILED"
    rows[1]["yaw_rmse_deg"] = "0.0"  # Stale failure output must not be drawn as zero.
    original = deepcopy(rows)
    plan = figures.sequence_render_data(list(reversed(rows)))
    assert len(plan["cells"]) == 120
    assert plan["metric_limits"]["yaw_rmse_deg"] == [0., pytest.approx(3.36)]
    assert all(cell["variant"] in (figures.FROZEN, "B3") for cell in plan["cells"] if cell["configuration_id"] == "A04")
    missing = [cell for cell in plan["cells"] if cell["plotted_value"] is None]
    assert len(missing) == 4
    assert all(cell["render_status"] == "UNAVAILABLE_EVALUATION_FAILED" for cell in missing)
    assert rows == original
    # Frozen literature rows remain in the source table; they do not alter these method scales.
    assert not any(cell["variant"] in ("LC01", "LC01-S") for cell in plan["cells"])


def test_missing_source_slot_is_preserved_and_unauthorized_a04_slot_is_rejected():
    plan = figures.sequence_render_data(_sequence_rows()[1:])
    assert len(plan["cells"]) == 120 and sum(cell["plotted_value"] is None for cell in plan["cells"]) == 4
    assert all(cell["evaluation_status"] == "NOT_RUN" for cell in plan["cells"] if cell["plotted_value"] is None)
    with pytest.raises(ValueError, match="Unauthorized"):
        figures.sequence_render_data(_sequence_rows() + [_row(profile="A04", variant="R5W")])
    with pytest.raises(ValueError, match="Duplicate"):
        figures.sequence_render_data(_sequence_rows() + [_row()])
    with pytest.raises(ValueError, match="Negative RMSE"):
        figures.sequence_render_data([_row(value="-0.1")])


def test_subset_keeps_exact_order_failed_and_absent_cases_without_fake_zero():
    rows = _subset_rows()
    rows[2]["evaluation_status"] = "NOT_RUN_ALGORITHM_FAILURE"
    rows = [row for row in rows if not (row["case_id"] == "D05_seed_00" and row["variant"] == "B3")]
    plan = figures.subset_render_data(rows, case_ids=CASES)
    assert plan["case_ids"] == CASES
    assert len(plan["cells"]) == 48
    assert sum(cell["plotted_value"] is None for cell in plan["cells"]) == 8
    assert all(cell["source_token"] == "0.12500000" for cell in plan["cells"] if cell["plotted_value"] is not None)
    assert all(cell["plotted_value"] == .125 for cell in plan["cells"] if cell["plotted_value"] is not None)
    with pytest.raises(ValueError, match="Unregistered"):
        figures.subset_render_data(rows, case_ids=CASES[:-1])
    with pytest.raises(ValueError, match="unique explicit"):
        figures.subset_render_data(rows, case_ids=CASES + CASES[:1])


def test_subset_delta_identity_and_failed_reference_are_enforced():
    rows = _subset_rows()
    rows[1]["delta_vs_frozen_yaw_rmse_deg"] = "0.12499999"
    with pytest.raises(ValueError, match="same-case source tokens"):
        figures.subset_render_data(rows, case_ids=CASES)
    rows[0]["evaluation_status"] = "UNAVAILABLE_EVALUATION_FAILED"
    plan = figures.subset_render_data(rows, case_ids=CASES)
    failed = [cell for cell in plan["cells"] if cell["case_id"] == CASES[0]]
    assert all(cell["plotted_value"] is None for cell in failed)
    assert all(cell["render_status"].startswith("FROZEN_") for cell in failed)
    assert figures.subset_render_data([], case_ids=[])["cells"] == []


def _csv_bytes(rows):
    output = io.StringIO(newline="")
    fields = list(dict.fromkeys(key for row in rows for key in row)) or ["status"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def _fixture(tmp_path):
    aggregate = tmp_path / figures.STAGE / "07_AGGREGATE"
    aggregate.mkdir(parents=True)
    pins = {}
    for name, rows in zip(figures.INPUT_NAMES, (_sequence_rows(), _subset_rows(), [{"sequence_id":"BY2","variant":"R5W","configuration_id":"F04","time":1,"nis":1}], [{"sequence_id":"BY2","lag_ms":1000,"sigma_deg":1,"k":1,"k_b":1}])):
        payload = _csv_bytes(rows)
        (aggregate / name).write_bytes(payload)
        pins[name] = _sha(payload)
    manifest = {"code_commit": "a" * 40, "files_sha256": pins, "subset_case_ids": CASES,
                "data_mode": "synthetic", "synthetic_data_used": True, "semisynthetic_data_used": False}
    payload = json.dumps(manifest).encode()
    (aggregate / "AGGREGATE_MANIFEST.json").write_bytes(payload)
    return aggregate, aggregate.parent / "08_FIGURES", _sha(payload)


def _render(aggregate, output, pin):
    return figures.render_t5bc(aggregate, output, code_freeze="a" * 40,
                               aggregate_manifest_sha256=pin, case_ids=CASES)


def test_manifest_and_table_pins_gate_before_output_creation(tmp_path):
    aggregate, output, pin = _fixture(tmp_path)
    with pytest.raises(ValueError, match="manifest SHA-256 mismatch"):
        _render(aggregate, output, "0" * 64)
    assert not output.exists()
    (aggregate / figures.INPUT_NAMES[0]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="source SHA-256 mismatch"):
        _render(aggregate, output, pin)
    assert not output.exists()


def test_paths_symlinks_existing_outputs_and_case_list_are_gated(tmp_path):
    aggregate, output, pin = _fixture(tmp_path)
    with pytest.raises(ValueError, match="registered T5bc"):
        _render(aggregate, aggregate / "new_figures", pin)
    output.mkdir()
    sentinel = output / "unrelated.txt"
    sentinel.write_text("preserved")
    with pytest.raises(FileExistsError):
        _render(aggregate, output, pin)
    assert sentinel.read_text() == "preserved"
    linked = tmp_path / "linked_aggregate"
    linked.symlink_to(aggregate, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        _render(linked, tmp_path / "other", pin)


def test_ordered_case_ids_must_match_pinned_aggregate_manifest(tmp_path):
    aggregate, output, pin = _fixture(tmp_path)
    with pytest.raises(ValueError, match="Ordered subset"):
        figures.render_t5bc(aggregate, output, code_freeze="a" * 40,
                            aggregate_manifest_sha256=pin, case_ids=list(reversed(CASES)))


def test_style_figures_have_zero_bar_baselines_all_case_labels_and_no_missing_marks():
    from legsa_gins.paper_rebuild.publication import qa
    import matplotlib.pyplot as plt

    rows = _sequence_rows()
    rows[1]["evaluation_status"] = "NOT_RUN"
    plan = figures.sequence_render_data(rows)
    fig = figures._sequence_figure(plan, "BY2")
    try:
        assert all(ax.get_ylim()[0] == 0 for ax in fig.axes)
        assert sum(len(ax.patches) for ax in fig.axes) == 36
        assert sum(text.get_text() == "NA" for ax in fig.axes for text in ax.texts) == 4
        assert all(row["pass"] for row in qa.check_figure(fig, "SYNTHETIC_SEQUENCE"))
    finally:
        plt.close(fig)
    rows = _subset_rows()
    rows[1]["evaluation_status"] = "NOT_RUN"
    plan = figures.subset_render_data(rows, case_ids=CASES)
    fig = figures._subset_figure(plan)
    try:
        assert [text.get_text() for text in fig.axes[0].get_yticklabels()] == CASES
        assert sum(len(ax.collections) for ax in fig.axes) == 44
        assert sum(text.get_text() == "NA R" for ax in fig.axes for text in ax.texts) == 4
        assert all(row["pass"] for row in qa.check_figure(fig, "SYNTHETIC_SUBSET"))
    finally:
        plt.close(fig)


def _stub_exports(monkeypatch):
    """Replace only the already-tested publication export backend, not data gates."""
    from legsa_gins.paper_rebuild.publication import qa, style

    def save(fig, directory, figure_id):
        directory.mkdir()
        result = {"figure_id": figure_id}
        for ext in ("png", "pdf", "svg"):
            path = directory / (figure_id + "." + ext)
            payload = ("synthetic test export " + figure_id + ext).encode()
            path.write_bytes(payload)
            result[ext], result[ext + "_sha256"] = str(path), _sha(payload)
        return result

    monkeypatch.setattr(style, "save_figure", save)
    monkeypatch.setattr(qa, "check_png", lambda path, figure_id: [])


def test_render_manifest_binds_inputs_outputs_counts_and_unperformed_manual_review(tmp_path, monkeypatch):
    _stub_exports(monkeypatch)
    aggregate, output, pin = _fixture(tmp_path)
    result = _render(aggregate, output, pin)
    assert result["aggregate_manifest_sha256"] == pin
    assert len(result["source_hashes"]) == 5
    assert len(result["figures"]) == 8
    assert result["manual_visual_inspection"] == "NOT_PERFORMED"
    assert result["synthetic_data_used"] is True and result["semisynthetic_data_used"] is False
    assert result["native_invocation_count"] == result["evaluator_invocation_count"] == result["trace_open_count"] == 0
    assert result["sequence_metric_cells"] == 120 and result["subset_metric_cells"] == 48
    assert result["missing_values_imputed"] is False
    assert result["subset_case_ids"] == CASES
    for product in result["figures"]:
        assert product["manual_visual_inspection"] == "NOT_PERFORMED"
        for ext in ("png", "pdf", "svg"):
            assert not Path(product[ext]).is_absolute()
            assert _sha((output / product[ext]).read_bytes()) == product[ext + "_sha256"]
    for name, digest in result["auxiliary_sha256"].items():
        assert _sha((output / name).read_bytes()) == digest
    document = (output / "T5BC_RENDER_MANIFEST.json").read_text()
    assert str(tmp_path) not in document
    assert json.loads(document) == result
    with pytest.raises(FileExistsError):
        _render(aggregate, output, pin)


def test_changed_source_after_rendering_cannot_receive_final_manifest(tmp_path, monkeypatch):
    _stub_exports(monkeypatch)
    aggregate, output, pin = _fixture(tmp_path)
    original = figures._subset_figure

    def changing(plan):
        (aggregate / figures.INPUT_NAMES[0]).write_bytes(b"changed during plot")
        return original(plan)

    monkeypatch.setattr(figures, "_subset_figure", changing)
    with pytest.raises(ValueError, match="changed during rendering"):
        _render(aggregate, output, pin)
    assert not (output / "T5BC_RENDER_MANIFEST.json").exists()
