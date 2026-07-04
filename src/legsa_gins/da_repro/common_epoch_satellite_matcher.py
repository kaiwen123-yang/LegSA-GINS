"""Common epoch/satellite matcher for dual receiver RAWX observations."""

from __future__ import annotations

from dataclasses import dataclass

from .raw_gnss_observation_parser import RawObservation


@dataclass(frozen=True)
class CommonObservationPair:
    epoch_tow: float
    sat_key: tuple[int, int, int]
    receiver1: RawObservation
    receiver2: RawObservation


def match_common_observations(
    gnss1: list[RawObservation],
    gnss2: list[RawObservation],
    *,
    epoch_round_digits: int = 3,
) -> list[CommonObservationPair]:
    index2: dict[tuple[float, tuple[int, int, int]], RawObservation] = {}
    for obs in gnss2:
        index2[(round(obs.rcv_tow, epoch_round_digits), obs.sat_key)] = obs
    pairs = []
    for obs1 in gnss1:
        epoch = round(obs1.rcv_tow, epoch_round_digits)
        obs2 = index2.get((epoch, obs1.sat_key))
        if obs2 is not None:
            pairs.append(CommonObservationPair(epoch, obs1.sat_key, obs1, obs2))
    return pairs


def common_epoch_summary(pairs: list[CommonObservationPair]) -> dict[str, object]:
    by_epoch: dict[float, int] = {}
    by_constellation: dict[int, int] = {}
    for pair in pairs:
        by_epoch[pair.epoch_tow] = by_epoch.get(pair.epoch_tow, 0) + 1
        by_constellation[pair.sat_key[0]] = by_constellation.get(pair.sat_key[0], 0) + 1
    common_counts = list(by_epoch.values())
    return {
        "common_pair_count": len(pairs),
        "common_epoch_count": len(by_epoch),
        "min_common_sats_per_epoch": min(common_counts) if common_counts else 0,
        "max_common_sats_per_epoch": max(common_counts) if common_counts else 0,
        "median_common_sats_per_epoch": _median(common_counts),
        "constellation_id_counts": dict(sorted(by_constellation.items())),
    }


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return float(values[mid])
    return 0.5 * (values[mid - 1] + values[mid])
