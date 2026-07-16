"""CLEAN1R1C runner gates distinguish inactive status from frozen config."""

import pytest

from legsa_gins.paper_rebuild.formal_runner import (
    FormalRunError,
    _assert_go2_vertical_disabled_status,
    _runtime_12g,
)


@pytest.mark.parametrize(
    ("enabled", "status"),
    ((False, False), (True, True)),
)
def test_vertical_disabled_status_matches_module_activation(
    enabled: bool, status: bool
) -> None:
    _assert_go2_vertical_disabled_status(
        {
            "go2_horizontal_velocity_prior_enabled": enabled,
            "go2_horizontal_velocity_prior_vertical_disabled": status,
        },
        {"go2_vertical_velocity_enabled": False},
    )


@pytest.mark.parametrize(
    ("enabled", "status"),
    ((False, True), (True, False)),
)
def test_vertical_disabled_status_mismatch_fails(
    enabled: bool, status: bool
) -> None:
    with pytest.raises(
        FormalRunError,
        match="FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH",
    ):
        _assert_go2_vertical_disabled_status(
            {
                "go2_horizontal_velocity_prior_enabled": enabled,
                "go2_horizontal_velocity_prior_vertical_disabled": status,
            },
            {"go2_vertical_velocity_enabled": False},
        )


def test_runtime_12g_matches_frozen_yaml_serialization() -> None:
    assert _runtime_12g(1.203865984496293) == 1.2038659845
