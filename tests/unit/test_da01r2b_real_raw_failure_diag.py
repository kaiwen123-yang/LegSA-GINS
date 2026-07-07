import json

from legsa_gins.da_repro.common import write_csv
from legsa_gins.da_repro.method_teunissen_clambda import CLASSIC_CASES, METHOD_ID
from legsa_gins.da_repro.orientation_audit import BaselineVector
from legsa_gins.da_repro.real_raw_failure_diag import diagnose_real_raw_failure


def test_real_raw_failure_diag_classifies_unstable_direction(tmp_path):
    runtime = tmp_path / "runtime"
    for case in CLASSIC_CASES:
        case_root = runtime / METHOD_ID / case.case_id
        rows = []
        for index in range(5):
            rows.append(
                {
                    "timestamp": float(index),
                    "baseline_east_m": 0.0,
                    "baseline_north_m": 0.355147,
                    "baseline_up_m": 0.0,
                    "baseline_length_m": 0.355147,
                    "num_dd": 5,
                    "design_rank": 3,
                    "design_condition_number": 2.0,
                    "code_residual_rms_m": 0.1,
                    "ambiguity_fixed_status": "float_with_integer_candidates",
                    "ambiguity_ratio": 1.2,
                }
            )
        write_csv(case_root / "epoch_output.csv", rows)
        (case_root / "eval_metrics.json").write_text(json.dumps({"yaw_rmse_deg": 100.0}), encoding="utf-8")
    status = [
        BaselineVector(time=float(index), east_m=-0.355147, north_m=0.0, up_m=0.0, source="status")
        for index in range(5)
    ]
    summary_rows, epoch_rows, ambiguity_rows, global_summary = diagnose_real_raw_failure(
        runtime_root=runtime,
        status_vectors=status,
    )
    assert len(summary_rows) == len(CLASSIC_CASES)
    assert epoch_rows
    assert len(ambiguity_rows) == len(CLASSIC_CASES)
    assert global_summary["raw_direction_unstable"] is True
    assert global_summary["implementation_fails"] is False
    assert global_summary["frame_fails"] is False
