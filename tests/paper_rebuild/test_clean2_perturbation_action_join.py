from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2_analysis import (
    build_perturbation_action_rows,
    build_source_aware_response_rows,
)


# The real current-provider ledger retains these 303 unique epochs.  Integer
# fixture times deliberately include both frozen boundaries (66 and 340).
EPOCH_TIMES = tuple(float(value) for value in range(55, 358))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _ledger(
    case_id: str,
    operations: list[tuple[str, set[float], set[float]]],
) -> list[dict[str, object]]:
    """Build one complete 303-row domain per operation.

    Each tuple is ``(operation, selected_times, withheld_times)``.  This mirrors
    mixed-case ledgers, where operation blocks repeat the same provider domain.
    """

    rows: list[dict[str, object]] = []
    for operation, selected_times, withheld_times in operations:
        for time_value in EPOCH_TIMES:
            selected = time_value in selected_times
            rows.append(
                {
                    "case_id": case_id,
                    "time": time_value,
                    "operation": operation,
                    "selected": selected,
                    "original_yaw_valid": True,
                    "modified_yaw_valid": not (
                        selected and time_value in withheld_times
                    ),
                }
            )
    return rows


def _mixed_ledger(case_id: str) -> list[dict[str, object]]:
    return _ledger(
        case_id,
        [
            ("baseline_vector_spike", {100.0}, set()),
            ("signed_yaw_spike", {101.0}, set()),
            ("yaw_valid_midpoint_outage", {102.0}, {102.0}),
        ],
    )


def _action_registry(case_id: str) -> list[dict[str, object]]:
    return [
        {
            "run_id": f"R{index:03d}",
            "case_id": case_id,
            "structural_method": "strong_dual_yaw_EKF",
            "ablation_id": "",
            "alias_roles": "canonical_strong",
        }
        for index in range(1, 111)
    ]


def _full_registry_and_ledgers(
    ledger_factory,
) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]]]:
    registry: list[dict[str, object]] = []
    ledgers: dict[str, list[dict[str, object]]] = {}
    for index in range(18):
        case_id = f"C{index:02d}_fixture"
        run_id = f"FULL_{index:02d}"
        registry.append(
            {
                "run_id": run_id,
                "case_id": case_id,
                "structural_method": "LegSA_Paper_V1",
                "ablation_id": "",
                "alias_roles": "canonical_LegSA",
            }
        )
        ledgers[case_id] = ledger_factory(case_id)
    return registry, ledgers


def _yaw_counters(*, normal: int, downweight: int, reject: int) -> dict[str, int]:
    return {
        "yaw_attempt_count": normal + downweight + reject,
        "yaw_normal_count": normal,
        "yaw_downweight_count": downweight,
        "yaw_reject_count": reject,
        "yaw_accepted_count": normal + downweight,
    }


def test_real_shaped_port_trace_joins_only_in_window_actions(tmp_path: Path) -> None:
    port = tmp_path / "PORT_GNSS_UPDATE_TRACE.csv"
    _write_csv(
        port,
        [
            {"gnss_time": 100.0, "yaw_update": 1, "yaw_mode": "NORMAL"},
            {"gnss_time": 101.0, "yaw_update": 1, "yaw_mode": "DOWNWEIGHT"},
        ],
    )
    registry = _action_registry("C01_outage_10s")
    artifacts = {
        row["run_id"]: {
            "port_gnss_update_trace": port,
            "source_aware_weight_trace": None,
        }
        for row in registry
    }
    sealed = {
        row["run_id"]: {
            "module_counters": {
                **_yaw_counters(normal=1, downweight=1, reject=0),
                "source_aware_evaluation_count": 0,
                "source_aware_weight_changed_count": 0,
            }
        }
        for row in registry
    }
    rows = build_perturbation_action_rows(
        registry,
        artifacts,
        {"C01_outage_10s": _mixed_ledger("C01_outage_10s")},
        sealed,
    )
    first = rows[0]
    assert first["ledger_epoch_domain_count"] == 303
    assert first["ledger_epoch_in_window_count"] == 274
    assert first["ledger_epoch_out_of_window_count"] == 29
    assert first["perturbed_epoch_count"] == 3
    assert first["perturbed_epoch_in_window_count"] == 3
    assert first["perturbed_epoch_attempted_count"] == 2
    assert first["perturbed_epoch_accepted_count"] == 2
    assert first["perturbed_epoch_downweighted_count"] == 1
    assert first["withheld_epoch_count"] == 1
    assert first["withheld_epoch_in_window_count"] == 1
    assert first["spike_epoch_count"] == 2
    assert first["spike_epoch_consumed_count"] == 2
    assert first["nonwithheld_missing_trace_count"] == 0
    assert "bad" not in first["accepted_epoch_wording"].casefold()


def test_source_aware_scales_use_port_and_perturbed_dual_yaw_epochs(
    tmp_path: Path,
) -> None:
    port = tmp_path / "PORT_GNSS_UPDATE_TRACE.csv"
    _write_csv(
        port,
        [
            {"gnss_time": 100.0, "yaw_update": 1, "yaw_mode": "NORMAL"},
            {"gnss_time": 101.0, "yaw_update": 0, "yaw_mode": "REJECT"},
        ],
    )
    source = tmp_path / "SOURCE_AWARE_WEIGHT_TRACE.csv"
    _write_csv(
        source,
        [
            {"time": 100.0, "source_id": "dual_antenna_yaw", "combined_R_scale": 2.0, "accepted": 1, "rejected": 0},
            {"time": 101.0, "source_id": "dual_antenna_yaw", "combined_R_scale": 4.0, "accepted": 0, "rejected": 1},
            {"time": 100.0, "source_id": "receiver_position", "combined_R_scale": 99.0, "accepted": 1, "rejected": 0},
        ],
    )
    registry, ledgers = _full_registry_and_ledgers(_mixed_ledger)
    artifacts = {
        row["run_id"]: {
            "port_gnss_update_trace": port,
            "source_aware_weight_trace": source,
        }
        for row in registry
    }
    sealed = {
        row["run_id"]: {
            "module_counters": {
                **_yaw_counters(normal=1, downweight=0, reject=1),
                "source_aware_evaluation_count": 3,
                "source_aware_weight_changed_count": 3,
            }
        }
        for row in registry
    }
    rows = build_source_aware_response_rows(registry, artifacts, ledgers, sealed)
    first = rows[0]
    assert first["ledger_epoch_domain_count"] == 303
    assert first["dual_yaw_source_aware_row_count"] == 2
    assert first["source_aware_response_eligible_row_count"] == 2
    assert first["pre_source_aware_schemeC_rejected_count"] == 0
    assert first["source_aware_row_on_port_reject_count"] == 1
    assert math.isclose(first["perturbed_epoch_R_scale_p50"], 3.0)
    assert math.isclose(first["perturbed_epoch_R_scale_p95"], 3.9)
    assert first["perturbed_epoch_R_scale_max"] == 4.0
    assert first["perturbed_epoch_source_aware_changed_ratio"] == 1.0


def test_c10_hard_reject_without_sa_rows_is_pre_source_aware_not_missing(
    tmp_path: Path,
) -> None:
    port = tmp_path / "PORT_GNSS_UPDATE_TRACE.csv"
    _write_csv(
        port,
        [
            {"gnss_time": time_value, "yaw_update": 0, "yaw_mode": "REJECT"}
            for time_value in EPOCH_TIMES
            if 66.0 < time_value <= 340.0
        ],
    )
    source = tmp_path / "SOURCE_AWARE_WEIGHT_TRACE.csv"
    _write_csv(
        source,
        [
            {"time": 67.0, "source_id": "receiver_position", "combined_R_scale": 1.0, "accepted": 1, "rejected": 0}
        ],
    )
    registry, ledgers = _full_registry_and_ledgers(
        lambda case_id: _ledger(
            case_id, [("yaw_std_scale", set(EPOCH_TIMES), set())]
        )
    )
    artifacts = {
        row["run_id"]: {
            "port_gnss_update_trace": port,
            "source_aware_weight_trace": source,
        }
        for row in registry
    }
    sealed = {
        row["run_id"]: {
            "module_counters": {
                **_yaw_counters(normal=0, downweight=0, reject=274),
                "source_aware_evaluation_count": 1,
                "source_aware_weight_changed_count": 0,
            }
        }
        for row in registry
    }
    first = build_source_aware_response_rows(
        registry, artifacts, ledgers, sealed
    )[0]
    assert first["perturbed_epoch_count"] == 303
    assert first["perturbed_epoch_in_window_count"] == 274
    assert first["perturbed_epoch_out_of_window_count"] == 29
    assert first["pre_source_aware_schemeC_rejected_count"] == 274
    assert first["port_nonreject_source_aware_missing_count"] == 0
    assert first["dual_yaw_source_aware_in_window_row_count"] == 0
    assert first["dual_yaw_source_aware_out_of_window_missing_count"] == 29
    assert first["perturbed_epoch_R_scale_p50"] == ""


def test_spike_hard_reject_without_sa_row_is_classified(tmp_path: Path) -> None:
    port = tmp_path / "PORT_GNSS_UPDATE_TRACE.csv"
    _write_csv(
        port,
        [{"gnss_time": 100.0, "yaw_update": 0, "yaw_mode": "REJECT"}],
    )
    source = tmp_path / "SOURCE_AWARE_WEIGHT_TRACE.csv"
    _write_csv(
        source,
        [
            {"time": 100.0, "source_id": "receiver_position", "combined_R_scale": 1.0, "accepted": 1, "rejected": 0}
        ],
    )
    registry, ledgers = _full_registry_and_ledgers(
        lambda case_id: _ledger(
            case_id, [("signed_yaw_spike", {100.0}, set())]
        )
    )
    artifacts = {
        row["run_id"]: {
            "port_gnss_update_trace": port,
            "source_aware_weight_trace": source,
        }
        for row in registry
    }
    sealed = {
        row["run_id"]: {
            "module_counters": {
                **_yaw_counters(normal=0, downweight=0, reject=1),
                "source_aware_evaluation_count": 1,
                "source_aware_weight_changed_count": 0,
            }
        }
        for row in registry
    }
    first = build_source_aware_response_rows(
        registry, artifacts, ledgers, sealed
    )[0]
    assert first["pre_source_aware_schemeC_rejected_count"] == 1
    assert first["port_nonreject_source_aware_missing_count"] == 0
    assert first["source_aware_response_eligible_row_count"] == 0


def test_selected_epochs_outside_frozen_window_are_counted_not_required(
    tmp_path: Path,
) -> None:
    selected = {66.0, 67.0, 340.0, 341.0}
    ledger_factory = lambda case_id: _ledger(
        case_id, [("baseline_vector_noise", selected, set())]
    )
    port = tmp_path / "PORT_GNSS_UPDATE_TRACE.csv"
    _write_csv(
        port,
        [
            {"gnss_time": 67.0, "yaw_update": 1, "yaw_mode": "NORMAL"},
            {"gnss_time": 340.0, "yaw_update": 1, "yaw_mode": "DOWNWEIGHT"},
        ],
    )

    action_registry = _action_registry("C04_fixture")
    action_artifacts = {
        row["run_id"]: {
            "port_gnss_update_trace": port,
            "source_aware_weight_trace": None,
        }
        for row in action_registry
    }
    action_sealed = {
        row["run_id"]: {
            "module_counters": {
                **_yaw_counters(normal=1, downweight=1, reject=0),
                "source_aware_evaluation_count": 0,
                "source_aware_weight_changed_count": 0,
            }
        }
        for row in action_registry
    }
    action = build_perturbation_action_rows(
        action_registry,
        action_artifacts,
        {"C04_fixture": ledger_factory("C04_fixture")},
        action_sealed,
    )[0]
    assert action["perturbed_epoch_count"] == 4
    assert action["perturbed_epoch_in_window_count"] == 2
    assert action["perturbed_epoch_out_of_window_count"] == 2
    assert action["perturbed_epoch_missing_trace_count"] == 2
    assert action["perturbed_epoch_out_of_window_missing_trace_count"] == 2
    assert action["nonwithheld_missing_trace_count"] == 0

    source = tmp_path / "SOURCE_AWARE_WEIGHT_TRACE.csv"
    _write_csv(
        source,
        [
            {"time": 67.0, "source_id": "dual_antenna_yaw", "combined_R_scale": 2.0, "accepted": 1, "rejected": 0},
            {"time": 340.0, "source_id": "dual_antenna_yaw", "combined_R_scale": 3.0, "accepted": 1, "rejected": 0},
        ],
    )
    full_registry, full_ledgers = _full_registry_and_ledgers(ledger_factory)
    full_artifacts = {
        row["run_id"]: {
            "port_gnss_update_trace": port,
            "source_aware_weight_trace": source,
        }
        for row in full_registry
    }
    full_sealed = {
        row["run_id"]: {
            "module_counters": {
                **_yaw_counters(normal=1, downweight=1, reject=0),
                "source_aware_evaluation_count": 2,
                "source_aware_weight_changed_count": 2,
            }
        }
        for row in full_registry
    }
    response = build_source_aware_response_rows(
        full_registry, full_artifacts, full_ledgers, full_sealed
    )[0]
    assert response["perturbed_epoch_count"] == 4
    assert response["perturbed_epoch_in_window_count"] == 2
    assert response["perturbed_epoch_out_of_window_count"] == 2
    assert response["dual_yaw_source_aware_missing_count"] == 2
    assert response["dual_yaw_source_aware_out_of_window_missing_count"] == 2
    assert response["port_nonreject_source_aware_missing_count"] == 0


def test_nonwithheld_in_window_perturbation_missing_from_port_fails_closed(
    tmp_path: Path,
) -> None:
    port = tmp_path / "PORT_GNSS_UPDATE_TRACE.csv"
    _write_csv(port, [{"gnss_time": 99.0, "yaw_update": 1, "yaw_mode": "NORMAL"}])
    registry = _action_registry("C07_fixture")
    artifacts = {
        row["run_id"]: {
            "port_gnss_update_trace": port,
            "source_aware_weight_trace": None,
        }
        for row in registry
    }
    sealed = {
        row["run_id"]: {
            "module_counters": {
                **_yaw_counters(normal=1, downweight=0, reject=0),
                "source_aware_evaluation_count": 0,
                "source_aware_weight_changed_count": 0,
            }
        }
        for row in registry
    }
    ledger = _ledger(
        "C07_fixture", [("baseline_vector_spike", {100.0}, set())]
    )
    with pytest.raises(Exception, match="In-window non-withheld perturbation epochs"):
        build_perturbation_action_rows(
            registry, artifacts, {"C07_fixture": ledger}, sealed
        )


def test_port_nonreject_without_dual_yaw_sa_row_fails_closed(tmp_path: Path) -> None:
    port = tmp_path / "PORT_GNSS_UPDATE_TRACE.csv"
    _write_csv(port, [{"gnss_time": 100.0, "yaw_update": 1, "yaw_mode": "NORMAL"}])
    source = tmp_path / "SOURCE_AWARE_WEIGHT_TRACE.csv"
    _write_csv(
        source,
        [
            {"time": 100.0, "source_id": "receiver_position", "combined_R_scale": 1.0, "accepted": 1, "rejected": 0}
        ],
    )
    registry, ledgers = _full_registry_and_ledgers(
        lambda case_id: _ledger(
            case_id, [("baseline_vector_spike", {100.0}, set())]
        )
    )
    artifacts = {
        row["run_id"]: {
            "port_gnss_update_trace": port,
            "source_aware_weight_trace": source,
        }
        for row in registry
    }
    sealed = {
        row["run_id"]: {
            "module_counters": {
                **_yaw_counters(normal=1, downweight=0, reject=0),
                "source_aware_evaluation_count": 1,
                "source_aware_weight_changed_count": 0,
            }
        }
        for row in registry
    }
    with pytest.raises(Exception, match="PORT non-REJECT"):
        build_source_aware_response_rows(registry, artifacts, ledgers, sealed)


def test_truncated_port_trace_cannot_disagree_with_sealed_global_counters(
    tmp_path: Path,
) -> None:
    port = tmp_path / "PORT_GNSS_UPDATE_TRACE.csv"
    _write_csv(port, [{"gnss_time": 100.0, "yaw_update": 1, "yaw_mode": "NORMAL"}])
    registry = _action_registry("C00_fixture")
    artifacts = {
        row["run_id"]: {
            "port_gnss_update_trace": port,
            "source_aware_weight_trace": None,
        }
        for row in registry
    }
    sealed = {
        row["run_id"]: {
            "module_counters": {
                **_yaw_counters(normal=2, downweight=0, reject=0),
                "source_aware_evaluation_count": 0,
                "source_aware_weight_changed_count": 0,
            }
        }
        for row in registry
    }
    ledger = _ledger("C00_fixture", [("none", set(), set())])
    with pytest.raises(Exception, match="global counter mismatch"):
        build_perturbation_action_rows(
            registry, artifacts, {"C00_fixture": ledger}, sealed
        )
