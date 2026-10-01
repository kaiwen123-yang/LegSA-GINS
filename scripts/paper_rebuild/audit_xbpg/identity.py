#!/usr/bin/env python3
"""Read-only provenance of five retained C00 methods, not performance evidence."""
import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import yaml


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--local", required=True, type=Path)
    paths = yaml.safe_load(p.parse_args().local.read_text())["paths"]
    root, source, clean = map(Path, (paths["code_root"], paths["audit_source_worktree"], paths["clean_root"]))
    v3 = clean / "stages/CLEAN8_PROTOCOL_V3"
    bridge = clean / "stages/CLEAN6_SENSOR_MODEL_V21/01_BINARY_BRIDGE"
    freeze = json.loads((bridge / "BINARY_FREEZE.json").read_text())
    binary = source / "build/p13_v21_cpp/legsa_v23_port_core_demo"
    evaluator = clean / "16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py"
    binary_sha, evaluator_sha = sha(binary), sha(evaluator)
    assert binary_sha == freeze["new_executable"]["sha256"]
    assert evaluator_sha == "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"
    final = {r["run_id"]: r for r in json.loads((v3 / "FINAL_RUN_RECORDS.json").read_text())}
    rows = []
    flags = ["enable_dual_yaw", "enable_receiver_velocity", "enable_raw_doppler", "enable_source_aware", "enable_go2_roll_pitch_prior", "enable_go2_horizontal_velocity_prior", "enable_baseline3d"]
    echo_keys = ["enable_basic_dual_yaw_baseline", "enable_dual_yaw_update", "enable_receiver_velocity_update", "enable_raw_doppler", "source_aware_weighting_enabled", "go2_attitude_weak_prior_enabled", "go2_horizontal_velocity_prior_enabled", "enable_multi_state_qm", "fgo_feedback_enabled", "enable_qa_fallback"]
    for method, run in [("F01", "RUN_00001"), ("F02", "RUN_00002"), ("F03", "RUN_00003"), ("F04", "RUN_00004"), ("A04", "RUN_00006")]:
        record = final[run]
        assert record["method_id"] == method
        config = v3 / "03_NATIVE" / run / "V3_RUNTIME_CONFIG.yaml"
        actual = sha(config)
        assert actual == record["config_hash"], run
        manifest = v3 / "03_NATIVE" / run / "RUN_MANIFEST.json"
        echoed = json.loads(manifest.read_text())
        values = {}
        for line in config.read_text().splitlines():
            if ":" in line and not line.lstrip().startswith("#"):
                k, v = line.split(":", 1)
                values[k.strip()] = v.strip()
        rows.append(dict(version="FORMAL_PROTOCOL_V3", method=method, profile=record["effective_profile"], run_id=run,
                         source_commit=freeze["code_commit"], runner_commit=record["code_commit"], binary_sha256=binary_sha,
                         config=f"<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3/03_NATIVE/{run}/V3_RUNTIME_CONFIG.yaml",
                         config_sha256=actual, evaluator_sha256=evaluator_sha,
                         provider_hashes=json.dumps(record["provider_hashes"], sort_keys=True),
                         flags_from_config=json.dumps({k: values.get(k, "ABSENT_FALSE_B3_NOT_IN_FORMAL_SOURCE" if k == "enable_baseline3d" else "ABSENT_REQUIRES_DEFAULT_REVIEW") for k in flags}, sort_keys=True),
                         native_echo=json.dumps({k: echoed.get(k,"ABSENT") for k in echo_keys},sort_keys=True),
                         echo_manifest_sha256=sha(manifest),
                         verification="BINARY_CONFIG_EVALUATOR_LIVE_HASH_MATCH;PROVIDERS_RECORDED_HASH_ONLY",
                         note="Scalar raw HPPOSECEF heading; B3 absent. Input payload reuse not newly authorized."))
    out = root / "docs/paper_rebuild/audit_xbpg_20261001/METHOD_IDENTITY.csv"
    common = {k:"NOT_APPLICABLE" for k in rows[0]}
    rows.extend([
        dict(common,version="CURRENT_SOURCE_BUILD",method="PORT_CORE_B3_OPT_IN",source_commit="eb3cbed314693358c7c38442b6fbbb7afcf0342e",
             binary_sha256="cbf554baf9c83490e40b207b97f04ef77f51d9962f7bce463f1e644416ef789e",verification="NATIVE_TEST_RESULTS_AND_CONFIG_SMOKE",note="Release GCC11.4; 6 toy modes + 2 config fixtures current/frozen comparison; not new formal result"),
        dict(common,version="ISOLATED_NUMERIC_CANDIDATE",method="MATRIX_BOUNDS_FINITE_WRAP",source_commit="eb3cbed314693358c7c38442b6fbbb7afcf0342e+NATIVE_CANDIDATE_NUMERIC.patch",
             binary_sha256="f498eeece34611a4496e13b4a4ccb235e35dbbdf992c1a61ab69f54741ebbb54",verification="NATIVE_CANDIDATE_RESULTS.json",note="Only isolated scratch copy; no real-data use; not installed"),
    ])
    prep_path = Path(paths["audit_root"]) / "gnss_exploration/PREPARATION.json"
    if prep_path.exists():
        prep = json.loads(prep_path.read_text())
        for name, binary_hash, config_hash in [("EXPLORATORY_RTKLIB_UNCONSTRAINED",prep["rnx_sha256"],prep["config_sha256"]),
                                               ("EXPLORATORY_CURRENT_RAW_DOPPLER_HELPER",prep["helper_sha256"],sha(root/"src/legsa_gins/raw_gnss/rtklib_doppler_helper_builder.py"))]:
            rows.append(dict(common,version="XBPG_GNSS_EXPLORATORY",method=name,source_commit=prep["rtklib_source_commit"],runner_commit="2271d5a38a49aa957bbc3539244ec18ad7fa55ff",
                             binary_sha256=binary_hash,config_sha256=config_hash,verification="EXPLORATORY_IDENTITY.csv;PREPARATION.json;RD_BUILD.json",note="No LegSA/F04 substitution; RD config identity is helper source hash plus RTKLIB defaults; four full calls retained"))
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    evidence = {"binary_sha256": binary_sha, "evaluator_sha256": evaluator_sha,
                "binary_source_commit": freeze["code_commit"], "build_flags": freeze["build_flags"],
                "base_cpp_tree": subprocess.check_output(["git", "-C", str(root), "rev-parse", "eb3cbed:cpp"], text=True).strip(),
                "formal_cpp_tree": subprocess.check_output(["git", "-C", str(root), "rev-parse", freeze["code_commit"] + ":cpp"], text=True).strip(),
                "binary_bridge_record_sha256": sha(bridge / "BINARY_BRIDGE_RESULT.json"),
                "identity_only": True, "new_solver_calls": 0, "new_evaluator_calls": 0}
    (Path(paths["audit_root"]) / "FORMAL_IDENTITY.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
