"""Deterministic current-provider Classic-18 perturbation policies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .manifest import sha256_file
from .paths import load_yaml_mapping


EXPECTED_CASE_CODES = tuple(f"C{index:02d}" for index in range(18))
NOMINAL_BASELINE_LENGTH_M = 0.350


class ClassicCaseError(ValueError):
    """A Classic-18 mapping, input epoch, or deterministic policy is invalid."""


@dataclass(frozen=True)
class ClassicCaseSpec:
    case_id: str
    case_code: str
    family: str
    display_label: str
    seed: int | None
    operations: tuple[dict[str, Any], ...]
    provider_std_scale: float


@dataclass(frozen=True)
class ClassicCaseCatalog:
    path: Path
    source_sha256: str
    source_spec_path: Path
    source_spec_sha256: str
    payload: dict[str, Any]
    cases: tuple[ClassicCaseSpec, ...]

    def case(self, case_id_or_code: str) -> ClassicCaseSpec:
        for case in self.cases:
            if case_id_or_code in {case.case_id, case.case_code}:
                return case
        raise ClassicCaseError(f"Unknown Classic-18 case: {case_id_or_code}")


@dataclass(frozen=True)
class AlignedGnssEpoch:
    row_index: int
    time: float
    fields: tuple[str, ...]
    baseline_e_m: float | None
    baseline_n_m: float | None
    baseline_u_m: float | None

    @property
    def yaw_deg(self) -> float:
        return float(self.fields[13])

    @property
    def yaw_std_deg(self) -> float:
        return float(self.fields[14])

    @property
    def position_valid(self) -> bool:
        return _validity(self.fields[15], "position_valid")

    @property
    def receiver_velocity_valid(self) -> bool:
        return _validity(self.fields[16], "receiver_velocity_valid")

    @property
    def yaw_valid(self) -> bool:
        return _validity(self.fields[17], "dual_yaw_valid")


@dataclass(frozen=True)
class ClassicCaseApplication:
    case: ClassicCaseSpec
    output_fields: tuple[tuple[str, ...], ...]
    provider_rows: tuple[dict[str, Any], ...]
    ledger_rows: tuple[dict[str, Any], ...]
    policy_report: dict[str, Any]


def _validity(value: str, label: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true"}:
        return True
    if normalized in {"0", "false"}:
        return False
    raise ClassicCaseError(f"Invalid {label}: {value!r}")


def wrap360(value: float) -> float:
    result = math.fmod(float(value), 360.0)
    if result < 0.0:
        result += 360.0
    return 0.0 if math.isclose(result, 360.0, abs_tol=1.0e-12) else result


def wrap_signed(value: float) -> float:
    return (float(value) + 180.0) % 360.0 - 180.0


def body_yaw_from_baseline(east: float, north: float) -> float:
    if not all(math.isfinite(value) for value in (east, north)):
        raise ClassicCaseError("Baseline heading contains NaN or infinity")
    if math.hypot(east, north) <= 1.0e-15:
        raise ClassicCaseError("Horizontal baseline is zero")
    return wrap360(math.degrees(math.atan2(east, north)) + 90.0)


def normalize_baseline(
    east: float,
    north: float,
    up: float,
    target_length_m: float = NOMINAL_BASELINE_LENGTH_M,
) -> tuple[float, float, float]:
    length = math.sqrt(east * east + north * north + up * up)
    if not math.isfinite(length) or length <= 1.0e-15:
        raise ClassicCaseError("Perturbed baseline cannot be normalized")
    if not math.isfinite(target_length_m) or target_length_m <= 0.0:
        raise ClassicCaseError("Nominal baseline length is invalid")
    scale = target_length_m / length
    return east * scale, north * scale, up * scale


def round_half_up_count(fraction: float, population: int) -> int:
    """Freeze selected cardinality; Python's banker rounding is intentionally excluded."""

    if not math.isfinite(fraction) or not 0.0 <= fraction <= 1.0 or population < 0:
        raise ClassicCaseError("Selection fraction/population is invalid")
    return int(math.floor(fraction * population + 0.5))


def fixed_cardinality_selection(
    valid_indices: Sequence[int], *, fraction: float, seed: int
) -> tuple[int, ...]:
    """Select sorted row indices through Generator(PCG64(seed)) without replacement."""

    population = len(valid_indices)
    count = round_half_up_count(fraction, population)
    if count == 0:
        return ()
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    # 先在有效序列的局部索引上抽样，再排序映射回原始行，确保账本顺序稳定。
    local = np.sort(rng.choice(population, size=count, replace=False))
    return tuple(int(valid_indices[int(index)]) for index in local)


def _resolve_source_spec(mapping_path: Path, configured: str) -> Path:
    candidate = Path(configured)
    if candidate.is_absolute():
        raise ClassicCaseError("Tracked Classic-18 source spec path must be repository-relative")
    code_root = mapping_path.parents[2]
    resolved = (code_root / candidate).resolve(strict=True)
    if code_root.resolve(strict=True) not in resolved.parents:
        raise ClassicCaseError("Classic-18 source spec escaped the repository")
    return resolved


def load_classic_case_catalog(path: str | Path) -> ClassicCaseCatalog:
    """Validate the active A1 mapping and its legacy-policy source hash."""

    source = Path(path).resolve(strict=True)
    payload = load_yaml_mapping(source)
    if payload.get("schema_version") != "paper_rebuild.clean2_classic18_active_mapping.v1":
        raise ClassicCaseError("Classic-18 active mapping schema mismatch")
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ClassicCaseError("Classic-18 provenance is missing")
    for field in (
        "legacy_performance_evidence_used",
        "legacy_provider_payload_used",
        "legacy_full_backend_solver_used",
        "legacy_full_backend_provider_layer_promoted",
    ):
        if provenance.get(field) is not False:
            raise ClassicCaseError(f"Classic-18 forbidden provenance flag changed: {field}")
    if provenance.get("active_mapping_source_backed") is not True:
        raise ClassicCaseError("Classic-18 active mapping must remain source-backed")
    source_spec = _resolve_source_spec(source, str(provenance.get("source_spec_path") or ""))
    source_hash = sha256_file(source_spec)
    if source_hash != provenance.get("source_spec_sha256"):
        raise ClassicCaseError("Classic-18 source specification hash mismatch")
    provider = payload.get("active_provider")
    if not isinstance(provider, Mapping) or provider.get("layer") != "A1_dual_diff_status_baseline_vector":
        raise ClassicCaseError("BLOCKED_CLEAN2_CLASSIC18_ACTIVE_MAPPING_AMBIGUOUS")
    if provider.get("baseline_vector") != "GNSS2_minus_GNSS1":
        raise ClassicCaseError("Classic-18 antenna order drifted")
    schema = payload.get("gnss_schema")
    if not isinstance(schema, Mapping) or schema.get("extended_column_count") != 18:
        raise ClassicCaseError("Classic-18 requires current 15+3 GNSS schema")
    deterministic = payload.get("determinism")
    if not isinstance(deterministic, Mapping):
        raise ClassicCaseError("Classic-18 determinism contract is missing")
    expected_determinism = {
        "bit_generator": "PCG64",
        "selected_count_rounding": "round_half_up",
        "selection": "sorted_choice_without_replacement",
        "outage_midpoint_policy": "upper_midpoint_index_N_floor_div_2",
        "mixed_rng_policy": "restart_PCG64_with_same_seed_for_each_sub_operation",
    }
    if any(deterministic.get(key) != value for key, value in expected_determinism.items()):
        raise ClassicCaseError("Classic-18 deterministic policy drifted")

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != 18:
        raise ClassicCaseError("Classic-18 mapping must contain exactly 18 cases")
    cases: list[ClassicCaseSpec] = []
    for expected_code, raw in zip(EXPECTED_CASE_CODES, raw_cases):
        if not isinstance(raw, Mapping) or raw.get("case_code") != expected_code:
            raise ClassicCaseError("Classic-18 case code/order mismatch")
        case_id = str(raw.get("case_id") or "")
        if not case_id.startswith(expected_code + "_"):
            raise ClassicCaseError("Classic-18 case id/code mismatch")
        seed_value = raw.get("seed")
        if seed_value is not None and seed_value not in {0, 1, 2}:
            raise ClassicCaseError("Classic-18 seed is outside 0,1,2")
        operations = raw.get("operations")
        if not isinstance(operations, list) or not operations or not all(
            isinstance(operation, Mapping) for operation in operations
        ):
            raise ClassicCaseError("Classic-18 operations are invalid")
        if expected_code in {"C15", "C16", "C17"} and tuple(
            operation.get("operation") for operation in operations
        ) != ("baseline_vector_noise", "baseline_vector_spike", "signed_yaw_spike"):
            raise ClassicCaseError("Classic-18 mixed operation order drifted")
        cases.append(
            ClassicCaseSpec(
                case_id=case_id,
                case_code=expected_code,
                family=str(raw.get("family") or ""),
                display_label=str(raw.get("display_label") or ""),
                seed=None if seed_value is None else int(seed_value),
                operations=tuple(dict(operation) for operation in operations),
                provider_std_scale=float(raw.get("provider_std_scale", 1.0)),
            )
        )
    return ClassicCaseCatalog(
        path=source,
        source_sha256=sha256_file(source),
        source_spec_path=source_spec,
        source_spec_sha256=source_hash,
        payload=payload,
        cases=tuple(cases),
    )


def _format_like(value: float, original: str, *, minimum_decimals: int = 6) -> str:
    if not math.isfinite(value):
        raise ClassicCaseError("Case output contains NaN or infinity")
    decimals = minimum_decimals
    if "." in original and "e" not in original.casefold():
        decimals = max(decimals, len(original.rsplit(".", 1)[1]))
    return f"{value:.{min(decimals, 12)}f}"


def _vector_length(state: Mapping[str, Any]) -> float | str:
    values = (state.get("e"), state.get("n"), state.get("u"))
    if any(value is None for value in values):
        return ""
    return math.sqrt(sum(float(value) ** 2 for value in values))


def _ledger_row(
    *,
    case: ClassicCaseSpec,
    epoch: AlignedGnssEpoch,
    state: Mapping[str, Any],
    operation: str,
    selected: bool,
    operation_input: Mapping[str, Any],
) -> dict[str, Any]:
    original_length = ""
    if epoch.baseline_e_m is not None:
        original_length = math.sqrt(
            epoch.baseline_e_m**2 + epoch.baseline_n_m**2 + epoch.baseline_u_m**2  # type: ignore[operator]
        )
    return {
        "case_id": case.case_id,
        "seed": "" if case.seed is None else case.seed,
        "time": epoch.time,
        "operation": operation,
        "selected": selected,
        "original_baseline_e": "" if epoch.baseline_e_m is None else epoch.baseline_e_m,
        "original_baseline_n": "" if epoch.baseline_n_m is None else epoch.baseline_n_m,
        "original_baseline_u": "" if epoch.baseline_u_m is None else epoch.baseline_u_m,
        "modified_baseline_e": "" if state.get("e") is None else state["e"],
        "modified_baseline_n": "" if state.get("n") is None else state["n"],
        "modified_baseline_u": "" if state.get("u") is None else state["u"],
        "original_length": original_length,
        "modified_length": _vector_length(state),
        "original_yaw": epoch.yaw_deg,
        "modified_yaw": state["yaw"],
        "yaw_delta_wrap_deg": wrap_signed(float(state["yaw"]) - epoch.yaw_deg),
        "original_yaw_std": epoch.yaw_std_deg,
        "modified_yaw_std": state["yaw_std"],
        "original_yaw_valid": epoch.yaw_valid,
        "modified_yaw_valid": state["yaw_valid"],
        "position_valid": epoch.position_valid,
        "receiver_velocity_valid": epoch.receiver_velocity_valid,
        "operation_input_baseline_e": "" if operation_input.get("e") is None else operation_input["e"],
        "operation_input_baseline_n": "" if operation_input.get("n") is None else operation_input["n"],
        "operation_input_baseline_u": "" if operation_input.get("u") is None else operation_input["u"],
        "operation_input_yaw": operation_input["yaw"],
        "operation_input_yaw_std": operation_input["yaw_std"],
        "operation_input_yaw_valid": operation_input["yaw_valid"],
    }


def _valid_vector_indices(epochs: Sequence[AlignedGnssEpoch]) -> list[int]:
    indices = []
    for index, epoch in enumerate(epochs):
        if epoch.yaw_valid:
            if None in {epoch.baseline_e_m, epoch.baseline_n_m, epoch.baseline_u_m}:
                raise ClassicCaseError("Yaw-valid GNSS epoch lacks a source-backed baseline vector")
            indices.append(index)
    if not indices:
        raise ClassicCaseError("Classic-18 input has no yaw-valid epoch")
    return indices


def apply_classic_case(
    epochs: Sequence[AlignedGnssEpoch], case: ClassicCaseSpec
) -> ClassicCaseApplication:
    """Apply only dual-yaw value/std/validity changes; position and velocity stay textual."""

    if not epochs:
        raise ClassicCaseError("Classic-18 input is empty")
    times = [epoch.time for epoch in epochs]
    if any(not math.isfinite(value) for value in times) or any(
        right <= left for left, right in zip(times, times[1:])
    ):
        raise ClassicCaseError("Classic-18 GNSS timestamps must be finite and strictly increasing")
    valid_indices = _valid_vector_indices(epochs)
    states: list[dict[str, Any]] = [
        {
            "e": epoch.baseline_e_m,
            "n": epoch.baseline_n_m,
            "u": epoch.baseline_u_m,
            "yaw": epoch.yaw_deg,
            "yaw_std": epoch.yaw_std_deg,
            "yaw_valid": epoch.yaw_valid,
        }
        for epoch in epochs
    ]
    ledger: list[dict[str, Any]] = []
    operation_counts: dict[str, int] = {}

    for operation_spec in case.operations:
        operation = str(operation_spec["operation"])
        selected: set[int] = set()
        operation_inputs = [dict(state) for state in states]
        if operation == "none":
            pass
        elif operation == "yaw_valid_midpoint_outage":
            midpoint_time = epochs[valid_indices[len(valid_indices) // 2]].time
            duration = float(operation_spec["duration_s"])
            selected = {
                index
                for index in valid_indices
                if midpoint_time <= epochs[index].time < midpoint_time + duration
            }
            for index in selected:
                states[index]["yaw_valid"] = False
        elif operation == "yaw_valid_min_interval":
            minimum = float(operation_spec["min_interval_s"])
            kept: list[int] = []
            for index in valid_indices:
                # 始终保留首个有效 epoch；之后只与上一个已保留 epoch 比较。
                if not kept or epochs[index].time - epochs[kept[-1]].time >= minimum - 1.0e-12:
                    kept.append(index)
            selected = set(valid_indices).difference(kept)
            for index in selected:
                states[index]["yaw_valid"] = False
        elif operation == "baseline_vector_noise":
            if case.seed is None:
                raise ClassicCaseError("Vector-noise case requires a seed")
            rng = np.random.Generator(np.random.PCG64(case.seed))
            noise = rng.normal(
                loc=0.0,
                scale=[
                    float(operation_spec["horizontal_sigma_m"]),
                    float(operation_spec["horizontal_sigma_m"]),
                    float(operation_spec["up_sigma_m"]),
                ],
                size=(len(valid_indices), 3),
            )
            selected = set(valid_indices)
            for local, index in enumerate(valid_indices):
                state = states[index]
                e, n, u = normalize_baseline(
                    float(state["e"]) + float(noise[local, 0]),
                    float(state["n"]) + float(noise[local, 1]),
                    float(state["u"]) + float(noise[local, 2]),
                    float(operation_spec["preserve_length_m"]),
                )
                state.update({"e": e, "n": n, "u": u, "yaw": body_yaw_from_baseline(e, n)})
        elif operation == "baseline_vector_spike":
            if case.seed is None:
                raise ClassicCaseError("Vector-spike case requires a seed")
            selected_tuple = fixed_cardinality_selection(
                valid_indices,
                fraction=float(operation_spec["fraction"]),
                seed=case.seed,
            )
            selected = set(selected_tuple)
            # 独立子操作从同一 seed 重启；choice 消耗后再生成方向，语义固定。
            rng = np.random.Generator(np.random.PCG64(case.seed))
            count = round_half_up_count(float(operation_spec["fraction"]), len(valid_indices))
            local_choice = np.sort(rng.choice(len(valid_indices), size=count, replace=False)) if count else []
            replay = tuple(valid_indices[int(value)] for value in local_choice)
            if replay != selected_tuple:
                raise ClassicCaseError("PCG64 selection replay mismatch")
            directions = rng.uniform(0.0, 2.0 * math.pi, size=count)
            for index, direction in zip(selected_tuple, directions):
                state = states[index]
                magnitude = float(operation_spec["magnitude_m"])
                e, n, u = normalize_baseline(
                    float(state["e"]) + magnitude * math.sin(float(direction)),
                    float(state["n"]) + magnitude * math.cos(float(direction)),
                    float(state["u"]),
                    float(operation_spec["preserve_length_m"]),
                )
                state.update({"e": e, "n": n, "u": u, "yaw": body_yaw_from_baseline(e, n)})
        elif operation == "signed_yaw_spike":
            if case.seed is None:
                raise ClassicCaseError("Yaw-spike case requires a seed")
            selected_tuple = fixed_cardinality_selection(
                valid_indices,
                fraction=float(operation_spec["fraction"]),
                seed=case.seed,
            )
            selected = set(selected_tuple)
            rng = np.random.Generator(np.random.PCG64(case.seed))
            count = round_half_up_count(float(operation_spec["fraction"]), len(valid_indices))
            local_choice = np.sort(rng.choice(len(valid_indices), size=count, replace=False)) if count else []
            replay = tuple(valid_indices[int(value)] for value in local_choice)
            if replay != selected_tuple:
                raise ClassicCaseError("PCG64 yaw-spike selection replay mismatch")
            signs = rng.choice(np.array([-1.0, 1.0]), size=count, replace=True)
            for index, sign in zip(selected_tuple, signs):
                state = states[index]
                delta = float(sign) * float(operation_spec["magnitude_deg"])
                radians = math.radians(delta)
                e0, n0, u0 = float(state["e"]), float(state["n"]), float(state["u"])
                n1 = n0 * math.cos(radians) - e0 * math.sin(radians)
                e1 = n0 * math.sin(radians) + e0 * math.cos(radians)
                e, n, u = normalize_baseline(
                    e1, n1, u0, float(operation_spec["preserve_length_m"])
                )
                state.update({"e": e, "n": n, "u": u, "yaw": body_yaw_from_baseline(e, n)})
        elif operation == "yaw_std_scale":
            factor = float(operation_spec["factor"])
            if not math.isfinite(factor) or factor <= 0.0:
                raise ClassicCaseError("Yaw std scale is invalid")
            # std列是case provider字段；即使该行yaw暂时无效也统一缩放，避免隐式分支语义。
            selected = set(range(len(epochs)))
            for index in range(len(epochs)):
                states[index]["yaw_std"] = float(states[index]["yaw_std"]) * factor
        else:
            raise ClassicCaseError(f"Unsupported Classic-18 operation: {operation}")

        operation_counts[operation] = len(selected)
        for index, epoch in enumerate(epochs):
            ledger.append(
                _ledger_row(
                    case=case,
                    epoch=epoch,
                    state=states[index],
                    operation=operation,
                    selected=index in selected,
                    operation_input=operation_inputs[index],
                )
            )

    output_fields: list[tuple[str, ...]] = []
    provider_rows: list[dict[str, Any]] = []
    for epoch, state in zip(epochs, states):
        fields = list(epoch.fields)
        # 未变化字段保留原token；C01-C03只能改validity，C10/C14只能改std。
        if abs(wrap_signed(float(state["yaw"]) - float(fields[13]))) > 1.0e-12:
            fields[13] = _format_like(float(state["yaw"]), fields[13])
        if not math.isclose(
            float(state["yaw_std"]), float(fields[14]), rel_tol=0.0, abs_tol=1.0e-15
        ):
            fields[14] = _format_like(float(state["yaw_std"]), fields[14])
        fields[17] = "1" if state["yaw_valid"] else "0"
        if tuple(fields[0:13]) != epoch.fields[0:13] or tuple(fields[15:17]) != epoch.fields[15:17]:
            raise ClassicCaseError("FAIL_CLEAN2_POSITION_VELOCITY_SOURCE_ISOLATION")
        allowed_changed_columns = (
            set()
            if case.case_code == "C00"
            else {17}
            if case.case_code in {"C01", "C02", "C03"}
            else {14}
            if case.case_code in {"C10", "C14"}
            else {13}
        )
        changed_columns = {
            index
            for index, (before, after) in enumerate(zip(epoch.fields, fields))
            if before != after
        }
        if not changed_columns.issubset(allowed_changed_columns):
            raise ClassicCaseError("Classic case changed an unauthorized GNSS token")
        output_fields.append(tuple(fields))
        provider_rows.append(
            {
                "case_id": case.case_id,
                "time": epoch.time,
                "baseline_e_m": "" if state["e"] is None else state["e"],
                "baseline_n_m": "" if state["n"] is None else state["n"],
                "baseline_u_m": "" if state["u"] is None else state["u"],
                "baseline_d_m": "" if state["u"] is None else -float(state["u"]),
                "baseline_length_m": _vector_length(state),
                "body_yaw_ned_deg": state["yaw"],
                "yaw_std_deg": state["yaw_std"],
                "position_valid": epoch.position_valid,
                "receiver_velocity_valid": epoch.receiver_velocity_valid,
                "yaw_valid": state["yaw_valid"],
                "source_layer": "A1_dual_diff_status_baseline_vector",
                "gnss_order": "GNSS2-GNSS1",
                "trace_used": False,
            }
        )
    return ClassicCaseApplication(
        case=case,
        output_fields=tuple(output_fields),
        provider_rows=tuple(provider_rows),
        ledger_rows=tuple(ledger),
        policy_report={
            "schema_version": "paper_rebuild.clean2_case_policy_report.v1",
            "case_id": case.case_id,
            "case_code": case.case_code,
            "family": case.family,
            "display_label": case.display_label,
            "seed": case.seed,
            "provider_std_scale": case.provider_std_scale,
            "operations": [dict(operation) for operation in case.operations],
            "rng": "numpy.random.Generator(PCG64(seed))",
            "valid_input_epoch_count": len(valid_indices),
            "operation_selected_counts": operation_counts,
            "position_or_receiver_velocity_changed": False,
            "trace_read_count": 0,
            "per_case_tuning": False,
            "metric_driven_selection": False,
            "epoch_deleted_for_metric": False,
        },
    )
