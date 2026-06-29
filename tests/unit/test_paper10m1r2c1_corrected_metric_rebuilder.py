import csv
from pathlib import Path

from legsa_gins.evaluation.yaw_metric_repair import CORRECTED_SUFFIX, rebuild_corrected_metrics


def _write_rows(path: Path) -> None:
    rows = [
        {
            "row_id": "r0",
            "case_id": "c0",
            "degradation_type_id": "CLEAN",
            "method_mode_id": "m0",
            "terminal_status": "COMPLETED_EVALUABLE",
            "horizontal_rmse_m": "1.0",
            "up_rmse_m": "2.0",
            "yaw_rmse_deg": "90.0",
        }
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_rebuilder_labels_evaluator_only_outputs(tmp_path):
    row_table = tmp_path / "rows.csv"
    _write_rows(row_table)
    out = tmp_path / "out"
    manifest = rebuild_corrected_metrics(
        row_table=row_table,
        output_dir=out,
        yaw_corrections={"r0": {"yaw_transform_applied": "minus_90_deg", "yaw_rmse_deg": "1.0"}},
        evaluator_only=True,
    )
    assert manifest["metric_table_role"] == CORRECTED_SUFFIX
    rows = list(csv.DictReader((out / "PAPER10M1R2C1_ROW_LEVEL_RESULT_TABLE_CORRECTED_EVALUATOR_ONLY.csv").open()))
    assert rows[0]["metric_table_role"] == CORRECTED_SUFFIX
    assert rows[0]["yaw_transform_applied"] == "minus_90_deg"


def test_rebuilder_writes_blocker_when_not_evaluator_only(tmp_path):
    row_table = tmp_path / "rows.csv"
    _write_rows(row_table)
    out = tmp_path / "blocked"
    manifest = rebuild_corrected_metrics(
        row_table=row_table,
        output_dir=out,
        yaw_corrections={},
        evaluator_only=False,
        blocked_reason="solver_provider_failure",
    )
    assert manifest["corrected_metrics_generated"] is False
    assert (out / "NO_CORRECTED_METRICS_GENERATED_BLOCKER.md").is_file()
