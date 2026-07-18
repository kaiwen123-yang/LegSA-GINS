from pathlib import Path
from typing import Any, Mapping

from legsa_gins.paper_rebuild.clean2r2a_run_registry import (
    build_clean_run_registry,
    validate_execution_protocol,
)
from legsa_gins.paper_rebuild.paths import load_yaml_mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs/paper_rebuild"


def _keys(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            result.append(str(key).casefold())
            result.extend(_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_keys(child))
    return result


def test_clean2r2a_contracts_have_no_non_clean_axis() -> None:
    paths = (
        CONFIG_DIR / "clean2r2a_ablation_2pow4.yaml",
        CONFIG_DIR / "clean2r2a_execution_protocol.yaml",
        CONFIG_DIR / "clean2r2a_statistical_contract.yaml",
    )
    forbidden = ("degradation", "perturbation", "seed")
    for path in paths:
        assert not any(fragment in key for key in _keys(load_yaml_mapping(path)) for fragment in forbidden)
    protocol = validate_execution_protocol(paths[1])
    assert protocol["scope"] == {
        "clean_case_only": True,
        "non_clean_case_count": 0,
        "non_clean_execution_authorized": False,
    }
    assert all(
        not any(fragment in key.casefold() for fragment in forbidden)
        for row in build_clean_run_registry()
        for key in row
    )
