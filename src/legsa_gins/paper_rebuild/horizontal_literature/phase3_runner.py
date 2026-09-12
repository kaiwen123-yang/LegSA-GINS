"""Phase-3 EXT03/Yang-2024 real BY2 lifecycle and variant scheduler.

Native processing is deliberately reference-closed: RAWX is reconstructed with
NAV-HPPOSECEF semantic decoding disabled, exact pairs are cached once, and one
chronological KF history is run per independent variant.  Only variants may be
parallel.  Post-native entry requires revalidation of every native hash.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml

from . import phase2_runner as phase2
from .ext03_yang2024 import (
    ADAPTER_STOCHASTIC_REGISTRY_REQUIRED_PARAMETERS,
    AmbiguityIdentity,
    DDObservationBlock,
    EXT03Config,
    EXT03State,
    EpochTrackingInput,
    PAPER_MODEL_REGISTRY,
    STOCHASTIC_PARAMETER_REGISTRY,
    SignalIdentity as CoreSignalIdentity,
    Yang2024Error,
    build_dd_observation,
    map_prior_dd_ambiguities_to_target_basis,
    process_epoch,
)
from .phase3_signal_inventory import (
    MODE_FREQUENCIES,
    SIGNAL_GROUPS,
    SignalInventoryResult,
    audit_signal_availability,
    integer_compatible,
)
from .shared_raw_backend import (
    RawBackendError,
    PntPosBridgeError,
    RawxEpoch,
    RawxMeasurement,
    RtklibBroadcastProvider,
    RTKLIB_NAVSYS_GPS,
    RTKLIB_NAVSYS_BDS,
    RTKLIB_NAVSYS_GPS_BDS,
    SignalIdentity,
    azimuth_elevation,
    correlated_dd_covariance,
    earth_rotation_correct_satellite,
    ecef_to_geodetic,
    pair_epochs,
    reconstruct_ubx_stream,
    rinex_satellite_id,
    integer_compatible_carrier_cycles,
    wavelength_m,
)

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPOSITORY_ROOT / "configs/paper_rebuild/horizontal_literature/PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml"
METHOD_ID = "EXT03_YANG2024"
CASE_ID = "C00"
DEFAULT_WORKERS = 16
MAX_WORKERS = 20
EXPECTED_PAIR_COUNT = 1509
BASELINE_LENGTH_M = 0.350
PASS_READY = "PASS_PHASE3_EXT03_YANG2024_C00_READY_FOR_NATIVE_COMPARISON"
PASS_POOR = "PASS_PHASE3_EXT03_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT"
PASS_PARTIAL = "PASS_PHASE3_EXT03_PARTIAL_SYSTEM_MODES_COMPLETE"
BLOCKED_PREFIX = "BLOCKED_PHASE3_EXT03_"
ALLOWED_MODES = frozenset({"preflight", "signal-audit", "resource-determinism-probe", "native-only", "post-native-diagnostics", "full"})

NATIVE_FILE_NAMES = {
    "heading_results": "EXT03_C00_NATIVE_HEADING_RESULTS.csv",
    "failure_ledger": "EXT03_C00_FAILURE_LEDGER.csv",
    "runtime": "EXT03_C00_RUNTIME.csv",
    "signal_availability": "EXT03_C00_SIGNAL_AVAILABILITY.csv",
    "dd_diagnostics": "EXT03_C00_DD_DIAGNOSTICS.csv",
    "kf_state_diagnostics": "EXT03_C00_KF_STATE_DIAGNOSTICS.csv",
    "constraint_diagnostics": "EXT03_C00_CONSTRAINT_DIAGNOSTICS.csv",
    "ambiguity_state_diagnostics": "EXT03_C00_AMBIGUITY_STATE_DIAGNOSTICS.csv",
    "cycle_slip_diagnostics": "EXT03_C00_CYCLE_SLIP_DIAGNOSTICS.csv",
    "mlambda_diagnostics": "EXT03_C00_MLAMBDA_DIAGNOSTICS.csv",
    "mode_summary": "EXT03_C00_MODE_SUMMARY.csv",
    "sensitivity_summary": "EXT03_C00_SENSITIVITY_SUMMARY.csv",
    "stochastic_registry": "EXT03_STOCHASTIC_PARAMETER_REGISTRY.csv",
    "native_summary": "EXT03_C00_NATIVE_SUMMARY.json",
    "native_freeze": "EXT03_C00_NATIVE_FREEZE.json",
}
FREEZE_HASH_KEYS = tuple(name for name in NATIVE_FILE_NAMES if name != "native_freeze")
_ADAPTER_STOCHASTIC_REGISTRY_RAW = (
    {"parameter": "code_measurement_sigma_model", "value": "sqrt(2*(0.003^2+0.003^2/sin(el)^2))*100", "unit": "m", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "rtkpos.c:varerr err[] eratio[]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "phase_measurement_sigma_model", "value": "sqrt(2*(0.003^2+0.003^2/sin(el)^2))", "unit": "m", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "rtkpos.c:varerr err[]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "gps_system_weight", "value": 1.0, "unit": "1", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "rtkpos.c:varerr EFACT_GPS", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "bds_system_weight", "value": 1.0, "unit": "1", "source": "RTKLIB 180043ee GPS-factor fallback for non-GLO/SBS", "paper_equation_or_RTKLIB_symbol": "rtkpos.c:varerr EFACT_GPS fallback", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "shared_pivot_covariance_model", "value": "diag(nonpivot_SD_variance)+pivot_SD_variance*11T", "unit": "m2", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "rtkpos.c:ddcov", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "number_of_frequencies", "value": 2, "unit": "1", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.nf", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "elevation_mask", "value": 15.0, "unit": "deg", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.elmin", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "dynamics", "value": "off", "unit": "bool", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.dynamics", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "tide_correction", "value": "off", "unit": "bool", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.tidecorr", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "relative_filter_iterations", "value": 1, "unit": "iteration", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.niter", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "ambiguity_resolution_mode", "value": "continuous", "unit": "enum", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.modear", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "BDS_ambiguity_resolution", "value": "on", "unit": "bool", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "prcopt_default.bdsmodear", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "maximum_ambiguity_outage", "value": 5, "unit": "epoch", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.maxout", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "minimum_lock_to_fix", "value": 0, "unit": "epoch", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.minlock", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "minimum_fixes_to_hold", "value": 10, "unit": "epoch", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.minfix", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "AR_maximum_iterations", "value": 1, "unit": "iteration", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.armaxiter", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "phase_constant_error", "value": 0.003, "unit": "m", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.err[1]/varerr", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "phase_elevation_error", "value": 0.003, "unit": "m", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.err[2]/varerr", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "code_phase_error_ratio", "value": 100.0, "unit": "1", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.eratio[0]/varerr", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "GPS_measurement_error_factor", "value": 1.0, "unit": "1", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "rtklib.h:EFACT_GPS; rtkpos.c:varerr", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "code_phase_error_ratio_frequency2", "value": 100.0, "unit": "1", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.eratio[1]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "baseline_phase_error", "value": 0.0, "unit": "m_per_10km", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.err[3]/varerr", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "ionosphere_process_noise", "value": 1.0e-3, "unit": "m/sqrt(s)", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.prn[1]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "troposphere_process_noise", "value": 1.0e-4, "unit": "m/sqrt(s)", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.prn[2]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "horizontal_acceleration_process_noise", "value": 0.1, "unit": "m/s2/sqrt(s)", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.prn[3]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "vertical_acceleration_process_noise", "value": 0.01, "unit": "m/s2/sqrt(s)", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.prn[4]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "position_process_noise", "value": 0.0, "unit": "m/sqrt(s)", "source": "RTKLIB 180043ee moving-base dynamics-off equivalence", "paper_equation_or_RTKLIB_symbol": "prcopt_default.prn[5]/udpos reset", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "initial_ionosphere_standard_deviation", "value": 0.03, "unit": "m", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.std[1]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "initial_troposphere_standard_deviation", "value": 0.3, "unit": "m", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.std[2]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "satellite_clock_stability", "value": 5.0e-12, "unit": "s/s", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.sclkstab", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "maximum_differential_age", "value": 30.0, "unit": "s", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.maxtdiff", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "innovation_rejection", "value": 30.0, "unit": "m", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "prcopt_default.maxinno", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_maximum_GDOP", "value": 30.0, "unit": "1", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "pntpos.c:valsol; prcopt_default.maxgdop", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_code_error_factor", "value": 100.0, "unit": "1", "source": "RTKLIB 180043ee default", "paper_equation_or_RTKLIB_symbol": "pntpos.c:varerr; prcopt_default.err[0]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_pseudorange_variance_formula", "value": "EFACT^2*err[0]^2*(err[1]^2+err[2]^2/sin(max(el,5deg)))", "unit": "m2", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:varerr", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_minimum_error_elevation", "value": 5.0, "unit": "deg", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:MIN_EL", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_code_bias_error_sigma", "value": 0.3, "unit": "m", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:ERR_CBIAS", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_broadcast_ionosphere_error_factor", "value": 0.5, "unit": "1", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:ERR_BRDCI", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_broadcast_ionosphere_variance", "value": "(modeled_ionosphere_delay_m*0.5)^2", "unit": "m2", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:ionocorr IONOOPT_BRDC", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_Saastamoinen_variance", "value": "(0.3/(sin(el)+0.1))^2", "unit": "m2", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:tropcorr ERR_SAAS", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_maximum_iterations", "value": 10, "unit": "iteration", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:MAXITR", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_satellite_broadcast_variance", "value": "ADDED_PER_SATELLITE_FROM_SATPOS_VARE", "unit": "m2", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:rescode vare[i]", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "pntpos_chi_square_validation", "value": "residual_vv<=chisqr[nv-nx-1]", "unit": "rule", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:valsol; rtkcmn.c:chisqr", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "SPP_Saastamoinen_relative_humidity", "value": 0.7, "unit": "1", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:REL_HUMI", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "SPP_Saastamoinen_error_sigma", "value": 0.3, "unit": "m", "source": "RTKLIB 180043ee", "paper_equation_or_RTKLIB_symbol": "pntpos.c:ERR_SAAS", "primary_or_sensitivity": "primary", "trace_tuned": False},
    {"parameter": "DD_Saastamoinen_relative_humidity", "value": 0.0, "unit": "1", "source": "RTKLIB 180043ee relative zdres hydrostatic model", "paper_equation_or_RTKLIB_symbol": "rtkpos.c:zdres tropmodel humi=0.0", "primary_or_sensitivity": "primary", "trace_tuned": False},
)

# These values remain in the registry because they are required to reproduce
# the stock RTKLIB cross-check, but the clean-room production state does not
# instantiate the corresponding states, hold logic, or rejection gates.
_DIAGNOSTIC_ONLY_PARAMETERS = frozenset({
    "tide_correction", "relative_filter_iterations", "ambiguity_resolution_mode",
    "BDS_ambiguity_resolution", "maximum_ambiguity_outage", "minimum_lock_to_fix",
    "minimum_fixes_to_hold", "AR_maximum_iterations", "ionosphere_process_noise",
    "troposphere_process_noise", "horizontal_acceleration_process_noise",
    "vertical_acceleration_process_noise", "initial_ionosphere_standard_deviation",
    "position_process_noise", "initial_troposphere_standard_deviation", "satellite_clock_stability",
    "maximum_differential_age", "innovation_rejection",
})
ADAPTER_STOCHASTIC_REGISTRY = tuple(
    {
        **row,
        "source": row["source"] + " / RTKLIB_DIAGNOSTIC_ONLY_INACTIVE_IN_PRODUCTION_ADAPTER",
        "primary_or_sensitivity": "diagnostic",
    }
    if row["parameter"] in _DIAGNOSTIC_ONLY_PARAMETERS else row
    for row in _ADAPTER_STOCHASTIC_REGISTRY_RAW
)


class Phase3RunnerError(RuntimeError):
    pass


class ResourceProbeRejected(Phase3RunnerError):
    def __init__(self, message: str, evidence: Mapping[str, Any]):
        self.evidence = dict(evidence)
        super().__init__(message)


class SppReceiverError(RawBackendError):
    def __init__(self, receiver: str, code: str, detail: str):
        self.code = f"{receiver}_{code}"
        super().__init__(f"{self.code}: {detail}")


class Phase3ObservationError(RawBackendError):
    """Structured per-epoch observation failure retained by the ledger."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True, order=True)
class Variant:
    system_mode: str
    constraint_mode: str
    baseline_sigma_m: float | None

    @property
    def variant_id(self) -> str:
        sigma = "NA" if self.baseline_sigma_m is None else f"{self.baseline_sigma_m:.3f}"
        return f"{self.system_mode}__{self.constraint_mode}__{sigma}"

    def row_identity(self) -> dict[str, Any]:
        return {
            "system_mode": self.system_mode,
            "constraint_mode": self.constraint_mode,
            "baseline_sigma_m": self.baseline_sigma_m,
        }


@dataclass(frozen=True)
class Phase3Paths:
    config_path: Path
    code_root: Path
    raw_root: Path
    by2_fix_root: Path
    clean_root: Path
    raw_hash_lock: Path
    gnss1_raw: Path
    gnss2_raw: Path
    trace: Path
    rtklib_root: Path
    convbin: Path
    rtklib_bridge: Path
    lambda_library: Path
    bridge_root: Path
    stage_root: Path
    native_root: Path
    report_root: Path
    final_report: Path
    final_status: Path

    @property
    def native_files(self) -> dict[str, Path]:
        return {key: self.native_root / value for key, value in NATIVE_FILE_NAMES.items()}


@dataclass(frozen=True)
class PreflightResult:
    paths: Phase3Paths
    contract: Mapping[str, Any]
    code_commit: str
    contract_hash: str
    raw_source_hashes: Mapping[str, str]
    provider_hashes: Mapping[str, str]
    source_fingerprint: str
    config_hash: str
    runtime_source_hashes: Mapping[str, str]
    runtime_dependency_hashes: Mapping[str, str]
    worktree_overlay_identity: Mapping[str, Any]


def _sha256(path: Path) -> str:
    return phase2._sha256_file(path)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _runtime_dependency_hashes(bridge_root: Path) -> dict[str, str]:
    relative_paths = (
        "lib/librtklib_legsa.so",
        "EXT03_PNTPOS_BRIDGE.patch",
        "Makefile",
    )
    result: dict[str, str] = {}
    for relative in relative_paths:
        path = Path(bridge_root) / relative
        if not path.is_file():
            raise Phase3RunnerError(f"required EXT03 runtime dependency absent: {relative}")
        result[relative] = _sha256(path)
    return result


def _validate_runtime_dependency_hashes(bridge_root: Path, expected: Mapping[str, str]) -> None:
    current = _runtime_dependency_hashes(bridge_root)
    if dict(current) != dict(expected):
        raise Phase3RunnerError("EXT03 runtime dependency overlay changed after preflight")


def _scientific_overlay_identity(worktree_overlay_identity: Mapping[str, Any]) -> dict[str, Any]:
    """Exclude repository-global audit metadata from scientific resume identity."""
    return {key: value for key, value in worktree_overlay_identity.items() if key != "global_worktree_audit_metadata"}


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        # dataclasses.asdict() recursively converts dataclass mapping keys to
        # dictionaries before this function can encode them, making keys such
        # as AmbiguityIdentity unhashable.  Recurse field-wise instead.
        return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {
            (_canonical(_jsonable(key)) if is_dataclass(key) else str(key)): _jsonable(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def terminal_json(value: Mapping[str, Any]) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, ensure_ascii=False)


def terminalize_failure(config_path: Path, mode: str, exc: BaseException) -> dict[str, Any]:
    """Preserve an original failed-attempt marker without replacing evidence."""
    payload = {"schema_version": "horizontal_literature.phase3.failed_attempt.v1", "terminal_status": f"{BLOCKED_PREFIX}{type(exc).__name__.upper()}", "mode": mode, "exception_type": type(exc).__name__, "exception_message": str(exc), "timestamp_ns": time.time_ns(), "native_or_post_success_claimed": False}
    try:
        preflight = preflight_phase3(config_path)
        attempt = preflight.paths.native_root.parent / f".attempt_EXT03_{preflight.source_fingerprint[:12]}"
        if attempt.is_dir():
            phase2._atomic_write_json(attempt / f"FAILED_ATTEMPT_{payload['timestamp_ns']}.json", payload)
    except Exception as marker_exc:
        payload["failure_marker_error"] = f"{type(marker_exc).__name__}: {marker_exc}"
    return payload


def load_phase3_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "horizontal_literature.phase3_ext03_yang2024.v1":
        raise Phase3RunnerError("unsupported Phase-3 contract schema")
    if value.get("method_id") != METHOD_ID or value.get("case_id") != CASE_ID:
        raise Phase3RunnerError("Phase-3 method/case identity drift")
    if value.get("formal_reproduction_level") != "FAITHFUL_ALGORITHM_REPRODUCTION" or value.get("reproduction_qualifier") != "WITH_DECLARED_UNSPECIFIED_STOCHASTIC_INSTANTIATION":
        raise Phase3RunnerError("Phase-3 reproduction-level drift")
    algorithm = value.get("algorithm", {})
    if float(algorithm.get("baseline_length_m", math.nan)) != BASELINE_LENGTH_M or float(algorithm.get("ratio_threshold", math.nan)) != 3.0:
        raise Phase3RunnerError("Phase-3 paper constants drift")
    parallel = value.get("parallel_execution", {})
    if int(parallel.get("default_workers", -1)) != DEFAULT_WORKERS or int(parallel.get("maximum_workers", -1)) != MAX_WORKERS or parallel.get("epoch_parallelism_inside_recursive_variant") is not False:
        raise Phase3RunnerError("Phase-3 parallel contract drift")
    if value.get("runtime_topology", {}).get("native_files") != NATIVE_FILE_NAMES:
        raise Phase3RunnerError("Phase-3 native output inventory drift")
    variants = requested_variants(value)
    if len(variants) != 10 or len(set(variants)) != 10:
        raise Phase3RunnerError("Phase-3 requested variant grid drift")
    flags = value.get("data_flags", {})
    forbidden = ("trace_used_online", "HPPOSECEF_solver_input", "status_baseline_solver_input", "Go2_yaw_solver_input", "EXT01_output_solver_input", "EXT02_output_solver_input", "LegSA_output_solver_input", "phase_bias_calibration")
    if any(flags.get(name) is not False for name in forbidden):
        raise Phase3RunnerError("Phase-3 forbidden-input flag drift")
    registry_names = {row["parameter"] for row in ADAPTER_STOCHASTIC_REGISTRY}
    if not set(ADAPTER_STOCHASTIC_REGISTRY_REQUIRED_PARAMETERS) <= registry_names:
        raise Phase3RunnerError("Phase-3 adapter stochastic registry is incomplete")
    return value


def requested_variants(contract: Mapping[str, Any] | None = None) -> tuple[Variant, ...]:
    source = load_phase3_contract() if contract is None else contract
    return tuple(Variant(str(row["system_mode"]), str(row["constraint_mode"]), None if row.get("baseline_sigma_m") is None else float(row["baseline_sigma_m"])) for row in source["requested_variants"])


def load_paths(config_path: Path) -> Phase3Paths:
    document = yaml.safe_load(Path(config_path).resolve().read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != "paper_rebuild.paths.v1":
        raise Phase3RunnerError("unsupported local paths schema")
    values = document.get("paths", {})
    required = ("code_root", "raw_root", "by2_fix_root", "clean_root", "horizontal_literature_rtklib_root", "horizontal_literature_convbin", "horizontal_literature_rtklib_bridge", "horizontal_literature_lambda_library", "horizontal_literature_bridge_root")
    if any(not isinstance(values.get(name), str) for name in required):
        raise Phase3RunnerError("local paths lack an EXT03 dependency")
    def absolute(name: str) -> Path:
        path = Path(values[name])
        if not path.is_absolute():
            raise Phase3RunnerError(f"local path is not absolute: {name}")
        return path.resolve(strict=False)
    by2 = absolute("by2_fix_root")
    clean = absolute("clean_root")
    stage = clean / "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
    report = stage / "11_REPORT"
    return Phase3Paths(
        Path(config_path).resolve(), absolute("code_root"), absolute("raw_root"), by2,
        clean, clean / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv",
        by2 / "gnss1-raw.csv", by2 / "gnss2-raw.csv",
        by2 / "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv",
        absolute("horizontal_literature_rtklib_root"), absolute("horizontal_literature_convbin"),
        absolute("horizontal_literature_rtklib_bridge"), absolute("horizontal_literature_lambda_library"),
        absolute("horizontal_literature_bridge_root"), stage, stage / "04_EXT03_YANG2024/C00",
        report, report / "PHASE3_EXT03_C00_REPORT.md", report / "PHASE3_STATUS.json",
    )


def preflight_phase3(config_path: Path) -> PreflightResult:
    paths = load_paths(config_path)
    if paths.code_root != REPOSITORY_ROOT.resolve():
        raise Phase3RunnerError("configured code_root is not this worktree")
    contract = load_phase3_contract()
    raw_hashes = phase2._verify_locked_raw(paths)  # identical immutable RAWX lock contract
    for path in (paths.rtklib_bridge, paths.lambda_library, paths.convbin):
        if not path.is_file():
            raise Phase3RunnerError(f"external provider absent: {path.name}")
    provider_hashes = phase2._external_provider_audit(paths)
    rtklib_head = provider_hashes["rtklib_commit"]
    code_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=paths.code_root, text=True, capture_output=True, check=True).stdout.strip()
    rnx2rtkp = paths.rtklib_root / "app/consapp/rnx2rtkp/gcc/rnx2rtkp"
    if not rnx2rtkp.is_file():
        raise Phase3RunnerError("pinned unmodified rnx2rtkp diagnostic binary absent")
    provider_hashes = {
        **provider_hashes,
        "lambda_library_sha256": _sha256(paths.lambda_library),
        "unmodified_rnx2rtkp_path": str(rnx2rtkp),
        "unmodified_rnx2rtkp_sha256": _sha256(rnx2rtkp),
    }
    contract_hash = _sha256(CONTRACT_PATH)
    config_hash = _sha256(paths.config_path)
    runtime_paths = (
        CONTRACT_PATH,
        REPOSITORY_ROOT / "scripts/paper_rebuild/run_horizontal_literature_phase3.py",
        Path(__file__).resolve(),
        Path(__file__).with_name("phase3_signal_inventory.py"),
        Path(__file__).with_name("ext03_yang2024.py"),
        Path(__file__).with_name("shared_raw_backend.py"),
        Path(__file__).with_name("phase2_runner.py"),
        Path(__file__).with_name("ext01_clambda.py"),
    )
    runtime_source_hashes = {str(path.relative_to(REPOSITORY_ROOT)): _sha256(path) for path in runtime_paths}
    runtime_dependency_hashes = _runtime_dependency_hashes(paths.bridge_root)
    global_git_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=paths.code_root, text=True, capture_output=True, check=True,
    ).stdout
    runtime_relative_paths = tuple(runtime_source_hashes)
    scoped_git_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *runtime_relative_paths],
        cwd=paths.code_root, text=True, capture_output=True, check=True,
    ).stdout
    status_lines = tuple(line for line in scoped_git_status.splitlines() if line)
    global_status_lines = tuple(line for line in global_git_status.splitlines() if line)
    worktree_overlay_identity = {
        "code_commit_semantics": "BASE_HEAD_ONLY_WITH_HASHED_RUNTIME_SOURCE_OVERLAY",
        "scope": "ENUMERATED_RUNTIME_SOURCE_PATHS_ONLY",
        "dirty": bool(status_lines),
        "status_porcelain_sha256": hashlib.sha256(scoped_git_status.encode()).hexdigest(),
        "status_entry_count": len(status_lines),
        "untracked_entry_count": sum(line.startswith("?? ") for line in status_lines),
        "tracked_change_entry_count": sum(not line.startswith("?? ") for line in status_lines),
        "path_semantics": "REPOSITORY_RELATIVE_PATHS_HASHED_NO_MACHINE_ROOT",
        "runtime_source_overlay_sha256": hashlib.sha256(_canonical(runtime_source_hashes).encode()).hexdigest(),
        "runtime_dependency_overlay_sha256": hashlib.sha256(_canonical(runtime_dependency_hashes).encode()).hexdigest(),
        "global_worktree_audit_metadata": {
            "excluded_from_scientific_fingerprint": True,
            "dirty": bool(global_status_lines),
            "status_porcelain_sha256": hashlib.sha256(global_git_status.encode()).hexdigest(),
            "status_entry_count": len(global_status_lines),
            "untracked_entry_count": sum(line.startswith("?? ") for line in global_status_lines),
            "tracked_change_entry_count": sum(not line.startswith("?? ") for line in global_status_lines),
        },
    }
    fingerprint = hashlib.sha256(_canonical({"method": METHOD_ID, "case": CASE_ID, "code_commit": code_commit, "code_commit_semantics": worktree_overlay_identity["code_commit_semantics"], "worktree_overlay": _scientific_overlay_identity(worktree_overlay_identity), "contract_hash": contract_hash, "config_hash": config_hash, "runtime_sources": runtime_source_hashes, "runtime_dependencies": runtime_dependency_hashes, "raw": raw_hashes, "providers": provider_hashes}).encode()).hexdigest()
    return PreflightResult(paths, contract, code_commit, contract_hash, raw_hashes, provider_hashes, fingerprint, config_hash, runtime_source_hashes, runtime_dependency_hashes, worktree_overlay_identity)


def deterministic_variant_schedule(variants: Sequence[Variant], workers: int) -> tuple[tuple[Variant, ...], ...]:
    if not 1 <= workers <= MAX_WORKERS:
        raise Phase3RunnerError("workers must be in 1..20")
    ordered = tuple(sorted(variants, key=lambda item: item.variant_id))
    slots: list[list[Variant]] = [[] for _ in range(min(workers, len(ordered)))]
    for index, variant in enumerate(ordered):
        slots[index % len(slots)].append(variant)
    return tuple(tuple(slot) for slot in slots)


def _ecef_vector_to_ned(vector: Sequence[float], reference_ecef_m: Sequence[float]) -> np.ndarray:
    lat, lon, _height = ecef_to_geodetic(reference_ecef_m)
    sin_lat, cos_lat, sin_lon, cos_lon = math.sin(lat), math.cos(lat), math.sin(lon), math.cos(lon)
    rotation = np.asarray([[-sin_lat*cos_lon, -sin_lat*sin_lon, cos_lat], [-sin_lon, cos_lon, 0.0], [-cos_lat*cos_lon, -cos_lat*sin_lon, -sin_lat]])
    return rotation @ np.asarray(vector, dtype=float)


def _saastamoinen_m(receiver_ecef_m: Sequence[float], satellite_ecef_m: Sequence[float], *, relative_humidity: float = 0.0) -> float:
    lat, _lon, height = ecef_to_geodetic(receiver_ecef_m)
    height = min(10000.0, max(-100.0, height))
    _az, elevation = azimuth_elevation(receiver_ecef_m, satellite_ecef_m)
    if elevation <= 0.0:
        raise RawBackendError("Saastamoinen requires positive elevation")
    pressure = 1013.25 * (1.0 - 2.2557e-5 * height) ** 5.2568
    temperature = 15.0 - 6.5e-3 * height + 273.16
    vapour = 6.108 * relative_humidity * math.exp((17.15 * temperature - 4684.0) / (temperature - 38.45))
    cosine = math.sin(elevation)
    dry = 0.0022768 * pressure / (1.0 - 0.00266 * math.cos(2.0 * lat) - 0.00028 * height / 1000.0) / cosine
    wet = 0.002277 * (1255.0 / temperature + 0.05) * vapour / cosine
    return dry + wet


def _mode_constellations(system_mode: str) -> tuple[str, ...]:
    return ("GPS", "BDS") if system_mode == "GPS_BDS_DUAL_FREQUENCY" else (("GPS",) if system_mode.startswith("GPS_") else ("BDS",))


def _pntpos_receiver(
    provider: RtklibBroadcastProvider,
    epoch: RawxEpoch,
    system_mode: str,
    initial_position_ecef_m: Sequence[float] | None,
    receiver: str,
) -> Any:
    navsys = {"GPS_DUAL_FREQUENCY": RTKLIB_NAVSYS_GPS, "BDS_DUAL_FREQUENCY": RTKLIB_NAVSYS_BDS, "GPS_BDS_DUAL_FREQUENCY": RTKLIB_NAVSYS_GPS_BDS}[system_mode]
    seed = np.zeros(3, dtype=float) if initial_position_ecef_m is None else np.asarray(initial_position_ecef_m, dtype=float)
    try:
        result = provider.pntpos_rawx_epoch(epoch, navsys, seed)
    except PntPosBridgeError as exc:
        raise SppReceiverError(receiver, exc.code, str(exc)) from exc
    return result


def _best_by_sv(epoch: RawxEpoch, group: str) -> dict[int, RawxMeasurement]:
    allowed = set(SIGNAL_GROUPS[group])
    result: dict[int, RawxMeasurement] = {}
    for measurement in epoch.measurements:
        key = (measurement.identity.gnss_id, measurement.identity.sig_id, measurement.identity.freq_id)
        if key not in allowed or not integer_compatible(measurement):
            continue
        previous = result.get(measurement.identity.sv_id)
        if previous is None or (-measurement.cno_dbhz, key) < (-previous.cno_dbhz, (previous.identity.gnss_id, previous.identity.sig_id, previous.identity.freq_id)):
            result[measurement.identity.sv_id] = measurement
    return result


def build_epoch_blocks(receiver1: RawxEpoch, receiver2: RawxEpoch, provider: RtklibBroadcastProvider, system_mode: str, spp1_ecef_m: Sequence[float], spp2_ecef_m: Sequence[float]) -> tuple[DDObservationBlock, ...]:
    """Build within-system dual-frequency blocks with one pivot per constellation."""
    mean_receiver = 0.5 * (np.asarray(spp1_ecef_m) + np.asarray(spp2_ecef_m))
    blocks: list[DDObservationBlock] = []
    groups_by_constellation = {"GPS": ("GPS_L1", "GPS_L2"), "BDS": ("BDS_B1", "BDS_B2")}
    for constellation in _mode_constellations(system_mode):
        groups = groups_by_constellation[constellation]
        maps = {(receiver, group): _best_by_sv(epoch, group) for receiver, epoch in ((1, receiver1), (2, receiver2)) for group in groups}
        common = set.intersection(*(set(maps[(receiver, group)]) for receiver in (1, 2) for group in groups))
        if len(common) < 2:
            raise Phase3ObservationError(f"INSUFFICIENT_{constellation}_DUAL_FREQUENCY_COMMON_SATELLITES", f"common satellite count={len(common)}")
        state_by_sv: dict[int, np.ndarray] = {}
        elevation_by_sv: dict[int, float] = {}
        for sv in sorted(common):
            measurement = maps[(1, groups[0])][sv]
            mean_range = 0.5 * (measurement.pr_mes_m + maps[(2, groups[0])][sv].pr_mes_m)
            try:
                state = provider.state(measurement.identity, receiver1.gps_week, receiver1.gps_tow_seconds, mean_range)
                satellite = earth_rotation_correct_satellite(state.position_ecef_m, mean_range / 299792458.0)
                _az, elevation = azimuth_elevation(mean_receiver, satellite)
            except RawBackendError:
                continue
            if state.health == 0 and elevation >= math.radians(15.0):
                state_by_sv[sv] = satellite; elevation_by_sv[sv] = elevation
        if len(state_by_sv) < 2:
            raise Phase3ObservationError(f"INSUFFICIENT_{constellation}_DUAL_FREQUENCY_SATELLITE_STATES", f"usable state count={len(state_by_sv)}")
        pivot_sv = min(state_by_sv, key=lambda sv: (-elevation_by_sv[sv], -min(maps[(receiver, group)][sv].locktime_ms for receiver in (1,2) for group in groups), sv))
        satellites = tuple(sv for sv in sorted(state_by_sv) if sv != pivot_sv)
        for group in groups:
            first, second = maps[(1, group)], maps[(2, group)]
            los = {rinex_satellite_id(first[sv].identity): _ecef_vector_to_ned((state_by_sv[sv] - mean_receiver) / np.linalg.norm(state_by_sv[sv] - mean_receiver), mean_receiver) for sv in state_by_sv}
            def corrected_sd(sv: int, phase: bool) -> float:
                m1, m2 = first[sv], second[sv]
                sat = state_by_sv[sv]
                try:
                    trop1, trop2 = _saastamoinen_m(spp1_ecef_m, sat), _saastamoinen_m(spp2_ecef_m, sat)
                except RawBackendError as exc:
                    raise Phase3ObservationError("DD_TROPOSPHERE_MODEL_FAILURE", str(exc)) from exc
                value1 = integer_compatible_carrier_cycles(m1) * wavelength_m(m1.identity) if phase else m1.pr_mes_m
                value2 = integer_compatible_carrier_cycles(m2) * wavelength_m(m2.identity) if phase else m2.pr_mes_m
                return (value2 - trop2) - (value1 - trop1)
            code_pivot, phase_pivot = corrected_sd(pivot_sv, False), corrected_sd(pivot_sv, True)
            code = np.asarray([corrected_sd(sv, False) - code_pivot for sv in satellites])
            phase_values = np.asarray([corrected_sd(sv, True) - phase_pivot for sv in satellites])
            def variances(sv: int) -> tuple[float, float]:
                # Pinned RTKLIB 180043ee varerr defaults at bl=0.350 m and
                # dt=0: fact=1 for GPS/BDS, err[1]=err[2]=0.003 m,
                # eratio[0]=100.  This is the official-code instantiation,
                # deliberately not the Phase1/2 UBX-stdev model.
                sine = math.sin(elevation_by_sv[sv])
                phase_sd_variance = 2.0 * (0.003**2 + 0.003**2 / sine**2)
                return phase_sd_variance * 100.0**2, phase_sd_variance
            pivot_code_var, pivot_phase_var = variances(pivot_sv)
            values = [variances(sv) for sv in satellites]
            covariance = np.block([[correlated_dd_covariance([item[0] for item in values], pivot_code_var), np.zeros((len(satellites), len(satellites)))], [np.zeros((len(satellites), len(satellites))), correlated_dd_covariance([item[1] for item in values], pivot_phase_var)]])
            blocks.append(DDObservationBlock(constellation, group, rinex_satellite_id(first[pivot_sv].identity), tuple(rinex_satellite_id(first[sv].identity) for sv in satellites), wavelength_m(first[pivot_sv].identity), los, code, phase_values, covariance))
    return tuple(blocks)


def _base_row(variant: Variant, epoch_index: int, epoch: RawxEpoch) -> dict[str, Any]:
    return {**variant.row_identity(), "method_id": METHOD_ID, "case_id": CASE_ID, "epoch_index": epoch_index, "gps_week": epoch.gps_week, "gps_tow_seconds": epoch.gps_tow_seconds, "ambiguity_correctness_known": False}


def _tracking_input(
    receiver1: RawxEpoch,
    receiver2: RawxEpoch,
    blocks: Sequence[DDObservationBlock],
    model: Any,
    previous_state: EXT03State | None,
    raw_memory: dict[tuple[int, SignalIdentity], tuple[int, bool, bool, bool]],
    receiver_status_memory: dict[int, int],
) -> EpochTrackingInput:
    """Build the paper's LLI/tracking, GF, MW, and prior-estimate chain."""
    actual_carrier: set[CoreSignalIdentity] = set()
    lock_resets: set[CoreSignalIdentity] = set()
    half_changes: set[CoreSignalIdentity] = set()
    clock_resets: set[CoreSignalIdentity] = set()
    group_for = {(gnss, sig, freq): group for group, identities in SIGNAL_GROUPS.items() for gnss, sig, freq in identities}
    current_measurements: dict[tuple[int, SignalIdentity], RawxMeasurement] = {}
    for receiver, epoch in ((1, receiver1), (2, receiver2)):
        for measurement in epoch.measurements:
            group = group_for.get((measurement.identity.gnss_id, measurement.identity.sig_id, measurement.identity.freq_id))
            if group is None:
                continue
            key = (receiver, measurement.identity)
            current_measurements[key] = measurement
            previous = raw_memory.get(key)
            current = (measurement.locktime_ms, measurement.carrier_valid, measurement.half_cycle_valid, measurement.half_cycle_subtracted)
            constellation = "GPS" if measurement.identity.gnss_id == 0 else "BDS"
            signal = CoreSignalIdentity(constellation, rinex_satellite_id(measurement.identity), group)
            if previous is not None:
                if current[1] != previous[1]:
                    actual_carrier.add(signal)
                if current[0] < previous[0]:
                    lock_resets.add(signal)
                if current[2] != previous[2] or current[3] != previous[3]:
                    half_changes.add(signal)
            raw_memory[key] = current
        prior_status = receiver_status_memory.get(receiver)
        clock_reset = bool(epoch.receiver_status & 0x02)
        if prior_status is not None and clock_reset:
            for measurement in epoch.measurements:
                group = group_for.get((measurement.identity.gnss_id, measurement.identity.sig_id, measurement.identity.freq_id))
                if group is not None:
                    constellation = "GPS" if measurement.identity.gnss_id == 0 else "BDS"
                    clock_resets.add(CoreSignalIdentity(constellation, rinex_satellite_id(measurement.identity), group))
        receiver_status_memory[receiver] = epoch.receiver_status
    geometry_free: dict[tuple[str, str], float] = {}
    melbourne_wubbena: dict[tuple[str, str], float] = {}
    by_constellation = {"GPS": ("GPS_L1", "GPS_L2"), "BDS": ("BDS_B1", "BDS_B2")}
    for constellation, groups in by_constellation.items():
        gnss = 0 if constellation == "GPS" else 3
        maps = {(receiver, group): _best_by_sv(epoch, group) for receiver, epoch in ((1, receiver1), (2, receiver2)) for group in groups}
        common = set.intersection(*(set(maps[(receiver, group)]) for receiver in (1, 2) for group in groups))
        for sv in common:
            gf_values, mw_values = [], []
            for receiver in (1, 2):
                first, second = maps[(receiver, groups[0])][sv], maps[(receiver, groups[1])][sv]
                if not (integer_compatible(first) and integer_compatible(second)):
                    continue
                lambda1, lambda2 = wavelength_m(first.identity), wavelength_m(second.identity)
                frequency1, frequency2 = 299792458.0/lambda1, 299792458.0/lambda2
                gf_values.append(integer_compatible_carrier_cycles(first)*lambda1 - integer_compatible_carrier_cycles(second)*lambda2)
                lambda_wide = 299792458.0 / abs(frequency1-frequency2)
                narrow_code = (frequency1*first.pr_mes_m + frequency2*second.pr_mes_m)/(frequency1+frequency2)
                mw_values.append(lambda_wide*(integer_compatible_carrier_cycles(first)-integer_compatible_carrier_cycles(second)) - narrow_code)
            if len(gf_values) == 2:
                satellite = rinex_satellite_id(maps[(1, groups[0])][sv].identity)
                # Between-receiver SD suppresses common satellite terms while
                # retaining a receiver tracking discontinuity.
                geometry_free[(constellation, satellite)] = gf_values[1] - gf_values[0]
                melbourne_wubbena[(constellation, satellite)] = mw_values[1] - mw_values[0]
    estimated: dict[AmbiguityIdentity, float] = {}
    if previous_state is not None:
        old = {identity: float(previous_state.state[3+index]) for index, identity in enumerate(previous_state.ambiguity_identities)}
        estimated, _unavailable = map_prior_dd_ambiguities_to_target_basis(model.ambiguity_identities, old)
    return EpochTrackingInput(
        actual_carrier_lli_tracking_discontinuities=frozenset(actual_carrier),
        receiver_locktime_resets=frozenset(lock_resets),
        half_cycle_state_changes=frozenset(half_changes),
        receiver_clock_reset_events=frozenset(clock_resets),
        geometry_free_m=geometry_free,
        melbourne_wubbena_m=melbourne_wubbena,
        estimated_dd_ambiguity_cycles=estimated,
    )


def run_variant_sequence(cache_root: Path, navigation_paths: Sequence[Path], bridge_path: Path, lambda_library: Path, variant: Variant, stop_count: int | None = None) -> list[dict[str, Any]]:
    """Run one recursive history strictly in original chronological order."""
    reader = phase2.CompactCacheReader(cache_root)
    provider = RtklibBroadcastProvider(bridge_path, navigation_paths)
    state: EXT03State | None = None
    raw_tracking_memory: dict[tuple[int, SignalIdentity], tuple[int, bool, bool, bool]] = {}
    receiver_status_memory: dict[int, int] = {}
    spp_previous: list[np.ndarray | None] = [None, None]
    records: list[dict[str, Any]] = []
    previous_tow: float | None = None
    count = len(reader) if stop_count is None else min(len(reader), int(stop_count))
    for index in range(count):
        receiver1, receiver2 = reader.pair(index)
        if previous_tow is not None and receiver1.gps_tow_seconds <= previous_tow:
            raise Phase3RunnerError("variant epoch history is not chronological")
        previous_tow = receiver1.gps_tow_seconds
        base = _base_row(variant, index, receiver1)
        started = time.perf_counter()
        spp_audit: dict[str, Any] = {}
        try:
            result1 = _pntpos_receiver(provider, receiver1, variant.system_mode, spp_previous[0], "GNSS1")
            spp_audit["GNSS1"] = _jsonable(result1)
            if not result1.accepted or result1.position_ecef_m is None:
                raise SppReceiverError("GNSS1", "PNTPOS_REJECTED", f"solstat={result1.solution_status} valid={result1.valid_satellite_count} obs={result1.constructed_observation_count} message={result1.message}")
            spp1 = np.asarray(result1.position_ecef_m, dtype=float); spp_previous[0] = spp1
            result2 = _pntpos_receiver(provider, receiver2, variant.system_mode, spp_previous[1], "GNSS2")
            spp_audit["GNSS2"] = _jsonable(result2)
            if not result2.accepted or result2.position_ecef_m is None:
                raise SppReceiverError("GNSS2", "PNTPOS_REJECTED", f"solstat={result2.solution_status} valid={result2.valid_satellite_count} obs={result2.constructed_observation_count} message={result2.message}")
            spp2 = np.asarray(result2.position_ecef_m, dtype=float); spp_previous[1] = spp2
            spp_baseline = _ecef_vector_to_ned(spp2 - spp1, spp1)
            blocks = build_epoch_blocks(receiver1, receiver2, provider, variant.system_mode, spp1, spp2)
            model = build_dd_observation(blocks)
            config = EXT03Config(constraint_mode=variant.constraint_mode, baseline_sigma_m=0.010 if variant.baseline_sigma_m is None else variant.baseline_sigma_m, baseline_prediction_mode="RTKLIB_MOVING_BASE_SPP_RESET")
            tracking = _tracking_input(receiver1, receiver2, blocks, model, state, raw_tracking_memory, receiver_status_memory)
            result = process_epoch(state, receiver1.gps_tow_seconds, model, config, tracking=tracking, spp_baseline_ned_m=spp_baseline, lambda_bridge_path=lambda_library)
            state = result.state
            payload = _jsonable(result)
            dd_audit = {"blocks": _jsonable(blocks), "observation_m": _jsonable(model.observation_m), "design": _jsonable(model.design), "covariance_m2": _jsonable(model.covariance_m2), "ambiguity_identities": _jsonable(model.ambiguity_identities), "block_row_slices": [(constellation, frequency, [rows.start, rows.stop]) for constellation, frequency, rows in model.block_row_slices], "ordering": "BLOCKS_[CODE_DD,PHASE_DD]_BASELINE_THEN_ALIGNED_AMBIGUITIES"}
            records.append({**base, "solution_state": result.solution_state, "paper_ratio_fixed": result.paper_ratio_fixed, "result": payload, "spp_audit": spp_audit, "dd_block_count": len(blocks), "dd_audit": dd_audit, "runtime_seconds": time.perf_counter()-started})
        except (RawBackendError, Yang2024Error, np.linalg.LinAlgError, ValueError) as exc:
            failure_code = getattr(exc, "code", None)
            if failure_code is None:
                failure_code = "NUMERICAL_LINEAR_ALGEBRA_FAILURE" if isinstance(exc, np.linalg.LinAlgError) else ("NUMERICAL_VALUE_ERROR" if isinstance(exc, ValueError) else "RAW_BACKEND_FAILURE")
            records.append({**base, "solution_state": "invalid", "paper_ratio_fixed": False, "failure_code": failure_code, "failure_detail": str(exc), "spp_audit": spp_audit, "runtime_seconds": time.perf_counter()-started})
    if len(records) != count or [row["epoch_index"] for row in records] != list(range(count)):
        raise Phase3RunnerError("variant row conservation failed")
    return records


def _scientific_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if key != "runtime_seconds"} for row in records]


def _write_worker_failure_evidence(root: Path, payload: Mapping[str, Any]) -> Path:
    """Persist a timestamped, non-success, no-replace worker ledger."""
    target = Path(root) / f"WORKER_FAILURE_{time.time_ns()}_{os.getpid()}.json"
    if target.exists():
        raise Phase3RunnerError("timestamped worker failure ledger collision")
    phase2._atomic_write_json(target, {"schema_version": "horizontal_literature.phase3.worker_failure.v1", "successful_native_claimed": False, **payload})
    return target


def _real_determinism_probe(cache: Path, navs: Sequence[Path], preflight: PreflightResult, variants: Sequence[Variant], failure_root: Path, subset_count: int = 64) -> dict[str, Any]:
    def execute(worker_count: int) -> dict[str, list[dict[str, Any]]]:
        output: dict[str, list[dict[str, Any]]] = {}
        completed_count = 0
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(run_variant_sequence, cache, navs, preflight.paths.rtklib_bridge, preflight.paths.lambda_library, variant, subset_count): variant for variant in variants}
            for future in as_completed(futures):
                variant = futures[future]
                try:
                    output[variant.variant_id] = _scientific_records(future.result())
                    completed_count += 1
                except BaseException as exc:
                    _write_worker_failure_evidence(failure_root, {"phase": f"WORKER_DETERMINISM_{worker_count}", "requested_workers": worker_count, "submitted_task_count": len(futures), "completed_task_count": completed_count, "failed_task_count": 1, "worker_failure_count": 1, "variant_id": variant.variant_id, "exception_type": type(exc).__name__, "exception_message": str(exc)})
                    raise
        return output
    one, sixteen = execute(1), execute(16)
    hash1 = hashlib.sha256(_canonical(one).encode()).hexdigest()
    hash16 = hashlib.sha256(_canonical(sixteen).encode()).hexdigest()
    return {"schema_version": "horizontal_literature.phase3.real_determinism.v1", "input_role": "REAL_RAW_INPUT_ONLY_NO_REFERENCE", "subset_original_indices": list(range(subset_count)), "workers_1_scientific_sha256": hash1, "workers_16_scientific_sha256": hash16, "row_level_scientific_equality": one == sixteen, "worker_failure_count": 0, "runtime_fields_excluded": ["runtime_seconds"], "trace_open_count": 0, "HPPOSECEF_semantic_decode_count": 0}


def _resource_probe(paths: Phase3Paths, workers: int) -> dict[str, Any]:
    before = phase2._system_resource_snapshot(paths.stage_root)
    started = time.perf_counter(); digest = hashlib.sha256(); byte_count = 0
    with paths.gnss1_raw.open("rb") as stream:
        while byte_count < 8 * 1024 * 1024:
            chunk = stream.read(min(1024 * 1024, 8 * 1024 * 1024-byte_count))
            if not chunk: break
            digest.update(chunk); byte_count += len(chunk)
    elapsed = time.perf_counter()-started
    after = phase2._system_resource_snapshot(paths.stage_root)
    thermal = phase2._temperature_stability(before, after)
    io = {"bytes_read": byte_count, "elapsed_seconds": elapsed, "throughput_bytes_per_second": byte_count/max(elapsed, 1e-12), "sha256": digest.hexdigest()}
    swap_stable = before["swap_in_pages"] == after["swap_in_pages"] and before["swap_out_pages"] == after["swap_out_pages"] and after["swap_used_bytes"] == 0
    cpu_stable = bool(after["cpu_count"] and after["load_average_1m_5m_15m"][0] <= after["cpu_count"])
    ram_stable = min(before["ram_available_bytes"], after["ram_available_bytes"]) > 0
    io_stable = byte_count > 0 and io["throughput_bytes_per_second"] > 0
    stable = ram_stable and swap_stable and cpu_stable and io_stable
    evidence = {"requested_workers": workers, "default_workers": DEFAULT_WORKERS, "maximum_workers": MAX_WORKERS, "worker_failure_count": 0, "before": before, "after": after, "thermal_stability": thermal, "io_probe": io, "RAM_stable": ram_stable, "swap_stable": swap_stable, "CPU_load_stable": cpu_stable, "IO_stable": io_stable, "stable_RAM_swap_CPU_load_IO": stable, "thread_environment": {name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")}, "maximum20_admitted": False}
    if workers == MAX_WORKERS:
        evidence["maximum20_admitted"] = stable and thermal["available"] and thermal["stable"]
        if not evidence["maximum20_admitted"]:
            evidence["resource_gate_rejected"] = True
            raise ResourceProbeRejected("20-worker resource gate lacks zero-swap thermal evidence", evidence)
    return evidence


def _write_resource_probe_failure_evidence(root: Path, exc: ResourceProbeRejected) -> Path:
    target = Path(root) / f"RESOURCE_PROBE_FAILURE_{time.time_ns()}_{os.getpid()}.json"
    if target.exists():
        raise Phase3RunnerError("timestamped resource-probe failure ledger collision")
    phase2._atomic_write_json(target, {"schema_version": "horizontal_literature.phase3.resource_probe_failure.v1", "successful_native_claimed": False, "exception_type": type(exc).__name__, "exception_message": str(exc), "resource_probe": exc.evidence})
    return target


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = tuple(dict.fromkeys(key for row in rows for key in row)) or ("empty",)
    normalized = [{key: (_canonical(_jsonable(row.get(key))) if isinstance(row.get(key), (dict, list, tuple)) else row.get(key)) for key in fields} for row in rows]
    phase2._atomic_write_csv(path, normalized, fields)


def _signal_output_rows(inventory: SignalInventoryResult) -> list[dict[str, Any]]:
    base = {"method_id": METHOD_ID, "case_id": CASE_ID, "system_mode": "ALL_AUDITED", "constraint_mode": "NOT_APPLICABLE", "baseline_sigma_m": None, "solution_state": "NOT_APPLICABLE", "paper_ratio_fixed": False, "ambiguity_correctness_known": False}
    rows = [{**base, **row} for row in inventory.epoch_rows]
    rows.extend({**base, **row.to_dict()} for row in inventory.rows)
    rows.extend({**base, **item.to_dict(), "row_scope": "MODE_SUPPORT", "solution_state": "SUPPORTED" if item.supported else "UNSUPPORTED"} for item in inventory.mode_support)
    return rows


def _prepare_cache(preflight: PreflightResult, attempt: Path, *, resume: bool = False) -> tuple[Path, tuple[Path, Path]]:
    source = attempt / "SOURCE_BACKEND"; source.mkdir(parents=True, exist_ok=resume)
    cache = attempt / "COMPACT_CACHE"
    navs_existing = (source / "gnss1.nav", source / "gnss2.nav")
    if cache.exists():
        if not resume:
            raise Phase3RunnerError("compact cache exists outside resume mode")
        phase2.validate_compact_cache(cache, source_fingerprint=preflight.source_fingerprint, expected_pair_count=EXPECTED_PAIR_COUNT)
        if not all(path.is_file() for path in navs_existing):
            raise Phase3RunnerError("resume cache lacks reconstructed navigation files")
        return cache, navs_existing
    reconstructions = []
    navs = []
    for number, raw in ((1, preflight.paths.gnss1_raw), (2, preflight.paths.gnss2_raw)):
        ubx = source / f"gnss{number}.ubx"; obs = source / f"gnss{number}.obs"; nav = source / f"gnss{number}.nav"
        reconstruction = reconstruct_ubx_stream(raw, ubx, decode_nav_hpposecef_semantics=False)
        if reconstruction.nav_hpposecef_semantic_decode_enabled or reconstruction.nav_hpposecef_epochs:
            raise Phase3RunnerError("native preparation decoded HPPOSECEF semantics")
        phase2._run_convbin(preflight.paths.convbin, ubx, obs, nav)
        reconstructions.append(reconstruction); navs.append(nav)
    pairs, failures = pair_epochs(reconstructions[0].rawx_epochs, reconstructions[1].rawx_epochs, tolerance_seconds=0.0)
    if failures or len(pairs) != EXPECTED_PAIR_COUNT:
        raise Phase3RunnerError(f"exact pair gate failed: {len(pairs)} pairs, {len(failures)} failures")
    phase2.write_compact_cache(cache, pairs, source_fingerprint=preflight.source_fingerprint, extra_manifest={"phase3_contract": True, "trace_open_count_before_native_freeze": 0, "HPPOSECEF_semantic_decode_count_before_native_freeze": 0})
    return cache, tuple(navs)


def _part_path(attempt: Path, variant: Variant) -> Path:
    return attempt / "VARIANT_PARTS" / f"{variant.variant_id}.json"


def _read_variant_part(path: Path, preflight: PreflightResult, variant: Variant) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "horizontal_literature.phase3.variant_part.v1" or value.get("source_fingerprint") != preflight.source_fingerprint or value.get("variant_id") != variant.variant_id:
        raise Phase3RunnerError("resume variant-part identity mismatch")
    records = value.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_PAIR_COUNT or [row.get("epoch_index") for row in records] != list(range(EXPECTED_PAIR_COUNT)):
        raise Phase3RunnerError("resume variant-part row conservation mismatch")
    digest = hashlib.sha256(_canonical(records).encode()).hexdigest()
    if digest != value.get("records_sha256"):
        raise Phase3RunnerError("resume variant-part hash mismatch")
    return records


def _write_variant_part(path: Path, preflight: PreflightResult, variant: Variant, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serial = _jsonable(list(records))
    phase2._atomic_write_json(path, {"schema_version": "horizontal_literature.phase3.variant_part.v1", "source_fingerprint": preflight.source_fingerprint, "variant_id": variant.variant_id, "records_sha256": hashlib.sha256(_canonical(serial).encode()).hexdigest(), "records": serial})


def _flatten_native(records: Sequence[Mapping[str, Any]], inventory: SignalInventoryResult, variants: Sequence[Variant], output_root: Path, preflight: PreflightResult, resource_probe: Mapping[str, Any], pntpos_bridge_provenance: Mapping[str, Any]) -> dict[str, Any]:
    _validate_runtime_dependency_hashes(preflight.paths.bridge_root, preflight.runtime_dependency_hashes)
    files = {key: output_root / name for key, name in NATIVE_FILE_NAMES.items()}
    heading, failures, runtime, dd, kf, constraint, ambiguity, slips, mlambda = [], [], [], [], [], [], [], [], []
    for record in records:
        identity = {key: record.get(key) for key in ("method_id", "case_id", "system_mode", "constraint_mode", "baseline_sigma_m", "epoch_index", "gps_week", "gps_tow_seconds", "solution_state", "paper_ratio_fixed", "ambiguity_correctness_known")}
        runtime.append({**identity, "runtime_seconds": record.get("runtime_seconds")})
        if record.get("solution_state") == "invalid":
            failures.append({**identity, "failure_code": record.get("failure_code"), "failure_detail": record.get("failure_detail")})
            heading.append({**identity, "failure_code": record.get("failure_code"), "baseline_ned_m": None, "baseline_length_m": None, "baseline_heading_deg": None, "baseline_pitch_deg": None, "body_yaw_deg": None})
            dd.append({**identity, "dd_block_count": 0, "diagnostic_status": "INVALID_EPOCH", "raw_pntpos_receiver_audit": record.get("spp_audit", {})})
            kf.append({**identity, "diagnostic_status": "INVALID_EPOCH", "raw_pntpos_receiver_audit": record.get("spp_audit", {})})
            constraint.append({**identity, "constraint_applied": False, "constraint_linearization_source": "INVALID_EPOCH"})
            ambiguity.append({**identity, "diagnostic_status": "INVALID_EPOCH"})
            slips.append({**identity, "diagnostic_status": "INVALID_EPOCH", "event_counter_semantics": "UNIQUE_AFFECTED_SIGNAL_IDENTITIES_RECEIVER_DIMENSION_DEDUPLICATED"})
            mlambda.append({**identity, "candidate_returned": False, "failure_code": record.get("failure_code")})
            continue
        result = record["result"]
        selected = result.get("fixed_baseline_ned_m") if record.get("paper_ratio_fixed") else result.get("float_baseline_ned_m")
        attitude = result.get("fixed_attitude") if record.get("paper_ratio_fixed") else result.get("float_attitude")
        heading.append({**identity, "failure_code": None, "baseline_ned_m": selected, "baseline_length_m": None if selected is None else float(np.linalg.norm(selected)), "baseline_heading_deg": None if attitude is None else attitude.get("baseline_heading_deg"), "baseline_pitch_deg": None if attitude is None else attitude.get("pitch_deg"), "body_yaw_deg": None if attitude is None else attitude.get("body_yaw_deg"), "ratio": result.get("mlambda_diagnostics", {}).get("ratio"), "ratio_is_infinite": result.get("mlambda_diagnostics", {}).get("ratio_is_infinite"), "zero_best_objective": result.get("mlambda_diagnostics", {}).get("zero_best_objective"), "constraint_innovation_m": result.get("constraint_diagnostics", {}).get("constraint_innovation_m"), "constraint_nis": result.get("constraint_diagnostics", {}).get("constraint_nis")})
        dd.append({**identity, "dd_block_count": record.get("dd_block_count"), "raw_pntpos_receiver_audit": record.get("spp_audit", {}), **record.get("dd_audit", {})})
        state_payload = result.get("state", {})
        kf.append({**identity, **result.get("kf_diagnostics", {}), "raw_pntpos_receiver_audit": record.get("spp_audit", {}), "float_state_vector": state_payload.get("state"), "full_covariance": state_payload.get("covariance")})
        constraint.append({**identity, **result.get("constraint_diagnostics", {})})
        ambiguity.append({**identity, **result.get("state_diagnostics", {}), "ambiguity_values_cycles": (state_payload.get("state") or [])[3:], "identity_value_alignment": "state[3+i] <-> ambiguity_state_identities[i]"})
        slips.append({**identity, "event_counter_semantics": "UNIQUE_AFFECTED_SIGNAL_IDENTITIES_RECEIVER_DIMENSION_DEDUPLICATED", **result.get("cycle_slip_diagnostics", {})})
        mlambda.append({**identity, **result.get("mlambda_diagnostics", {})})
    common_na = {"method_id": METHOD_ID, "case_id": CASE_ID, "system_mode": "ALL_AUDITED", "constraint_mode": "NOT_APPLICABLE", "baseline_sigma_m": None, "solution_state": "NOT_APPLICABLE", "paper_ratio_fixed": False, "ambiguity_correctness_known": False}
    signal_rows = _signal_output_rows(inventory)
    summaries = []
    for variant in variants:
        subset = [row for row in records if all(row.get(key) == value for key, value in variant.row_identity().items())]
        valid = [row for row in subset if row.get("solution_state") != "invalid"]
        def numbers(getter: Any) -> list[float]:
            values = []
            for row in valid:
                value = getter(row.get("result", {}))
                if value is not None and math.isfinite(float(value)):
                    values.append(float(value))
            return values
        ratios = numbers(lambda result: result.get("mlambda_diagnostics", {}).get("ratio"))
        covariance_traces = numbers(lambda result: result.get("kf_diagnostics", {}).get("covariance_trace"))
        constraint_innovations = numbers(lambda result: result.get("constraint_diagnostics", {}).get("constraint_innovation_m"))
        constraint_nis = numbers(lambda result: result.get("constraint_diagnostics", {}).get("constraint_nis"))
        ambiguity_counts = numbers(lambda result: result.get("state_diagnostics", {}).get("ambiguity_state_count"))
        float_norms = numbers(lambda result: np.linalg.norm(result.get("float_baseline_ned_m")) if result.get("float_baseline_ned_m") is not None else None)
        fixed_norms = numbers(lambda result: np.linalg.norm(result.get("fixed_baseline_ned_m")) if result.get("fixed_baseline_ned_m") is not None else None)
        fixed_indices = [int(row["epoch_index"]) for row in subset if row.get("paper_ratio_fixed")]
        selected_attitudes, selected_lengths = [], []
        for row in valid:
            result = row["result"]
            fixed = bool(row.get("paper_ratio_fixed"))
            baseline = result.get("fixed_baseline_ned_m") if fixed else result.get("float_baseline_ned_m")
            attitude = result.get("fixed_attitude") if fixed else result.get("float_attitude")
            if baseline is not None and attitude is not None:
                selected_lengths.append(float(np.linalg.norm(baseline)))
                selected_attitudes.append(attitude)
        def distribution(values: Sequence[float]) -> dict[str, Any]:
            return {"count": len(values), "mean": float(np.mean(values)) if values else None, "median": float(np.median(values)) if values else None, "standard_deviation": float(np.std(values)) if values else None, "minimum": float(np.min(values)) if values else None, "maximum": float(np.max(values)) if values else None}
        def circular(values: Sequence[float]) -> dict[str, Any]:
            if not values: return {"count": 0, "circular_mean_deg": None, "resultant_length": None}
            radians = np.radians(values); sine, cosine = float(np.mean(np.sin(radians))), float(np.mean(np.cos(radians)))
            return {"count": len(values), "circular_mean_deg": math.degrees(math.atan2(sine,cosine))%360.0, "resultant_length": math.hypot(sine,cosine)}
        valid_indices = [int(row["epoch_index"]) for row in valid]
        summaries.append({**common_na, **variant.row_identity(), "solution_state": "SUMMARY", "row_count": len(subset), "valid_count": len(valid), "valid_rate": len(valid)/len(subset) if subset else None, "valid_continuity_epoch_count": len(valid_indices), "valid_max_index_gap": max((b-a for a,b in zip(valid_indices,valid_indices[1:])), default=None), "float_count": sum(row.get("solution_state") == "float" for row in subset), "paper_ratio_fixed_count": len(fixed_indices), "paper_ratio_fixed_rate": len(fixed_indices)/len(subset) if subset else None, "invalid_count": sum(row.get("solution_state") == "invalid" for row in subset), "finite_ratio_count": len(ratios), "ratio_infinite_count": sum(bool(row.get("result", {}).get("mlambda_diagnostics", {}).get("ratio_is_infinite")) for row in valid), "ratio_mean": np.mean(ratios) if ratios else None, "ratio_median": np.median(ratios) if ratios else None, "covariance_trace_mean": np.mean(covariance_traces) if covariance_traces else None, "constraint_innovation_mean_m": np.mean(constraint_innovations) if constraint_innovations else None, "constraint_NIS_mean": np.mean(constraint_nis) if constraint_nis else None, "ambiguity_state_count_mean": np.mean(ambiguity_counts) if ambiguity_counts else None, "float_baseline_norm_mean_m": np.mean(float_norms) if float_norms else None, "fixed_baseline_norm_mean_m": np.mean(fixed_norms) if fixed_norms else None, "selected_baseline_length_m": distribution(selected_lengths), "selected_baseline_heading_deg": circular([float(item["baseline_heading_deg"]) for item in selected_attitudes]), "selected_body_yaw_deg": circular([float(item["body_yaw_deg"]) for item in selected_attitudes]), "selected_pitch_deg": distribution([float(item["pitch_deg"]) for item in selected_attitudes]), "fixed_continuity_epoch_count": len(fixed_indices), "fixed_max_index_gap": max((b-a for a,b in zip(fixed_indices, fixed_indices[1:])), default=None), "runtime_seconds_total": sum(float(row.get("runtime_seconds", 0.0)) for row in subset)})
    sensitivity = [row for row in summaries if row["system_mode"] == "GPS_BDS_DUAL_FREQUENCY" and row["constraint_mode"] == "CONSTRAINED"]
    registry = [{**common_na, **_jsonable(item)} for item in STOCHASTIC_PARAMETER_REGISTRY]
    registry.extend({**common_na, **row} for row in ADAPTER_STOCHASTIC_REGISTRY)
    for key, rows in (("heading_results", heading), ("failure_ledger", failures), ("runtime", runtime), ("signal_availability", signal_rows), ("dd_diagnostics", dd), ("kf_state_diagnostics", kf), ("constraint_diagnostics", constraint), ("ambiguity_state_diagnostics", ambiguity), ("cycle_slip_diagnostics", slips), ("mlambda_diagnostics", mlambda), ("mode_summary", summaries), ("sensitivity_summary", sensitivity), ("stochastic_registry", registry)):
        _write_csv(files[key], rows)
    provenance = {"data_mode": "real_by2_raw", "synthetic_data_used": False, "semisynthetic_data_used": False, "trace_used_online": False, "receiver_imu_as_body_imu": False, "final_v23_output_solver_input": False, "LegSA_output_solver_input": False, "per_case_tuning": False, "output_only_correction": False, "epoch_deleted_for_metric": False, "old_runtime_input_count": 0, "status_baseline_solver_input": False, "Go2_yaw_solver_input": False, "EXT01_output_solver_input": False, "EXT02_output_solver_input": False, "RTKLIB_diagnostic_output_solver_input": False, "phase_bias_calibration": False, "code_commit": preflight.code_commit, "code_commit_semantics": "BASE_HEAD_ONLY_WITH_HASHED_RUNTIME_SOURCE_OVERLAY", "worktree_overlay_identity": preflight.worktree_overlay_identity, "config_hash": preflight.config_hash, "contract_hash": preflight.contract_hash, "runtime_source_hashes": preflight.runtime_source_hashes, "runtime_dependency_hashes": preflight.runtime_dependency_hashes, "raw_source_hashes": preflight.raw_source_hashes, "provider_hashes": preflight.provider_hashes}
    summary = {"schema_version": "horizontal_literature.phase3.native_summary.v1", "method_id": METHOD_ID, "case_id": CASE_ID, "paired_epoch_count": EXPECTED_PAIR_COUNT, "supported_modes": list(inventory.supported_modes()), "unsupported_modes": [item.to_dict() for item in inventory.mode_support if not item.supported], "variant_count": len(variants), "expected_native_heading_rows": EXPECTED_PAIR_COUNT * len(variants), "native_heading_rows": len(heading), "trace_open_count": 0, "HPPOSECEF_semantic_decode_count": 0, "resource_probe": resource_probe, "model_registry": _jsonable(PAPER_MODEL_REGISTRY), "combined_system_bias_handling": {"DD_blocks": "SEPARATE_WITHIN_GPS_AND_WITHIN_BDS", "GPS_BDS_cross_DD": False, "explicit_relative_hardware_bias_state": False, "GPS_BDS_measurement_factors": [1.0, 1.0], "pntpos_clock_handling": "EACH_RECEIVER_INDEPENDENT_GPS_CLOCK_PLUS_BDS_MINUS_GPS_OFFSET_SPP_ONLY", "pntpos_clock_or_ISB_transferred_to_DD": False}, "pntpos_bridge_provenance": _jsonable(pntpos_bridge_provenance), "provenance": provenance, "official_code_search_result": preflight.contract["paper_source"]["official_code_search"]["result"]}
    phase2._atomic_write_json(files["native_summary"], summary)
    hashes = {key: _sha256(files[key]) for key in FREEZE_HASH_KEYS}
    row_counts = {"heading_results": len(heading), "failure_ledger": len(failures), "runtime": len(runtime), "signal_availability": len(signal_rows), "dd_diagnostics": len(dd), "kf_state_diagnostics": len(kf), "constraint_diagnostics": len(constraint), "ambiguity_state_diagnostics": len(ambiguity), "cycle_slip_diagnostics": len(slips), "mlambda_diagnostics": len(mlambda), "mode_summary": len(summaries), "sensitivity_summary": len(sensitivity), "stochastic_registry": len(registry)}
    freeze = {"schema_version": "horizontal_literature.phase3.native_freeze.v1", "source_fingerprint": preflight.source_fingerprint, "native_hashes": hashes, "native_row_counts": row_counts, "trace_open_count_at_freeze": 0, "HPPOSECEF_semantic_decode_count_at_freeze": 0, "status_baseline_solver_input": False, "Go2_yaw_solver_input": False, "EXT01_output_solver_input": False, "EXT02_output_solver_input": False, "LegSA_output_solver_input": False, "RTKLIB_diagnostic_output_solver_input": False, "phase_bias_calibration": False, "paired_epoch_count": EXPECTED_PAIR_COUNT, "variant_count": len(variants), "heading_row_count": len(heading), "provenance": provenance}
    _validate_runtime_dependency_hashes(preflight.paths.bridge_root, preflight.runtime_dependency_hashes)
    phase2._atomic_write_json(files["native_freeze"], freeze)
    return freeze


def _validate_failure_ledger_matches_invalid_headings(
    headings: Sequence[Mapping[str, str]], failures: Sequence[Mapping[str, str]]
) -> None:
    fields = ("system_mode", "constraint_mode", "baseline_sigma_m", "epoch_index", "gps_week", "gps_tow_seconds", "failure_code")
    invalid = [tuple(row.get(field, "") for field in fields) for row in headings if row.get("solution_state") == "invalid"]
    ledger = [tuple(row.get(field, "") for field in fields) for row in failures]
    if any(not key[-1] for key in invalid) or sorted(invalid) != sorted(ledger):
        raise Phase3RunnerError("failure ledger does not exactly match invalid native heading rows")


def validate_native_freeze(native_root: Path) -> dict[str, Any]:
    root = Path(native_root); path = root / NATIVE_FILE_NAMES["native_freeze"]
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "horizontal_literature.phase3.native_freeze.v1" or value.get("trace_open_count_at_freeze") != 0 or value.get("HPPOSECEF_semantic_decode_count_at_freeze") != 0:
        raise Phase3RunnerError("invalid Phase-3 native freeze")
    if set(value.get("native_hashes", {})) != set(FREEZE_HASH_KEYS):
        raise Phase3RunnerError("native freeze inventory incomplete")
    for key, digest in value["native_hashes"].items():
        if _sha256(root / NATIVE_FILE_NAMES[key]) != digest:
            raise Phase3RunnerError(f"native hash mismatch: {key}")
    if int(value.get("heading_row_count", -1)) != int(value.get("paired_epoch_count", -1)) * int(value.get("variant_count", -1)):
        raise Phase3RunnerError("native freeze row conservation failed")
    expected = int(value["paired_epoch_count"])*int(value["variant_count"])
    counts = value.get("native_row_counts")
    if counts is not None:
        for key in ("heading_results", "runtime", "dd_diagnostics", "kf_state_diagnostics", "constraint_diagnostics", "ambiguity_state_diagnostics", "cycle_slip_diagnostics", "mlambda_diagnostics"):
            if int(counts.get(key, -1)) != expected:
                raise Phase3RunnerError(f"native per-epoch diagnostic conservation failed: {key}")
        for key, recorded in counts.items():
            if key in {"native_summary", "native_freeze"}: continue
            path = root / NATIVE_FILE_NAMES[key]
            if path.suffix == ".csv" and len(_read_csv(path)) != int(recorded):
                raise Phase3RunnerError(f"native recorded row count mismatch: {key}")
        headings = _read_csv(root/NATIVE_FILE_NAMES["heading_results"])
        _validate_failure_ledger_matches_invalid_headings(headings, _read_csv(root/NATIVE_FILE_NAMES["failure_ledger"]))
        per_variant: dict[tuple[str,str,str], int] = {}
        for row in headings:
            key = (row["system_mode"], row["constraint_mode"], row.get("baseline_sigma_m", ""))
            per_variant[key] = per_variant.get(key, 0)+1
            if row.get("solution_state") != "invalid":
                vector = np.asarray(json.loads(row["baseline_ned_m"]), dtype=float)
                if vector.shape != (3,) or np.any(~np.isfinite(vector)) or not math.isfinite(float(row["baseline_length_m"])):
                    raise Phase3RunnerError("native heading contains nonfinite valid baseline")
        if set(per_variant.values()) != {int(value["paired_epoch_count"])} or len(per_variant) != int(value["variant_count"]):
            raise Phase3RunnerError("native per-variant heading conservation failed")
        for row in _read_csv(root/NATIVE_FILE_NAMES["kf_state_diagnostics"]):
            if row.get("solution_state") != "invalid":
                state = np.asarray(json.loads(row["float_state_vector"]), dtype=float)
                covariance = np.asarray(json.loads(row["full_covariance"]), dtype=float)
                if state.ndim != 1 or covariance.shape != (state.size,state.size) or np.any(~np.isfinite(state)) or np.any(~np.isfinite(covariance)):
                    raise Phase3RunnerError("native KF diagnostic state/covariance is nonfinite or misaligned")
    return value


def _atomic_finalize_native(attempt_output: Path, final: Path) -> None:
    if final.exists():
        raise Phase3RunnerError("final native root appeared before atomic finalize")
    if attempt_output.parent.parent != final.parent:
        raise Phase3RunnerError("attempt output and final root must share the stage parent")
    validate_native_freeze(attempt_output)
    phase2._atomic_install_noreplace(attempt_output, final, label="Phase-3 native root", kind="directory")
    validate_native_freeze(final)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _wrap180(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _strict_csv_bool(value: Any, *, field: str) -> bool:
    if value is True or value == "true": return True
    if value is False or value == "false": return False
    raise Phase3RunnerError(f"invalid canonical CSV boolean for {field}: {value!r}")


def _optional_finite_csv_float(value: Any, *, field: str) -> float | None:
    if value in (None,""): return None
    try: result=float(value)
    except (TypeError,ValueError) as exc: raise Phase3RunnerError(f"invalid CSV numeric for {field}: {value!r}") from exc
    if not math.isfinite(result): raise Phase3RunnerError(f"non-finite CSV numeric for {field}: {value!r}")
    return result


def _build_trace_summary_rows(trace_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    def error_stats(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        values=[_optional_finite_csv_float(row.get("native_minus_trace_wrapsafe_deg"),field="native_minus_trace_wrapsafe_deg") for row in rows]
        array = np.asarray([value for value in values if value is not None],dtype=float)
        if not array.size: return {"count":0}
        absolute=np.abs(array)
        return {"count":int(array.size),"bias":float(np.mean(array)),"rmse":float(np.sqrt(np.mean(array**2))),"mae":float(np.mean(absolute)),"median_absolute":float(np.median(absolute)),"p90_absolute":float(np.percentile(absolute,90)),"p95_absolute":float(np.percentile(absolute,95)),"p99_absolute":float(np.percentile(absolute,99)),"max_absolute":float(np.max(absolute))}
    output: list[dict[str, Any]]=[]
    state_keys=sorted({(row["system_mode"],row["constraint_mode"],row.get("baseline_sigma_m"),row["solution_state"]) for row in trace_rows})
    for key in state_keys:
        subset=[row for row in trace_rows if (row["system_mode"],row["constraint_mode"],row.get("baseline_sigma_m"),row["solution_state"])==key]
        matched=[row for row in subset if _strict_csv_bool(row.get("fixed_window_matched"),field="fixed_window_matched")]
        tows=sorted(float(row["gps_tow_seconds"]) for row in matched)
        output.append({"method_id":METHOD_ID,"case_id":CASE_ID,"system_mode":key[0],"constraint_mode":key[1],"baseline_sigma_m":key[2],"solution_state":key[3],"paper_ratio_fixed":key[3]=="paper_ratio_fixed","ambiguity_correctness_known":False,"row_count":len(subset),"matched_count":len(matched),"coverage":None if key[3]=="invalid" else (len(matched)/len(subset) if subset else None),"window_timestamp_fraction":len(matched)/len(subset) if subset else None,**error_stats(matched),"continuity_count":len(tows),"maximum_gap_seconds":max((b-a for a,b in zip(tows,tows[1:])),default=None)})
    variant_keys=sorted({(row["system_mode"],row["constraint_mode"],row.get("baseline_sigma_m")) for row in trace_rows})
    for key in variant_keys:
        variant=[row for row in trace_rows if (row["system_mode"],row["constraint_mode"],row.get("baseline_sigma_m"))==key]
        window=[row for row in variant if _strict_csv_bool(row.get("fixed_window_matched"),field="fixed_window_matched")]
        valid=[row for row in variant if row.get("solution_state")!="invalid"]
        valid_matched=[row for row in valid if _strict_csv_bool(row.get("fixed_window_matched"),field="fixed_window_matched") and _optional_finite_csv_float(row.get("native_minus_trace_wrapsafe_deg"),field="native_minus_trace_wrapsafe_deg") is not None]
        fixed=[row for row in valid_matched if _strict_csv_bool(row.get("paper_ratio_fixed"),field="paper_ratio_fixed")]
        tows=sorted(float(row["gps_tow_seconds"]) for row in valid_matched)
        output.append({"method_id":METHOD_ID,"case_id":CASE_ID,"system_mode":key[0],"constraint_mode":key[1],"baseline_sigma_m":key[2],"solution_state":"ALL_VALID","paper_ratio_fixed":False,"ambiguity_correctness_known":False,"row_count":len(variant),"valid_count":len(valid),"fixed_window_input_count":len(window),"window_timestamp_fraction":len(window)/len(variant) if variant else None,"valid_matched_count":len(valid_matched),"valid_coverage":len(valid_matched)/len(window) if window else None,"paper_ratio_fixed_matched_count":len(fixed),"paper_ratio_fixed_rate_of_window":len(fixed)/len(window) if window else None,"paper_ratio_fixed_rate_of_valid_matched":len(fixed)/len(valid_matched) if valid_matched else None,**error_stats(valid_matched),"valid_continuity_count":len(tows),"valid_maximum_gap_seconds":max((b-a for a,b in zip(tows,tows[1:])),default=None)})
    return output


def _validate_post_native_freeze(root: Path) -> dict[str, Any]:
    path = Path(root) / "EXT03_C00_POST_NATIVE_FREEZE.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "horizontal_literature.phase3.post_native_freeze.v1":
        raise Phase3RunnerError("invalid post-native freeze schema")
    for name, digest in value.get("files", {}).items():
        target = Path(root) / name
        if not target.is_file() or _sha256(target) != digest:
            raise Phase3RunnerError(f"post-native hash mismatch: {name}")
    return value


def _primary_post_recovery_inventory(preflight: PreflightResult, *, expected_file_count: int | None = None) -> dict[str, Any]:
    root = preflight.paths.native_root / "POST_NATIVE"
    _validate_post_native_freeze(root)
    files = sorted(path for path in root.iterdir() if path.is_file())
    if expected_file_count is not None and len(files) != expected_file_count:
        raise Phase3RunnerError(f"primary POST_NATIVE file count changed: {len(files)} != {expected_file_count}")
    report_status = (preflight.paths.final_report, preflight.paths.final_status)
    if any(not path.is_file() for path in report_status):
        raise Phase3RunnerError("primary Phase3 report/status missing before recovery")
    file_inventory = {path.name:{"sha256":_sha256(path),"size_bytes":path.stat().st_size} for path in files}
    report_inventory = {path.name:{"sha256":_sha256(path),"size_bytes":path.stat().st_size} for path in report_status}
    return {
        "primary_post_file_count":len(files),
        "primary_post_total_bytes":sum(item["size_bytes"] for item in file_inventory.values()),
        "primary_post_files":file_inventory,
        "primary_post_aggregate_sha256":hashlib.sha256(_canonical(file_inventory).encode()).hexdigest(),
        "primary_report_status":report_inventory,
        "primary_report_status_aggregate_sha256":hashlib.sha256(_canonical(report_inventory).encode()).hexdigest(),
    }


def _parse_rtklib_enu_pos(text: str) -> list[dict[str, Any]]:
    """Parse the exact 15-column pinned ``solution.c:outenu`` record."""
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        lexical = line.strip()
        if not lexical or lexical.startswith(("%", "#")):
            continue
        fields = [item.strip() for item in lexical.split(",")] if "," in lexical else lexical.split()
        if len(fields) != 15:
            raise Phase3RunnerError(f"RTKLIB .pos row {line_number} must have exactly 15 fields")
        try:
            values = [float(field) for field in fields]
            week = int(values[0]); tow = values[1]
            east, north, up = values[2:5]; quality = int(values[5])
            satellites = int(values[6]); age_s, ratio = values[13:15]
        except ValueError as exc:
            raise Phase3RunnerError(f"RTKLIB .pos row {line_number} is not numeric") from exc
        if any(not math.isfinite(value) for value in values):
            raise Phase3RunnerError(f"RTKLIB .pos row {line_number} contains non-finite values")
        if values[0] != week or values[5] != quality or values[6] != satellites:
            raise Phase3RunnerError(f"RTKLIB .pos row {line_number} has non-integral week/quality/satellite fields")
        if not 0 <= week <= 9999 or not 0 <= tow < 604800.001 or quality < 0 or satellites < 0 or age_s < 0 or ratio < 0:
            raise Phase3RunnerError(f"RTKLIB .pos row {line_number} violates TOW/ENU bounds")
        rows.append({
            "gps_week": week,
            "gps_tow_seconds": tow,
            "baseline_enu_m": [east, north, up],
            "baseline_ned_m": [north, east, -up],
            "quality": quality,
            "satellite_count": satellites,
            "age_s": age_s,
            "ratio": ratio,
            "standard_deviations_enu_m": values[7:10],
            "covariances_en_nu_ue_m2": values[10:13],
        })
    return rows


def _rtklib_native_comparison(
    parsed: Sequence[Mapping[str, Any]], native_rows: Sequence[Mapping[str, str]]
) -> dict[str, Any]:
    """Value-blind unique-nearest time association, then diagnostic comparison."""
    associations = _associate_rtklib_native_times(parsed, native_rows)
    vector_differences: list[float] = []
    direction_angles: list[float] = []
    norm_differences: list[float] = []
    quality_overlap = {"FIXED_FIXED": 0, "FLOAT_FLOAT": 0, "FIXED_FLOAT": 0, "FLOAT_FIXED": 0}
    matched_ratios: list[dict[str, Any]] = []
    matched_associations = [row for row in associations if row["association_status"] == "ASSOCIATED_UNIQUE_NEAREST_SAME_WEEK"]
    for association in matched_associations:
        stock = parsed[int(association["stock_index"])]
        native = native_rows[int(association["native_index"])]
        if not native.get("baseline_ned_m"):
            continue
        native_baseline = np.asarray(json.loads(native["baseline_ned_m"]), dtype=float)
        stock_baseline = np.asarray(stock["baseline_ned_m"], dtype=float)
        if native_baseline.shape != (3,) or not np.all(np.isfinite(native_baseline)):
            raise Phase3RunnerError("malformed native NED baseline in RTKLIB comparison")
        vector_differences.append(float(np.linalg.norm(stock_baseline-native_baseline)))
        stock_norm, native_norm = float(np.linalg.norm(stock_baseline)), float(np.linalg.norm(native_baseline))
        norm_differences.append(stock_norm-native_norm)
        if stock_norm > 0 and native_norm > 0:
            direction_angles.append(math.degrees(math.acos(float(np.clip(np.dot(stock_baseline,native_baseline)/(stock_norm*native_norm),-1,1)))))
        stock_state = "FIXED" if int(stock["quality"]) == 1 else "FLOAT"
        native_state = "FIXED" if native.get("paper_ratio_fixed") == "true" else "FLOAT"
        quality_overlap[f"{stock_state}_{native_state}"] += 1
        matched_ratios.append({"gps_week": association["gps_week"], "stock_gps_tow_seconds": association["stock_gps_tow_seconds"], "native_rawx_gps_tow_seconds": association["native_rawx_gps_tow_seconds"], "stock_minus_rawx_seconds": association["stock_minus_rawx_seconds"], "rtklib_ratio": stock["ratio"], "native_ratio": None if native.get("ratio") in (None, "") else float(native["ratio"])})
    def simple_stats(values: Sequence[float]) -> dict[str, Any]:
        return {"count": len(values), "mean": float(np.mean(values)) if values else None, "median": float(np.median(values)) if values else None, "max": float(np.max(values)) if values else None}
    return {
        "time_association_policy": "SAME_WEEK_UNIQUE_NEAREST_STRICT_MONOTONIC_ONE_TO_ONE_REJECT_TIE_OR_DISTANCE_GE_HALF_LOCAL_NATIVE_CADENCE_VALUE_BLIND",
        "time_associated_count": len(matched_associations),
        "time_associations": associations,
        "matched_finite_baseline_count": len(vector_differences),
        "baseline_vector_difference_m": simple_stats(vector_differences),
        "baseline_direction_angle_difference_deg": simple_stats(direction_angles),
        "baseline_norm_rtklib_minus_native_m": simple_stats(norm_differences),
        "fixed_float_overlap": quality_overlap,
        "rtklib_unassociated_week_tow": [[row["gps_week"], row["stock_gps_tow_seconds"], row["association_status"]] for row in associations if row["association_status"] != "ASSOCIATED_UNIQUE_NEAREST_SAME_WEEK"],
        "native_unassociated_week_tow": [[int(row["gps_week"]), float(row["gps_tow_seconds"])] for index,row in enumerate(native_rows) if index not in {int(item["native_index"]) for item in matched_associations}],
        "ratio_by_time_association": matched_ratios,
        "pivot_semantics_caveat": "stock RTKLIB pivot selection differs; diagnostic only",
    }


def _associate_rtklib_native_times(
    parsed: Sequence[Mapping[str, Any]], native_rows: Sequence[Mapping[str, str]]
) -> list[dict[str, Any]]:
    """Associate timestamps without consulting solution values or accuracy."""
    native_by_week: dict[int, list[tuple[float, int]]] = {}
    for index, row in enumerate(native_rows):
        week, tow = int(row["gps_week"]), float(row["gps_tow_seconds"])
        native_by_week.setdefault(week, []).append((tow,index))
    for week, values in native_by_week.items():
        values.sort()
        if len({tow for tow,_index in values}) != len(values):
            raise Phase3RunnerError(f"duplicate native RAWX TOW in GPS week {week}")
    used: set[int] = set()
    last_native_index_by_week: dict[int,int] = {}
    output: list[dict[str, Any]] = []
    previous_stock: tuple[int,float] | None = None
    for stock_index, stock in enumerate(parsed):
        week, stock_tow = int(stock["gps_week"]), float(stock["gps_tow_seconds"])
        if previous_stock is not None and (week,stock_tow) <= previous_stock:
            raise Phase3RunnerError("RTKLIB stock rows are not strict chronological week/TOW")
        previous_stock = (week,stock_tow)
        candidates = native_by_week.get(week, [])
        base = {"stock_index":stock_index, "gps_week":week, "stock_gps_tow_seconds":stock_tow, "association_policy":"SAME_WEEK_UNIQUE_NEAREST_STRICT_MONOTONIC_ONE_TO_ONE_REJECT_TIE_OR_DISTANCE_GE_HALF_LOCAL_NATIVE_CADENCE_VALUE_BLIND"}
        if not candidates:
            output.append({**base,"association_status":"REJECTED_NO_NATIVE_IN_SAME_WEEK","native_index":None,"native_rawx_gps_tow_seconds":None,"stock_minus_rawx_seconds":None,"local_native_cadence_seconds":None})
            continue
        distances = [abs(stock_tow-tow) for tow,_index in candidates]
        minimum = min(distances)
        nearest_positions = [position for position,value in enumerate(distances) if math.isclose(value,minimum,rel_tol=0.0,abs_tol=1e-12)]
        if len(nearest_positions) != 1:
            output.append({**base,"association_status":"REJECTED_MIDPOINT_TIE","native_index":None,"native_rawx_gps_tow_seconds":None,"stock_minus_rawx_seconds":None,"local_native_cadence_seconds":None})
            continue
        position = nearest_positions[0]; native_tow,native_index = candidates[position]
        neighbor_cadences = []
        if position > 0: neighbor_cadences.append(native_tow-candidates[position-1][0])
        if position+1 < len(candidates): neighbor_cadences.append(candidates[position+1][0]-native_tow)
        local_cadence = min(neighbor_cadences) if neighbor_cadences else math.nan
        if not neighbor_cadences or not math.isfinite(local_cadence) or local_cadence <= 0 or minimum >= 0.5*local_cadence-1e-12:
            output.append({**base,"association_status":"REJECTED_DISTANCE_GE_HALF_LOCAL_CADENCE","native_index":None,"native_rawx_gps_tow_seconds":native_tow,"stock_minus_rawx_seconds":stock_tow-native_tow,"local_native_cadence_seconds":None if not math.isfinite(local_cadence) else local_cadence})
            continue
        if native_index in used:
            status = "REJECTED_NATIVE_REUSE"
        elif native_index <= last_native_index_by_week.get(week,-1):
            status = "REJECTED_NON_MONOTONIC_NATIVE_ASSOCIATION"
        else:
            status = "ASSOCIATED_UNIQUE_NEAREST_SAME_WEEK"
            used.add(native_index); last_native_index_by_week[week]=native_index
        output.append({**base,"association_status":status,"native_index":native_index if status.startswith("ASSOCIATED") else None,"native_rawx_gps_tow_seconds":native_tow,"stock_minus_rawx_seconds":stock_tow-native_tow,"local_native_cadence_seconds":local_cadence})
    return output


def _post_native_rtklib_time_recovery(
    preflight: PreflightResult,
    freeze: Mapping[str, Any],
    prior_inventory: Mapping[str, Any],
    final: Path,
    attempt: Path,
    report_path: Path,
    status_path: Path,
) -> dict[str, Any]:
    """Narrow recovery using only frozen native and primary-post artifacts."""
    primary = preflight.paths.native_root/"POST_NATIVE"
    position_path = primary/"RTKLIB_UNMODIFIED_MOVING_BASE.pos"
    diagnostic_path = primary/"EXT03_C00_RTKLIB_DIAGNOSTIC.json"
    if not position_path.is_file() or not diagnostic_path.is_file():
        raise Phase3RunnerError("primary POST_NATIVE lacks frozen RTKLIB diagnostic inputs")
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    mode = diagnostic.get("system_mode")
    headings = _read_csv(preflight.paths.native_files["heading_results"])
    native_primary = [row for row in headings if row["system_mode"]==mode and row["constraint_mode"]=="CONSTRAINED" and row.get("baseline_sigma_m") in {"0.01","0.010"}]
    parsed = _parse_rtklib_enu_pos(position_path.read_text(encoding="utf-8",errors="strict"))
    comparison = _rtklib_native_comparison(parsed,native_primary)
    associated = [row for row in comparison["time_associations"] if row["association_status"]=="ASSOCIATED_UNIQUE_NEAREST_SAME_WEEK"]
    offsets = [float(row["stock_minus_rawx_seconds"]) for row in associated]
    associated_invalid = sum(not native_primary[int(row["native_index"])].get("baseline_ned_m") for row in associated)
    comparison["fixed_float_overlap_key_orientation"]="RTKLIB_STOCK_STATE__NATIVE_EXT03_STATE"
    comparison["associated_native_invalid_count"]=associated_invalid
    expected_overlap={"FLOAT_FLOAT":344,"FIXED_FLOAT":159,"FLOAT_FIXED":89,"FIXED_FIXED":16}
    if len(parsed)!=660 or len(associated)!=660 or comparison["matched_finite_baseline_count"]!=608 or associated_invalid!=52:
        raise Phase3RunnerError("RTKLIB time recovery BY2 row-count invariant failed")
    if not offsets or any(not math.isclose(value,0.002,rel_tol=0.0,abs_tol=1e-9) for value in offsets):
        raise Phase3RunnerError("RTKLIB time recovery did not confirm deterministic +0.002 s offset")
    if comparison["fixed_float_overlap"]!=expected_overlap:
        raise Phase3RunnerError("RTKLIB/native fixed-float overlap invariant failed")
    frozen_trace_path=primary/"EXT03_C00_TRACE_DIAGNOSTICS.csv"
    frozen_proxy_path=primary/"EXT03_C00_PROXY_DIAGNOSTICS.csv"
    frozen_mode_path=preflight.paths.native_files["mode_summary"]
    if not frozen_trace_path.is_file() or not frozen_proxy_path.is_file() or not frozen_mode_path.is_file():
        raise Phase3RunnerError("frozen mode/proxy/trace applicability evidence is incomplete")
    trace_summary_rows=_build_trace_summary_rows(_read_csv(frozen_trace_path))
    primary_key=(mode,"CONSTRAINED","0.01")
    def primary_row(row: Mapping[str,Any]) -> bool:
        return (row.get("system_mode"),row.get("constraint_mode"),row.get("baseline_sigma_m"))==primary_key
    all_valid=next((row for row in trace_summary_rows if primary_row(row) and row.get("solution_state")=="ALL_VALID"),None)
    fixed_trace=next((row for row in trace_summary_rows if primary_row(row) and row.get("solution_state")=="paper_ratio_fixed"),None)
    if all_valid is None or fixed_trace is None:
        raise Phase3RunnerError("recovery trace summary lacks primary ALL_VALID/fixed rows")
    native_valid=sum(row.get("solution_state")!="invalid" for row in native_primary)
    native_fixed=sum(_strict_csv_bool(row.get("paper_ratio_fixed"),field="paper_ratio_fixed") for row in native_primary)
    native_invalid=sum(row.get("solution_state")=="invalid" for row in native_primary)
    proxy_primary=[row for row in _read_csv(frozen_proxy_path) if primary_row(row)]
    proxy_fixed=[row for row in proxy_primary if _strict_csv_bool(row.get("paper_ratio_fixed"),field="paper_ratio_fixed")]
    proxy_inconsistent=sum(_strict_csv_bool(row.get("proxy_inconsistent_ratio_fixed"),field="proxy_inconsistent_ratio_fixed") for row in proxy_fixed)
    def close(actual: Any, expected: float, tolerance: float) -> bool:
        return actual is not None and math.isclose(float(actual),expected,rel_tol=0.0,abs_tol=tolerance)
    gates={
        "native_row_count":len(native_primary)==1509,"native_valid_count":native_valid==609,"native_fixed_count":native_fixed==105,"native_invalid_count":native_invalid==900,
        "proxy_fixed_count":len(proxy_fixed)==105,"proxy_inconsistent_fixed_count":proxy_inconsistent==101,
        "fixed_window_input_count":all_valid.get("fixed_window_input_count")==1370,"valid_matched_count":all_valid.get("valid_matched_count")==541,
        "valid_coverage":close(all_valid.get("valid_coverage"),0.3948905109,5e-11),"fixed_matched_count":all_valid.get("paper_ratio_fixed_matched_count")==105,
        "fixed_rate_of_window":close(all_valid.get("paper_ratio_fixed_rate_of_window"),0.0766423358,5e-11),"valid_rmse_deg":close(all_valid.get("rmse"),84.3438,5e-4),"valid_max_gap_seconds":close(all_valid.get("valid_maximum_gap_seconds"),38.4,1e-9),
        "fixed_trace_count":fixed_trace.get("count")==105,"fixed_trace_rmse_deg":close(fixed_trace.get("rmse"),40.6308,5e-4),"fixed_trace_max_abs_deg":close(fixed_trace.get("max_absolute"),158.788,5e-4),"fixed_trace_max_gap_seconds":close(fixed_trace.get("maximum_gap_seconds"),129.8,1e-9),
    }
    if not all(gates.values()):
        raise Phase3RunnerError(f"frozen PASS_POOR applicability evidence gate failed: {[key for key,value in gates.items() if not value]}")
    poor_evidence={"terminal_status":PASS_POOR,"decision_rule":"FROZEN_PROXY_INCONSISTENCY_AT_PREREGISTERED_30_DEG_AND_FROZEN_TRACE_ERROR_ESTABLISH_POOR_APPLICABILITY_NO_NATIVE_SELECTION","gates":gates,"native":{"row_count":len(native_primary),"valid_count":native_valid,"paper_ratio_fixed_count":native_fixed,"invalid_count":native_invalid},"proxy":{"paper_ratio_fixed_count":len(proxy_fixed),"proxy_inconsistent_ratio_fixed_count":proxy_inconsistent},"trace":{"ALL_VALID":all_valid,"PAPER_RATIO_FIXED":fixed_trace}}
    attempt.mkdir()
    source_links={
        "native_freeze_sha256":_sha256(preflight.paths.native_files["native_freeze"]),
        "primary_post_freeze_sha256":_sha256(primary/"EXT03_C00_POST_NATIVE_FREEZE.json"),
        "primary_rtklib_position_sha256":_sha256(position_path),
        "primary_rtklib_diagnostic_sha256":_sha256(diagnostic_path),
        "native_heading_sha256":_sha256(preflight.paths.native_files["heading_results"]),
        "native_mode_summary_sha256":_sha256(frozen_mode_path),
        "primary_proxy_diagnostics_sha256":_sha256(frozen_proxy_path),
        "primary_trace_diagnostics_sha256":_sha256(frozen_trace_path),
    }
    payload={"schema_version":"horizontal_literature.phase3.rtklib_time_association_recovery.v1","terminal_status":PASS_POOR,"supersedes_for_rtklib_time_association_only":True,"association_uses_solution_values_or_accuracy":False,"source_links":source_links,"prior_primary_post_and_report_status_inventory":prior_inventory,"comparison":comparison,"frozen_poor_applicability_evidence":poor_evidence}
    phase2._atomic_write_json(attempt/"EXT03_C00_RTKLIB_TIME_ASSOCIATION_R1.json",payload)
    _write_csv(attempt/"EXT03_C00_TRACE_SUMMARY_R1.csv",trace_summary_rows)
    summary={"schema_version":"horizontal_literature.phase3.post_native.v1","terminal_status":PASS_POOR,"scientific_terminal_basis":"FROZEN_NATIVE_AND_PRIMARY_POST_APPLICABILITY_EVIDENCE_NO_NATIVE_SELECTION","supersedes_for_rtklib_time_association_only":True,"native_files_mutated":False,"primary_post_files_mutated":False,"source_links":source_links,"prior_primary_post_and_report_status_inventory":prior_inventory,"RTKLIB_time_association":comparison,"frozen_poor_applicability_evidence":poor_evidence,"recovery_trace_summary":"EXT03_C00_TRACE_SUMMARY_R1.csv"}
    phase2._atomic_write_json(attempt/"EXT03_C00_POST_NATIVE_SUMMARY.json",summary)
    inventory={path.name:_sha256(path) for path in attempt.iterdir() if path.is_file()}
    phase2._atomic_write_json(attempt/"EXT03_C00_POST_NATIVE_FREEZE.json",{"schema_version":"horizontal_literature.phase3.post_native_freeze.v1","files":inventory,"native_freeze_sha256":source_links["native_freeze_sha256"],"supersedes_for_rtklib_time_association_only":True,"prior_primary_post_and_report_status_inventory":prior_inventory})
    _validate_post_native_freeze(attempt)
    phase2._atomic_install_noreplace(attempt,final,label="Phase-3 RTKLIB time-association recovery",kind="directory")
    _validate_post_native_freeze(final)
    report_text=f"""# Phase 3 EXT03 C00 RTKLIB time-association recovery R1

Terminal status: `{PASS_POOR}`

This recovery supersedes the frozen primary post-native output only for the
RTKLIB-to-native timestamp association. It used the frozen RTKLIB `.pos` and
native heading table, selected no native mode or row by solution value, and
left native plus primary `POST_NATIVE` evidence byte-identical.

Associated RTKLIB rows: `{len(associated)}`; finite native comparisons: `{comparison['matched_finite_baseline_count']}`;
associated native-invalid rows: `{associated_invalid}`. Overlap keys are
`RTKLIB_STOCK_STATE__NATIVE_EXT03_STATE`.

The frozen primary mode has `609/1509` valid rows, `105` ratio-fixed rows,
and `900` invalid rows. The frozen proxy marks `101/105` ratio-fixed rows
inconsistent at the preregistered 30-degree threshold. Frozen trace ALL_VALID
coverage is `541/1370`; its RMSE is `84.3438 deg`. The ratio-fixed trace RMSE
is `40.6308 deg`. These hash-linked facts establish `{PASS_POOR}` without
changing or selecting any native output.
"""
    phase2._atomic_write_bytes(report_path,report_text.encode())
    phase2._atomic_write_json(status_path,{"schema_version":"horizontal_literature.phase3.status.v1","terminal_status":PASS_POOR,"method_id":METHOD_ID,"case_id":CASE_ID,"native_freeze_sha256":source_links["native_freeze_sha256"],"post_native_root":str(final),"independent_review":"PENDING","git_commit_created":False,"supersedes_for_rtklib_time_association_only":True,"prior_primary_post_and_report_status_inventory":prior_inventory})
    after=_primary_post_recovery_inventory(preflight,expected_file_count=12)
    if after!=prior_inventory:
        raise Phase3RunnerError("primary POST_NATIVE or Phase3 report/status changed during recovery")
    validate_native_freeze(preflight.paths.native_root)
    return {"terminal_status":PASS_POOR,"post_native_root":str(final),"post_native_summary":summary}


def _post_native_diagnostics(preflight: PreflightResult, recovery_id: str | None) -> dict[str, Any]:
    freeze = validate_native_freeze(preflight.paths.native_root)
    recovery_prior_inventory: dict[str, Any] | None = None
    if recovery_id is not None:
        if recovery_id != "RTKLIB_TIME_ASSOCIATION_R1":
            raise Phase3RunnerError("unsupported post-native recovery identity")
        recovery_prior_inventory = _primary_post_recovery_inventory(preflight, expected_file_count=12)
    slug = "POST_NATIVE" if recovery_id is None else f"POST_NATIVE_RECOVERY_{recovery_id}"
    if not all(ch.isalnum() or ch in "_-" for ch in slug) or len(slug) > 96:
        raise Phase3RunnerError("invalid post-native recovery id")
    final = preflight.paths.native_root / slug
    report_path = preflight.paths.final_report if recovery_id is None else preflight.paths.report_root / f"PHASE3_EXT03_C00_REPORT_{recovery_id}.md"
    status_path = preflight.paths.final_status if recovery_id is None else preflight.paths.report_root / f"PHASE3_STATUS_{recovery_id}.json"
    if recovery_id is not None and (report_path.exists() or status_path.exists()):
        raise Phase3RunnerError("post-native recovery report/status collision")
    if final.exists():
        raise Phase3RunnerError("post-native child already exists")
    attempt = preflight.paths.native_root / f".attempt_{slug}"
    if attempt.exists():
        raise Phase3RunnerError("post-native attempt already exists")
    if recovery_id == "RTKLIB_TIME_ASSOCIATION_R1":
        assert recovery_prior_inventory is not None
        return _post_native_rtklib_time_recovery(preflight,freeze,recovery_prior_inventory,final,attempt,report_path,status_path)
    attempt.mkdir()
    # Exactly two semantic receiver-stream decodes, strictly after freeze.
    recon1 = reconstruct_ubx_stream(preflight.paths.gnss1_raw, attempt / "gnss1_post.ubx", decode_nav_hpposecef_semantics=True)
    recon2 = reconstruct_ubx_stream(preflight.paths.gnss2_raw, attempt / "gnss2_post.ubx", decode_nav_hpposecef_semantics=True)
    hp1 = {epoch.itow_ms: epoch for epoch in recon1.nav_hpposecef_epochs}
    hp2 = {epoch.itow_ms: epoch for epoch in recon2.nav_hpposecef_epochs}
    if len(hp1) != len(recon1.nav_hpposecef_epochs) or len(hp2) != len(recon2.nav_hpposecef_epochs):
        raise Phase3RunnerError("duplicate HPPOSECEF iTOW in post-native diagnostic")
    headings = _read_csv(preflight.paths.native_files["heading_results"])
    unique_raw_itows = sorted({int(round(float(row["gps_tow_seconds"])*1000.0)) % 604800000 for row in headings})
    associations = phase2._proxy_common_grid_associations(unique_raw_itows, list(hp1), list(hp2))
    association_by_raw = {int(row["rawx_itow_ms"]): row for row in associations}
    observed_offsets = {row.get("proxy_itow_minus_rawx_ms") for row in associations if row.get("proxy_association_status") == "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"}
    if observed_offsets != {2}:
        raise Phase3RunnerError(f"audited HPPOSECEF matcher did not confirm fixed +2 ms: {observed_offsets}")
    proxy_rows: list[dict[str, Any]] = []
    for row in headings:
        raw_itow = int(round(float(row["gps_tow_seconds"]) * 1000.0)) % 604800000
        association = association_by_raw[raw_itow]
        proxy_itow = association.get("proxy_itow_ms")
        base = dict(row)
        base.update({**association, "proxy_association_policy": "AUDITED_UNIQUE_NEAREST_COMMON_GRID_CONFIRMED_PLUS_2MS", "proxy_role": "SAME_SOURCE_DESCRIPTIVE_NOT_INDEPENDENT_TRUTH"})
        if association.get("proxy_association_status") != "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW" or proxy_itow not in hp1 or proxy_itow not in hp2 or not row.get("baseline_ned_m"):
            proxy_rows.append({**base, "proxy_association_status": "UNAVAILABLE", "vector_angle_difference_deg": None, "body_yaw_error_deg": None, "baseline_length_error_m": None, "proxy_inconsistent_ratio_fixed": False})
            continue
        p1, p2 = hp1[proxy_itow].position_ecef_m, hp2[proxy_itow].position_ecef_m
        proxy = _ecef_vector_to_ned(p2-p1, p1)
        native = np.asarray(json.loads(row["baseline_ned_m"]), dtype=float)
        norm_product = float(np.linalg.norm(proxy)*np.linalg.norm(native))
        angle = None if norm_product == 0 else math.degrees(math.acos(float(np.clip(np.dot(proxy, native)/norm_product, -1.0, 1.0))))
        proxy_heading = math.degrees(math.atan2(proxy[1], proxy[0])) % 360.0
        error = _wrap180(float(row["body_yaw_deg"]) - ((proxy_heading+90.0)%360.0)) if row.get("body_yaw_deg") else None
        proxy_rows.append({**base, "proxy_association_status": "ASSOCIATED_FIXED_PLUS_2MS", "proxy_baseline_ned_m": proxy.tolist(), "proxy_length_m": float(np.linalg.norm(proxy)), "vector_angle_difference_deg": angle, "body_yaw_error_deg": error, "baseline_length_error_m": float(np.linalg.norm(native)-np.linalg.norm(proxy)), "proxy_inconsistent_ratio_fixed": bool(row.get("paper_ratio_fixed") == "true" and angle is not None and angle > 30.0), "proxy_inconsistent_threshold_deg": 30.0})
    _write_csv(attempt / "EXT03_C00_PROXY_DIAGNOSTICS.csv", proxy_rows)
    frozen_source_fingerprint = str(freeze.get("source_fingerprint", ""))
    if len(frozen_source_fingerprint) < 12:
        raise Phase3RunnerError("native freeze lacks source fingerprint for post-native cache recovery")
    native_attempt = preflight.paths.native_root.parent / f".attempt_EXT03_{frozen_source_fingerprint[:12]}"
    leap_seconds, leap_evidence = phase2._validated_compact_cache_leap_seconds(native_attempt / "COMPACT_CACHE")
    if leap_evidence.get("receiver_epoch_field_count_verified") != 3018 or leap_seconds != 18:
        raise Phase3RunnerError("post-native trace gate lacks 3018 RAWX leap-second fields equal to 18")
    trace_payload, trace_hash = phase2._locked_trace_bytes(preflight.paths)
    trace_input = [{**row, "method_native_accepted": "true" if row.get("solution_state") in {"float", "paper_ratio_fixed"} and row.get("body_yaw_deg") else "false"} for row in headings]
    trace_rows = phase2._trace_reference(trace_payload, trace_input, leap_seconds=leap_seconds)
    # Restore variant identity removed by the shared evaluator's narrow return.
    for source, target in zip(trace_input, trace_rows, strict=True):
        target.update({key: source.get(key) for key in ("method_id", "case_id", "system_mode", "constraint_mode", "baseline_sigma_m", "solution_state", "paper_ratio_fixed", "ambiguity_correctness_known")})
    _write_csv(attempt / "EXT03_C00_TRACE_DIAGNOSTICS.csv", trace_rows)
    def stats(values: Iterable[Any]) -> dict[str, Any]:
        array = np.asarray([float(value) for value in values if value is not None and str(value) not in {"", "nan"}], dtype=float)
        array = array[np.isfinite(array)]
        if not array.size:
            return {"count": 0}
        absolute = np.abs(array)
        return {"count": int(array.size), "bias": float(np.mean(array)), "rmse": float(np.sqrt(np.mean(array**2))), "mae": float(np.mean(absolute)), "median_absolute": float(np.median(absolute)), "p90_absolute": float(np.percentile(absolute,90)), "p95_absolute": float(np.percentile(absolute,95)), "p99_absolute": float(np.percentile(absolute,99)), "max_absolute": float(np.max(absolute))}
    def relationship(rows: Sequence[Mapping[str, Any]], left: str, right: str) -> dict[str, Any]:
        pairs = [(float(row[left]), float(row[right])) for row in rows if row.get(left) not in (None, "") and row.get(right) not in (None, "")]
        return {"count": len(pairs), "pearson": float(np.corrcoef(np.asarray(pairs).T)[0,1]) if len(pairs) >= 2 and np.std(np.asarray(pairs)[:,0]) > 0 and np.std(np.asarray(pairs)[:,1]) > 0 else None}
    proxy_summary_rows, trace_summary_rows = [], []
    group_keys = sorted({(row["system_mode"], row["constraint_mode"], row.get("baseline_sigma_m"), row["solution_state"]) for row in proxy_rows})
    for key in group_keys:
        subset = [row for row in proxy_rows if (row["system_mode"], row["constraint_mode"], row.get("baseline_sigma_m"), row["solution_state"]) == key]
        associated = [row for row in subset if row.get("proxy_association_status") == "ASSOCIATED_FIXED_PLUS_2MS"]
        proxy_summary_rows.append({"method_id": METHOD_ID, "case_id": CASE_ID, "system_mode": key[0], "constraint_mode": key[1], "baseline_sigma_m": key[2], "solution_state": key[3], "paper_ratio_fixed": key[3] == "paper_ratio_fixed", "ambiguity_correctness_known": False, "row_count": len(subset), "associated_count": len(associated), "coverage": len(associated)/len(subset) if subset else None, "vector_angle": stats(row.get("vector_angle_difference_deg") for row in associated), "body_yaw_error": stats(row.get("body_yaw_error_deg") for row in associated), "baseline_length_error": stats(row.get("baseline_length_error_m") for row in associated), "ratio_vs_proxy_angle": relationship(associated, "ratio", "vector_angle_difference_deg"), "constraint_innovation_vs_proxy_angle": relationship(associated, "constraint_innovation_m", "vector_angle_difference_deg"), "proxy_inconsistent_ratio_fixed_count": sum(bool(row.get("proxy_inconsistent_ratio_fixed")) for row in associated)})
    _write_csv(attempt / "EXT03_C00_PROXY_SUMMARY.csv", proxy_summary_rows)
    trace_summary_rows = _build_trace_summary_rows(trace_rows)
    _write_csv(attempt / "EXT03_C00_TRACE_SUMMARY.csv", trace_summary_rows)
    phase2_recovery = preflight.paths.stage_root / "03_EXT02_CWLS/C00/POST_NATIVE_RECOVERY_PROXY_TIME_ASSOCIATION_R1"
    phase2_fractional = phase2_recovery / "EXT02_C00_FRACTIONAL_DD_DIAGNOSTICS.csv"
    phase2_post_manifest = phase2_recovery / "EXT02_C00_POST_NATIVE_DIAGNOSTICS_MANIFEST.json"
    strata: list[dict[str, Any]] = []
    if phase2_fractional.is_file():
        fractional_rows = _read_csv(phase2_fractional)
        by_group: dict[str, dict[str, Any]] = {}
        for row in fractional_rows:
            if not row.get("epoch_index", "").isdigit(): continue
            index = int(row["epoch_index"])
            identity_pairs = json.loads(row.get("identity_fractional_pairs") or "[]")
            for identity_row in identity_pairs:
                group_fields = {name: identity_row.get(name) for name in ("pivot_identity", "satellite_identity", "r1_subHalfCyc", "r2_subHalfCyc")}
                group = _canonical(group_fields)
                entry = by_group.setdefault(group, {"group_fields": group_fields, "epochs": set(), "fractional": []})
                entry["epochs"].add(index); entry["fractional"].append(float(identity_row["production_fractional_cycles"]))
            categorical = {
                "sub_half_cycle_combination": row.get("sub_half_cycle_combination"),
                "lock_reset_present": row.get("lock_reset_present"),
                "cycle_slip_present": row.get("cycle_slip_present"),
                "pivot_changed": row.get("pivot_changed"),
                "low_dd_dimension": row.get("low_dd_dimension"),
            }
            group = _canonical(categorical)
            entry = by_group.setdefault(group, {"group_fields": categorical, "epochs": set(), "fractional": []})
            entry["epochs"].add(index)
            if row.get("fractional_dd_cycles"):
                entry["fractional"].extend(float(value) for value in json.loads(row["fractional_dd_cycles"]))
        variant_keys = sorted({(row["system_mode"], row["constraint_mode"], row.get("baseline_sigma_m")) for row in headings})
        for group, entry in sorted(by_group.items()):
            for variant_key in variant_keys:
                selected = [row for row in headings if (row["system_mode"],row["constraint_mode"],row.get("baseline_sigma_m")) == variant_key and int(row["epoch_index"]) in entry["epochs"]]
                ratios = [float(row["ratio"]) for row in selected if row.get("ratio")]
                strata.append({"group_key": group, "group_fields": entry["group_fields"], "system_mode": variant_key[0], "constraint_mode": variant_key[1], "baseline_sigma_m": variant_key[2], "epoch_count": len(entry["epochs"]), "fractional_observation_count": len(entry["fractional"]), "fractional_rms_cycles": float(np.sqrt(np.mean(np.square(entry["fractional"])))) if entry["fractional"] else None, "ratio_count": len(ratios), "ratio_mean": float(np.mean(ratios)) if ratios else None, "paper_ratio_fixed_rate": sum(row.get("paper_ratio_fixed") == "true" for row in selected)/len(selected) if selected else None, "calibration_applied": False})
    phase_bias = {"calibration_applied": False, "subtraction_applied": False, "source_role": "FROZEN_PHASE2_RECOVERY_POST_NATIVE_RELATIONSHIP_ONLY", "source_recovery_id": "PROXY_TIME_ASSOCIATION_R1", "source_relative_path": "03_EXT02_CWLS/C00/POST_NATIVE_RECOVERY_PROXY_TIME_ASSOCIATION_R1/EXT02_C00_FRACTIONAL_DD_DIAGNOSTICS.csv", "source_available": phase2_fractional.is_file(), "source_sha256": _sha256(phase2_fractional) if phase2_fractional.is_file() else None, "source_post_manifest_sha256": _sha256(phase2_post_manifest) if phase2_post_manifest.is_file() else None, "source_schema_fields": list(phase2.FRACTIONAL_FIELDS), "identity_group_keys": ["pivot_identity", "satellite_identity", "r1_subHalfCyc", "r2_subHalfCyc"], "categorical_strata_fields": ["sub_half_cycle_combination", "lock_reset_present", "cycle_slip_present", "pivot_changed", "low_dd_dimension"], "ratio_fix_strata": strata}
    phase2._atomic_write_json(attempt / "EXT03_C00_PHASE_BIAS_RELATIONSHIP.json", phase_bias)
    native_summary = json.loads(preflight.paths.native_files["native_summary"].read_text(encoding="utf-8"))
    supported_modes = native_summary.get("supported_modes", [])
    diagnostic_mode = next((name for name in ("GPS_BDS_DUAL_FREQUENCY", "GPS_DUAL_FREQUENCY", "BDS_DUAL_FREQUENCY") if name in supported_modes), None)
    rtklib_diag: dict[str, Any] = {"role": "POST_NATIVE_DIAGNOSTIC_ONLY", "output_solver_input": False, "system_mode": diagnostic_mode, "status": "UNAVAILABLE_NO_SUPPORTED_MODE"}
    source_attempt = native_attempt / "SOURCE_BACKEND"
    rnx2rtkp = preflight.paths.rtklib_root / "app/consapp/rnx2rtkp/gcc/rnx2rtkp"
    expected_rnx2rtkp_hash = preflight.provider_hashes.get("unmodified_rnx2rtkp_sha256")
    if not rnx2rtkp.is_file() or _sha256(rnx2rtkp) != expected_rnx2rtkp_hash:
        raise Phase3RunnerError("unmodified rnx2rtkp hash changed after preflight")
    if diagnostic_mode is not None and rnx2rtkp.is_file() and all((source_attempt/name).is_file() for name in ("gnss1.obs", "gnss2.obs", "gnss1.nav", "gnss2.nav")):
        navsys = {"GPS_DUAL_FREQUENCY": 1, "BDS_DUAL_FREQUENCY": 32, "GPS_BDS_DUAL_FREQUENCY": 33}[diagnostic_mode]
        config_text = f"""pos1-posmode       =movingbase
pos1-frequency     =l1+l2
pos1-soltype       =forward
pos1-elmask        =15
pos1-snrmask       =0
pos1-dynamics      =off
pos1-tidecorr      =off
pos1-ionoopt       =off
pos1-tropopt       =saas
pos1-sateph        =brdc
pos1-exclsats      =
pos1-navsys        ={navsys}
pos2-armode        =continuous
pos2-gloarmode     =off
pos2-bdsarmode     =on
pos2-arthres       =3
pos2-arlockcnt     =0
pos2-arelmask      =0
pos2-aroutcnt      =5
pos2-arminfix      =10
pos2-armaxiter     =1
pos2-slipthres     =0.05
pos2-maxage        =30
pos2-rejionno      =30
pos2-niter         =1
pos2-baselen       =0.350
pos2-basesig       =0.010
out-solformat      =enu
out-outhead        =on
out-outopt         =on
out-timesys        =gpst
out-timeform       =tow
out-timendec       =3
out-fieldsep       =,
out-solstatic      =all
out-outstat        =off
stats-eratio1      =100
stats-eratio2      =100
stats-errphase     =0.003
stats-errphaseel   =0.003
stats-errphasebl   =0
stats-errdoppler   =1
stats-stdbias      =30
stats-stdiono      =0.03
stats-stdtrop      =0.3
stats-prnaccelh    =0.1
stats-prnaccelv    =0.01
stats-prnbias      =0.0001
stats-prniono      =0.001
stats-prntrop      =0.0001
stats-prnpos       =0
stats-clkstab      =5e-12
ant1-postype       =single
ant2-postype       =single
"""
        config_path = attempt / "RTKLIB_UNMODIFIED_MOVING_BASE.conf"
        output_path = attempt / "RTKLIB_UNMODIFIED_MOVING_BASE.pos"
        phase2._atomic_write_bytes(config_path, config_text.encode())
        command = [str(rnx2rtkp), "-k", str(config_path), "-o", str(output_path), str(source_attempt/"gnss2.obs"), str(source_attempt/"gnss1.obs"), str(source_attempt/"gnss1.nav"), str(source_attempt/"gnss2.nav")]
        completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=1800)
        parsed = _parse_rtklib_enu_pos(output_path.read_text(encoding="utf-8", errors="strict")) if output_path.is_file() else []
        baselines = [row["baseline_ned_m"] for row in parsed]
        qualities = [row["quality"] for row in parsed]
        native_primary = [row for row in headings if row["system_mode"] == diagnostic_mode and row["constraint_mode"] == "CONSTRAINED" and row.get("baseline_sigma_m") in {"0.01", "0.010"}]
        exact_comparison = _rtklib_native_comparison(parsed, native_primary)
        rtklib_diag = {"role": "POST_NATIVE_DIAGNOSTIC_ONLY", "output_solver_input": False, "system_mode": diagnostic_mode, "status": "COMPLETE" if completed.returncode == 0 and output_path.is_file() else "FAILED", "returncode": completed.returncode, "command": command, "rnx2rtkp_sha256_verified": expected_rnx2rtkp_hash, "config_sha256": _sha256(config_path), "output_sha256": _sha256(output_path) if output_path.is_file() else None, "stderr_tail": completed.stderr[-2000:], "parsed_solution_count": len(parsed), "fixed_quality_count": sum(value == 1 for value in qualities), "float_quality_count": sum(value == 2 for value in qualities), "baseline_norm_mean_m": float(np.mean([np.linalg.norm(value) for value in baselines])) if baselines else None, "native_primary_row_count": len(native_primary), "native_primary_ratio_fixed_count": sum(row.get("paper_ratio_fixed") == "true" for row in native_primary), "availability_count_difference_rtklib_minus_native_valid": len(parsed)-sum(row.get("solution_state") != "invalid" for row in native_primary), "time_associated_comparison": exact_comparison, "failure_period_comparison": {"rtklib_unassociated": exact_comparison["rtklib_unassociated_week_tow"], "native_unassociated": exact_comparison["native_unassociated_week_tow"]}}
    phase2._atomic_write_json(attempt / "EXT03_C00_RTKLIB_DIAGNOSTIC.json", rtklib_diag)
    primary_mode = "GPS_BDS_DUAL_FREQUENCY" if "GPS_BDS_DUAL_FREQUENCY" in supported_modes else (supported_modes[0] if supported_modes else None)
    primary = [row for row in proxy_rows if row.get("system_mode") == primary_mode and row.get("constraint_mode") == "CONSTRAINED" and row.get("baseline_sigma_m") in {"0.01", "0.010"}]
    primary_fixed = [row for row in primary if row.get("paper_ratio_fixed") == "true"]
    primary_inconsistent = sum(bool(row.get("proxy_inconsistent_ratio_fixed")) for row in primary_fixed)
    if len(supported_modes) < len(MODE_FREQUENCIES):
        terminal_status = PASS_PARTIAL
    elif not primary_fixed:
        terminal_status = PASS_POOR
    else:
        terminal_status = PASS_READY
    if recovery_id == "RTKLIB_TIME_ASSOCIATION_R1":
        # This recovery repairs only a deterministic diagnostic timestamp
        # association.  The scientific applicability verdict remains the
        # evidence-backed poor result; no native row or mode is reselected.
        terminal_status = PASS_POOR
    summary = {"schema_version": "horizontal_literature.phase3.post_native.v1", "terminal_status": terminal_status, "scientific_terminal_basis": "FROZEN_NATIVE_AND_PRIMARY_POST_APPLICABILITY_EVIDENCE_NO_NATIVE_SELECTION" if recovery_id else "CURRENT_POST_NATIVE_EVIDENCE", "native_freeze_sha256": _sha256(preflight.paths.native_files["native_freeze"]), "native_hashes_revalidated": True, "trace_sha256": trace_hash, "trace_open_count": 1, "trace_leap_second_evidence": leap_evidence, "HPPOSECEF_receiver_stream_decode_count": 2, "proxy_association": "AUDITED_UNIQUE_NEAREST_COMMON_GRID_CONFIRMED_PLUS_2MS", "proxy_inconsistent_threshold_deg": 30.0, "proxy_inconsistent_ratio_fixed_count": sum(bool(row.get("proxy_inconsistent_ratio_fixed")) for row in proxy_rows), "primary_mode": primary_mode, "primary_ratio_fixed_count": len(primary_fixed), "primary_proxy_inconsistent_ratio_fixed_count": primary_inconsistent, "native_files_mutated": False, "RTKLIB_diagnostic": rtklib_diag, "RTKLIB_diagnostic_output_solver_input": False, "phase_bias_calibration": False, "supersedes_for_rtklib_time_association_only": recovery_id == "RTKLIB_TIME_ASSOCIATION_R1", "prior_primary_post_and_report_status_inventory": recovery_prior_inventory}
    phase2._atomic_write_json(attempt / "EXT03_C00_POST_NATIVE_SUMMARY.json", summary)
    inventory = {path.name: _sha256(path) for path in attempt.iterdir() if path.is_file()}
    phase2._atomic_write_json(attempt / "EXT03_C00_POST_NATIVE_FREEZE.json", {"schema_version": "horizontal_literature.phase3.post_native_freeze.v1", "files": inventory, "native_freeze_sha256": summary["native_freeze_sha256"], "supersedes_for_rtklib_time_association_only": recovery_id == "RTKLIB_TIME_ASSOCIATION_R1", "prior_primary_post_and_report_status_inventory": recovery_prior_inventory})
    _validate_post_native_freeze(attempt)
    phase2._atomic_install_noreplace(attempt, final, label="Phase-3 post-native child", kind="directory")
    _validate_post_native_freeze(final)
    validate_native_freeze(preflight.paths.native_root)
    report_text = f"""# Phase 3 EXT03 Yang 2024 C00 report

Terminal status: `{terminal_status}`

The native Yang-2024 GPS/BDS DD Kalman-filter outputs were sealed before any
same-source trace or NAV-HPPOSECEF semantic access. The implementation is
`FAITHFUL_ALGORITHM_REPRODUCTION WITH_DECLARED_UNSPECIFIED_STOCHASTIC_INSTANTIATION`.
The formal publisher PDF was access-closed in this environment; the supplied
formal Eq. (1)-(9) contract was used, and no attributable official source code
or supplement was found in the single focused search.

Native freeze: `{preflight.paths.native_files['native_freeze']}`
Post-native child: `{final}`
Supported modes: `{', '.join(supported_modes)}`
Proxy-inconsistent ratio-fixed rows (>30 deg): `{summary['proxy_inconsistent_ratio_fixed_count']}`
RTKLIB diagnostic status: `{rtklib_diag['status']}`

No phase-bias calibration or subtraction was applied. EXT01/EXT02, EXT04,
Classic-18, common-backbone navigation, and Canonical-541 were not executed by
this Phase-3 runner.

## Identity and equation-to-code map

- Paper: Yang et al., IEEE TIM 73 (2024), article 1003414, DOI 10.1109/TIM.2024.3374423.
- RTKLIB: `{preflight.provider_hashes.get('rtklib_commit')}`, BSD-2-Clause, unmodified provider plus audited bridges.
- Eqs. (1)-(3),(8)-(9): `build_epoch_blocks` and `build_dd_observation`.
- Eq. (4): `ned_attitude`; Eqs. (5)-(7): `baseline_constraint_linearization` and `constraint_update`.
- KF/dynamic state/MLAMBDA: `process_epoch`, `reconcile_ambiguity_state`, and `mlambda_resolve`.

## Native evidence

- Signal inventory: `{preflight.paths.native_files['signal_availability']}`.
- Stochastic registry: `{preflight.paths.native_files['stochastic_registry']}` (all `trace_tuned=false`).
- Mode and sensitivity summaries: `{preflight.paths.native_files['mode_summary']}`, `{preflight.paths.native_files['sensitivity_summary']}`.
- Float/fixed/invalid rows, ratios, ambiguity-state counts, constraint innovation/NIS, native baseline/yaw/pitch, runtime, and worker determinism are recorded in the 15-file native inventory and freeze.
- Primary `{primary_mode}` constrained sigma 0.010 row/fixed/invalid counts: `{len(primary)}/{len(primary_fixed)}/{sum(row.get('solution_state') == 'invalid' for row in primary)}`.
- Parallel strategy: independent variants only; every recursive variant is strict chronological order. The input-only workers 1 versus 16 scientific-field comparison is hashed in the native summary resource evidence.

## Post-native descriptive evidence

- Proxy rows/summary: `{final/'EXT03_C00_PROXY_DIAGNOSTICS.csv'}`, `{final/'EXT03_C00_PROXY_SUMMARY.csv'}`.
- Trace rows/summary: `{final/'EXT03_C00_TRACE_DIAGNOSTICS.csv'}`, `{final/'EXT03_C00_TRACE_SUMMARY.csv'}`.
- Fractional-DD relationship: `{final/'EXT03_C00_PHASE_BIAS_RELATIONSHIP.json'}`; relationship only, no calibration.
- Unmodified RTKLIB diagnostic: `{final/'EXT03_C00_RTKLIB_DIAGNOSTIC.json'}`; diagnostic-only and never solver input.

## Reproduction

`python3 scripts/paper_rebuild/run_horizontal_literature_phase3.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --method-id EXT03_YANG2024 --case-id C00 --trace-mode disabled --workers 16`

Focused implementation tests are maintained in `test_horizontal_ext03_yang2024.py` and `test_horizontal_phase3_c00.py`. Independent reviewer verdict remains `PENDING`; the supervisor/human owns the final review and Git decision. No commit, push, merge, or tag is performed by this runner.
"""
    preflight.paths.report_root.mkdir(parents=True, exist_ok=True)
    phase2._atomic_write_bytes(report_path, report_text.encode())
    phase2._atomic_write_json(status_path, {"schema_version": "horizontal_literature.phase3.status.v1", "terminal_status": terminal_status, "method_id": METHOD_ID, "case_id": CASE_ID, "native_freeze_sha256": summary["native_freeze_sha256"], "post_native_root": str(final), "independent_review": "PENDING", "git_commit_created": False, "supersedes_for_rtklib_time_association_only": recovery_id == "RTKLIB_TIME_ASSOCIATION_R1", "prior_primary_post_and_report_status_inventory": recovery_prior_inventory})
    if recovery_prior_inventory is not None:
        recovery_after = _primary_post_recovery_inventory(preflight, expected_file_count=12)
        if recovery_after != recovery_prior_inventory:
            raise Phase3RunnerError("primary POST_NATIVE or Phase3 report/status changed during recovery")
    return {"terminal_status": terminal_status, "post_native_root": str(final), "post_native_summary": summary}


def run_phase3(config_path: Path, *, mode: str = "preflight", method_id: str = METHOD_ID, case_id: str = CASE_ID, trace_mode: str = "disabled", workers: int = DEFAULT_WORKERS, resume: bool = False, post_recovery_id: str | None = None) -> dict[str, Any]:
    if method_id != METHOD_ID or case_id != CASE_ID or mode not in ALLOWED_MODES or not 1 <= workers <= MAX_WORKERS:
        raise Phase3RunnerError("invalid Phase-3 invocation")
    if mode in {"preflight", "signal-audit", "resource-determinism-probe", "native-only"} and trace_mode != "disabled":
        raise Phase3RunnerError("native lifecycle requires --trace-mode disabled")
    preflight = preflight_phase3(config_path)
    if mode == "preflight":
        return {"terminal_status": "PASS_PHASE3_EXT03_PREFLIGHT_ONLY", "source_fingerprint": preflight.source_fingerprint, "formal_run_launched": False}
    if mode == "post-native-diagnostics":
        return _post_native_diagnostics(preflight, post_recovery_id)
    if mode == "full" and preflight.paths.native_root.exists():
        return _post_native_diagnostics(preflight, post_recovery_id)
    hidden_attempt = preflight.paths.native_root.parent / f".attempt_EXT03_{preflight.source_fingerprint[:12]}"
    identity_path = hidden_attempt / "ATTEMPT_IDENTITY.json"
    if hidden_attempt.exists():
        if not resume:
            raise Phase3RunnerError("fingerprinted attempt exists outside resume mode")
        if not identity_path.is_file() or json.loads(identity_path.read_text(encoding="utf-8")).get("source_fingerprint") != preflight.source_fingerprint:
            raise Phase3RunnerError("resume attempt fingerprint mismatch")
    else:
        hidden_attempt.mkdir(parents=True)
        phase2._atomic_write_json(identity_path, {"schema_version": "horizontal_literature.phase3.attempt.v1", "source_fingerprint": preflight.source_fingerprint})
    try:
        resource_probe = _resource_probe(preflight.paths, workers)
    except ResourceProbeRejected as exc:
        _write_resource_probe_failure_evidence(hidden_attempt, exc)
        raise
    if mode == "resource-determinism-probe":
        cache, navs = _prepare_cache(preflight, hidden_attempt, resume=resume)
        reader = phase2.CompactCacheReader(cache)
        inventory = audit_signal_availability([reader.pair(index) for index in range(len(reader))], RtklibBroadcastProvider(preflight.paths.rtklib_bridge, navs))
        variants = tuple(item for item in requested_variants(preflight.contract) if item.system_mode in set(inventory.supported_modes()))
        determinism = _real_determinism_probe(cache, navs, preflight, variants, hidden_attempt)
        if not determinism["row_level_scientific_equality"]:
            raise Phase3RunnerError("workers 1 and 16 differ on real input-only recursive subset")
        evidence = {"resource_probe": resource_probe, "worker_determinism": determinism}
        target = hidden_attempt / "RESOURCE_DETERMINISM_PROBE.json"
        if target.exists():
            if not resume or json.loads(target.read_text(encoding="utf-8")) != evidence:
                raise Phase3RunnerError("resource/determinism probe collision or drift")
        else:
            phase2._atomic_write_json(target, evidence)
        return {"terminal_status": "PASS_PHASE3_EXT03_RESOURCE_DETERMINISM_PROBE_ONLY", **evidence, "formal_run_launched": False}
    if mode == "full":
        run_phase3(config_path, mode="native-only", method_id=method_id, case_id=case_id, trace_mode="disabled", workers=workers, resume=True)
        return _post_native_diagnostics(preflight, post_recovery_id)
    if mode == "signal-audit":
        attempt_audit = hidden_attempt
        cache, navs = _prepare_cache(preflight, attempt_audit, resume=resume)
        reader = phase2.CompactCacheReader(cache)
        inventory = audit_signal_availability(
            [reader.pair(index) for index in range(len(reader))],
            RtklibBroadcastProvider(preflight.paths.rtklib_bridge, navs),
        )
        rows = _signal_output_rows(inventory)
        audit_dir = attempt_audit / "SIGNAL_AUDIT"
        if audit_dir.exists():
            support = json.loads((audit_dir/"EXT03_C00_SIGNAL_SUPPORT_FREEZE.json").read_text(encoding="utf-8"))
            signal_existing = audit_dir/NATIVE_FILE_NAMES["signal_availability"]
            if not resume or support.get("source_fingerprint") != preflight.source_fingerprint or support.get("signal_availability_sha256") != _sha256(signal_existing):
                raise Phase3RunnerError("signal-audit resume evidence mismatch")
            return {"terminal_status": "PASS_PHASE3_EXT03_SIGNAL_AUDIT_ONLY", "signal_audit_attempt": str(attempt_audit), "supported_modes": list(inventory.supported_modes()), "formal_run_launched": False, "resumed": True}
        audit_dir.mkdir()
        signal_path = audit_dir / NATIVE_FILE_NAMES["signal_availability"]
        _write_csv(signal_path, rows)
        support_path = audit_dir / "EXT03_C00_SIGNAL_SUPPORT_FREEZE.json"
        phase2._atomic_write_json(support_path, {"schema_version": "horizontal_literature.phase3.signal_support_freeze.v1", "source_fingerprint": preflight.source_fingerprint, "signal_availability_sha256": _sha256(signal_path), "mode_support": [item.to_dict() for item in inventory.mode_support], "trace_open_count": 0, "HPPOSECEF_semantic_decode_count": 0})
        return {"terminal_status": "PASS_PHASE3_EXT03_SIGNAL_AUDIT_ONLY", "signal_audit_attempt": str(attempt_audit), "supported_modes": list(inventory.supported_modes()), "formal_run_launched": False}
    if preflight.paths.native_root.exists():
        raise Phase3RunnerError("native target already exists; no overwrite is permitted")
    attempt = hidden_attempt
    cache, navs = _prepare_cache(preflight, attempt, resume=resume)
    reader = phase2.CompactCacheReader(cache)
    provider = RtklibBroadcastProvider(preflight.paths.rtklib_bridge, navs)
    pairs = [reader.pair(index) for index in range(len(reader))]
    inventory = audit_signal_availability(pairs, provider)
    supported = set(inventory.supported_modes())
    variants = tuple(item for item in requested_variants(preflight.contract) if item.system_mode in supported)
    if not variants:
        raise Phase3RunnerError("UNSUPPORTED_EXT03_ON_BY2_NO_DUAL_FREQUENCY_MODE_WITH_EPHEMERIS")
    signal_freeze = attempt / "SIGNAL_AUDIT/EXT03_C00_SIGNAL_SUPPORT_FREEZE.json"
    if not signal_freeze.is_file():
        signal_freeze.parent.mkdir(parents=True, exist_ok=True)
        signal_rows = _signal_output_rows(inventory)
        signal_csv = signal_freeze.parent / NATIVE_FILE_NAMES["signal_availability"]
        _write_csv(signal_csv, signal_rows)
        phase2._atomic_write_json(signal_freeze, {"schema_version": "horizontal_literature.phase3.signal_support_freeze.v1", "source_fingerprint": preflight.source_fingerprint, "signal_availability_sha256": _sha256(signal_csv), "mode_support": [item.to_dict() for item in inventory.mode_support], "trace_open_count": 0, "HPPOSECEF_semantic_decode_count": 0})
    probe_path = attempt / "RESOURCE_DETERMINISM_PROBE.json"
    if probe_path.is_file():
        probe_payload = json.loads(probe_path.read_text(encoding="utf-8"))
        if probe_payload.get("worker_determinism", {}).get("row_level_scientific_equality") is not True:
            raise Phase3RunnerError("stored worker determinism evidence is invalid")
        resource_probe = probe_payload
    else:
        determinism = _real_determinism_probe(cache, navs, preflight, variants, attempt)
        if not determinism["row_level_scientific_equality"]:
            raise Phase3RunnerError("workers 1 and 16 differ on real input-only recursive subset")
        resource_probe = {"resource_probe": resource_probe, "worker_determinism": determinism}
        phase2._atomic_write_json(probe_path, resource_probe)
    records: list[dict[str, Any]] = []
    pending: list[Variant] = []
    for variant in variants:
        part = _part_path(attempt, variant)
        if resume and part.is_file():
            records.extend(_read_variant_part(part, preflight, variant))
        else:
            pending.append(variant)
    if pending:
        resource_probe = {**resource_probe, "variant_executor_requested_workers": workers, "variant_executor_max_workers": workers, "active_variant_task_count": min(workers, len(pending)), "submitted_variant_task_count": len(pending), "worker_failure_count": 0}
        completed_task_count = 0
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(run_variant_sequence, cache, navs, preflight.paths.rtklib_bridge, preflight.paths.lambda_library, variant): variant for variant in pending}
            for future in as_completed(futures):
                variant = futures[future]
                try:
                    part_records = future.result()
                    completed_task_count += 1
                except BaseException as exc:
                    _write_worker_failure_evidence(attempt, {"phase": "NATIVE_VARIANT_EXECUTOR", "requested_workers": workers, "submitted_task_count": len(futures), "completed_task_count": completed_task_count, "failed_task_count": 1, "worker_failure_count": 1, "variant_id": variant.variant_id, "exception_type": type(exc).__name__, "exception_message": str(exc)})
                    raise
                _write_variant_part(_part_path(attempt, variant), preflight, variant, part_records)
                records.extend(part_records)
    resource_probe = {**resource_probe, "worker_failure_count": int(resource_probe.get("worker_failure_count", 0))}
    records.sort(key=lambda row: (str(row["system_mode"]), str(row["constraint_mode"]), -1.0 if row["baseline_sigma_m"] is None else float(row["baseline_sigma_m"]), int(row["epoch_index"])))
    output = attempt / "NATIVE_OUTPUT"
    if output.exists():
        if not resume:
            raise Phase3RunnerError("native-output attempt collision")
        validate_native_freeze(output)
        _atomic_finalize_native(output, preflight.paths.native_root)
        freeze = validate_native_freeze(preflight.paths.native_root)
        terminal = PASS_READY if len(supported) == len(MODE_FREQUENCIES) else PASS_PARTIAL
        return {"terminal_status": terminal, "native_freeze": freeze, "supported_modes": sorted(supported), "formal_run_launched": True, "post_native_opened": False, "resumed_finalization": True}
    output.mkdir()
    _flatten_native(records, inventory, variants, output, preflight, resource_probe, _jsonable(provider.pntpos_bridge_provenance()))
    _atomic_finalize_native(output, preflight.paths.native_root)
    freeze = validate_native_freeze(preflight.paths.native_root)
    terminal = PASS_READY if len(supported) == len(MODE_FREQUENCIES) else PASS_PARTIAL
    return {"terminal_status": terminal, "native_freeze": freeze, "supported_modes": sorted(supported), "formal_run_launched": True, "post_native_opened": False}
