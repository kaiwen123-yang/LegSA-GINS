"""One chronological, reference-closed EXT03 reproduction history.

The Yang KF/constraint/MLAMBDA implementation is reused without modification.
Only the raw-DD input adapter and its explicit signal-identity transitions are
new.  This module opens no files and creates no providers or execution context.
The caller owns the provider, frozen lambda library, input identity and outputs.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from . import ext03_yang2024 as core
from . import reproduction_backend as backend
from .phase3_runner import (
    ADAPTER_STOCHASTIC_REGISTRY, SppReceiverError,
    _ecef_vector_to_ned, _pntpos_receiver, _tracking_input,
)
from .phase3_signal_inventory import SIGNAL_GROUPS
from .shared_raw_backend import RawBackendError, RawxEpoch, rinex_satellite_id


IMPLEMENTATION_VERSION = "EXT03_REPRODUCTION_OWN_TRANSMIT_EXACT_SIGNAL_V1"
SYSTEM_MODE = "GPS_BDS_DUAL_FREQUENCY"
CONFIG = core.EXT03Config(
    constraint_mode="CONSTRAINED", baseline_sigma_m=0.010,
    baseline_prediction_mode="RTKLIB_MOVING_BASE_SPP_RESET",
)
_GROUP_FOR = {identity: group for group, identities in SIGNAL_GROUPS.items() for identity in identities}
_TRACKING_CATEGORIES = (
    "actual_carrier_lli_tracking_discontinuities", "receiver_locktime_resets",
    "half_cycle_state_changes", "receiver_clock_reset_events",
)


def _core_signal(identity):
    group = _GROUP_FOR.get((identity.gnss_id, identity.sig_id, identity.freq_id))
    return None if group is None else core.SignalIdentity(
        "GPS" if identity.gnss_id == 0 else "BDS", rinex_satellite_id(identity), group,
    )


def _jsonable(value: Any) -> Any:
    """Lossless finite numbers; nonfinite diagnostic values have named tokens."""
    if is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, Mapping):
        return {
            (key if isinstance(key, str) else json.dumps(_jsonable(key), sort_keys=True)): _jsonable(item)
            for key, item in value.items()
        }
    if isinstance(value, (set, frozenset)):
        return sorted((_jsonable(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("+Infinity" if value > 0 else "-Infinity")
    return value


def parameter_registry() -> list[dict[str, Any]]:
    """One primary configuration; preserve engineering provenance explicitly.

    This corrects provenance in the new registry only.  Inactive RTKLIB defaults
    and the old sensitivity grid do not become settings of this engine.
    """
    paper_parameters = {"initial_baseline_variance", "initial_ambiguity_variance", "ratio_threshold"}
    rows = []
    for item in core.STOCHASTIC_PARAMETER_REGISTRY:
        if item.primary_or_sensitivity != "primary":
            continue
        row = _jsonable(item)
        row["inherited_source"] = row["source"]
        row["source"] = (
            "PROJECT_PHYSICAL_CONTRACT" if item.parameter == "baseline_length"
            else "PAPER_DISCLOSED" if item.parameter in paper_parameters
            else "ENGINEERING_INHERITED_NOT_PAPER_DISCLOSED"
        )
        row["paper_disclosed_value"] = item.parameter in paper_parameters
        rows.append(row)
    for item in ADAPTER_STOCHASTIC_REGISTRY:
        if item["primary_or_sensitivity"] != "primary":
            continue
        rows.append({
            **item, "inherited_source": item["source"],
            "source": "ENGINEERING_INHERITED_NOT_PAPER_DISCLOSED",
            "paper_disclosed_value": False,
        })
    return rows


class ReproductionEXT03Engine:
    """GPS+BDS dual frequency, constrained sigma=.010, exactly one history.

    SPP seeds and KF states advance at the same points as the old phase3 loop.
    Raw tracking is observed before SPP and pending events survive invalid rows.
    A failed epoch preserves the previous successful KF state.
    Signal-selection memory is tied to that KF history, so a failed update
    cannot silently consume a pending exact-signal change.
    """

    def __init__(self, provider: Any, lambda_library: str | Path):
        if lambda_library is None:
            raise ValueError("a frozen MLAMBDA library is required")
        self.provider = provider
        self.lambda_library = lambda_library
        self.state: core.EXT03State | None = None
        self.raw_tracking_memory: dict = {}
        self.receiver_status_memory: dict[int, int] = {}
        self.spp_previous: list[np.ndarray | None] = [None, None]
        self.previous_tow: float | None = None
        self.gps_week: int | None = None
        self.epoch_index = 0
        self.selected_signal_memory: dict[core.SignalIdentity, Any] = {}
        self.pending_tracking_events = {category: set() for category in _TRACKING_CATEGORIES}

    def _read_raw_tracking(self, receiver1, receiver2):
        """Read raw flags even when SPP/DD later fail, without computing GF/MW.

        Pending events retain receiver and exact component identity.  An unused
        component's invalid flag must not reset a different selected component.
        The event criteria are the old _tracking_input criteria, not new gates.
        """
        events = []
        for receiver, epoch in ((1, receiver1), (2, receiver2)):
            clock_reset = receiver in self.receiver_status_memory and bool(epoch.receiver_status & 0x02)
            for measurement in epoch.measurements:
                if _core_signal(measurement.identity) is None:
                    continue
                key = (receiver, measurement.identity)
                previous = self.raw_tracking_memory.get(key)
                current = (measurement.locktime_ms, measurement.carrier_valid,
                           measurement.half_cycle_valid, measurement.half_cycle_subtracted)
                reasons = []
                if previous is not None:
                    if current[1] != previous[1]:
                        reasons.append(_TRACKING_CATEGORIES[0])
                    if current[0] < previous[0]:
                        reasons.append(_TRACKING_CATEGORIES[1])
                    if current[2] != previous[2] or current[3] != previous[3]:
                        reasons.append(_TRACKING_CATEGORIES[2])
                if clock_reset:
                    reasons.append(_TRACKING_CATEGORIES[3])
                for reason in reasons:
                    self.pending_tracking_events[reason].add(key)
                if reasons:
                    events.append({"receiver": receiver, "raw_identity": measurement.identity,
                                   "previous_lock_cp_half_subhalf": previous,
                                   "current_lock_cp_half_subhalf": current,
                                   "raw_flags": measurement.tracking_audit(), "reasons": reasons})
                self.raw_tracking_memory[key] = current
            self.receiver_status_memory[receiver] = epoch.receiver_status
        return {"observed_raw_measurement_count": len(receiver1.measurements) + len(receiver2.measurements),
                "events": events}

    def _selected_signals(self, epoch: RawxEpoch) -> dict[core.SignalIdentity, Any]:
        selected = {}
        for measurement in epoch.measurements:
            identity = measurement.identity
            signal = _core_signal(identity)
            if signal is not None:
                if signal in selected:
                    raise RawBackendError("common-signal adapter returned multiple identities for one frequency/SV")
                selected[signal] = identity
        return selected

    def step(self, receiver1: RawxEpoch, receiver2: RawxEpoch) -> dict[str, Any]:
        """Consume one exact pair; numerical/input failures become invalid rows.

        Pair identity and chronology errors are hard input-order exceptions,
        before SPP or history mutation.  No GPS-week rollover is inferred.
        """
        tow = float(receiver1.gps_tow_seconds)
        if not math.isfinite(tow) or (
            receiver1.gps_week, receiver1.gps_tow_seconds
        ) != (receiver2.gps_week, receiver2.gps_tow_seconds):
            raise RawBackendError("expected finite, exact receiver-local epoch pairing")
        if self.gps_week is not None and receiver1.gps_week != self.gps_week:
            raise RawBackendError("one history cannot silently cross GPS weeks")
        if self.previous_tow is not None and tow <= self.previous_tow:
            raise core.Yang2024Error("epoch history is not chronological", code="NON_CHRONOLOGICAL_EPOCH")
        self.previous_tow, self.gps_week = tow, receiver1.gps_week
        base = {
            "schema_version": "ext_reproduction.ext03.epoch.v1",
            "implementation_version": IMPLEMENTATION_VERSION,
            "dd_adapter_version": backend.ADAPTER_VERSION,
            "method_id": "EXT03_YANG2024", "system_mode": SYSTEM_MODE,
            "constraint_mode": CONFIG.constraint_mode, "baseline_sigma_m": CONFIG.baseline_sigma_m,
            "epoch_index": self.epoch_index, "gps_week": receiver1.gps_week, "gps_tow_seconds": tow,
            "ambiguity_correctness_known": False, "reference_read_count": 0,
            "previous_state_epoch_time_s": None if self.state is None else self.state.epoch_time_s,
        }
        self.epoch_index += 1
        spp_audit: dict[str, Any] = {}
        selection_audit: Any = None
        signal_switches: list[dict[str, Any]] = []
        dd_audit: dict[str, Any] = {}
        raw_tracking_audit = self._read_raw_tracking(receiver1, receiver2)
        pending_before = _jsonable(self.pending_tracking_events)
        pending_applied = None
        stage_evidence = {
            "SPP": {receiver: {"attempted": False, "returned": False, "accepted": None}
                    for receiver in ("GNSS1", "GNSS2")},
            "DD_MODEL_BUILT": False, "CORE_PROCESS_CALLED": False,
            "float_solution_returned": False, "mlambda_attempted": False,
            "mlambda_completed": False, "mlambda_result_returned": False,
            "two_candidates_returned": False, "MLAMBDA_failure_code": None,
            "internal_stage_status": "CORE_NOT_ENTERED", "unknown_reason": None,
        }
        try:
            positions = []
            for index, epoch in enumerate((receiver1, receiver2)):
                receiver = f"GNSS{index + 1}"
                stage_evidence["SPP"][receiver]["attempted"] = True
                solution = _pntpos_receiver(self.provider, epoch, SYSTEM_MODE, self.spp_previous[index], receiver)
                stage_evidence["SPP"][receiver].update(
                    returned=True, accepted=bool(solution.accepted and solution.position_ecef_m is not None),
                )
                spp_audit[receiver] = _jsonable(solution)
                if not solution.accepted or solution.position_ecef_m is None:
                    raise SppReceiverError(receiver, "PNTPOS_REJECTED", (
                        f"solstat={solution.solution_status} valid={solution.valid_satellite_count} "
                        f"obs={solution.constructed_observation_count} message={solution.message}"
                    ))
                position = np.asarray(solution.position_ecef_m, dtype=float)
                self.spp_previous[index] = position
                positions.append(position)
            spp1, spp2 = positions
            spp_baseline = _ecef_vector_to_ned(spp2 - spp1, spp1)
            first, second, selection_audit = backend.common_signal_epochs(receiver1, receiver2)
            blocks, geometry_audit = backend.build_dual_frequency_blocks(first, second, self.provider, spp1, spp2)
            model = core.build_dd_observation(blocks)
            stage_evidence["DD_MODEL_BUILT"] = True
            dd_audit = {
                "blocks": _jsonable(blocks), "observation_m": model.observation_m,
                "design": model.design, "covariance_m2": model.covariance_m2,
                "ambiguity_identities": _jsonable(model.ambiguity_identities),
                "block_row_slices": [(system, frequency, [rows.start, rows.stop]) for system, frequency, rows in model.block_row_slices],
                "geometry": geometry_audit,
                "ordering": "BLOCKS_[CODE_DD,PHASE_DD]_BASELINE_THEN_ALIGNED_AMBIGUITIES",
            }
            # Only GF/MW/prior-DD come from this call.  Temporary dictionaries
            # cannot consume or override the live raw tracking/clock history.
            tracking = _tracking_input(first, second, blocks, model, self.state, {}, {})
            selected = self._selected_signals(first)
            modeled_signals = {signal for identity in model.ambiguity_identities
                               for signal in (identity.signal, identity.pivot_signal)}
            modeled_raw_keys = {(receiver, identity) for signal, identity in selected.items()
                                if signal in modeled_signals for receiver in (1, 2)}
            pending_applied = {
                category: frozenset(_core_signal(identity) for receiver, identity in keys & modeled_raw_keys)
                for category, keys in self.pending_tracking_events.items()
            }
            switched = frozenset(signal for signal, identity in selected.items()
                                 if signal in modeled_signals and signal in self.selected_signal_memory
                                 and identity != self.selected_signal_memory[signal])
            signal_switches = [{"signal": signal, "previous_raw_identity": self.selected_signal_memory[signal],
                                "current_raw_identity": selected[signal], "reason": "EXACT_SIGNAL_IDENTITY_CHANGED"}
                               for signal in sorted(switched, key=lambda item: (item.constellation, item.frequency, item.satellite))]
            tracking = replace(tracking, **{
                **pending_applied,
                "actual_carrier_lli_tracking_discontinuities": pending_applied[_TRACKING_CATEGORIES[0]] | switched,
            })
            # The old core is deliberately not instrumented or modified.  If
            # it raises, its internal KF/search progress cannot be reconstructed
            # from the adapter's final state_updated=False or error label.
            stage_evidence.update(
                CORE_PROCESS_CALLED=True, float_solution_returned=None,
                mlambda_attempted=None, mlambda_completed=None,
                mlambda_result_returned=None, two_candidates_returned=None,
                internal_stage_status="UNKNOWN_CORE_CALL_NOT_RETURNED",
                unknown_reason="Unmodified process_epoch exposes no partial-result stage receipt on exception.",
            )
            result = core.process_epoch(
                self.state, tow, model, CONFIG, tracking=tracking,
                spp_baseline_ned_m=spp_baseline, lambda_bridge_path=self.lambda_library,
            )
            mlambda = result.mlambda_diagnostics
            two_candidates = bool(mlambda.candidate_returned and mlambda.best_integer is not None
                                  and mlambda.second_integer is not None)
            stage_evidence.update(
                float_solution_returned=True, mlambda_attempted=True,
                mlambda_completed=bool(mlambda.failure_code is None and two_candidates),
                mlambda_result_returned=True, two_candidates_returned=two_candidates,
                MLAMBDA_failure_code=mlambda.failure_code,
                internal_stage_status="CORE_RESULT_RETURNED", unknown_reason=None,
            )
            self.state = result.state
            self.selected_signal_memory.update({signal: identity for signal, identity in selected.items()
                                                if signal in modeled_signals})
            for pending in self.pending_tracking_events.values():
                pending.difference_update(modeled_raw_keys)
            baseline = result.fixed_baseline_ned_m if result.paper_ratio_fixed else result.float_baseline_ned_m
            attitude = result.fixed_attitude if result.paper_ratio_fixed else result.float_attitude
            return _jsonable({
                **base, "solution_state": result.solution_state, "paper_ratio_fixed": result.paper_ratio_fixed,
                "state_updated": True, "state": result.state,
                "stage_evidence": stage_evidence,
                "baseline_ned_m": baseline, "yaw_deg": attitude.body_yaw_deg,
                "body_yaw_deg": attitude.body_yaw_deg, "baseline_heading_deg": attitude.baseline_heading_deg,
                "baseline_length_m": attitude.baseline_length_m,
                "float_baseline_ned_m": result.float_baseline_ned_m,
                "fixed_baseline_ned_m": result.fixed_baseline_ned_m,
                "float_attitude": result.float_attitude, "fixed_attitude": result.fixed_attitude,
                "ambiguities": {"identities": result.state.ambiguity_identities,
                                "float_cycles": result.state.state[3:],
                                "best_integer": result.mlambda_diagnostics.best_integer,
                                "second_integer": result.mlambda_diagnostics.second_integer},
                "covariance": result.state.covariance,
                "ratio": result.mlambda_diagnostics.ratio,
                "ratio_is_infinite": result.mlambda_diagnostics.ratio_is_infinite,
                "mlambda": result.mlambda_diagnostics, "slip": result.cycle_slip_diagnostics,
                "state_diagnostics": result.state_diagnostics, "kf_diagnostics": result.kf_diagnostics,
                "constraint_diagnostics": result.constraint_diagnostics,
                "spp_audit": spp_audit, "spp_baseline_ned_m": spp_baseline,
                "signal_selection_audit": selection_audit, "signal_switches": signal_switches,
                "raw_tracking_audit": raw_tracking_audit, "tracking_pending_before": pending_before,
                "tracking_pending_applied": pending_applied,
                "tracking_pending_after": self.pending_tracking_events,
                "dd_block_count": len(blocks), "dd_audit": dd_audit,
            })
        except (RawBackendError, core.Yang2024Error, np.linalg.LinAlgError, ValueError) as exc:
            failure_code = getattr(exc, "code", None) or (
                "NUMERICAL_LINEAR_ALGEBRA_FAILURE" if isinstance(exc, np.linalg.LinAlgError)
                else "NUMERICAL_VALUE_ERROR" if isinstance(exc, ValueError) else "RAW_BACKEND_FAILURE"
            )
            return _jsonable({
                **base, "solution_state": "invalid", "paper_ratio_fixed": False,
                "failure_code": failure_code, "failure_detail": str(exc),
                "state_updated": False, "state": self.state,
                "stage_evidence": stage_evidence,
                "baseline_ned_m": None, "yaw_deg": None, "body_yaw_deg": None,
                "baseline_heading_deg": None, "baseline_length_m": None,
                "float_baseline_ned_m": None, "fixed_baseline_ned_m": None,
                "float_attitude": None, "fixed_attitude": None,
                "ambiguities": None, "covariance": None, "ratio": None, "ratio_is_infinite": False,
                "mlambda": None, "slip": None,
                "spp_audit": spp_audit, "signal_selection_audit": selection_audit,
                "signal_switches": signal_switches, "dd_audit": dd_audit,
                "raw_tracking_audit": raw_tracking_audit, "tracking_pending_before": pending_before,
                "tracking_pending_applied": pending_applied,
                "tracking_pending_after": self.pending_tracking_events,
            })
