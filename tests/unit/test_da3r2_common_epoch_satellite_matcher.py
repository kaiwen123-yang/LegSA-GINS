from legsa_gins.da_repro.common_epoch_satellite_matcher import common_epoch_summary, match_common_observations
from legsa_gins.da_repro.raw_gnss_observation_parser import RawObservation


def _obs(receiver: str, tow: float, sv: int) -> RawObservation:
    return RawObservation(receiver, 1.0, tow, 1, "GPS", 0, sv, 0, 0, 1.0, 2.0, -1.0, 45.0, 0.19, 1)


def test_da3r2_common_epoch_satellite_matcher():
    pairs = match_common_observations([_obs("gnss1", 10.0, 3)], [_obs("gnss2", 10.0, 3), _obs("gnss2", 10.0, 4)])
    assert len(pairs) == 1
    summary = common_epoch_summary(pairs)
    assert summary["common_epoch_count"] == 1
