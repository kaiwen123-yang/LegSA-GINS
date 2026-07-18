"""CLEAN2R2A1 的 BY2 clean-only 2^4 模块消融合同。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .methods import EXPECTED_FEATURES, FEATURE_FIELDS
from .paths import load_yaml_mapping


STAGE_ID = "CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
DATA_MODE = "real_clean"
BIT_ORDER = ("RD", "SA", "RP", "HV")
FEATURE_MAP = {
    "RD": "enable_raw_doppler",
    "SA": "enable_source_aware",
    "RP": "enable_go2_roll_pitch_prior",
    "HV": "enable_go2_horizontal_velocity_prior",
}
BACKBONE_FEATURES = {
    "enable_dual_yaw": True,
    "enable_receiver_velocity": True,
}
VARIANT_IDS = tuple(f"AB{value:04b}" for value in range(16))
PAIRWISE_TERMS = (
    ("RD", "SA"),
    ("RD", "RP"),
    ("RD", "HV"),
    ("SA", "RP"),
    ("SA", "HV"),
    ("RP", "HV"),
)


class Clean2R2AAblationError(ValueError):
    """消融合同不完整或发生方法身份漂移。"""


@dataclass(frozen=True)
class AblationProfile:
    configuration_id: str
    bit_string: str
    module_flags: Mapping[str, bool]
    feature_flags: Mapping[str, bool]
    canonical_equivalent_method_id: str | None

    def effect_code(self, factor: str) -> int:
        if factor not in BIT_ORDER:
            raise Clean2R2AAblationError(f"unknown factor: {factor}")
        return 1 if self.module_flags[factor] else -1


def _expected_profile(configuration_id: str) -> AblationProfile:
    if configuration_id not in VARIANT_IDS:
        raise Clean2R2AAblationError(f"unknown configuration: {configuration_id}")
    bits = configuration_id.removeprefix("AB")
    # 位序只允许 RD、SA、RP、HV，禁止按结果重新解释 bit。
    module_flags = {factor: bit == "1" for factor, bit in zip(BIT_ORDER, bits, strict=True)}
    features = {
        **BACKBONE_FEATURES,
        **{FEATURE_MAP[factor]: module_flags[factor] for factor in BIT_ORDER},
    }
    equivalent = {
        "AB0000": "strong_dual_yaw_EKF",
        "AB1111": "LegSA_Paper_V1",
    }.get(configuration_id)
    return AblationProfile(
        configuration_id=configuration_id,
        bit_string=bits,
        module_flags=module_flags,
        feature_flags=features,
        canonical_equivalent_method_id=equivalent,
    )


def canonical_ablation_profiles() -> tuple[AblationProfile, ...]:
    """按二进制升序生成 16 个且仅 16 个 clean 配置。"""

    return tuple(_expected_profile(configuration_id) for configuration_id in VARIANT_IDS)


def load_ablation_contract(path: str | Path) -> tuple[AblationProfile, ...]:
    payload = load_yaml_mapping(path)
    expected_top = {
        "schema_version",
        "stage_id",
        "case_id",
        "data_mode",
        "backbone_method_id",
        "variant_count",
        "bit_order",
        "feature_map",
        "fixed_backbone_features",
        "variants",
    }
    if set(payload) != expected_top:
        raise Clean2R2AAblationError("ablation contract top-level fields mismatch")
    expected_scalars = {
        "schema_version": "paper_rebuild.clean2r2a1_ablation.v1",
        "stage_id": STAGE_ID,
        "case_id": CASE_ID,
        "data_mode": DATA_MODE,
        "backbone_method_id": "strong_dual_yaw_EKF",
        "variant_count": 16,
    }
    if any(payload.get(key) != value for key, value in expected_scalars.items()):
        raise Clean2R2AAblationError("ablation contract identity mismatch")
    if tuple(payload.get("bit_order") or ()) != BIT_ORDER:
        raise Clean2R2AAblationError("bit order must be RD,SA,RP,HV")
    if dict(payload.get("feature_map") or {}) != FEATURE_MAP:
        raise Clean2R2AAblationError("feature map mismatch")
    if dict(payload.get("fixed_backbone_features") or {}) != BACKBONE_FEATURES:
        raise Clean2R2AAblationError("strong backbone features mismatch")
    rows = payload.get("variants")
    if not isinstance(rows, list) or len(rows) != 16:
        raise Clean2R2AAblationError("exactly 16 variants are required")
    profiles: list[AblationProfile] = []
    for expected_id, row in zip(VARIANT_IDS, rows, strict=True):
        if not isinstance(row, Mapping):
            raise Clean2R2AAblationError("variant row must be a mapping")
        expected = _expected_profile(expected_id)
        expected_fields = {
            "configuration_id",
            "bit_string",
            *BIT_ORDER,
            "canonical_equivalent_method_id",
        }
        if set(row) != expected_fields:
            raise Clean2R2AAblationError(f"variant fields mismatch: {expected_id}")
        if row.get("configuration_id") != expected.configuration_id:
            raise Clean2R2AAblationError("variant order or identity mismatch")
        if str(row.get("bit_string")) != expected.bit_string:
            raise Clean2R2AAblationError(f"bit string mismatch: {expected_id}")
        if any(row.get(factor) is not expected.module_flags[factor] for factor in BIT_ORDER):
            raise Clean2R2AAblationError(f"module bit mismatch: {expected_id}")
        if row.get("canonical_equivalent_method_id") != expected.canonical_equivalent_method_id:
            raise Clean2R2AAblationError(f"canonical identity mismatch: {expected_id}")
        profiles.append(expected)
    return tuple(profiles)


def assert_canonical_method_identities(profiles: Sequence[AblationProfile]) -> None:
    by_id = {profile.configuration_id: profile for profile in profiles}
    if set(by_id) != set(VARIANT_IDS):
        raise Clean2R2AAblationError("ablation variant set mismatch")
    if dict(by_id["AB0000"].feature_flags) != EXPECTED_FEATURES["strong_dual_yaw_EKF"]:
        raise Clean2R2AAblationError("AB0000 is not the strong method identity")
    if dict(by_id["AB1111"].feature_flags) != EXPECTED_FEATURES["LegSA_Paper_V1"]:
        raise Clean2R2AAblationError("AB1111 is not the LegSA method identity")
    for profile in profiles:
        if tuple(profile.feature_flags) != FEATURE_FIELDS:
            raise Clean2R2AAblationError(f"feature order mismatch: {profile.configuration_id}")


def effect_code(bit_enabled: bool) -> int:
    return 1 if bit_enabled else -1
