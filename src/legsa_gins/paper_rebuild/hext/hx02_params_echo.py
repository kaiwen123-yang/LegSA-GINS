"""HX-02 parameter echo: the registered parameter items read back from native outputs.

The same extractor is applied to the CLEAN4 BY2 record and to every HX-02 run;
each run's echo must equal the CLEAN4 BY2 echo item by item (parameters are
sequence-independent). Items are parameters and parameter sources only, never
results, timings, paths or binary identities.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

CSV_LIMIT = 64 * 1024 * 1024
NATIVE_DIRS = {
    "EXT01": "02_EXT01_CLAMBDA/C00_VALIDATED_R2",
    "EXT02": "03_EXT02_CWLS/C00",
    "EXT03": "04_EXT03_YANG2024/C00",
    "EXT04": "05_EXT04_WU2025_MODULE/C00",
}
EXT04_POLICIES = ("FAR_ALL_AMBIGUITIES", "EXT04_PAR_DECLARED_POLICY_V1")
HARTLEY_KEYS = ("run_id", "backend_id", "process_policy", "sigma_fk_m", "process_noise_policy_tag", "eq52_calls",
                "joint_encoder_adapter_call_count", "state_order", "initialization_window_half_open")
GINAV_SEQUENCE_KEYS = ("data_dir", "start_time", "end_time")


def _csv(path: Path) -> list[dict[str, str]]:
    previous = csv.field_size_limit()
    csv.field_size_limit(CSV_LIMIT)
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    finally:
        csv.field_size_limit(previous)


def _unique(rows, column, where=None) -> list[str]:
    return sorted({row[column] for row in rows if where is None or where(row)})


def ext01(root: Path) -> dict[str, Any]:
    base = Path(root) / NATIVE_DIRS["EXT01"]
    summary = json.loads((base / "EXT01_C00_VALIDATED_SUMMARY.json").read_text(encoding="utf-8"))
    search = _csv(base / "EXT01_C00_VALIDATED_SEARCH_CERTIFICATES.csv")
    native = _csv(base / "EXT01_C00_VALIDATED_NATIVE_HEADING_RESULTS.csv")
    return {
        "stochastic_model": summary["stochastic_model"],
        "half_cycle_contract": summary["half_cycle_contract"],
        "rtklib_gps_l1_diagnostic_configuration": summary["rtklib_diagnostic"].get("configuration"),
        "lambda_seed_count_requested": _unique(search, "lambda_seed_count_requested"),
        "configured_node_limit": _unique(search, "configured_node_limit"),
        "receiver_order": _unique(native, "receiver_order", lambda r: r["receiver_order"] != ""),
        "dd_sign_convention": _unique(native, "dd_sign_convention", lambda r: r["dd_sign_convention"] != ""),
        "phase_convention": _unique(native, "phase_convention", lambda r: r["phase_convention"] != ""),
        "ambiguity_acceptance_test_defined": _unique(native, "ambiguity_acceptance_test_defined"),
    }


def ext02(root: Path) -> dict[str, Any]:
    base = Path(root) / NATIVE_DIRS["EXT02"]
    summary = json.loads((base / "EXT02_C00_NATIVE_SUMMARY.json").read_text(encoding="utf-8"))
    rows = _csv(base / "EXT02_C00_NATIVE_HEADING_RESULTS.csv")
    accepted = lambda r: r["method_native_accepted"] == "true"  # noqa: E731
    return {
        "baseline_length_m": summary["baseline_length_m"], "K_policy": summary["K_policy"],
        "common_backbone_yaw_std_deg": summary["common_backbone_yaw_std_deg"],
        "objective_oracle_indices": summary["objective_oracle_indices"],
        "paper_source_identity": summary["paper_source_identity"],
        "row_candidate_threshold_delta": _unique(rows, "candidate_threshold_delta", accepted),
        "row_K_policy": _unique(rows, "K_policy", accepted),
        "row_baseline_length_m": sorted({f"{float(r['baseline_length_m']):.12f}" for r in rows if accepted(r)}),
    }


def ext03(root: Path) -> dict[str, Any]:
    base = Path(root) / NATIVE_DIRS["EXT03"]
    summary = json.loads((base / "EXT03_C00_NATIVE_SUMMARY.json").read_text(encoding="utf-8"))
    registry = _csv(base / "EXT03_STOCHASTIC_PARAMETER_REGISTRY.csv")
    return {
        "model_registry": summary["model_registry"],
        "combined_system_bias_handling": summary["combined_system_bias_handling"],
        "stochastic_parameter_registry": [{k: r[k] for k in ("parameter", "value", "unit", "source",
                                                            "paper_equation_or_RTKLIB_symbol",
                                                            "primary_or_sensitivity", "trace_tuned")}
                                          for r in registry],
        "primary_variant_present": sorted({(r["system_mode"], r["constraint_mode"], r["baseline_sigma_m"])
                                           for r in _csv(base / "EXT03_C00_MODE_SUMMARY.csv")
                                           if (r["system_mode"], r["constraint_mode"], r["baseline_sigma_m"])
                                           == ("GPS_BDS_DUAL_FREQUENCY", "CONSTRAINED", "0.01")}),
    }


def ext04(root: Path) -> dict[str, Any]:
    base = Path(root) / NATIVE_DIRS["EXT04"]
    summary = json.loads((base / "EXT04_C00_NATIVE_SUMMARY.json").read_text(encoding="utf-8"))
    policy = [r for r in _csv(base / "EXT04_POLICY_PARAMETER_REGISTRY.csv") if r["policy_identity"] in EXT04_POLICIES]
    stochastic = _csv(base / "EXT04_STOCHASTIC_PARAMETER_REGISTRY.csv")
    return {
        "policy_identity": summary["policy_identity"],
        "reproduction_level": summary["reproduction_level"],
        "paper_exact_policy_status": summary["paper_exact_policy_status"],
        "policy_parameter_registry": [{k: v for k, v in r.items() if k not in ("case_id",)} for r in policy],
        "stochastic_parameter_registry": [{k: v for k, v in r.items() if k not in ("case_id",)} for r in stochastic],
    }


def file_identities(method: str, root: Path) -> dict[str, Any]:
    """Contract/schema file hashes recorded by the native run (information, not echo items:
    the frozen EXT02/EXT04 contract files gained post-native sections after the CLEAN4 run)."""
    base = Path(root) / NATIVE_DIRS[method]
    name = {"EXT01": "EXT01_C00_VALIDATED_SUMMARY.json", "EXT02": "EXT02_C00_NATIVE_SUMMARY.json",
            "EXT03": "EXT03_C00_NATIVE_SUMMARY.json", "EXT04": "EXT04_C00_NATIVE_SUMMARY.json"}[method]
    summary = json.loads((base / name).read_text(encoding="utf-8"))
    return {key: summary.get(key) or summary.get("provenance", {}).get(key)
            for key in ("phase1r_contract_sha256", "contract_hash", "heading_schema_hash", "config_hash")}


def hartley(summary_path: Path) -> dict[str, Any]:
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    return {key: summary.get(key) for key in HARTLEY_KEYS}


def ginav(config_path: Path) -> dict[str, Any]:
    """Every configuration line except the declared sequence fields, verbatim."""
    lines = Path(config_path).read_bytes().decode("ascii").splitlines(keepends=True)
    kept = [line for line in lines if line.split("=", 1)[0].strip() not in GINAV_SEQUENCE_KEYS]
    return {"non_sequence_lines_sha256": hashlib.sha256("".join(kept).encode("ascii")).hexdigest(),
            "non_sequence_line_count": len(kept), "line_count": len(lines)}


def rtklib(conf_path: Path) -> dict[str, Any]:
    return {"configuration_sha256": hashlib.sha256(Path(conf_path).read_bytes()).hexdigest()}


def compare(actual: Mapping[str, Any], reference: Mapping[str, Any]) -> dict[str, Any]:
    items = sorted(set(actual) | set(reference))
    rows = [{"item": key, "equal": json.dumps(actual.get(key), sort_keys=True, default=str)
             == json.dumps(reference.get(key), sort_keys=True, default=str)} for key in items]
    return {"item_count": len(rows), "equal_count": sum(r["equal"] for r in rows),
            "differing_items": [r["item"] for r in rows if not r["equal"]],
            "all_equal": all(r["equal"] for r in rows)}
