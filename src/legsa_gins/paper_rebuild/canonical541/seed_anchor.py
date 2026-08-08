"""Seed registry, stable RNG substreams, and source-only anchor realization."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .matrix_spec import WINDOW_END_S, WINDOW_START_S


SEEDS = tuple(260306001 + index for index in range(9))
SEED_IDS = tuple(f"seed_{index:02d}" for index in range(9))
ANCHOR_NAMES = (
    "user_original_206p2s", "early_motion", "mid_straight", "turn_segment",
    "low_speed_segment", "high_motion_segment", "lower_quality_but_valid_A1",
    "raw_doppler_residual_candidate", "late_recovery_segment",
)


class AnchorPolicyError(ValueError):
    """Source-only anchor inputs are incomplete or non-finite."""


@dataclass(frozen=True)
class AnchorContext:
    time_s: np.ndarray
    horizontal_speed_mps: np.ndarray
    yaw_rate_deg_s: np.ndarray
    position_valid: np.ndarray
    dual_yaw_valid: np.ndarray
    a1_quality: np.ndarray
    baseline_length_m: np.ndarray
    raw_doppler_diagnostic_score: np.ndarray
    raw_doppler_valid: np.ndarray
    mean_foot_speed_norm: np.ndarray

    def validate(self) -> None:
        arrays = tuple(getattr(self, field) for field in self.__dataclass_fields__)
        if not arrays or len({len(array) for array in arrays}) != 1 or len(arrays[0]) < 2:
            raise AnchorPolicyError("anchor context arrays must have one common non-trivial length")
        for array in arrays[:3] + arrays[5:8] + arrays[9:]:
            if not np.all(np.isfinite(array)):
                raise AnchorPolicyError("anchor context contains NaN or Inf")
        if np.any(np.diff(self.time_s) <= 0):
            raise AnchorPolicyError("anchor context time must be strictly increasing")


def seed_manifest() -> list[dict[str, Any]]:
    return [
        {
            "seed_index": seed_id,
            "seed_value": seed,
            "anchor_name": anchor,
            "rng_algorithm": "numpy.random.PCG64",
            "component_substreams": "numpy.random.SeedSequence.spawn",
        }
        for seed_id, seed, anchor in zip(SEED_IDS, SEEDS, ANCHOR_NAMES)
    ]


def stable_component_rngs(seed_value: int, component_names: Sequence[str]) -> dict[str, np.random.Generator]:
    """Derive substreams by sorted component identity, never call order.

    中文说明：组件名先排序，再由 SeedSequence.spawn 分配子流，避免新增一个
    handler 分支后改变其他组件的随机序列。
    """

    names = tuple(sorted(set(component_names)))
    if len(names) != len(component_names):
        raise AnchorPolicyError("component substream names must be unique")
    spawned = np.random.SeedSequence(int(seed_value)).spawn(len(names))
    return {name: np.random.Generator(np.random.PCG64(sequence)) for name, sequence in zip(names, spawned)}


def _percentile_time(q: float) -> float:
    return float(WINDOW_START_S + q * (WINDOW_END_S - WINDOW_START_S))


def _centers(context: AnchorContext, duration_s: float) -> Iterable[tuple[int, np.ndarray]]:
    half = duration_s / 2.0
    for index, center in enumerate(context.time_s):
        if center < WINDOW_START_S + half or center > WINDOW_END_S - half:
            continue
        mask = (context.time_s >= center - half) & (context.time_s < center + half)
        if np.count_nonzero(mask) >= 2:
            yield index, mask


def _nearest_valid_time(context: AnchorContext, target: float, valid: np.ndarray | None = None) -> float:
    mask = (context.time_s >= WINDOW_START_S) & (context.time_s <= WINDOW_END_S)
    if valid is not None:
        mask &= valid.astype(bool)
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        return float(np.clip(target, WINDOW_START_S, WINDOW_END_S))
    index = indices[int(np.argmin(np.abs(context.time_s[indices] - target)))]
    return float(context.time_s[index])


def _zscore(values: np.ndarray) -> np.ndarray:
    std = float(np.std(values))
    return np.zeros_like(values, dtype=float) if std <= 1e-12 else (values - float(np.mean(values))) / std


def _contiguous_true_segments(time_s: np.ndarray, mask: np.ndarray) -> list[np.ndarray]:
    """Return deterministic continuous runs, splitting both false masks and time gaps."""

    indices = np.flatnonzero(mask)
    if not indices.size:
        return []
    positive_steps = np.diff(time_s)
    nominal = float(np.median(positive_steps[positive_steps > 0])) if np.any(positive_steps > 0) else 0.0
    gap_limit = max(1.0e-9, nominal * 1.5)
    groups: list[list[int]] = [[int(indices[0])]]
    for left, right in zip(indices, indices[1:]):
        if int(right) != int(left) + 1 or float(time_s[right] - time_s[left]) > gap_limit:
            groups.append([])
        groups[-1].append(int(right))
    return [np.asarray(group, dtype=int) for group in groups if group]


def realize_anchor(seed_index: int, context: AnchorContext) -> dict[str, Any]:
    context.validate()
    if seed_index not in range(9):
        raise AnchorPolicyError("seed index is outside seed_00..seed_08")
    fallback_q = (None, 0.15, 0.45, 0.55, 0.30, 0.65, 0.70, 0.75, 0.85)[seed_index]
    fallback = 206.2 if seed_index == 0 else _percentile_time(float(fallback_q))
    selected: float | None = None
    rule_status = "selected"
    if seed_index == 0:
        # 中文说明：seed_00 是人工冻结的 206.2 s；只有共同有效窗口不含该时刻时才 clip。
        selected = float(np.clip(206.2, WINDOW_START_S, WINDOW_END_S))
    elif seed_index == 1:
        valid = context.position_valid & context.dual_yaw_valid & (context.horizontal_speed_mps > 0.20)
        for index, mask in _centers(context, 1.0):
            if np.all(valid[mask]):
                selected = float(context.time_s[index]); break
    elif seed_index == 2:
        candidates = []
        valid = context.position_valid & context.dual_yaw_valid & (context.horizontal_speed_mps > 0.30) & (np.abs(context.yaw_rate_deg_s) < 5.0)
        for index, mask in _centers(context, 3.0):
            if np.all(valid[mask]):
                candidates.append(index)
        if candidates:
            target = _percentile_time(0.45)
            selected = float(context.time_s[min(candidates, key=lambda i: abs(context.time_s[i] - target))])
    elif seed_index == 3:
        candidates = [(float(np.median(np.abs(context.yaw_rate_deg_s[mask]))), index)
                      for index, mask in _centers(context, 2.0)
                      if np.all(context.horizontal_speed_mps[mask] > 0.15)]
        if candidates:
            selected = float(context.time_s[max(candidates)[1]])
    elif seed_index == 4:
        candidates = [(float(np.median(context.horizontal_speed_mps[mask])), index)
                      for index, mask in _centers(context, 2.0)
                      if np.all((context.horizontal_speed_mps[mask] >= 0.05)
                                & (context.horizontal_speed_mps[mask] <= 0.25)
                                & (np.abs(context.yaw_rate_deg_s[mask]) < 10.0))]
        if candidates:
            selected = float(context.time_s[min(candidates)[1]])
    elif seed_index == 5:
        score = (_zscore(context.horizontal_speed_mps)
                 + _zscore(context.mean_foot_speed_norm)
                 + 0.5 * _zscore(np.abs(context.yaw_rate_deg_s)))
        candidates = [(float(np.mean(score[mask])), index) for index, mask in _centers(context, 2.0)]
        if candidates:
            selected = float(context.time_s[max(candidates)[1]])
    elif seed_index == 6:
        valid = context.dual_yaw_valid & (context.baseline_length_m >= 0.20) & (context.baseline_length_m <= 0.55)
        values = context.a1_quality[valid]
        if values.size and float(np.ptp(values)) > 1.0e-12:
            threshold = float(np.quantile(values, 0.10))
            segments = _contiguous_true_segments(
                context.time_s, valid & (context.a1_quality <= threshold),
            )
            if segments:
                # 中文说明：选择最低质量连续片段的中心；不再退化为一个孤立历元。
                chosen = min(
                    segments,
                    key=lambda segment: (
                        float(np.median(context.a1_quality[segment])),
                        -len(segment), float(context.time_s[segment[0]]),
                    ),
                )
                selected = float(context.time_s[chosen[len(chosen) // 2]])
    elif seed_index == 7:
        valid_indices = np.flatnonzero(context.raw_doppler_valid)
        if valid_indices.size:
            index = valid_indices[int(np.argmax(context.raw_doppler_diagnostic_score[valid_indices]))]
            selected = float(context.time_s[index])
    else:
        selected = min(_percentile_time(0.85), WINDOW_END_S - 30.0)
        selected = _nearest_valid_time(context, selected)
    if selected is None:
        selected = _nearest_valid_time(context, fallback)
        rule_status = "fallback_percentile"
    return {
        "seed_index": SEED_IDS[seed_index], "seed_value": SEEDS[seed_index],
        "anchor_name": ANCHOR_NAMES[seed_index], "anchor_time_s": selected,
        "selection_status": rule_status, "trace_used": False,
        "algorithm_output_used": False,
    }


def realize_all_anchors(context: AnchorContext) -> list[dict[str, Any]]:
    return [realize_anchor(index, context) for index in range(9)]


def anchor_context_from_fresh_bundle(bundle: Any, *, go2_body_raw: str | None = None) -> tuple[AnchorContext, dict[str, Any]]:
    """Build anchor features from solver-visible providers and hash-locked Go2 raw.

    Go2 high-level rows supply motion metadata only; they are never truth.
    """

    position = bundle.tables["gnss_position"].rows
    velocity = bundle.tables["receiver_velocity"].rows
    yaw = bundle.tables["dual_yaw"].rows
    raw = bundle.tables["raw_doppler"].rows
    hv = bundle.tables["go2_hv"].rows
    times = np.asarray([float(row["time"]) for row in position])

    def nearest(table: list[Mapping[str, Any]], field: str, default: float = 0.0) -> np.ndarray:
        source_times = np.asarray([float(row["time"]) for row in table])
        values = np.asarray([float(row.get(field, default) or default) for row in table])
        indices = np.searchsorted(source_times, times).clip(0, len(source_times) - 1)
        previous = np.maximum(0, indices - 1)
        choose_previous = np.abs(source_times[previous] - times) < np.abs(source_times[indices] - times)
        indices[choose_previous] = previous[choose_previous]
        return values[indices]

    # 中文说明：anchor motion axis冻结为Go2 horizontal-velocity weak-prior
    # metadata；receiver NAV-PVT velocity 不能静默替代它，且两者都不是truth。
    go2_vn = nearest(hv, "vn"); go2_ve = nearest(hv, "ve")
    speed = np.hypot(go2_vn, go2_ve)
    yaw_values = nearest(yaw, "yaw_deg"); yaw_unwrapped = np.unwrap(np.deg2rad(yaw_values))
    yaw_rate = np.rad2deg(np.gradient(yaw_unwrapped, times))
    position_valid = np.asarray([str(row.get("valid", "1")) in {"1", "true", "True"} for row in position])
    yaw_valid = np.asarray([str(row.get("valid", "1")) in {"1", "true", "True"} for row in yaw])
    baseline = nearest(yaw, "baseline_length_m", 0.0)
    physical = (baseline >= 0.20) & (baseline <= 0.55)
    rel_acc = nearest(yaw, "rel_acc_m", 1.0)
    quality = physical.astype(float) * 10.0 - rel_acc
    raw_valid = nearest(raw, "valid", 0.0).astype(bool)
    raw_std = nearest(raw, "std_vn", 1.0) + nearest(raw, "std_ve", 1.0) + nearest(raw, "std_vd", 1.0)
    raw_score = nearest(raw, "gdop_like", 0.0) + raw_std - nearest(raw, "quality", 0.0) * 0.01
    foot_speed = np.hypot(nearest(hv, "vn"), nearest(hv, "ve"))
    report: dict[str, Any] = {
        "go2_body_raw_used": False, "go2_role": "motion_metadata_not_truth",
        "horizontal_speed_source": "fresh_go2_horizontal_velocity_weak_prior",
        "receiver_velocity_used_for_anchor_speed": False,
    }
    if go2_body_raw is not None:
        from legsa_gins.go2_state.go2_body_state_parser import standardize_go2_body_state
        rows, parse_report = standardize_go2_body_state(go2_body_raw, base_time=1772784000.0)
        source_times = np.asarray([float(row["aligned_time"]) for row in rows if row.get("aligned_time") is not None])
        source_values = []
        for row in rows:
            if row.get("aligned_time") is None: continue
            vectors = []
            for foot in range(4):
                values = [row.get(f"foot_speed_body_{3 * foot + axis}") for axis in range(3)]
                if all(value not in (None, "") for value in values):
                    vectors.append(math.sqrt(sum(float(value) ** 2 for value in values)))
            source_values.append(float(np.mean(vectors)) if vectors else 0.0)
        if len(source_times) >= 2:
            foot_speed = np.interp(times, source_times, np.asarray(source_values))
        report.update(go2_body_raw_used=True, go2_parse_report=parse_report)
    context = AnchorContext(
        time_s=times, horizontal_speed_mps=speed, yaw_rate_deg_s=yaw_rate,
        position_valid=position_valid, dual_yaw_valid=yaw_valid,
        a1_quality=quality, baseline_length_m=baseline,
        raw_doppler_diagnostic_score=raw_score, raw_doppler_valid=raw_valid,
        mean_foot_speed_norm=foot_speed,
    )
    context.validate()
    return context, report


def place_interval(anchor_time_s: float, duration_s: float,
                   window: tuple[float, float] = (WINDOW_START_S, WINDOW_END_S)) -> tuple[float, float]:
    """Place a half-open interval, shifting before any unavoidable clipping."""
    start_bound, end_bound = map(float, window)
    duration = float(duration_s)
    if duration <= 0 or end_bound <= start_bound:
        raise AnchorPolicyError("invalid interval/window")
    if duration >= end_bound - start_bound:
        return start_bound, end_bound
    start = float(anchor_time_s) - duration / 2.0
    end = start + duration
    if start < start_bound:
        end += start_bound - start; start = start_bound
    if end > end_bound:
        start -= end - end_bound; end = end_bound
    return start, end


def place_repeated_d07(anchor_time_s: float) -> tuple[tuple[float, float], ...]:
    centers = np.asarray([anchor_time_s - 6.0, anchor_time_s, anchor_time_s + 6.0], dtype=float)
    starts = centers - 1.5
    ends = centers + 1.5
    if starts[0] < WINDOW_START_S:
        shift = WINDOW_START_S - starts[0]; starts += shift; ends += shift
    if ends[-1] > WINDOW_END_S:
        shift = ends[-1] - WINDOW_END_S; starts -= shift; ends -= shift
    return tuple((float(start), float(end)) for start, end in zip(starts, ends))
