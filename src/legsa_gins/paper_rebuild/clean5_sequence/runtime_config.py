"""CLEAN5 runtime-config preparation from sealed BY2 scientific profiles.

No solver or evaluator is invoked. Native CLEAN2R2A identity transport is kept
separate from the actual CLEAN5 sequence identity recorded by the outer audit.
Only the three explicitly authorized C-03 categories may differ from a sealed
profile. All five profiles must pass the joint BY2/BY2H/BY2O parameter gate
before either sequence's runtime configuration files are written.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..final_v23_clean_parity import active_runtime_config
from ..manifest import sha256_file

METHODS = {
    "F01": "single_antenna_EKF",
    "F02": "basic_dual_yaw_EKF",
    "F03": "AB0000",
    "A04": "AB1011",
    "F04": "AB1111",
}
CONFIG_FILENAMES = {"F01": "F01.yaml", "F02": "F02.yaml", "F03": "AB0000.yaml",
                    "A04": "AB1011.yaml", "F04": "AB1111.yaml"}
NATIVE_IDENTITY = {
    "stage_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD",
    "protocol_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION",
    "case_id": "CLEAN1_BY2_CLEAN_NORMAL",
    "data_mode": "real_clean",
}
PATH_IDENTITY_KEYS = frozenset({
    "imupath", "gnsspath", "raw_doppler_factor_path", "go2_attitude_prior_path",
    "go2_horizontal_velocity_prior_path", "outputpath", "stage_id", "protocol_id",
    "case_id", "run_id", "run_label", "data_mode", "algorithm_id",
})
SEQUENCE_DEFINITION_KEYS = frozenset({"starttime", "endtime", "initpos", "initatt"})
BACKEND_PROVENANCE_KEYS = frozenset({
    "raw_doppler_backend_source_files", "raw_doppler_backend_source_hashes",
    "helper_executable_hash", "obs_source_hash", "nav_source_hash", "conversion_config_hash",
})
OVERRIDE_CATEGORIES = {
    "a_path_and_identity": PATH_IDENTITY_KEYS,
    "b_sequence_definition": SEQUENCE_DEFINITION_KEYS,
    "c_backend_provenance": BACKEND_PROVENANCE_KEYS,
}
ALLOWED_OVERRIDES = frozenset().union(*OVERRIDE_CATEGORIES.values())
PATH_ROLES = {
    "imupath": "imu_runtime_input",
    "gnsspath": "gnss_runtime_input",
    "raw_doppler_factor_path": "raw_doppler_provider",
    "go2_attitude_prior_path": "go2_attitude_prior",
    "go2_horizontal_velocity_prior_path": "go2_horizontal_velocity_prior",
}
BACKEND_CONFIG_KEYS = (
    "raw_doppler_backend_source_files", "raw_doppler_backend_source_hashes",
    "helper_executable_hash", "obs_source_hash", "nav_source_hash",
    "conversion_config_hash", "raw_doppler_backend_id", "covariance_policy",
)
PROFILE_FLAGS = frozenset({
    "enable_dual_yaw", "enable_receiver_velocity", "enable_raw_doppler",
    "enable_source_aware", "enable_go2_roll_pitch_prior",
    "enable_go2_horizontal_velocity_prior",
})
SEALED_CONFIG_SHA256 = {
    "F01": "4b0553bc06fb0046ed66379a9b07b2c5d40fa1bbfd95bffbff0a39ebf9d3068f",
    "F02": "5f2f078e273ec31f7bf99859eb8e48abeeb25adafabe96acb5e0ee2e90c535ab",
    "F03": "25c627ece8c7663e87f89d91e69b3a203ad5229788759904554da89a22f5fa75",
    "A04": "61118df6084647e613df1af31a2f8e8ce14892b5752e51c33645b64df9a92c96",
    "F04": "c8837578a153fe29e345d6f8148beba8ebb971e0dd7fd0d0499ba338a7bbb799",
}
SEALED_MANIFEST_SHA256 = "dbf0b2913eabc9ac1f8fec0f1a32b05e172d2fcec70666fbfe9a5a4ccd91e333"
NATIVE_IDENTITY_STATIC_AUDIT = {
    "source": "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp",
    "source_sha256": "36d380d4f6db066768b53236ef1b2d2bb17cfca9178390623e81cc313a8d4703",
    "identity_guard_lines": [259, 261, 291, 312],
    "method_flag_guard_lines": [369, 400],
    "numeric_load_lines": [548, 585],
    "finding": "CLEAN2R2A stage/protocol/case/data_mode route formal identity and method checks; "
               "starttime/endtime/initpos/initatt load independently from numerical config fields",
    "formal_validation_disabled": False,
    "cpp_modified": False,
    "solver_invoked_to_check_identity": False,
    "port_runtime": {
        "source": "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp",
        "source_sha256": "9a00eabdbbd7d629da4e476461a69872c9eb26550a9c286fcc59931e1d04bc99",
        "formal_identity_provenance_lines": [1114, 1137],
        "counter_validation_lines": [200, 245, 1543, 1544],
        "initial_state_lines": [36, 44, 1404],
        "window_lines": [1347, 1357, 1417, 1436, 1464],
        "finding": "runFromConfig preserves loader-validated formal phase/run identity and sets provenance "
                   "flags; validateFormalRuntimeCounters routes on algorithm_id and AB bits. The state "
                   "initialization and effective window consume configured numeric values independently",
        "counter_checks_disabled": False,
        "native_stage_selects_new_filter_parameters": False,
    },
}


class RuntimeConfigError(RuntimeError):
    """An unsupported config difference or source identity blocks preparation."""

    def __init__(self, message: str, *, details: Any = None, method_id: str | None = None):
        super().__init__(message)
        self.details = details
        self.method_id = method_id


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mapping(text: str) -> dict[str, Any]:
    value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise RuntimeConfigError("runtime config is not a mapping")
    # Reject non-finite values even where YAML would otherwise accept them.
    json.dumps(value, allow_nan=False)
    return value


def scientific_runtime_config_hash(text: str) -> str:
    """Use exactly canonical541.runner.scientific_runtime_config_hash rules."""
    payload = _scientific_payload(text)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return _sha(encoded)


def _scientific_payload(text: str) -> dict[str, Any]:
    payload = _mapping(text)
    for field in ("run_id", "run_label", "case_id", "algorithm_id", "outputpath"):
        payload.pop(field, None)
    for field in PATH_ROLES:
        if field in payload:
            payload[field] = f"input-role://{field}"
    return payload


def frozen_parameter_hash(text: str) -> str:
    """Canonical scientific normalization, then remove exactly categories a/b/c."""
    payload = _scientific_payload(text)
    for field in ALLOWED_OVERRIDES:
        payload.pop(field, None)
    return _sha(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def parameter_diff(reference: Mapping[str, Any], actual: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return every changed/added/removed key; no tolerance or hidden ignores."""
    missing = {"missing_key": True}
    return [
        {"key": key, "sealed": reference.get(key, missing), "actual": actual.get(key, missing),
         "allowed": key in ALLOWED_OVERRIDES,
         "category": next((name for name, keys in OVERRIDE_CATEGORIES.items() if key in keys), None)}
        for key in sorted(set(reference) | set(actual))
        if key not in reference or key not in actual or reference[key] != actual[key]
    ]


def apply_runtime_overrides(reference: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Apply only C-03D keys; even a no-op forbidden-key override is rejected."""
    forbidden = sorted(set(overrides) - ALLOWED_OVERRIDES)
    if forbidden:
        raise RuntimeConfigError("runtime override keys are outside C-03D whitelist", details=forbidden)
    missing = sorted(set(overrides) - set(reference))
    if missing:
        raise RuntimeConfigError("runtime overrides are not replacements of existing fields", details=missing)
    result = {**reference, **overrides}
    json.dumps(result, allow_nan=False)
    return result


def load_sealed_profiles(base_provider_gate: str | Path) -> dict[str, Any]:
    """Read only the provider gate, output-seal metadata and five sealed configs."""
    gate_path = Path(base_provider_gate).resolve(strict=True)
    gate_bytes = gate_path.read_bytes()
    gate = json.loads(gate_bytes)
    if (gate_path.name != "CLEAN2R2A1_ACTIVE_PROVIDER_FREEZE.json"
            or gate.get("passed") is not True
            or gate.get("stage_id") != "CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME"):
        raise RuntimeConfigError("sealed CLEAN2R2A1 provider gate identity failed")
    stage = gate_path.parent.parent
    manifest_path = stage / "07_OUTPUT_SEAL" / "OUTPUT_HASH_MANIFEST.csv"
    journal_path = stage / "07_OUTPUT_SEAL" / "OUTPUT_SEAL_JOURNAL.json"
    journal_bytes = journal_path.read_bytes()
    journal = json.loads(journal_bytes)
    manifest_bytes = manifest_path.read_bytes()
    if (journal.get("passed") is not True
            or journal.get("all_outputs_sealed_before_trace") is not True
            or journal.get("output_hash_manifest_sha256") != SEALED_MANIFEST_SHA256
            or _sha(manifest_bytes) != SEALED_MANIFEST_SHA256):
        raise RuntimeConfigError("sealed CLEAN2R2A1 output-hash manifest failed")
    rows = list(csv.DictReader(manifest_bytes.decode("utf-8-sig").splitlines()))
    runtime_root = (stage / "06_FORMAL_RUNS").resolve(strict=True)
    profiles = {}
    for method, configuration in METHODS.items():
        matches = [row for row in rows if row.get("algorithm_id") == configuration
                   and row.get("relative_path", "").endswith("/CLEAN2R2A1_RUNTIME_CONFIG.yaml")]
        if len(matches) != 1:
            raise RuntimeConfigError(f"sealed profile row is not unique: {method}")
        row = matches[0]
        path = (runtime_root / row["relative_path"]).resolve(strict=True)
        if runtime_root not in path.parents:
            raise RuntimeConfigError("sealed config escaped its runtime root")
        data = path.read_bytes()
        digest = _sha(data)
        if (row.get("sealed_before_trace") != "True"
                or digest != SEALED_CONFIG_SHA256[method]
                or digest != row.get("sha256") or len(data) != int(row["size_bytes"])):
            raise RuntimeConfigError(f"sealed runtime config hash/size mismatch: {method}")
        text = data.decode("utf-8")
        values = _mapping(text)
        if values.get("algorithm_id") != configuration or any(
                values.get(key) != value for key, value in NATIVE_IDENTITY.items()):
            raise RuntimeConfigError(f"sealed native profile identity mismatch: {method}")
        profiles[method] = {"path": str(path), "sha256": digest, "text": text, "values": values}
    return {"profiles": profiles, "base_provider_gate": str(gate_path),
            "base_provider_gate_sha256": _sha(gate_bytes),
            "output_hash_manifest": str(manifest_path), "output_hash_manifest_sha256": _sha(manifest_bytes),
            "output_seal_journal": str(journal_path), "output_seal_journal_sha256": _sha(journal_bytes)}


def _literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _native_override_literal(key: str, value: Any) -> str:
    if key in {"raw_doppler_backend_source_files", "raw_doppler_backend_source_hashes"}:
        # Sealed YAML stores list/dict values. The frozen C++ loader retains the
        # unquoted JSON collection as a string; UTF-8 avoids literal \u escapes.
        expected_type = list if key.endswith("source_files") else dict
        if not isinstance(value, expected_type):
            raise RuntimeConfigError(f"native provenance collection has wrong type: {key}")
    return _literal(value)


def _template_from_sealed(sealed: Mapping[str, Any]) -> str:
    """Rebuild a sealed profile through the maintained numerical template."""
    auxiliary = {
        "raw_doppler": sealed["raw_doppler_factor_path"],
        "go2_roll_pitch": sealed["go2_attitude_prior_path"],
        "go2_horizontal_velocity": sealed["go2_horizontal_velocity_prior_path"],
    }
    kwargs = {"method_id": "LegSA_Paper_V1", "auxiliary_paths": auxiliary,
              "run_id": str(sealed["run_id"])}
    args = (Path(sealed["imupath"]), Path(sealed["gnsspath"]), Path(sealed["outputpath"]))
    base = _mapping(active_runtime_config(*args, **kwargs))
    profile_fields = PROFILE_FLAGS | frozenset(NATIVE_IDENTITY) | {"algorithm_id"}
    unexpected = [key for key in base if key not in sealed or (
        base[key] != sealed[key] and key not in profile_fields)]
    if unexpected:
        raise RuntimeConfigError("active_runtime_config numerical template differs from sealed profile",
                                 details=unexpected)
    extras = {key: _literal(value) for key, value in sealed.items()
              if key not in base or key in profile_fields}
    rebuilt = active_runtime_config(*args, **kwargs, extra_config=extras)
    differences = parameter_diff(sealed, _mapping(rebuilt))
    if differences:
        raise RuntimeConfigError("maintained template did not reproduce sealed profile", details=differences)
    return rebuilt


def _validate_contract(contract: Mapping[str, Any]) -> None:
    identity = contract["identity"]
    expected_modes = {"BY2H": "real_by2h_raw", "BY2O": "real_by2o_raw"}
    if expected_modes.get(identity.get("dataset_id")) != identity.get("data_mode"):
        raise RuntimeConfigError("runtime config requires a frozen BY2H/BY2O identity")
    if contract["method_set"]["methods"] != METHODS or contract["method_set"]["execution_order"] != list(METHODS):
        raise RuntimeConfigError("runtime method identities/order differ from frozen five profiles")
    window = contract["window_contract"]
    if not float(window["t_start"]) < float(window["t_end"]):
        raise RuntimeConfigError("runtime window is empty or reversed")


def build_runtime_config(*, method_id: str, contract: Mapping[str, Any],
                         provider_manifest: Mapping[str, Any], sealed_profile: Mapping[str, Any],
                         output_path: str | Path) -> tuple[str, dict[str, Any]]:
    """Build one config in memory, rejecting all changes outside C-03D's list."""
    _validate_contract(contract)
    if method_id not in METHODS:
        raise RuntimeConfigError(f"unknown frozen method: {method_id}")
    sealed_text = str(sealed_profile["text"])
    if (_sha(sealed_text.encode("utf-8")) != SEALED_CONFIG_SHA256[method_id]
            or sealed_profile.get("sha256") != SEALED_CONFIG_SHA256[method_id]):
        raise RuntimeConfigError("sealed profile bytes were changed after validation", method_id=method_id)
    sealed = _mapping(sealed_text)
    if sealed.get("algorithm_id") != METHODS[method_id]:
        raise RuntimeConfigError("wrong sealed profile for selected method")
    text = _template_from_sealed(sealed)
    actual = _mapping(text)
    identity = contract["identity"]
    for key in ("dataset_id", "stage_id", "data_mode"):
        if provider_manifest.get(key) != identity[key]:
            raise RuntimeConfigError(f"fresh provider identity mismatch: {key}", method_id=method_id)
    backend = provider_manifest.get("raw_doppler_backend")
    if not isinstance(backend, Mapping):
        raise RuntimeConfigError("fresh provider manifest has no raw_doppler_backend")
    fresh_provenance = {}
    for key in BACKEND_CONFIG_KEYS:
        if key not in backend:
            raise RuntimeConfigError(f"fresh provider backend lacks native provenance: {key}")
        fresh_provenance[key] = backend[key]
    expected_sources = [f"{identity['fix_prefix']}/gnss1-raw.csv", f"{identity['fix_prefix']}/gnss1-status.csv"]
    expected_hashes = {path: identity["raw_files_sha256"][path] for path in expected_sources}
    if (fresh_provenance["raw_doppler_backend_source_files"] != expected_sources
            or fresh_provenance["raw_doppler_backend_source_hashes"] != expected_hashes):
        raise RuntimeConfigError("fresh backend source lineage differs from sequence hash lock", method_id=method_id)
    for key in ("raw_doppler_backend_id", "covariance_policy"):
        if fresh_provenance[key] != sealed.get(key):
            raise RuntimeConfigError(f"fresh backend changes frozen scientific field: {key}", method_id=method_id)
    for key in BACKEND_PROVENANCE_KEYS - {"raw_doppler_backend_source_files", "raw_doppler_backend_source_hashes"}:
        digest = fresh_provenance[key]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise RuntimeConfigError(f"fresh backend has invalid SHA256: {key}", method_id=method_id)
    artifacts = provider_manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise RuntimeConfigError("fresh provider manifest has no artifacts mapping")
    overrides = {key: fresh_provenance[key] for key in BACKEND_PROVENANCE_KEYS}
    # Preserve the sealed YAML collection types and unquoted native JSON form.
    for key in ("raw_doppler_backend_source_files", "raw_doppler_backend_source_hashes"):
        expected_type = list if key.endswith("source_files") else dict
        if not isinstance(sealed.get(key), expected_type):
            raise RuntimeConfigError(f"sealed native provenance has wrong collection type: {key}")
    for field, role in PATH_ROLES.items():
        entry = artifacts.get(role)
        if not isinstance(entry, Mapping) or not entry.get("path"):
            raise RuntimeConfigError(f"fresh provider manifest lacks artifact path: {role}")
        overrides[field] = str(entry["path"])
    init = contract["initialization_contract"]
    run_id = f"CLEAN5_{identity['dataset_id']}_{method_id}_{METHODS[method_id]}"
    overrides.update({**NATIVE_IDENTITY, "run_id": run_id, "run_label": run_id,
                      "outputpath": str(output_path), "starttime": contract["window_contract"]["t_start"],
                      "endtime": contract["window_contract"]["t_end"],
                      "initpos": init["initpos"], "initatt": init["initatt"]})
    actual = apply_runtime_overrides(actual, overrides)
    differences = parameter_diff(sealed, actual)
    forbidden = [row for row in differences if not row["allowed"]]
    if forbidden:
        raise RuntimeConfigError("runtime config contains non-whitelisted parameter differences", details=forbidden)
    if any(actual.get(key) != sealed.get(key) for key in PROFILE_FLAGS):
        raise RuntimeConfigError("runtime profile flags differ from sealed profile", method_id=method_id)
    # Replace only literal value lines, preserving every other template token.
    lines = []
    seen = set()
    for line in text.splitlines():
        key = line.split(":", 1)[0] if ":" in line and not line.startswith("#") else None
        if key in overrides:
            if key in seen:
                raise RuntimeConfigError(f"duplicate runtime key: {key}")
            seen.add(key)
            line = f"{key}: {_native_override_literal(key, overrides[key])}"
        lines.append(line)
    if seen != set(overrides):
        raise RuntimeConfigError("runtime template lacks an authorized override key")
    rendered = "\n".join(lines) + "\n"
    if _mapping(rendered) != actual:
        raise RuntimeConfigError("runtime serialization changed parameter values")
    return rendered, {
        "method_id": method_id, "effective_configuration_id": METHODS[method_id],
        "config_relative_path": CONFIG_FILENAMES[method_id],
        "actual_identity": {key: identity[key] for key in ("dataset_id", "stage_id", "data_mode")},
        "native_identity": {key: actual[key] for key in (*NATIVE_IDENTITY, "algorithm_id", "run_id", "run_label")},
        "native_identity_is_compatibility_transport_only": True,
        "native_identity_changes_numerical_parameters": False,
        "native_identity_static_audit": NATIVE_IDENTITY_STATIC_AUDIT,
        "initialization_source": {"contract_rule": init["rule_source"],
                                  "position_epoch_R1": init["position_epoch_R1"], "yaw_epoch_R1": init["yaw_epoch_R1"]},
        "sealed_profile_path": sealed_profile.get("path"), "sealed_profile_sha256": sealed_profile.get("sha256"),
        "sealed_scientific_runtime_config_sha256": scientific_runtime_config_hash(str(sealed_profile["text"])),
        "scientific_runtime_config_sha256": scientific_runtime_config_hash(rendered),
        "scientific_runtime_config_hash": scientific_runtime_config_hash(rendered),
        "sealed_frozen_parameter_hash": frozen_parameter_hash(sealed_text),
        "frozen_parameter_hash": frozen_parameter_hash(rendered),
        "profile_flags": {key: actual.get(key) for key in sorted(PROFILE_FLAGS)},
        "runtime_config_sha256": _sha(rendered.encode("utf-8")),
        "allowed_override_keys": sorted(ALLOWED_OVERRIDES), "parameter_differences": differences,
        "override_categories": {name: sorted(keys) for name, keys in OVERRIDE_CATEGORIES.items()},
        "non_whitelisted_difference_count": 0, "solver_execution_count": 0,
        "evaluator_execution_count": 0, "trace_content_read_count": 0,
    }


BACKEND_SOURCE_AUDIT = (
    {"source": "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp",
     "sha256": "36d380d4f6db066768b53236ef1b2d2bb17cfca9178390623e81cc313a8d4703",
     "line_ranges": [[111, 125], [753, 786]],
     "finding": "Lines 773-784 read all six fields as strings. Numeric controls are separately loaded "
                "at 759-769; stringOrDefault strips only outer quotes at 111-125."},
    {"source": "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp",
     "sha256": "9a00eabdbbd7d629da4e476461a69872c9eb26550a9c286fcc59931e1d04bc99",
     "line_ranges": [[68, 73], [1276, 1283]],
     "finding": "None of the six field names is referenced. The config is passed to the provider loader; "
                "status is transported to output and its enablement flags are retained."},
    {"source": "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp",
     "sha256": "4d2e329a1f6a11ed232941c3150a5569791f7ac5fceb0362e91e5dd856dc6a50",
     "line_ranges": [[125, 144], [996, 1055]],
     "finding": "None of the six field names is referenced. Numeric residual/H/R use velocity, std, "
                "lever arm and frozen controls at 1016-1055. Provider admission is checked at 1012/1039."},
    {"source": "cpp/legsa_v23_port_core/src/factors/raw_doppler_factor_loader.cpp",
     "sha256": "6634a30568ac943a778c17c3faef133c820a6f93a246d6ed9a9f5b251cec6249",
     "line_ranges": [[96, 107], [130, 136], [194, 207]],
     "finding": "Integrity gates require source identities, lowercase SHA256 values and row/config "
                "obs/nav/conversion equality. They can block malformed/mismatched inputs; hash bytes "
                "are not converted to numerical filter values. Status records the hashes."},
    {"source": "cpp/legsa_v23_port_core/src/factors/raw_doppler_factor.cpp",
     "sha256": "46786a1a0e4e31db2aba87023d754a5bd2e6480cd57be1eeec4f41f6dcc2946f",
     "line_ranges": [[14, 27]],
     "finding": "isProviderBacked includes lineage_valid, so integrity admission has indirect influence "
                "on accepted measurements. Standard deviation and residual functions use numerical fields only."},
    {"source": "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp",
     "sha256": "e28c94befae770b0f652da8918c068bf04855c5d3ccb225678d0c9e2dbcd4872",
     "line_ranges": [[549, 558]],
     "finding": "All six provenance values are serialized into the output manifest."},
)


def audit_backend_provenance_sources(code_root: str | Path) -> dict[str, Any]:
    """Bind the read-only source interpretation to exact unchanged C++ bytes."""
    root = Path(code_root).resolve(strict=True)
    sources = []
    for item in BACKEND_SOURCE_AUDIT:
        path = (root / item["source"]).resolve(strict=True)
        if root not in path.parents or _sha(path.read_bytes()) != item["sha256"]:
            raise RuntimeConfigError(f"backend provenance source audit identity changed: {item['source']}")
        lines = path.read_text(encoding="utf-8").splitlines()
        references = {key: [n for n, line in enumerate(lines, 1) if key in line]
                      for key in sorted(BACKEND_PROVENANCE_KEYS)}
        if path.name in {"port_runtime.cpp", "gi_engine.cpp"} and any(references.values()):
            raise RuntimeConfigError(f"new direct backend provenance reference: {item['source']}")
        sources.append({**item, "field_reference_lines": references})
    return {
        "passed": True, "sources": sources, "read_only": True,
        "hash_bytes_used_as_numerical_filter_values": False,
        "globally_manifest_only": False,
        "integrity_and_admission_checks_present": True,
        "integrity_admission_can_block_invalid_inputs": True,
        "integrity_and_formal_validation_preserved": True,
        "cpp_modified": False, "binary_rebuilt": False, "solver_execution_count": 0,
    }


def _diff_markdown(report: Mapping[str, Any]) -> str:
    lines = ["# Runtime config diff versus sealed CLEAN2R2A1 BY2", "",
             f"Sequence: {report['dataset_id']}; status: {report['status']}; solver/evaluator executions: 0.", "",
             "Native stage/protocol/case/data_mode remain approved compatibility transport; the CLEAN5 "
             "wrapper records the true sequence identity. Profile flags and all non-whitelisted values are preserved.", "",
             "## Authorized replacement categories", ""]
    for name, keys in OVERRIDE_CATEGORIES.items():
        lines.append(f"- {name}: " + ", ".join(f"`{key}`" for key in sorted(keys)))
    lines.extend(["", "The changed-key set must be a subset of exactly the union above. "
                  "raw_doppler_backend_id and covariance_policy remain frozen.", "",
                  "## Joint frozen parameter gate", "",
                  "scientific_runtime_config_hash retains provenance and is recorded without a cross-sequence equality gate. "
                  "frozen_parameter_hash uses the same normalization and then removes every category (a)/(b)/(c) key.", "",
                  "| Profile | BY2 frozen_parameter_hash | BY2H | BY2O | Gate |",
                  "| --- | --- | --- | --- | --- |"])
    for gate in report["joint_frozen_parameter_gate"]["profiles"]:
        hashes = gate["frozen_parameter_hashes"]
        lines.append(f"| {gate['method_id']} / {gate['effective_configuration_id']} | {hashes['BY2']} | "
                     f"{hashes['BY2H']} | {hashes['BY2O']} | PASS |")
    for profile in report["profiles"]:
        lines.extend(["", f"## {profile['method_id']} / {profile['effective_configuration_id']}", "",
                      f"Sealed config SHA256: `{profile['sealed_profile_sha256']}`.",
                      f"Rendered config SHA256: `{profile['runtime_config_sha256']}`.",
                      f"BY2 scientific hash: `{profile['sealed_scientific_runtime_config_sha256']}`.",
                      f"Rendered scientific hash: `{profile['scientific_runtime_config_hash']}`.", ""])
        for category in OVERRIDE_CATEGORIES:
            lines.extend([f"### {category}", "", "| Key | Sealed BY2 | Rendered sequence |",
                          "| --- | --- | --- |"])
            selected = [row for row in profile["parameter_differences"] if row["category"] == category]
            for row in selected:
                cells = [str(row["key"]), _literal(row["sealed"]), _literal(row["actual"])]
                lines.append("| " + " | ".join(cell.replace("|", "&#124;").replace("\n", "\\n") for cell in cells) + " |")
            if not selected:
                lines.append("| (no changes) | | |")
            lines.append("")
    lines.extend(["## Read-only backend source audit", "",
                  "The six values do not enter residual, H, R, state initialization or frozen filter-parameter arithmetic. "
                  "They are not globally manifest-only: provider integrity/lineage checks can reject malformed or "
                  "mismatched inputs, and lineage_valid participates in provider admission. These checks remain enabled.", ""])
    for item in report["backend_provenance_source_audit"]["sources"]:
        positions = ", ".join(f"{lo}-{hi}" for lo, hi in item["line_ranges"])
        lines.extend([f"- `{item['source']}` lines {positions}; SHA256 `{item['sha256']}`. {item['finding']}"])
    lines.extend(["", "## Frozen executable for separately authorized C-04", "",
                  "```json", json.dumps(report["frozen_executable"], sort_keys=True, indent=2), "```", "",
                  "C-04 must use this absolute executable path and SHA256. No executable was built or invoked by config rendering.", ""])
    return "\n".join(lines)


def render_joint_runtime_configs(*, contracts: Mapping[str, Mapping[str, Any]],
                                 provider_manifests: Mapping[str, Mapping[str, Any]],
                                 base_provider_gate: str | Path,
                                 output_dirs: Mapping[str, str | Path],
                                 code_root: str | Path) -> dict[str, Any]:
    """Write both sequence config sets only after all five three-way gates pass."""
    datasets = ("BY2H", "BY2O")
    for name, supplied in (("contracts", contracts), ("provider_manifests", provider_manifests),
                           ("output_dirs", output_dirs)):
        if set(supplied) != set(datasets):
            raise RuntimeConfigError(f"joint runtime rendering requires exactly BY2H and BY2O: {name}")
    outputs = {dataset: Path(output_dirs[dataset]).resolve() for dataset in datasets}
    if outputs["BY2H"] == outputs["BY2O"] or any(
            outputs[a] in outputs[b].parents for a, b in (("BY2H", "BY2O"), ("BY2O", "BY2H"))):
        raise RuntimeConfigError("joint runtime output directories overlap")
    for out in outputs.values():
        if out.exists() or not out.parent.is_dir():
            raise RuntimeConfigError("runtime config output must be new with an existing parent")
    source_audit = audit_backend_provenance_sources(code_root)
    execution_fields = (
        "code_freeze_commit", "code_commit", "code_worktree_dirty_at_generation", "execution_worktree",
        "execution_worktree_head", "execution_worktree_git_status", "execution_worktree_untracked_files",
        "execution_worktree_detached", "origin_stage_clean3_math_repair_head",
    )
    execution = {key: provider_manifests["BY2H"].get(key) for key in execution_fields}
    if any(key not in provider_manifests[d] for d in datasets for key in execution_fields) or any(
            provider_manifests["BY2O"][key] != execution[key] for key in execution_fields):
        raise RuntimeConfigError("joint provider execution snapshot fields are missing or differ")
    freeze = execution["code_freeze_commit"]
    if (not isinstance(freeze, str) or len(freeze) != 40 or any(c not in "0123456789abcdef" for c in freeze)
            or any(execution[key] != freeze for key in ("code_commit", "execution_worktree_head",
                                                       "origin_stage_clean3_math_repair_head"))
            or execution["execution_worktree"] != str(Path(code_root).resolve(strict=True))
            or execution["execution_worktree_git_status"] != ""
            or execution["execution_worktree_untracked_files"] != "all"
            or execution["execution_worktree_detached"] is not True
            or execution["code_worktree_dirty_at_generation"] is not False):
        raise RuntimeConfigError("joint provider execution snapshot is not the clean detached code freeze")
    sealed = load_sealed_profiles(base_provider_gate)
    pending: dict[str, dict[str, tuple[str, dict[str, Any]]]] = {}
    artifact_checks = {}
    for dataset in datasets:
        contract = contracts[dataset]
        if contract["identity"]["dataset_id"] != dataset:
            raise RuntimeConfigError(f"joint runtime contract key/identity mismatch: {dataset}")
        config_hash = _sha(json.dumps(contract, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        if provider_manifests[dataset].get("config_hash") != config_hash:
            raise RuntimeConfigError(f"provider contract config_hash mismatch: {dataset}")
        artifact_checks[dataset] = {}
        artifacts = provider_manifests[dataset].get("artifacts", {})
        for role in PATH_ROLES.values():
            entry = artifacts.get(role, {})
            path = Path(str(entry.get("path", "")))
            if not path.is_absolute() or path.is_symlink() or not path.is_file():
                raise RuntimeConfigError(f"rendered provider artifact path unavailable: {dataset}/{role}")
            digest = sha256_file(path)
            if digest != entry.get("sha256"):
                raise RuntimeConfigError(f"rendered provider artifact hash mismatch: {dataset}/{role}")
            artifact_checks[dataset][role] = {"path": str(path), "sha256": digest, "passed": True}
        pending[dataset] = {}
        for method in METHODS:
            pending[dataset][method] = build_runtime_config(
                method_id=method, contract=contract, provider_manifest=provider_manifests[dataset],
                sealed_profile=sealed["profiles"][method],
                output_path=outputs[dataset].parent / "04_FORMAL_RUNS" / method)
    gates = []
    for method in METHODS:
        hashes = {"BY2": frozen_parameter_hash(sealed["profiles"][method]["text"]),
                  **{dataset: frozen_parameter_hash(pending[dataset][method][0]) for dataset in datasets}}
        passed = len(set(hashes.values())) == 1
        gate = {"method_id": method, "effective_configuration_id": METHODS[method],
                "frozen_parameter_hashes": hashes, "passed": passed}
        gates.append(gate)
        if not passed:
            raise RuntimeConfigError("joint BY2/BY2H/BY2O frozen_parameter_hash mismatch",
                                     method_id=method, details=gate)
    frozen_executable = provider_manifests["BY2H"].get("frozen_executable")
    if (not isinstance(frozen_executable, Mapping)
            or frozen_executable != provider_manifests["BY2O"].get("frozen_executable")
            or not Path(str(frozen_executable.get("path", ""))).is_absolute()
            or frozen_executable.get("sha256") != "9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f"):
        raise RuntimeConfigError("joint config preparation lacks matching frozen absolute executable identity")
    joint_gate = {"passed": True, "profile_count": len(gates), "profiles": gates,
                  "scientific_runtime_config_hash_is_cross_sequence_gate": False}
    reports = {}
    for dataset in datasets:
        identity = contracts[dataset]["identity"]
        manifest = provider_manifests[dataset]
        reports[dataset] = {
            "schema_version": "paper_rebuild.clean5.runtime_config_audit.v2",
            "status": "PASS_PREPARED_NOT_EXECUTED",
            **{key: identity[key] for key in ("data_mode", "dataset_id", "stage_id")},
            "synthetic_data_used": False, "semisynthetic_data_used": False,
            "native_identity": NATIVE_IDENTITY, "true_sequence_identity_in_wrapper": True,
            "method_order": list(METHODS), "profiles": [pending[dataset][m][1] for m in METHODS],
            "sealed_source": {key: value for key, value in sealed.items() if key != "profiles"},
            "provider_manifest_identity": {key: manifest.get(key) for key in ("dataset_id", "stage_id", "data_mode")},
            "provider_artifact_revalidation": artifact_checks[dataset],
            "joint_frozen_parameter_gate": joint_gate, "backend_provenance_source_audit": source_audit,
            "override_categories": {name: sorted(keys) for name, keys in OVERRIDE_CATEGORIES.items()},
            **execution, "config_hash": manifest["config_hash"],
            "source_contract_config_hash": manifest["config_hash"],
            "frozen_executable": dict(frozen_executable),
            "solver_execution_count": 0, "evaluator_execution_count": 0, "trace_content_read_count": 0,
            "non_whitelisted_difference_count": 0,
        }
    # Materialize every JSON/Markdown document before the first mkdir/write.
    documents = {dataset: {
        "RUNTIME_CONFIG_AUDIT.json": json.dumps(reports[dataset], ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        "RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.json": json.dumps(reports[dataset], ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        "RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.md": _diff_markdown(reports[dataset]),
        **{CONFIG_FILENAMES[method]: pending[dataset][method][0] for method in METHODS},
    } for dataset in datasets}
    for dataset in datasets:
        outputs[dataset].mkdir(parents=False, exist_ok=False)
        for name, text in documents[dataset].items():
            with (outputs[dataset] / name).open("x", encoding="utf-8") as handle:
                handle.write(text)
    return {"status": "PASS_PREPARED_NOT_EXECUTED", "joint_frozen_parameter_gate": joint_gate,
            "sequences": reports}


def render_runtime_configs(**_: Any) -> dict[str, Any]:
    """A single-sequence write cannot satisfy the authorized joint rendering gate."""
    raise RuntimeConfigError("use render_joint_runtime_configs for the required BY2/BY2H/BY2O gate")
