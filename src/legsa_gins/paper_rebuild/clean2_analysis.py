"""Descriptive CLEAN2 factorial, Classic-18, and sentinel-LOO analysis."""

from __future__ import annotations

import csv
import json
import math
import statistics
import bisect
from pathlib import Path
from typing import Any, Mapping, Sequence

from .clean2_ablation import (
    MODULE_ORDER,
    PAIRWISE_TERMS,
    AblationCatalog,
    descriptive_effect_label,
    effect_coefficient,
    reported_factorial_effect,
)
from .clean2_case_provider import validate_case_provider_index
from .clean2_run_registry import read_run_registry
from .manifest import sha256_file, write_json_atomic


class Clean2AnalysisError(RuntimeError):
    """A CLEAN2 aggregate is partial, non-finite, or internally inconsistent."""


FORMAL_WINDOW_START_EXCLUSIVE_SECONDS = 66.0
FORMAL_WINDOW_END_INCLUSIVE_SECONDS = 340.0
CLASSIC18_LEDGER_EPOCH_DOMAIN_COUNT = 303


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).resolve(strict=True).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise Clean2AnalysisError(f"Analysis input table is empty: {Path(path).name}")
    return rows


def _csv_bool(value: Any) -> bool:
    normalized = str(value).strip().casefold()
    if normalized not in {"true", "false", "1", "0"}:
        raise Clean2AnalysisError(f"Invalid boolean token in action evidence: {value}")
    return normalized in {"true", "1"}


def _percentile_type7(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise Clean2AnalysisError("Cannot aggregate an empty response series")
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def load_case_perturbation_ledgers(
    case_provider_index_path: str | Path,
) -> dict[str, list[dict[str, str]]]:
    """Resolve the 18 current-provider ledgers without consulting trace or metrics."""

    payload, validated_cases = validate_case_provider_index(case_provider_index_path)
    cases = payload.get("cases")
    if payload.get("case_count") != 18 or not isinstance(cases, list) or len(cases) != 18:
        raise Clean2AnalysisError("Classic-18 provider index is incomplete")
    result: dict[str, list[dict[str, str]]] = {}
    for case in cases:
        if not isinstance(case, Mapping):
            raise Clean2AnalysisError("Classic-18 provider index row is malformed")
        case_id = str(case.get("case_id") or "")
        validated = validated_cases.get(case_id)
        if validated is None:
            raise Clean2AnalysisError("Validated Classic-18 case row is missing")
        manifest = Path(str(validated.get("manifest_path") or "")).resolve(strict=True)
        ledger = manifest.parent / "CASE_PERTURBATION_LEDGER.csv"
        rows = _read_csv(ledger)
        if not case_id or any(row.get("case_id") != case_id for row in rows):
            raise Clean2AnalysisError("Case perturbation ledger identity mismatch")
        _validate_complete_case_ledger(rows, case_id=case_id)
        if case_id in result:
            raise Clean2AnalysisError("Case perturbation ledgers contain duplicate ids")
        result[case_id] = rows
    if len(result) != 18:
        raise Clean2AnalysisError("Classic-18 perturbation ledger set is incomplete")
    return result


def _ledger_time_domain(
    ledger_rows: Sequence[Mapping[str, Any]],
) -> set[float]:
    """Return every unique provider epoch retained by a case ledger.

    Mixed cases have one 303-row block per operation, so duplicate timestamps
    across different operations are expected.  The analysis domain remains the
    complete provider epoch set; selected perturbations are a subset of it.
    """

    domain: set[float] = set()
    for row in ledger_rows:
        try:
            time_value = float(row["time"])
        except (KeyError, TypeError, ValueError) as exc:
            raise Clean2AnalysisError("Perturbation ledger has an invalid time") from exc
        if not math.isfinite(time_value):
            raise Clean2AnalysisError("Perturbation ledger time is non-finite")
        domain.add(time_value)
    if not domain:
        raise Clean2AnalysisError("Perturbation ledger epoch domain is empty")
    return domain


def _validate_complete_case_ledger(
    ledger_rows: Sequence[Mapping[str, Any]], *, case_id: str
) -> set[float]:
    """Require each declared operation to retain the same complete 303 epochs."""

    by_operation: dict[str, list[float]] = {}
    for row in ledger_rows:
        operation = str(row.get("operation") or "")
        if not operation:
            raise Clean2AnalysisError(f"Case ledger operation is blank: {case_id}")
        try:
            time_value = float(row["time"])
        except (KeyError, TypeError, ValueError) as exc:
            raise Clean2AnalysisError(f"Case ledger time is invalid: {case_id}") from exc
        if not math.isfinite(time_value):
            raise Clean2AnalysisError(f"Case ledger time is non-finite: {case_id}")
        by_operation.setdefault(operation, []).append(time_value)
    if not by_operation:
        raise Clean2AnalysisError(f"Case ledger has no operations: {case_id}")
    reference: set[float] | None = None
    for operation, times in by_operation.items():
        domain = set(times)
        if (
            len(times) != CLASSIC18_LEDGER_EPOCH_DOMAIN_COUNT
            or len(domain) != CLASSIC18_LEDGER_EPOCH_DOMAIN_COUNT
            or any(right <= left for left, right in zip(times, times[1:]))
        ):
            raise Clean2AnalysisError(
                f"Case ledger does not retain one ordered 303-epoch domain: "
                f"{case_id}/{operation}"
            )
        if reference is None:
            reference = domain
        elif domain != reference:
            raise Clean2AnalysisError(
                f"Case ledger operation domains disagree: {case_id}/{operation}"
            )
    if reference is None:
        raise Clean2AnalysisError(f"Case ledger has no epoch domain: {case_id}")
    return reference


def _split_formal_window(times: set[float]) -> tuple[set[float], set[float]]:
    """Split epochs by the frozen solver interval ``66 < t <= 340``."""

    in_window = {
        value
        for value in times
        if FORMAL_WINDOW_START_EXCLUSIVE_SECONDS
        < value
        <= FORMAL_WINDOW_END_INCLUSIVE_SECONDS
    }
    return in_window, set(times).difference(in_window)


def _selected_time_sets(
    ledger_rows: Sequence[Mapping[str, Any]],
) -> tuple[set[float], set[float], set[float], tuple[str, ...]]:
    selected: set[float] = set()
    withheld: set[float] = set()
    spike: set[float] = set()
    operations: set[str] = set()
    for row in ledger_rows:
        operation = str(row.get("operation") or "")
        if operation:
            operations.add(operation)
        if not _csv_bool(row.get("selected", False)) or operation == "none":
            continue
        try:
            time_value = float(row["time"])
        except (KeyError, TypeError, ValueError) as exc:
            raise Clean2AnalysisError("Perturbation ledger has an invalid selected time") from exc
        if not math.isfinite(time_value):
            raise Clean2AnalysisError("Perturbation ledger time is non-finite")
        selected.add(time_value)
        if _csv_bool(row["original_yaw_valid"]) and not _csv_bool(row["modified_yaw_valid"]):
            withheld.add(time_value)
        if operation in {"baseline_vector_spike", "signed_yaw_spike"}:
            spike.add(time_value)
    return selected, withheld, spike, tuple(sorted(operations))


def _nearest_rows_by_time(
    requested: set[float],
    rows: Sequence[Mapping[str, Any]],
    *,
    time_field: str,
    tolerance_seconds: float = 1.0e-6,
) -> tuple[dict[float, Mapping[str, Any]], set[float]]:
    parsed: list[tuple[float, Mapping[str, Any]]] = []
    for row in rows:
        try:
            value = float(row[time_field])
        except (KeyError, TypeError, ValueError) as exc:
            raise Clean2AnalysisError(f"Action trace lacks a valid {time_field}") from exc
        if not math.isfinite(value):
            raise Clean2AnalysisError("Action trace time is non-finite")
        parsed.append((value, row))
    parsed.sort(key=lambda item: item[0])
    times = [item[0] for item in parsed]
    if any(math.isclose(left, right, rel_tol=0.0, abs_tol=1e-12) for left, right in zip(times, times[1:])):
        raise Clean2AnalysisError("Action trace has duplicate timestamps")
    matched: dict[float, Mapping[str, Any]] = {}
    for wanted in requested:
        index = bisect.bisect_left(times, wanted)
        candidates = []
        if index > 0:
            candidates.append(parsed[index - 1])
        if index < len(parsed):
            candidates.append(parsed[index])
        if not candidates:
            continue
        value, row = min(candidates, key=lambda item: abs(item[0] - wanted))
        if abs(value - wanted) <= tolerance_seconds:
            matched[wanted] = row
    return matched, set(requested).difference(matched)


def _yaw_action(row: Mapping[str, Any]) -> str:
    mode = str(row.get("yaw_mode") or "NONE").strip().upper()
    if mode not in {"NONE", "NORMAL", "DOWNWEIGHT", "REJECT"}:
        raise Clean2AnalysisError(f"Unknown scheme-C action in PORT trace: {mode}")
    if mode == "NONE" and _csv_bool(row.get("yaw_update", False)):
        # Basic fixed-std uses the yaw update but may not route through scheme-C
        # counters.  It is still an accepted/normal attempt for response counts.
        return "NORMAL"
    return mode


def _action_counts(
    times: set[float], update_rows: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, int], set[float], set[float]]:
    matched, missing = _nearest_rows_by_time(times, update_rows, time_field="gnss_time")
    actions = [_yaw_action(row) for row in matched.values()]
    normal = actions.count("NORMAL")
    downweighted = actions.count("DOWNWEIGHT")
    rejected = actions.count("REJECT")
    return {
        "attempted": normal + downweighted + rejected,
        "accepted": normal + downweighted,
        "normal": normal,
        "downweighted": downweighted,
        "rejected": rejected,
    }, set(matched), missing


def _sealed_counter_map(
    sealed_runs_by_id: Mapping[str, Mapping[str, Any]], run_id: str
) -> dict[str, int]:
    sealed = sealed_runs_by_id.get(run_id)
    counters = sealed.get("module_counters") if isinstance(sealed, Mapping) else None
    if not isinstance(counters, Mapping):
        raise Clean2AnalysisError(f"Sealed global counters are missing: {run_id}")
    try:
        result = {str(key): int(value) for key, value in counters.items()}
    except (TypeError, ValueError) as exc:
        raise Clean2AnalysisError("Sealed global counters are malformed") from exc
    return result


def _reconcile_global_action_trace(
    *, run_id: str, update_rows: Sequence[Mapping[str, Any]], counters: Mapping[str, int]
) -> dict[str, int]:
    actions = [_yaw_action(row) for row in update_rows]
    actual = {
        "yaw_normal_count": actions.count("NORMAL"),
        "yaw_downweight_count": actions.count("DOWNWEIGHT"),
        "yaw_reject_count": actions.count("REJECT"),
    }
    actual["yaw_attempt_count"] = sum(actual.values())
    actual["yaw_accepted_count"] = actual["yaw_normal_count"] + actual["yaw_downweight_count"]
    for field, value in actual.items():
        if counters.get(field) != value:
            raise Clean2AnalysisError(
                f"Sealed PORT action trace/global counter mismatch: {run_id}/{field}"
            )
    return actual


def _reconcile_global_source_trace(
    *,
    run_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    counters: Mapping[str, int],
) -> dict[str, int]:
    scales: list[float] = []
    for row in source_rows:
        try:
            scale = float(row["combined_R_scale"])
        except (KeyError, TypeError, ValueError) as exc:
            raise Clean2AnalysisError("SOURCE_AWARE_WEIGHT_TRACE has invalid R scale") from exc
        if not math.isfinite(scale) or scale <= 0.0:
            raise Clean2AnalysisError("SOURCE_AWARE_WEIGHT_TRACE has non-finite R scale")
        scales.append(scale)
    changed = sum(not math.isclose(scale, 1.0, rel_tol=0.0, abs_tol=1e-12) for scale in scales)
    if (
        counters.get("source_aware_evaluation_count") != len(source_rows)
        or counters.get("source_aware_weight_changed_count") != changed
    ):
        raise Clean2AnalysisError(f"Sealed source-aware trace/global counter mismatch: {run_id}")
    return {"evaluation_count": len(source_rows), "changed_count": changed}


def build_perturbation_action_rows(
    registry_rows: Sequence[Mapping[str, Any]],
    artifact_index: Mapping[str, Mapping[str, Path | None]],
    ledgers_by_case: Mapping[str, Sequence[Mapping[str, Any]]],
    sealed_runs_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Join declared perturbation epochs to neutral scheme-C action labels."""

    if len(registry_rows) != 110 or set(artifact_index) != {
        str(row["run_id"]) for row in registry_rows
    }:
        raise Clean2AnalysisError("Perturbation-action join requires all 110 runs")
    if set(sealed_runs_by_id) != set(artifact_index):
        raise Clean2AnalysisError("Perturbation-action join lacks the complete sealed run set")
    output: list[dict[str, Any]] = []
    for registry in registry_rows:
        run_id = str(registry["run_id"])
        case_id = str(registry["case_id"])
        ledger = ledgers_by_case.get(case_id)
        trace_path = artifact_index[run_id].get("port_gnss_update_trace")
        if ledger is None or trace_path is None:
            raise Clean2AnalysisError("CLEAN2 action join lacks a case ledger or sealed PORT trace")
        update_rows = _read_csv(trace_path)
        counters = _sealed_counter_map(sealed_runs_by_id, run_id)
        global_actions = _reconcile_global_action_trace(
            run_id=run_id, update_rows=update_rows, counters=counters
        )
        source_path = artifact_index[run_id].get("source_aware_weight_trace")
        if source_path is not None:
            _reconcile_global_source_trace(
                run_id=run_id,
                source_rows=_read_csv(source_path),
                counters=counters,
            )
        elif counters.get("source_aware_evaluation_count") != 0:
            raise Clean2AnalysisError("SA counters are nonzero without a sealed source trace")
        ledger_domain = _ledger_time_domain(ledger)
        ledger_in_window, ledger_out_of_window = _split_formal_window(ledger_domain)
        selected, withheld, spikes, operations = _selected_time_sets(ledger)
        selected_in_window, selected_out_of_window = _split_formal_window(selected)
        withheld_in_window, withheld_out_of_window = _split_formal_window(withheld)
        spikes_in_window, spikes_out_of_window = _split_formal_window(spikes)

        # 中文说明：ledger 保留完整 303 域；formal PORT 只覆盖 66<t<=340。
        # 因此只对窗口内且未 withheld 的 epoch 要求 PORT 行，窗外缺行不是执行失败。
        matched_selected_all, missing_selected_all = _nearest_rows_by_time(
            selected, update_rows, time_field="gnss_time"
        )
        perturbed, matched_selected_in, missing_selected_in = _action_counts(
            selected_in_window, update_rows
        )
        matched_spikes_all, missing_spikes_all = _nearest_rows_by_time(
            spikes, update_rows, time_field="gnss_time"
        )
        spike_actions, matched_spikes_in, missing_spikes_in = _action_counts(
            spikes_in_window, update_rows
        )
        unexpected_missing = missing_selected_in.difference(withheld_in_window)
        unexpected_spike_missing = missing_spikes_in.difference(withheld_in_window)
        if unexpected_missing or unexpected_spike_missing:
            raise Clean2AnalysisError(
                f"In-window non-withheld perturbation epochs are missing from PORT trace: {run_id}"
            )
        output.append(
            {
                "run_id": run_id,
                "case_id": case_id,
                "structural_method": registry["structural_method"],
                "ablation_id": registry["ablation_id"],
                "alias_roles": registry["alias_roles"],
                "operations": ";".join(operations),
                "formal_window_rule": "66<t<=340",
                "ledger_epoch_domain_count": len(ledger_domain),
                "ledger_epoch_in_window_count": len(ledger_in_window),
                "ledger_epoch_out_of_window_count": len(ledger_out_of_window),
                "perturbed_epoch_count": len(selected),
                "perturbed_epoch_in_window_count": len(selected_in_window),
                "perturbed_epoch_out_of_window_count": len(selected_out_of_window),
                "perturbed_epoch_matched_trace_count": len(matched_selected_all),
                "perturbed_epoch_missing_trace_count": len(missing_selected_all),
                "perturbed_epoch_in_window_matched_trace_count": len(matched_selected_in),
                "perturbed_epoch_in_window_missing_trace_count": len(missing_selected_in),
                "perturbed_epoch_out_of_window_matched_trace_count": len(
                    set(matched_selected_all).intersection(selected_out_of_window)
                ),
                "perturbed_epoch_out_of_window_missing_trace_count": len(
                    missing_selected_all.intersection(selected_out_of_window)
                ),
                "in_window_nonwithheld_epoch_count": len(
                    selected_in_window.difference(withheld_in_window)
                ),
                "nonwithheld_missing_trace_count": len(unexpected_missing),
                "perturbed_epoch_attempted_count": perturbed["attempted"],
                "perturbed_epoch_accepted_count": perturbed["accepted"],
                "perturbed_epoch_normal_count": perturbed["normal"],
                "perturbed_epoch_downweighted_count": perturbed["downweighted"],
                "perturbed_epoch_rejected_count": perturbed["rejected"],
                "perturbed_epoch_in_window_attempted_count": perturbed["attempted"],
                "perturbed_epoch_in_window_accepted_count": perturbed["accepted"],
                "perturbed_epoch_in_window_normal_count": perturbed["normal"],
                "perturbed_epoch_in_window_downweighted_count": perturbed[
                    "downweighted"
                ],
                "perturbed_epoch_in_window_rejected_count": perturbed["rejected"],
                "in_window_nonwithheld_missing_trace_count": len(unexpected_missing),
                "withheld_epoch_count": len(withheld),
                "withheld_epoch_in_window_count": len(withheld_in_window),
                "withheld_epoch_out_of_window_count": len(withheld_out_of_window),
                "spike_epoch_count": len(spikes),
                "spike_epoch_in_window_count": len(spikes_in_window),
                "spike_epoch_out_of_window_count": len(spikes_out_of_window),
                "spike_epoch_matched_trace_count": len(matched_spikes_all),
                "spike_epoch_missing_trace_count": len(missing_spikes_all),
                "spike_epoch_in_window_matched_trace_count": len(matched_spikes_in),
                "spike_epoch_in_window_missing_trace_count": len(missing_spikes_in),
                "spike_epoch_out_of_window_matched_trace_count": len(
                    set(matched_spikes_all).intersection(spikes_out_of_window)
                ),
                "spike_epoch_out_of_window_missing_trace_count": len(
                    missing_spikes_all.intersection(spikes_out_of_window)
                ),
                "spike_epoch_attempted_count": spike_actions["attempted"],
                "spike_epoch_consumed_count": spike_actions["accepted"],
                "spike_epoch_downweighted_count": spike_actions["downweighted"],
                "spike_epoch_rejected_count": spike_actions["rejected"],
                "spike_epoch_in_window_attempted_count": spike_actions["attempted"],
                "spike_epoch_in_window_consumed_count": spike_actions["accepted"],
                "spike_epoch_in_window_downweighted_count": spike_actions[
                    "downweighted"
                ],
                "spike_epoch_in_window_rejected_count": spike_actions["rejected"],
                "accepted_epoch_wording": "accepted specified perturbation epoch",
                "global_yaw_attempt_count_crosschecked": global_actions["yaw_attempt_count"],
                "global_action_counter_crosscheck": True,
                "global_source_aware_counter_crosscheck": True,
            }
        )
    return output


def build_source_aware_response_rows(
    registry_rows: Sequence[Mapping[str, Any]],
    artifact_index: Mapping[str, Mapping[str, Path | None]],
    ledgers_by_case: Mapping[str, Sequence[Mapping[str, Any]]],
    sealed_runs_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize full-LegSA dual-yaw R scales only on declared perturbation epochs."""

    full_rows = [row for row in registry_rows if _canonical_name(row) == "LegSA_Paper_V1"]
    if len(full_rows) != 18:
        raise Clean2AnalysisError("Source-aware response requires 18 canonical full-LegSA runs")
    if not {str(row["run_id"]) for row in full_rows}.issubset(sealed_runs_by_id):
        raise Clean2AnalysisError("Source-aware response lacks sealed global counters")
    output: list[dict[str, Any]] = []
    for registry in full_rows:
        run_id = str(registry["run_id"])
        case_id = str(registry["case_id"])
        artifacts = artifact_index.get(run_id)
        if not isinstance(artifacts, Mapping):
            raise Clean2AnalysisError("Full LegSA run lacks a sealed artifact-index row")
        port_path = artifacts.get("port_gnss_update_trace")
        source_path = artifact_index[run_id].get("source_aware_weight_trace")
        if port_path is None or source_path is None:
            raise Clean2AnalysisError(
                "Full LegSA run lacks a sealed PORT or SOURCE_AWARE_WEIGHT_TRACE"
            )
        ledger = ledgers_by_case.get(case_id)
        if ledger is None:
            raise Clean2AnalysisError("Full LegSA run lacks its perturbation ledger")
        ledger_domain = _ledger_time_domain(ledger)
        ledger_in_window, ledger_out_of_window = _split_formal_window(ledger_domain)
        selected, withheld, _, operations = _selected_time_sets(ledger)
        selected_in_window, selected_out_of_window = _split_formal_window(selected)
        withheld_in_window, withheld_out_of_window = _split_formal_window(withheld)
        update_rows = _read_csv(port_path)
        counters = _sealed_counter_map(sealed_runs_by_id, run_id)
        _reconcile_global_action_trace(
            run_id=run_id, update_rows=update_rows, counters=counters
        )
        all_source_rows = _read_csv(source_path)
        source_rows = [
            row for row in all_source_rows if row.get("source_id") == "dual_antenna_yaw"
        ]
        _reconcile_global_source_trace(
            run_id=run_id,
            source_rows=all_source_rows,
            counters=counters,
        )
        port_matched_all, port_missing_all = _nearest_rows_by_time(
            selected, update_rows, time_field="gnss_time"
        )
        port_matched_in, port_missing_in = _nearest_rows_by_time(
            selected_in_window, update_rows, time_field="gnss_time"
        )
        required_port_missing = port_missing_in.difference(withheld_in_window)
        if required_port_missing:
            raise Clean2AnalysisError(
                f"In-window non-withheld perturbation epochs are missing from PORT trace: {run_id}"
            )

        source_matched_all, source_missing_all = _nearest_rows_by_time(
            selected, source_rows, time_field="time"
        )
        source_matched_in, source_missing_in = _nearest_rows_by_time(
            selected_in_window, source_rows, time_field="time"
        )
        required_source_missing: set[float] = set()
        pre_source_aware_scheme_c_rejected: set[float] = set()
        source_row_on_port_reject: set[float] = set()
        for time_value in selected_in_window.difference(withheld_in_window):
            port_row = port_matched_in.get(time_value)
            if port_row is None:
                # The fail-closed PORT check above already handles this branch.
                continue
            port_action = _yaw_action(port_row)
            if time_value in source_matched_in:
                source_rejected = _csv_bool(
                    source_matched_in[time_value].get("rejected", False)
                )
                if port_action == "REJECT":
                    # This is a post-policy/source-aware reject and legitimately
                    # has a source trace row.
                    if not source_rejected:
                        raise Clean2AnalysisError(
                            f"PORT reject/source-aware action mismatch: {run_id}"
                        )
                    source_row_on_port_reject.add(time_value)
                elif source_rejected:
                    raise Clean2AnalysisError(
                        f"PORT non-reject/source-aware action mismatch: {run_id}"
                    )
                continue
            if port_action == "REJECT":
                # 中文说明：scheme-C hard reject 在 source-aware 之前返回；没有
                # SA 行是预期证据，必须单独分类，不能误报为 trace 缺失。
                pre_source_aware_scheme_c_rejected.add(time_value)
            else:
                required_source_missing.add(time_value)
        if required_source_missing:
            raise Clean2AnalysisError(
                f"PORT non-REJECT perturbation epochs are missing from source-aware trace: {run_id}"
            )

        response_matched = {
            time_value: row
            for time_value, row in source_matched_in.items()
            if time_value not in withheld_in_window
        }
        scales = [float(row["combined_R_scale"]) for row in response_matched.values()]
        if not all(math.isfinite(value) and value > 0.0 for value in scales):
            raise Clean2AnalysisError("Perturbed-epoch source-aware R scale is invalid")
        changed = [
            row
            for row in response_matched.values()
            if _csv_bool(row.get("rejected", False))
            or not math.isclose(float(row["combined_R_scale"]), 1.0, rel_tol=0.0, abs_tol=1e-12)
        ]
        accepted = sum(
            _csv_bool(row.get("accepted", False)) for row in response_matched.values()
        )
        rejected = sum(
            _csv_bool(row.get("rejected", False)) for row in response_matched.values()
        )
        output.append(
            {
                "run_id": run_id,
                "case_id": case_id,
                "method": "LegSA_Paper_V1",
                "operations": ";".join(operations),
                "formal_window_rule": "66<t<=340",
                "ledger_epoch_domain_count": len(ledger_domain),
                "ledger_epoch_in_window_count": len(ledger_in_window),
                "ledger_epoch_out_of_window_count": len(ledger_out_of_window),
                "perturbed_epoch_count": len(selected),
                "perturbed_epoch_in_window_count": len(selected_in_window),
                "perturbed_epoch_out_of_window_count": len(selected_out_of_window),
                "in_window_nonwithheld_epoch_count": len(
                    selected_in_window.difference(withheld_in_window)
                ),
                "withheld_epoch_count": len(withheld),
                "withheld_epoch_in_window_count": len(withheld_in_window),
                "withheld_epoch_out_of_window_count": len(withheld_out_of_window),
                "perturbed_epoch_port_matched_count": len(port_matched_all),
                "perturbed_epoch_port_missing_count": len(port_missing_all),
                "perturbed_epoch_in_window_port_matched_count": len(port_matched_in),
                "perturbed_epoch_in_window_port_missing_count": len(port_missing_in),
                "perturbed_epoch_out_of_window_port_matched_count": len(
                    set(port_matched_all).intersection(selected_out_of_window)
                ),
                "perturbed_epoch_out_of_window_port_missing_count": len(
                    port_missing_all.intersection(selected_out_of_window)
                ),
                "dual_yaw_source_aware_row_count": len(source_matched_all),
                "dual_yaw_source_aware_missing_count": len(source_missing_all),
                "dual_yaw_source_aware_in_window_row_count": len(source_matched_in),
                "dual_yaw_source_aware_in_window_missing_count": len(source_missing_in),
                "dual_yaw_source_aware_out_of_window_row_count": len(
                    set(source_matched_all).intersection(selected_out_of_window)
                ),
                "dual_yaw_source_aware_out_of_window_missing_count": len(
                    source_missing_all.intersection(selected_out_of_window)
                ),
                "withheld_source_aware_missing_count": len(
                    source_missing_all.intersection(withheld)
                ),
                "withheld_source_aware_row_count": len(
                    set(source_matched_all).intersection(withheld)
                ),
                "pre_source_aware_schemeC_rejected_count": len(
                    pre_source_aware_scheme_c_rejected
                ),
                "source_aware_row_on_port_reject_count": len(source_row_on_port_reject),
                "port_nonreject_source_aware_missing_count": len(
                    required_source_missing
                ),
                "nonwithheld_source_aware_missing_count": len(required_source_missing),
                "source_aware_response_eligible_row_count": len(response_matched),
                "perturbed_epoch_R_scale_p50": "" if not scales else _percentile_type7(scales, 0.50),
                "perturbed_epoch_R_scale_p95": "" if not scales else _percentile_type7(scales, 0.95),
                "perturbed_epoch_R_scale_max": "" if not scales else max(scales),
                "perturbed_epoch_source_aware_changed_count": len(changed),
                "perturbed_epoch_source_aware_changed_ratio": (
                    "" if not response_matched else len(changed) / len(response_matched)
                ),
                "perturbed_epoch_source_aware_accepted_count": accepted,
                "perturbed_epoch_source_aware_rejected_count": rejected,
                "global_source_aware_counter_crosscheck": True,
            }
        )
    return output


def _flatten_metrics(summary: Mapping[str, Any]) -> dict[str, float]:
    metrics = summary.get("metrics")
    if not isinstance(metrics, Mapping):
        raise Clean2AnalysisError("CLEAN2 summary lacks metrics")
    flattened: dict[str, float] = {}
    for metric in ("horizontal", "up", "position_3d", "roll", "pitch", "yaw"):
        stats = metrics.get(metric)
        if not isinstance(stats, Mapping):
            raise Clean2AnalysisError(f"CLEAN2 summary lacks metric: {metric}")
        for statistic in ("rmse", "mae", "p95", "max"):
            value = float(stats.get(statistic, math.nan))
            if not math.isfinite(value):
                raise Clean2AnalysisError("CLEAN2 summary contains NaN or infinity")
            flattened[f"{metric}_{statistic}"] = value
    return flattened


def factorial_effect_tables(
    catalog: AblationCatalog,
    factorial_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compute beta and 2*beta exactly as frozen before results."""

    if len(factorial_rows) != 16:
        raise Clean2AnalysisError("C00 factorial table must contain 16 rows")
    by_id = {str(row["ablation_id"]): row for row in factorial_rows}
    if len(by_id) != 16:
        raise Clean2AnalysisError("C00 factorial ids are duplicated")
    metric_fields = sorted(
        field
        for field in factorial_rows[0]
        if field.endswith(("_rmse", "_mae", "_p95", "_max"))
    )
    if not metric_fields:
        raise Clean2AnalysisError("C00 factorial table has no metrics")
    main: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    for metric in metric_fields:
        values = {ablation_id: float(row[metric]) for ablation_id, row in by_id.items()}
        for module in MODULE_ORDER:
            beta = effect_coefficient(catalog, values, (module,))
            effect = reported_factorial_effect(catalog, values, (module,))
            main.append(
                {
                    "metric": metric,
                    "module": module,
                    "coefficient_beta": beta,
                    "reported_effect_2beta": effect,
                    "descriptive_label": descriptive_effect_label(effect),
                    "lower_is_better": True,
                    "p_value": "NOT_COMPUTED",
                }
            )
        for left, right in PAIRWISE_TERMS:
            beta = effect_coefficient(catalog, values, (left, right))
            effect = reported_factorial_effect(catalog, values, (left, right))
            pairs.append(
                {
                    "metric": metric,
                    "interaction": f"{left}_x_{right}",
                    "coefficient_beta": beta,
                    "reported_effect_2beta": effect,
                    "descriptive_label": descriptive_effect_label(effect),
                    "p_value": "NOT_COMPUTED",
                }
            )
    return main, pairs


def sentinel_marginal_loss(
    full_metrics: Mapping[str, float], no_module_metrics: Mapping[str, float]
) -> dict[str, float]:
    if set(full_metrics) != set(no_module_metrics):
        raise Clean2AnalysisError("Sentinel full/LOO metric fields differ")
    result = {
        metric: float(no_module_metrics[metric]) - float(full_metrics[metric])
        for metric in full_metrics
    }
    if not all(math.isfinite(value) for value in result.values()):
        raise Clean2AnalysisError("Sentinel marginal loss contains NaN or infinity")
    return result


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> Path:
    if not rows:
        raise Clean2AnalysisError(f"Refusing to write empty analysis table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    if any(set(row) != set(fields) for row in rows):
        raise Clean2AnalysisError(f"Analysis rows have inconsistent fields: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _canonical_name(row: Mapping[str, Any]) -> str | None:
    aliases = set(str(row.get("alias_roles") or "").split(";"))
    structural = str(row["structural_method"])
    if not row["ablation_id"]:
        return structural
    if "canonical_strong" in aliases:
        return "strong_dual_yaw_EKF"
    if "canonical_LegSA" in aliases:
        return "LegSA_Paper_V1"
    return None


def build_analysis_rows(
    registry_rows: Sequence[Mapping[str, Any]], summaries: Mapping[str, Mapping[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    if len(registry_rows) != 110 or set(summaries) != {str(row["run_id"]) for row in registry_rows}:
        raise Clean2AnalysisError("CLEAN2 analysis requires all 110 summaries")
    enriched: list[dict[str, Any]] = []
    for row in registry_rows:
        summary = summaries[str(row["run_id"])]
        enriched.append(
            {
                **dict(row),
                **_flatten_metrics(summary),
                "matched_epoch_count": int(summary["matched_epoch_count"]),
                "unmatched_epoch_count": int(summary["unmatched_epoch_count"]),
                "coverage": float(summary["coverage"]),
                "finite_output": bool(summary["finite_output"]),
            }
        )
    factorial = [row for row in enriched if row["case_id"].startswith("C00_") and row["ablation_id"]]
    canonical: list[dict[str, Any]] = []
    for row in enriched:
        method = _canonical_name(row)
        if method is not None:
            canonical.append({"method": method, **row})
    if len(canonical) != 72:
        raise Clean2AnalysisError("Canonical Classic-18 table must contain 18x4 rows")
    c00_by_method = {
        row["method"]: row for row in canonical if row["case_id"].startswith("C00_")
    }
    deltas: list[dict[str, Any]] = []
    metric_fields = [field for field in factorial[0] if field.endswith(("_rmse", "_mae", "_p95", "_max"))]
    for row in canonical:
        base = c00_by_method[row["method"]]
        deltas.append(
            {
                "case_id": row["case_id"],
                "method": row["method"],
                **{f"delta_{metric}": float(row[metric]) - float(base[metric]) for metric in metric_fields},
            }
        )
    sentinel_results: list[dict[str, Any]] = []
    sentinel_marginals: list[dict[str, Any]] = []
    sentinel_codes = {"C01", "C04", "C07", "C10", "C11", "C15"}
    for case_code in sentinel_codes:
        case_rows = [row for row in enriched if row["case_id"].startswith(case_code + "_")]
        full = next(row for row in case_rows if _canonical_name(row) == "LegSA_Paper_V1")
        sentinel_results.append({"sentinel_role": "FULL", **full})
        for row in case_rows:
            aliases = set(str(row["alias_roles"]).split(";"))
            loo = next((alias for alias in aliases if alias.startswith("LOO_NO_")), None)
            if loo is None:
                continue
            sentinel_results.append({"sentinel_role": loo, **row})
            marginal = sentinel_marginal_loss(
                {field: float(full[field]) for field in metric_fields},
                {field: float(row[field]) for field in metric_fields},
            )
            sentinel_marginals.append(
                {"case_id": row["case_id"], "module": loo.removeprefix("LOO_NO_"), **marginal}
            )
    if len(sentinel_results) != 30 or len(sentinel_marginals) != 24:
        raise Clean2AnalysisError("Sentinel full/LOO rows are incomplete")
    return {
        "enriched": enriched,
        "factorial": factorial,
        "canonical": canonical,
        "deltas": deltas,
        "sentinel_results": sentinel_results,
        "sentinel_marginals": sentinel_marginals,
    }


def family_seed_aggregates(canonical_deltas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    families = {
        "baseline_vector_noise": ("C04", "C05", "C06"),
        "baseline_vector_spike": ("C07", "C08", "C09"),
        "yaw_spike": ("C11", "C12", "C13"),
        "mixed": ("C15", "C16", "C17"),
    }
    metric_fields = [field for field in canonical_deltas[0] if field.startswith("delta_")]
    output: list[dict[str, Any]] = []
    methods = sorted({str(row["method"]) for row in canonical_deltas})
    for family, codes in families.items():
        for method in methods:
            rows = [
                row
                for row in canonical_deltas
                if row["method"] == method and any(str(row["case_id"]).startswith(code + "_") for code in codes)
            ]
            if len(rows) != 3:
                raise Clean2AnalysisError(f"Seed family {family}/{method} does not contain 3 seeds")
            for metric in metric_fields:
                values = [float(row[metric]) for row in rows]
                output.append(
                    {
                        "family": family,
                        "method": method,
                        "metric": metric,
                        "mean": statistics.fmean(values),
                        "median": statistics.median(values),
                        "worst": max(values),
                        "per_seed_values": json.dumps(values, separators=(",", ":")),
                        "seed_count": 3,
                    }
                )
    return output


def _canonical_delta_rows(canonical: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    c00 = {
        str(row["method"]): row
        for row in canonical
        if str(row["case_id"]).startswith("C00_")
    }
    if len(c00) != 4:
        raise Clean2AnalysisError("Canonical table lacks the four C00 references")
    metric_fields = [
        field
        for field in canonical[0]
        if field.endswith(("_rmse", "_mae", "_p95", "_max"))
    ]
    return [
        {
            "case_id": row["case_id"],
            "method": row["method"],
            **{
                f"delta_{metric}": float(row[metric]) - float(c00[str(row["method"])][metric])
                for metric in metric_fields
            },
        }
        for row in canonical
    ]


def _rows_equal(
    expected: Sequence[Mapping[str, Any]], actual: Sequence[Mapping[str, Any]]
) -> bool:
    if len(expected) != len(actual):
        return False
    for left, right in zip(expected, actual):
        if set(left) != set(right):
            return False
        for field in left:
            left_value, right_value = left[field], right[field]
            try:
                left_number, right_number = float(left_value), float(right_value)
            except (TypeError, ValueError):
                if str(left_value).casefold() != str(right_value).casefold():
                    return False
            else:
                if not (
                    math.isfinite(left_number)
                    and math.isfinite(right_number)
                    and math.isclose(
                        left_number, right_number, rel_tol=1.0e-12, abs_tol=1.0e-12
                    )
                ):
                    return False
    return True


def _independent_table_crosscheck(
    *,
    outputs: Mapping[str, Path],
    catalog: AblationCatalog,
    evaluation_row_crosscheck: Mapping[str, Any] | None,
) -> dict[str, Any]:
    factorial = _read_csv(outputs["factorial"])
    main_actual = _read_csv(outputs["main_effects"])
    pairs_actual = _read_csv(outputs["interactions"])
    main_expected, pairs_expected = factorial_effect_tables(catalog, factorial)
    canonical = _read_csv(outputs["canonical"])
    deltas_actual = _read_csv(outputs["deltas"])
    deltas_expected = _canonical_delta_rows(canonical)
    family_actual = _read_csv(outputs["family"])
    family_expected = family_seed_aggregates(deltas_actual)
    sentinel = _read_csv(outputs["sentinel"])
    marginal_actual = _read_csv(outputs["marginal"])
    sentinel_metric_fields = [
        field
        for field in sentinel[0]
        if field.endswith(("_rmse", "_mae", "_p95", "_max"))
    ]
    full_by_case = {
        row["case_id"]: row for row in sentinel if row["sentinel_role"] == "FULL"
    }
    marginal_expected = []
    for row in sentinel:
        if not row["sentinel_role"].startswith("LOO_NO_"):
            continue
        full = full_by_case[row["case_id"]]
        marginal_expected.append(
            {
                "case_id": row["case_id"],
                "module": row["sentinel_role"].removeprefix("LOO_NO_"),
                **{
                    field: float(row[field]) - float(full[field])
                    for field in sentinel_metric_fields
                },
            }
        )
    actions = _read_csv(outputs["actions"])
    source = _read_csv(outputs["source_aware"])
    failure = _read_csv(outputs["failure"])
    action_domains_consistent = all(
        int(row["ledger_epoch_domain_count"])
        == int(row["ledger_epoch_in_window_count"])
        + int(row["ledger_epoch_out_of_window_count"])
        and int(row["perturbed_epoch_count"])
        == int(row["perturbed_epoch_in_window_count"])
        + int(row["perturbed_epoch_out_of_window_count"])
        and int(row["withheld_epoch_count"])
        == int(row["withheld_epoch_in_window_count"])
        + int(row["withheld_epoch_out_of_window_count"])
        and int(row["spike_epoch_count"])
        == int(row["spike_epoch_in_window_count"])
        + int(row["spike_epoch_out_of_window_count"])
        and int(row["perturbed_epoch_matched_trace_count"])
        + int(row["perturbed_epoch_missing_trace_count"])
        == int(row["perturbed_epoch_count"])
        for row in actions
    )
    source_domains_consistent = all(
        int(row["ledger_epoch_domain_count"])
        == int(row["ledger_epoch_in_window_count"])
        + int(row["ledger_epoch_out_of_window_count"])
        and int(row["perturbed_epoch_count"])
        == int(row["perturbed_epoch_in_window_count"])
        + int(row["perturbed_epoch_out_of_window_count"])
        and int(row["withheld_epoch_count"])
        == int(row["withheld_epoch_in_window_count"])
        + int(row["withheld_epoch_out_of_window_count"])
        and int(row["perturbed_epoch_port_matched_count"])
        + int(row["perturbed_epoch_port_missing_count"])
        == int(row["perturbed_epoch_count"])
        and int(row["dual_yaw_source_aware_row_count"])
        + int(row["dual_yaw_source_aware_missing_count"])
        == int(row["perturbed_epoch_count"])
        for row in source
    )
    checks = {
        "factorial_main_effects_recomputed": _rows_equal(main_expected, main_actual),
        "factorial_pairwise_interactions_recomputed": _rows_equal(
            pairs_expected, pairs_actual
        ),
        "canonical_deltas_recomputed": _rows_equal(deltas_expected, deltas_actual),
        "family_seed_aggregates_recomputed": _rows_equal(family_expected, family_actual),
        "sentinel_marginal_losses_recomputed": _rows_equal(
            marginal_expected, marginal_actual
        ),
        "action_table_110_unique_runs": len(actions) == 110
        and len({row["run_id"] for row in actions}) == 110
        and action_domains_consistent
        and all(int(row["nonwithheld_missing_trace_count"]) == 0 for row in actions)
        and all(_csv_bool(row["global_action_counter_crosscheck"]) for row in actions)
        and all(_csv_bool(row["global_source_aware_counter_crosscheck"]) for row in actions),
        "source_aware_table_18_full_runs": len(source) == 18
        and {row["method"] for row in source} == {"LegSA_Paper_V1"}
        and source_domains_consistent
        and all(
            int(row["port_nonreject_source_aware_missing_count"]) == 0
            for row in source
        )
        and all(int(row["nonwithheld_source_aware_missing_count"]) == 0 for row in source)
        and all(_csv_bool(row["global_source_aware_counter_crosscheck"]) for row in source),
        "finite_table_110_unique_runs": len(failure) == 110
        and len({row["run_id"] for row in failure}) == 110
        and all(_csv_bool(row["finite_output"]) for row in failure),
        "row_level_metrics_recomputed": evaluation_row_crosscheck is not None
        and evaluation_row_crosscheck.get("passed") is True
        and evaluation_row_crosscheck.get("independent_row_recomputation_count") == 110,
    }
    return {
        "checks": checks,
        "table_sha256": {
            key: sha256_file(path)
            for key, path in outputs.items()
            if path.suffix.casefold() in {".csv", ".md"}
        },
        "passed": all(checks.values()),
    }


def write_clean2_analysis(
    *,
    registry_path: str | Path,
    summaries: Mapping[str, Mapping[str, Any]],
    ablation_catalog: AblationCatalog,
    perturbation_action_rows: Sequence[Mapping[str, Any]],
    source_aware_response_rows: Sequence[Mapping[str, Any]],
    output_dir: str | Path | None = None,
    ablation_output_dir: str | Path | None = None,
    classic_output_dir: str | Path | None = None,
    evaluation_row_crosscheck: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    rows = build_analysis_rows(read_run_registry(registry_path), summaries)
    main, pairs = factorial_effect_tables(ablation_catalog, rows["factorial"])
    if output_dir is not None:
        ablation_destination = classic_destination = Path(output_dir)
    else:
        if ablation_output_dir is None or classic_output_dir is None:
            raise Clean2AnalysisError("Separate CLEAN2 analysis destinations are required")
        ablation_destination = Path(ablation_output_dir)
        classic_destination = Path(classic_output_dir)
    ablation_destination.mkdir(parents=True, exist_ok=True)
    classic_destination.mkdir(parents=True, exist_ok=True)
    outputs = {
        "factorial": _write_csv(ablation_destination / "CLEAN2_C00_FACTORIAL_RESULTS.csv", rows["factorial"]),
        "main_effects": _write_csv(ablation_destination / "CLEAN2_C00_MODULE_MAIN_EFFECTS.csv", main),
        "interactions": _write_csv(ablation_destination / "CLEAN2_C00_PAIRWISE_INTERACTIONS.csv", pairs),
        "canonical": _write_csv(classic_destination / "CLEAN2_CANONICAL_CLASSIC18_18x4.csv", rows["canonical"]),
        "deltas": _write_csv(classic_destination / "CLEAN2_CASE_METHOD_DELTAS.csv", rows["deltas"]),
        "family": _write_csv(classic_destination / "CLEAN2_FAMILY_SEED_AGGREGATES.csv", family_seed_aggregates(rows["deltas"])),
        "sentinel": _write_csv(classic_destination / "CLEAN2_SENTINEL_LOO_RESULTS.csv", rows["sentinel_results"]),
        "marginal": _write_csv(classic_destination / "CLEAN2_SENTINEL_MODULE_MARGINAL_LOSS.csv", rows["sentinel_marginals"]),
        "actions": _write_csv(classic_destination / "CLEAN2_PERTURBATION_ACTION_SUMMARY.csv", perturbation_action_rows),
        "source_aware": _write_csv(classic_destination / "CLEAN2_SOURCE_AWARE_RESPONSE_SUMMARY.csv", source_aware_response_rows),
    }
    failure_rows = [
        {
            "run_id": row["run_id"],
            "case_id": row["case_id"],
            "finite_output": row["finite_output"],
            "terminal_pass": True,
            "matched_epoch_count": row["matched_epoch_count"],
            "unmatched_epoch_count": row["unmatched_epoch_count"],
            "coverage": row["coverage"],
        }
        for row in rows["enriched"]
    ]
    outputs["failure"] = _write_csv(
        classic_destination / "CLEAN2_FAILURE_AND_FINITE_OUTPUT_SUMMARY.csv", failure_rows
    )
    interpretation = ablation_destination / "CLEAN2_C00_FACTORIAL_INTERPRETATION.md"
    interpretation.write_text(
        "# CLEAN2 C00 factorial interpretation\n\n"
        "Effects use frozen -1/+1 coding. `coefficient_beta=sum(x*y)/16`; the "
        "reported main/interaction effect is `2*beta`. Negative values are descriptively "
        "helpful for lower-is-better metrics, positive values harmful, and zero-ish neutral. "
        "No p-values, significance claims, or universal causal claims are made.\n",
        encoding="utf-8",
    )
    outputs["interpretation"] = interpretation
    independent = _independent_table_crosscheck(
        outputs=outputs,
        catalog=ablation_catalog,
        evaluation_row_crosscheck=evaluation_row_crosscheck,
    )
    if not independent["passed"]:
        raise Clean2AnalysisError("FAIL_CLEAN2_AGGREGATE_CROSSCHECK")
    crosscheck = write_json_atomic(
        classic_destination / "CLEAN2_AGGREGATE_CROSSCHECK.json",
        {
            "schema_version": "paper_rebuild.clean2_aggregate_crosscheck.v2",
            "unique_summary_count": len(summaries),
            "factorial_row_count": len(rows["factorial"]),
            "canonical_row_count": len(rows["canonical"]),
            "sentinel_LOO_extra_count": len(rows["sentinel_marginals"]),
            "finite_output_count": sum(bool(row["finite_output"]) for row in rows["enriched"]),
            "expected": {"summaries": 110, "factorial": 16, "canonical": 72, "sentinel_LOO_extra": 24, "finite": 110},
            "independent_table_recomputation": independent,
            "independent_row_recomputation": dict(evaluation_row_crosscheck or {}),
            "passed": all(bool(row["finite_output"]) for row in rows["enriched"])
            and independent["passed"],
        },
    )
    outputs["crosscheck"] = crosscheck
    analysis_index = write_json_atomic(
        classic_destination / "CLEAN2_ANALYSIS_INDEX.json",
        {
            "schema_version": "paper_rebuild.clean2_analysis_index.v2",
            "tables": {key: str(value) for key, value in outputs.items()},
            "passed": True,
        },
    )
    outputs["analysis_index"] = analysis_index
    return {key: str(value) for key, value in outputs.items()}
