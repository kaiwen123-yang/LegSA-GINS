#!/usr/bin/env python3
"""Fail-closed local-only finalization of the frozen H5 four-run native attempt."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = REPOSITORY / "scripts/paper_rebuild/run_hartley_h5_by2.py"
SPEC = importlib.util.spec_from_file_location("hartley_h5_frozen_runtime_launcher", LAUNCHER_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError("cannot load frozen H5 runtime launcher")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
h5 = launcher.h5
_verify_provider = launcher._verify_provider
_verify_frozen_files = launcher._verify_frozen_files
_validate_native_outputs = launcher._validate_native_outputs
_csv_rows = launcher._csv_rows
_policy = launcher._policy
_sigma = launcher._sigma
RUNS_DIRECTORY = launcher.RUNS_DIRECTORY
PROVIDER_DIRECTORY = launcher.PROVIDER_DIRECTORY
PROVIDER_MANIFEST = launcher.PROVIDER_MANIFEST
SUPERVISOR_EVIDENCE_SHA256 = {
    "SUPERVISOR_STORAGE_HEALTH.json": "4119e22d6a4e7a2ce09fffe371c2d1da35a03036a21bc27221afc4e702ca3125",
    "SUPERVISOR_FILE_ACCESS_AUDIT.json": "509a0e07805a3fe7c2670517598782e3d28c6d8c249c743e16ff062276601919",
    "SUPERVISOR_ATTEMPT_LEDGER.json": "50167d4e843a46fcf0a6be9c0c460905f1eaa22054de4748292f5e9ee379d2c9",
}

FINAL_RUN_DIRECTORIES = (
    "01_PRIMARY_GO2_ALLAN_EQ61_FK10MM",
    "02_FK05MM",
    "03_FK20MM",
    "04_PAPER_PROCESS_REGRESSION",
)
COMPACT_RUN_FILES = (
    "NATIVE_CONFIG.cfg", "NATIVE_SUMMARY.json", "NATIVE_FREEZE.json",
    *h5.OUTPUT_SCHEMAS.keys(), "COVARIANCE_CHECKPOINTS.npz",
)


def _variant_comparison_row(
    run_directory: Path, summary: dict[str, object]
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    nav = _csv_rows(run_directory / "NAV.csv", h5.OUTPUT_SCHEMAS["NAV.csv"])
    innovations = _csv_rows(
        run_directory / "KINEMATIC_INNOVATIONS.csv",
        h5.OUTPUT_SCHEMAS["KINEMATIC_INNOVATIONS.csv"],
    )
    nis = _csv_rows(run_directory / "NIS_DIAGNOSTICS.csv", h5.OUTPUT_SCHEMAS["NIS_DIAGNOSTICS.csv"])
    covariance = _csv_rows(
        run_directory / "COVARIANCE_DIAGONALS.csv",
        h5.OUTPUT_SCHEMAS["COVARIANCE_DIAGONALS.csv"],
    )
    runtime = _csv_rows(run_directory / "RUNTIME.csv", h5.OUTPUT_SCHEMAS["RUNTIME.csv"])
    final = nav[-1]
    innovation_values = np.asarray([
        float(row[column]) for row in innovations
        for column in ("innovation_x", "innovation_y", "innovation_z")
    ])
    nis_values = np.asarray([
        float(row["nis"]) for row in nis if int(row["contact_count"]) > 0
    ])
    covariance_columns = h5.OUTPUT_SCHEMAS["COVARIANCE_DIAGONALS.csv"][4:31]
    final_covariance_trace = sum(
        float(covariance[-1][column]) for column in covariance_columns
        if covariance[-1][column] != ""
    )
    norm = lambda columns: float(np.linalg.norm([float(final[column]) for column in columns]))
    rotation = np.asarray([[float(row[f"r{axis // 3}{axis % 3}"]) for axis in range(9)]
                           for row in nav])
    velocity = np.asarray([[float(row[column]) for column in ("vx", "vy", "vz")]
                           for row in nav])
    position = np.asarray([[float(row[column]) for column in ("px", "py", "pz")]
                           for row in nav])
    gyro_bias = np.asarray([[float(row[column]) for column in ("bgx", "bgy", "bgz")]
                            for row in nav])
    accel_bias = np.asarray([[float(row[column]) for column in ("bax", "bay", "baz")]
                             for row in nav])
    innovation_norms = np.asarray([
        np.linalg.norm([float(row[column]) for column in
                        ("innovation_x", "innovation_y", "innovation_z")])
        for row in innovations
    ])
    covariance_diagonals = np.asarray([
        float(row[column]) for row in covariance for column in covariance_columns
        if row[column] != ""
    ])
    final_covariance_diagonal = np.asarray([
        float(covariance[-1][column]) for column in covariance_columns
        if covariance[-1][column] != ""
    ])
    row = {
        "run_id": summary["run_id"],
        "comparison_scope": "NATIVE_ONLY_NO_REFERENCE_NO_RANKING",
        "process_policy": summary["process_policy"],
        "sigma_fk_m": summary["sigma_fk_m"],
        "state_rows": summary["state_rows"],
        "final_position_norm_m": norm(("px", "py", "pz")),
        "final_velocity_norm_m_per_s": norm(("vx", "vy", "vz")),
        "final_gyro_bias_norm_rad_per_s": norm(("bgx", "bgy", "bgz")),
        "final_accel_bias_norm_m_per_s2": norm(("bax", "bay", "baz")),
        "innovation_measurement_rows": len(innovations),
        "innovation_component_rms": (
            float(np.sqrt(np.mean(innovation_values ** 2))) if innovation_values.size else 0.0
        ),
        "nis_evaluated_rows": int(nis_values.size),
        "nis_mean": float(np.mean(nis_values)) if nis_values.size else 0.0,
        "final_covariance_trace": final_covariance_trace,
        "runtime_seconds": float(runtime[0]["elapsed_seconds"]),
    }
    series = {
        "rotation": rotation, "velocity": velocity, "position": position,
        "gyro_bias": gyro_bias, "accel_bias": accel_bias,
        "state": np.concatenate((rotation, velocity, position, gyro_bias, accel_bias), axis=1),
        "innovation": innovation_norms, "nis": nis_values,
        "covariance": covariance_diagonals,
        "final_covariance": final_covariance_diagonal,
    }
    return row, series


def _difference_from_primary(
    series: dict[str, np.ndarray], primary: dict[str, np.ndarray], runtime_difference: float
) -> dict[str, float]:
    def rms_difference(name: str) -> float:
        left, right = series[name], primary[name]
        if left.shape != right.shape:
            raise h5.HartleyH5Error(f"native comparison shape mismatch: {name}")
        return float(np.sqrt(np.mean((left - right) ** 2))) if left.size else 0.0

    def distribution_difference(name: str) -> float:
        left, right = series[name], primary[name]
        if left.size == 0 and right.size == 0:
            return 0.0
        if left.size == 0 or right.size == 0:
            raise h5.HartleyH5Error(f"native comparison distribution missing: {name}")
        quantiles = np.linspace(0.0, 1.0, 101)
        return float(np.mean(np.abs(np.quantile(left, quantiles) - np.quantile(right, quantiles))))

    return {
        "state_component_rms_difference_from_primary": rms_difference("state"),
        "rotation_matrix_rms_difference_from_primary": rms_difference("rotation"),
        "final_rotation_frobenius_difference_from_primary": float(np.linalg.norm(
            series["rotation"][-1] - primary["rotation"][-1]
        )),
        "velocity_rms_difference_from_primary_m_per_s": rms_difference("velocity"),
        "position_rms_difference_from_primary_m": rms_difference("position"),
        "gyro_bias_rms_difference_from_primary_rad_per_s": rms_difference("gyro_bias"),
        "accel_bias_rms_difference_from_primary_m_per_s2": rms_difference("accel_bias"),
        "innovation_norm_quantile_l1_difference_from_primary": distribution_difference("innovation"),
        "nis_quantile_l1_difference_from_primary": distribution_difference("nis"),
        "covariance_diagonal_rms_difference_from_primary": rms_difference("covariance"),
        "final_covariance_diagonal_l2_difference_from_primary": float(np.linalg.norm(
            series["final_covariance"] - primary["final_covariance"]
        )),
        "runtime_seconds_difference_from_primary": runtime_difference,
    }


def _csv_payload(rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: (format(value, ".17g") if isinstance(value, float) else value)
                         for key, value in row.items()})
    return stream.getvalue().encode()


def _finalize_native(
    attempt: Path, publication_root: Path, storage_health_json: Path | None = None,
    file_access_audit_json: Path | None = None,
    attempt_ledger_json: Path | None = None,
) -> dict[str, object]:
    if publication_root.exists() or publication_root.with_name(publication_root.name + ".building").exists():
        raise h5.HartleyH5Error("local H5 publication destination already exists")
    _, provider = _verify_provider(attempt)
    runtime_launcher_sha256 = h5.sha256_file(LAUNCHER_PATH)
    finalizer_source_sha256 = h5.sha256_file(Path(__file__))
    runs_root = attempt / RUNS_DIRECTORY
    if {path.name for path in runs_root.iterdir()} != set(h5.H5_RUN_IDS) or any(
        not path.is_dir() for path in runs_root.iterdir()
    ):
        raise h5.HartleyH5Error("finalization requires exactly four preregistered run directories")

    expected_frozen = set((*h5.OUTPUT_SCHEMAS, "NATIVE_CONFIG.cfg", "NATIVE_SUMMARY.json",
                           "COVARIANCE_CHECKPOINTS.npz"))
    summaries: list[dict[str, object]] = []
    common: dict[str, object] | None = None
    copied: list[tuple[Path, str]] = []
    for run_id, destination_name in zip(h5.H5_RUN_IDS, FINAL_RUN_DIRECTORIES):
        run_directory = runs_root / run_id
        frozen = _verify_frozen_files(run_directory)
        if set(frozen) != expected_frozen:
            raise h5.HartleyH5Error("native freeze manifest is not the exact required file set")
        validated = _validate_native_outputs(run_directory, h5.H5_RECORD_COUNT)
        summary = validated["summary"]
        expected = {
            "run_id": run_id, "backend_id": h5.H5_BACKEND_ID,
            "process_policy": _policy(run_id), "sigma_fk_m": _sigma(run_id),
            "state_rows": h5.H5_RECORD_COUNT,
            "propagation_calls": h5.H5_PROPAGATION_COUNT,
            "eq61_calls": h5.H5_PROPAGATION_COUNT, "eq52_calls": 0,
            "joint_encoder_adapter_call_count": 0, "dropped_input_rows": 0,
            "forbidden_value_decode_count": 0, "reference_open_count": 0,
            "trace_open_count": 0, "nonfinite_state_count": 0,
            "nonfinite_covariance_count": 0, "nonfinite_output_count": 0,
            "rotation_gate_failure_count": 0, "state_dimension_failure_count": 0,
            "covariance_checkpoint_failure_count": 0, "synthetic_data_used": False,
            "semisynthetic_data_used": False, "reference_opened": False,
            "trace_used_online": False, "old_runtime_input_count": 0,
        }
        mismatch = {key: (summary.get(key), value) for key, value in expected.items()
                    if summary.get(key) != value}
        if mismatch:
            raise h5.HartleyH5Error(f"final native run gate mismatch for {run_id}: {mismatch}")
        config_lines = (run_directory / "NATIVE_CONFIG.cfg").read_text().splitlines(keepends=True)
        config = dict(line.rstrip("\n").split("=", 1) for line in config_lines)
        recomputed = hashlib.sha256("".join(
            line for line in config_lines if not line.startswith("config_hash=")
        ).encode()).hexdigest()
        identity = {
            "cache_sha256": summary.get("cache_sha256"),
            "raw_source_sha256": summary.get("raw_source_sha256"),
            "prefix_sha256": summary.get("prefix_sha256"),
            "scoped_source_manifest_sha256": summary.get("scoped_source_manifest_sha256"),
            "native_executable_sha256": summary.get("native_executable_sha256"),
        }
        if (config.get("config_hash") != recomputed or summary.get("config_hash") != recomputed or
                any(config.get(key) != str(value) for key, value in identity.items()
                    if key in config)):
            raise h5.HartleyH5Error("final native config/source/binary binding mismatch")
        if common is None:
            common = identity
        elif identity != common:
            raise h5.HartleyH5Error("four native runs do not share exact source/cache/executable identities")
        summaries.append(summary)
        for name in COMPACT_RUN_FILES:
            copied.append((run_directory / name, f"08_BY2_NATIVE/{destination_name}/{name}"))

    assert common is not None
    if common["cache_sha256"] != provider.get("cache_sha256") or common["raw_source_sha256"] != provider.get("raw_sha256"):
        raise h5.HartleyH5Error("provider/run source or cache identity mismatch")
    copied.extend([
        (attempt / PROVIDER_DIRECTORY / "H5_INPUT_CACHE.bin",
         "08_BY2_NATIVE/00_PROVIDER/H5_INPUT_CACHE.bin"),
        (attempt / PROVIDER_DIRECTORY / PROVIDER_MANIFEST,
         f"08_BY2_NATIVE/00_PROVIDER/{PROVIDER_MANIFEST}"),
        (attempt / PROVIDER_DIRECTORY / "H5_INPUT_CONTACT_EVENT_LEDGER.jsonl",
         "08_BY2_NATIVE/00_PROVIDER/H5_INPUT_CONTACT_EVENT_LEDGER.jsonl"),
    ])
    comparison_metrics = [
        _variant_comparison_row(runs_root / run_id, summary)
        for run_id, summary in zip(h5.H5_RUN_IDS, summaries)
    ]
    primary_series = comparison_metrics[0][1]
    primary_runtime = float(comparison_metrics[0][0]["runtime_seconds"])
    comparison_rows: list[dict[str, object]] = []
    for row, series in comparison_metrics:
        row.update(_difference_from_primary(
            series, primary_series, float(row["runtime_seconds"]) - primary_runtime
        ))
        comparison_rows.append(row)
    payloads: dict[str, bytes] = {}
    payloads["08_BY2_NATIVE/05_NATIVE_COMPARISON/H5_VARIANT_NATIVE_COMPARISON.csv"] = _csv_payload(comparison_rows)
    storage_health: dict[str, object] = {
        "status": "PENDING_SUPERVISOR_INJECTION",
        "selected_publication_target": "LOCAL_SCRATCH",
        "external_stage_accessed_by_finalizer": False,
    }
    if storage_health_json is not None:
        if (storage_health_json.name != "SUPERVISOR_STORAGE_HEALTH.json" or
                storage_health_json.resolve().parent != attempt.resolve() or
                h5.sha256_file(storage_health_json) !=
                SUPERVISOR_EVIDENCE_SHA256["SUPERVISOR_STORAGE_HEALTH.json"]):
            raise h5.HartleyH5Error("supervisor storage-health source identity mismatch")
        raw_health = storage_health_json.read_bytes()
        parsed_health = json.loads(raw_health)
        supervisor_read_only = (
            parsed_health.get("read_only") is True and
            parsed_health.get("repair_invoked") is False and
            parsed_health.get("query") == "Get-Volume -DriveLetter G" and
            parsed_health.get("DriveLetter") == "G"
        )
        if (parsed_health.get("provenance_label") != "SUPERVISOR_READ_ONLY_QUERY" and
                not supervisor_read_only):
            raise h5.HartleyH5Error("storage health JSON lacks supervisor-read-only provenance")
        copied.append((
            storage_health_json,
            "08_BY2_NATIVE/00_PROVIDER/SUPERVISOR_STORAGE_HEALTH.json",
        ))
        storage_health = parsed_health
    evidence_paths = (file_access_audit_json, attempt_ledger_json)
    for evidence_path in evidence_paths:
        if evidence_path is None:
            continue
        if evidence_path.name not in SUPERVISOR_EVIDENCE_SHA256:
            raise h5.HartleyH5Error("unknown supervisor evidence basename")
        if evidence_path.resolve().parent != attempt.resolve():
            raise h5.HartleyH5Error("supervisor evidence must be an immutable attempt-root file")
        if h5.sha256_file(evidence_path) != SUPERVISOR_EVIDENCE_SHA256[evidence_path.name]:
            raise h5.HartleyH5Error("supervisor evidence hash mismatch")
        json.loads(evidence_path.read_text())
        copied.append((evidence_path, f"08_BY2_NATIVE/00_PROVIDER/{evidence_path.name}"))
    status = {
        "schema_version": "hartley.h5.native_status.v1",
        "terminal_status": "PASS_LSE01_H5_BY2_NATIVE_FOUR_RUN_FINALIZED_LOCAL_ONLY",
        "run_order": list(h5.H5_RUN_IDS), "run_count": 4,
        "state_rows_per_run": h5.H5_RECORD_COUNT,
        "propagation_calls_per_run": h5.H5_PROPAGATION_COUNT,
        "eq61_calls_per_run": h5.H5_PROPAGATION_COUNT,
        "eq52_calls_total": 0, "joint_encoder_adapter_calls_total": 0,
        "real_BY2_EQ52_run": False,
        "paper_process_regression_classification": {
            "paper_branch_label": "PAPER_PROCESS_PARAMETER_REGRESSION",
            "measurement_adapter_label": "WITH_NONPAPER_GO2_FK_PROXY_MEASUREMENT_ADAPTER",
        },
        "frozen_transition_event_count_excluding_initial_add": provider["frozen_transition_event_count_excluding_initial_add"],
        "cache_sha256": provider["cache_sha256"],
        "runtime_launcher_sha256": runtime_launcher_sha256,
        "finalizer_source_sha256": finalizer_source_sha256,
        "native_executable_sha256": common["native_executable_sha256"],
        "scoped_source_manifest_sha256": common["scoped_source_manifest_sha256"],
        "reference_open_count": 0, "trace_open_count": 0,
        "forbidden_value_decode_count": 0, "old_runtime_input_count": 0,
        "comparison_scope": "NATIVE_ONLY_NO_REFERENCE_NO_RANKING",
        "h6_authorized": False, "h6_executed": False,
        "h7_authorized": False, "h7_executed": False,
        "external_stage_published": False, "storage_health": storage_health,
        "file_access_audit_sha256": (
            SUPERVISOR_EVIDENCE_SHA256["SUPERVISOR_FILE_ACCESS_AUDIT.json"]
            if file_access_audit_json is not None else "PENDING_SUPERVISOR_INJECTION"
        ),
        "attempt_ledger_sha256": (
            SUPERVISOR_EVIDENCE_SHA256["SUPERVISOR_ATTEMPT_LEDGER.json"]
            if attempt_ledger_json is not None else "PENDING_SUPERVISOR_INJECTION"
        ),
    }
    health_report = (
        f"`{storage_health['FileSystemType']}` / `{storage_health['HealthStatus']}` / "
        f"`{storage_health['OperationalStatus']}`; selected "
        f"`{storage_health['selected_execution_storage']}`"
        if "FileSystemType" in storage_health else
        f"`{storage_health.get('status', 'PENDING_SUPERVISOR_INJECTION')}`"
    )
    report = (
        "# LSE01 H5 BY2 Native Finalization\n\n"
        "Status: `PASS_LSE01_H5_BY2_NATIVE_FOUR_RUN_FINALIZED_LOCAL_ONLY`.\n\n"
        "The exact preregistered four-run sequence passed native-only validation. "
        "All runs share one immutable provider cache, scoped source identity, and native executable identity. "
        "Eq61 calls equal propagations; Eq52 and joint-encoder adapter calls are zero.\n\n"
        "The paper branch is labelled `PAPER_PROCESS_PARAMETER_REGRESSION` with "
        "`WITH_NONPAPER_GO2_FK_PROXY_MEASUREMENT_ADAPTER`; `real_BY2_EQ52_run` is false.\n\n"
        "`H5_VARIANT_NATIVE_COMPARISON.csv` contains native state, bias, innovation, NIS, covariance, and runtime summaries only. "
        "It performs no reference comparison or ranking. H6 and H7 remain unauthorized and unexecuted.\n\n"
        "Publication target: local scratch only. External G-stage publication was not invoked. "
        f"Storage-health record: {health_report}. Supervisor file-access audit and attempt ledger "
        "are copied byte-exact under `00_PROVIDER`; source strace logs remain local and unpublished.\n"
    ).encode()
    payloads["11_REPORT/LSE01_H5_STATUS.json"] = (
        json.dumps(status, sort_keys=True, indent=2) + "\n"
    ).encode()
    payloads["11_REPORT/LSE01_H5_BY2_NATIVE_REPORT.md"] = report
    copied_identities = {
        relative: {"source": str(source.relative_to(attempt)),
                   "size": source.stat().st_size, "sha256": h5.sha256_file(source)}
        for source, relative in copied
    }
    parity = {
        "schema_version": "hartley.h5.scratch_publication_parity.v1",
        "copied_file_count": len(copied), "all_copied_bytes_equal": True,
        "files": copied_identities,
    }
    payloads["H5_SCRATCH_PUBLICATION_PARITY.json"] = (
        json.dumps(parity, sort_keys=True, indent=2) + "\n"
    ).encode()
    manifest = {
        "schema_version": "hartley.h5.local_publication_manifest.v1",
        "runtime_launcher_sha256": runtime_launcher_sha256,
        "finalizer_source_sha256": finalizer_source_sha256,
        "files": {
            **{name: {"size": identity["size"], "sha256": identity["sha256"]}
               for name, identity in sorted(copied_identities.items())},
            **{name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
               for name, data in sorted(payloads.items())},
        },
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    payloads["H5_LOCAL_PUBLICATION_MANIFEST.json"] = manifest_bytes
    payloads["H5_LOCAL_PUBLICATION_MANIFEST.sha256"] = (
        hashlib.sha256(manifest_bytes).hexdigest() + "  H5_LOCAL_PUBLICATION_MANIFEST.json\n"
    ).encode()

    building = publication_root.with_name(publication_root.name + ".building")
    building.mkdir(parents=True, exist_ok=False)
    for source, relative in copied:
        destination = building / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        def chunks():
            with source.open("rb") as handle:
                while block := handle.read(1024 * 1024):
                    yield block
        h5.exclusive_write_bytes(destination, chunks())
    for relative, data in payloads.items():
        destination = building / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        h5.exclusive_write_bytes(destination, [data])
    for source, relative in copied:
        destination = building / relative
        if (destination.stat().st_size != source.stat().st_size or
                h5.sha256_file(destination) != h5.sha256_file(source)):
            raise h5.HartleyH5Error("local scratch copied-file parity verification failed")
    for relative, data in payloads.items():
        destination = building / relative
        if destination.stat().st_size != len(data) or h5.sha256_file(destination) != hashlib.sha256(data).hexdigest():
            raise h5.HartleyH5Error("local scratch publication parity verification failed")
    building.rename(publication_root)
    return {"status": status["terminal_status"], "publication_root": str(publication_root),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "published_file_count": len(copied) + len(payloads)}



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--publication-root", type=Path, required=True)
    parser.add_argument("--storage-health-json", type=Path)
    parser.add_argument("--file-access-audit-json", type=Path, required=True)
    parser.add_argument("--attempt-ledger-json", type=Path, required=True)
    args = parser.parse_args()
    result = _finalize_native(
        args.attempt_root, args.publication_root, args.storage_health_json,
        args.file_access_audit_json, args.attempt_ledger_json,
    )
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
