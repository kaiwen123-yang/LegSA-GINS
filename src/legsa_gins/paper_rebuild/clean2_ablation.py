"""Frozen CLEAN2 2^4 module-ablation catalog and effect coding."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .manifest import sha256_file
from .paths import load_yaml_mapping


MODULE_ORDER = ("RD", "SA", "RP", "HV")
FEATURE_BY_MODULE = {
    "RD": "enable_raw_doppler",
    "SA": "enable_source_aware",
    "RP": "enable_go2_roll_pitch_prior",
    "HV": "enable_go2_horizontal_velocity_prior",
}
EXPECTED_IDS = tuple(f"AB{value:04b}" for value in range(16))
PAIRWISE_TERMS = (
    ("RD", "SA"),
    ("RD", "RP"),
    ("RD", "HV"),
    ("SA", "RP"),
    ("SA", "HV"),
    ("RP", "HV"),
)
LOO_BY_MODULE = {
    "RD": "AB0111",
    "SA": "AB1011",
    "RP": "AB1101",
    "HV": "AB1110",
}


class Clean2AblationError(ValueError):
    """The tracked factorial design or a requested variant is invalid."""


@dataclass(frozen=True)
class AblationVariant:
    ablation_id: str
    bits: str
    label: str
    features: tuple[bool, bool, bool, bool]
    alias_roles: tuple[str, ...]

    def feature_mapping(self) -> dict[str, bool]:
        return {
            FEATURE_BY_MODULE[module]: enabled
            for module, enabled in zip(MODULE_ORDER, self.features)
        }

    def effect_code(self, module: str) -> int:
        if module not in MODULE_ORDER:
            raise Clean2AblationError(f"Unknown CLEAN2 module: {module}")
        return 1 if self.features[MODULE_ORDER.index(module)] else -1


@dataclass(frozen=True)
class AblationCatalog:
    path: Path
    source_sha256: str
    payload: dict[str, Any]
    variants: tuple[AblationVariant, ...]

    def variant(self, ablation_id: str) -> AblationVariant:
        for variant in self.variants:
            if variant.ablation_id == ablation_id:
                return variant
        raise Clean2AblationError(f"Unknown CLEAN2 ablation id: {ablation_id}")


def load_ablation_catalog(path: str | Path) -> AblationCatalog:
    """Load and fail closed on any bit-order or 16-cell design drift."""

    source = Path(path).resolve(strict=True)
    payload = load_yaml_mapping(source)
    if payload.get("schema_version") != "paper_rebuild.clean2_ablation_2pow4.v1":
        raise Clean2AblationError("CLEAN2 ablation schema mismatch")
    if payload.get("stage_id") != "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18":
        raise Clean2AblationError("CLEAN2 ablation stage identity mismatch")
    if payload.get("backbone") != "strong_dual_yaw_EKF":
        raise Clean2AblationError("CLEAN2 factorial backbone drifted")
    bit_contract = payload.get("bit_contract")
    if not isinstance(bit_contract, Mapping):
        raise Clean2AblationError("CLEAN2 bit contract is missing")
    if tuple(bit_contract.get("bit_string_left_to_right") or ()) != MODULE_ORDER:
        raise Clean2AblationError("CLEAN2 bit string must be left-to-right RD,SA,RP,HV")
    if tuple(bit_contract.get("feature_fields_left_to_right") or ()) != tuple(
        FEATURE_BY_MODULE[module] for module in MODULE_ORDER
    ):
        raise Clean2AblationError("CLEAN2 bit-to-feature mapping drifted")

    raw_variants = payload.get("variants")
    if not isinstance(raw_variants, list) or len(raw_variants) != 16:
        raise Clean2AblationError("CLEAN2 factorial must contain exactly 16 variants")
    variants: list[AblationVariant] = []
    for expected_id, raw in zip(EXPECTED_IDS, raw_variants):
        if not isinstance(raw, Mapping):
            raise Clean2AblationError("CLEAN2 ablation variant must be a mapping")
        bits = expected_id.removeprefix("AB")
        if raw.get("ablation_id") != expected_id or str(raw.get("bits")) != bits:
            raise Clean2AblationError("CLEAN2 ablation id/order differs from binary order")
        expected_flags = tuple(character == "1" for character in bits)
        actual_flags = tuple(raw.get(module) for module in MODULE_ORDER)
        if actual_flags != expected_flags or not all(isinstance(value, bool) for value in actual_flags):
            raise Clean2AblationError(f"CLEAN2 feature flags disagree with {expected_id}")
        aliases = raw.get("alias_roles") or []
        if not isinstance(aliases, list) or not all(isinstance(value, str) for value in aliases):
            raise Clean2AblationError("CLEAN2 alias roles are invalid")
        variants.append(
            AblationVariant(
                ablation_id=expected_id,
                bits=bits,
                label=str(raw.get("label") or ""),
                features=expected_flags,
                alias_roles=tuple(aliases),
            )
        )
    if "canonical_strong" not in variants[0].alias_roles:
        raise Clean2AblationError("AB0000 must alias canonical strong")
    if "canonical_LegSA" not in variants[-1].alias_roles:
        raise Clean2AblationError("AB1111 must alias canonical LegSA")
    for module, ablation_id in LOO_BY_MODULE.items():
        expected_alias = f"LOO_NO_{module}"
        if expected_alias not in next(v for v in variants if v.ablation_id == ablation_id).alias_roles:
            raise Clean2AblationError(f"Sentinel alias mismatch for {module}")
    formula = payload.get("factorial_effect_contract")
    if not isinstance(formula, Mapping):
        raise Clean2AblationError("Frozen factorial effect contract is missing")
    if formula.get("coefficient_formula") != "beta_term=sum(x_term*y)/16":
        raise Clean2AblationError("Factorial coefficient formula drifted")
    if formula.get("reported_effect_formula") != "effect_term=2*beta_term":
        raise Clean2AblationError("Factorial reported-effect formula drifted")
    return AblationCatalog(
        path=source,
        source_sha256=sha256_file(source),
        payload=payload,
        variants=tuple(variants),
    )


def ablation_id_from_features(features: Mapping[str, bool]) -> str:
    """Encode feature flags without reversing the human-visible bit order."""

    bits: list[str] = []
    for module in MODULE_ORDER:
        field = FEATURE_BY_MODULE[module]
        value = features.get(field)
        if not isinstance(value, bool):
            raise Clean2AblationError(f"Missing boolean feature: {field}")
        bits.append("1" if value else "0")
    return "AB" + "".join(bits)


def factorial_design_rows(catalog: AblationCatalog) -> list[dict[str, Any]]:
    """Return the fixed design matrix used by registry and analysis."""

    rows: list[dict[str, Any]] = []
    for variant in catalog.variants:
        row: dict[str, Any] = {
            "ablation_id": variant.ablation_id,
            "bits": variant.bits,
            "label": variant.label,
            **variant.feature_mapping(),
        }
        row.update({f"x_{module}": variant.effect_code(module) for module in MODULE_ORDER})
        rows.append(row)
    return rows


def require_complete_metric_vector(
    catalog: AblationCatalog,
    values_by_ablation: Mapping[str, float],
) -> list[float]:
    """Return finite values in frozen design order; partial tables are rejected."""

    import math

    if set(values_by_ablation) != set(EXPECTED_IDS):
        raise Clean2AblationError("Factorial metric vector must contain all and only 16 variants")
    values = [float(values_by_ablation[variant.ablation_id]) for variant in catalog.variants]
    if not all(math.isfinite(value) for value in values):
        raise Clean2AblationError("Factorial metric vector contains NaN or infinity")
    return values


def effect_coefficient(
    catalog: AblationCatalog,
    values_by_ablation: Mapping[str, float],
    term: Sequence[str],
) -> float:
    """Compute beta=sum(product(x_j)*y)/16 under the pre-frozen coding."""

    modules = tuple(term)
    if not modules or len(set(modules)) != len(modules) or any(module not in MODULE_ORDER for module in modules):
        raise Clean2AblationError("Factorial term must contain unique known modules")
    values = require_complete_metric_vector(catalog, values_by_ablation)
    total = 0.0
    for variant, value in zip(catalog.variants, values):
        code = 1
        for module in modules:
            code *= variant.effect_code(module)
        total += code * value
    return total / 16.0


def reported_factorial_effect(
    catalog: AblationCatalog,
    values_by_ablation: Mapping[str, float],
    term: Sequence[str],
) -> float:
    """Report the conventional doubled coefficient (high-minus-low contrast)."""

    return 2.0 * effect_coefficient(catalog, values_by_ablation, term)


def descriptive_effect_label(effect: float, *, tolerance: float = 1.0e-12) -> str:
    """Label a lower-is-better contrast without significance or causal wording."""

    if abs(effect) <= tolerance:
        return "neutral"
    return "helpful" if effect < 0.0 else "harmful"
