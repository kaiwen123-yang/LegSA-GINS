"""Fresh CLEAN5 providers from the frozen BY2 low-level generation recipe.

This module never runs a solver or evaluator, opens a trace, hashes raw files, or
chooses a window.  The caller supplies a verified sequence contract and encloses
each generation in independent raw-hash checkpoints and an openat audit.
"""
from __future__ import annotations

import csv
import json
import math
import shutil
from decimal import Decimal
from pathlib import Path

from .. import final_v23_clean_input as exact
from .. import formal_generation as formal
from .. import providers
from ..clean1r2r1_formal import rebase_auxiliary_time_csv
from ..manifest import sha256_file, sha256_text
from .provider_contract import SequenceProviderError, validate_frozen_parameters, validate_sequence_time
from .provider_parity import validate_by2_parity


def _progress(dataset: str, step: str) -> None:
    print(f"{dataset}: {step}", flush=True)


def _write_json_exclusive(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _copy_exclusive(source: Path, destination: Path) -> Path:
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
    return destination


def _provider_entry(path: Path, window: list[float], *, csv_format: bool = False,
                    time_origin: str = "sequence_R1") -> dict:
    times = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        if csv_format:
            times = [float(row["time"]) for row in csv.DictReader(handle)]
        else:
            times = [float(line.split()[0]) for line in handle if line.strip() and not line.lstrip().startswith("#")]
    if not times or any(not math.isfinite(t) for t in times) or any(a >= b for a, b in zip(times, times[1:])):
        raise SequenceProviderError(f"Provider time support is empty, nonfinite or non-increasing: {path.name}")
    start, end = window
    return {"path": str(path), "sha256": sha256_file(path), "row_count": len(times),
            "time_start": times[0], "time_end": times[-1], "time_origin": time_origin,
            "in_window_count": sum(start <= value <= end for value in times),
            "runtime_start_exclusive_in_window_count": sum(start < value <= end for value in times),
            "in_window_count_convention": "closed [t_start, t_end]", "full_support_retained": True}


def _assert_runtime_input_hashes(artifacts: dict) -> dict:
    """The auxiliary/quality chain must leave the sealed 7/15-column bytes alone."""
    rows = {}
    for role in ("imu_runtime_input", "gnss_runtime_input"):
        entry = artifacts[role]
        actual = sha256_file(entry["path"])
        rows[role] = {"initial_sha256": entry["sha256"], "final_sha256": actual,
                      "unchanged": actual == entry["sha256"]}
    if not all(row["unchanged"] for row in rows.values()):
        raise SequenceProviderError("Auxiliary generation modified a sealed IMU/GNSS runtime input")
    return rows


def _physical_gate(sequence, output: Path, base_time: float) -> tuple[list[dict], dict]:
    rows, audit = providers.build_physical_dual_yaw_provider(
        sequence.fix_root / "gnss1-status.csv", sequence.fix_root / "gnss2-status.csv",
        base_time=base_time, max_rows=None, fixed_yaw_std_deg=1.5,
    )
    count = len(rows)
    out_of_band = sum(not row["physical_in_band"] for row in rows)
    gate = {"dataset_id": sequence.dataset_id, "data_mode": sequence.data_mode,
            "physical_pass": bool(audit["physical_baseline_gate_pass"]),
            "epoch_count": count, "median_baseline_length_m": audit["median_baseline_length_m"],
            "p05_baseline_length_m": audit["p05_baseline_length_m"],
            "p95_baseline_length_m": audit["p95_baseline_length_m"],
            "four_meter_band_epoch_count": sum(3.5 <= row["baseline_length_m"] <= 4.5 for row in rows),
            "out_of_band_epoch_count": out_of_band,
            "out_of_band_fraction": out_of_band / count if count else None,
            "physical_band_m": [0.20, 0.60], "trace_used": False,
            "per_epoch": [{"time": row["time"], "baseline_length_m": row["baseline_length_m"],
                           "physical_in_band": row["physical_in_band"]} for row in rows]}
    _write_json_exclusive(output / "DUAL_YAW_PHYSICAL_AUDIT.json", audit)
    _write_json_exclusive(output / "YAW_PHYSICAL_GATE.json", gate)
    if not gate["physical_pass"]:
        raise SequenceProviderError(f"{sequence.dataset_id}: physical dual-yaw gate FAILED; no further providers generated")
    return rows, gate


def _exact_runtime_inputs(sequence, output: Path, base_time: float, *, stage_id: str | None = None) -> tuple[Path, Path, list, list, dict]:
    scratch = output / ".compat-builder"
    generated = providers._generate_process_data_compat_with_active_pvt(
        sequence.fix_root, sequence.body_path, scratch,
        base_time=base_time, yaw_source_mode="status", yaw_sign=1.0, yaw_install_offset_deg=0.0,
        yaw_std_mode="fixed_1p5", status_fixed_yaw_std_deg=1.5, enable_outage=False,
        outlier_mode="none", yaw_noise_std_deg=0.0, imu_install_roll_deg=-1.0,
        imu_install_pitch_deg=0.0, imu_install_yaw_deg=0.0, imu_gnss_time_offset=0.0,
        receiver_velocity_match_tolerance_seconds=0.1, dual_yaw_match_tolerance_seconds=0.6,
        receiver_velocity_std_mps=0.05, stage_id=stage_id or sequence.stage_id,
        max_status_rows=None, max_raw_rows=None, max_imu_messages=None,
    )
    report = generated["report"]
    required = {"trace_solver_input": False, "trace_yaw_for_solver": False,
                "yaw_noise_injection": False, "yaw_noise_std_deg": 0.0,
                "yaw_source": "A1_dual_diff_status", "receiver_velocity_std_mps": 0.05}
    if any((report.get(key) is not value) if isinstance(value, bool) else (report.get(key) != value)
           for key, value in required.items()):
        raise SequenceProviderError("Maintained compatibility builder violated the frozen clean-real profile")
    gnss_scratch, imu_scratch = Path(generated["gnss_path"]), Path(generated["imu_path"])
    gnss_rows = exact._read_numeric_table(gnss_scratch, exact.GNSS_COLUMNS)
    imu_rows = exact._read_numeric_table(imu_scratch, exact.IMU_COLUMNS)
    yaw_rows, yaw_audit = exact.build_clean_a1_yaw_rows(
        sequence.fix_root / "gnss1-status.csv", sequence.fix_root / "gnss2-status.csv",
        base_time=base_time, max_rows=None,
    )
    exact._apply_exact_clean_yaw(gnss_rows, yaw_rows, tolerance=0.6)
    exact._write_exact_input_tables(gnss_scratch, imu_scratch, gnss_rows, imu_rows)
    gnss_rows = exact._read_numeric_table(gnss_scratch, exact.GNSS_COLUMNS)
    imu_rows = exact._read_numeric_table(imu_scratch, exact.IMU_COLUMNS)
    if any(not -180.0 <= row[13] < 180.0 or row[14] != 1.5 for row in gnss_rows):
        raise SequenceProviderError("Exact clean yaw range/std serialization mismatch")
    imu_report = generated["imu_report"]
    if (imu_report.get("receiver_imu_as_body_imu") is not False
            or imu_report.get("flu_to_frd_applied_once") is not True
            or imu_report.get("imu_install_correction_rpy_deg") != [-1.0, 0.0, 0.0]
            or imu_report.get("imu_row_count") != len(imu_rows)
            or not 0 < int(imu_report.get("gyro_bias_window", 0)) <= 1000):
        raise SequenceProviderError("Maintained IMU builder violated the frozen increment contract")
    for label, rows in (("gnss_15_column", gnss_rows), ("imu_increment_7_column", imu_rows)):
        if not exact.audit_time_rows(rows, label=label)["strictly_increasing"]:
            raise SequenceProviderError(f"Non-increasing {label} timestamps")
    imu_path = _copy_exclusive(imu_scratch, output / exact.IMU_OUTPUT_NAME)
    gnss_path = _copy_exclusive(gnss_scratch, output / exact.GNSS_OUTPUT_NAME)
    return imu_path, gnss_path, imu_rows, gnss_rows, {
        "compatibility_builder_report": report, "imu_report": imu_report,
        "exact_a1_audit": yaw_audit, "exact_a1_row_count": len(yaw_rows),
        "exact_a1_in_window_count": None,
        "exact_a1_times": [float(row["aligned_time"]) for row in yaw_rows],
    }


def _rebase_exclusive(source: Path, output: Path, name: str, offset: float) -> tuple[Path, dict]:
    rebased_dir = output / ".rebased"
    rebased_dir.mkdir(exist_ok=True)
    scratch = rebased_dir / name
    report = rebase_auxiliary_time_csv(source, scratch, offset_seconds=offset)
    return _copy_exclusive(scratch, output / name), report


def _source_quality(sequence, output: Path, gnss_path: Path, timing: dict) -> tuple[Path, dict]:
    """Retain the formal UTC-day quality sidecar; never append to final GNSS15."""
    scratch = output / ".source-quality"
    scratch.mkdir()
    gnss18 = scratch / "FORMAL_GNSS_18_COLUMN_UTC_DAY.txt"
    offset = Decimal(str(timing["auxiliary_rebase_offset_seconds"]))
    with gnss_path.open("r", encoding="utf-8") as src, gnss18.open("x", encoding="utf-8") as dst:
        for line in src:
            fields = line.split()
            fields[0] = f"{Decimal(fields[0]) + offset:.6f}"
            dst.write(" ".join(fields) + "\n")
    counts = formal._upgrade_gnss_to_formal_18_columns(
        gnss18, gnss1_status=sequence.fix_root / "gnss1-status.csv",
        gnss2_status=sequence.fix_root / "gnss2-status.csv", gnss1_raw=sequence.fix_root / "gnss1-raw.csv",
        base_time=timing["utc_day_midnight"], receiver_velocity_match_tolerance_seconds=0.1,
        dual_yaw_match_tolerance_seconds=0.6,
    )
    temporary = scratch / "SOURCE_QUALITY_METADATA.csv"
    formal._write_source_quality(gnss18, temporary)
    return _copy_exclusive(temporary, output / temporary.name), {
        **counts, "scratch_18_column_path": str(gnss18), "time_origin": "UTC_day_midnight",
        "final_gnss_columns": 15, "scratch_used_as_runtime_input": False,
    }


def _go2(sequence, output: Path, timing: dict, generation: dict) -> tuple[dict, dict]:
    attitude, horizontal, audit = providers._go2_priors(
        sequence.body_path, base_time=timing["utc_day_midnight"], max_messages=None,
        frame_name=generation["go2_velocity_frame_transform"],
        roll_pitch_std_deg=float(generation["go2_roll_pitch_std_deg"]),
        horizontal_std_mps=float(generation["go2_horizontal_velocity_std_mps"]),
    )
    if not attitude or not horizontal:
        raise SequenceProviderError("Frozen Go2 weak-prior recipe yielded an empty provider")
    scratch = output / ".go2-utc"
    scratch.mkdir()
    result, rebases = {}, {}
    for role, name, rows in (
        ("go2_attitude_prior", "GO2_ROLL_PITCH_PRIOR.csv", attitude),
        ("go2_horizontal_velocity_prior", "GO2_HORIZONTAL_VELOCITY_PRIOR.csv", horizontal),
    ):
        source = scratch / name
        providers._write_csv(source, rows, list(rows[0]))
        path, rebase = _rebase_exclusive(source, output, name, timing["auxiliary_rebase_offset_seconds"])
        result[role] = _provider_entry(path, timing["window"], csv_format=True)
        rebases[role] = rebase
    return result, {"generation": audit, "rebasing": rebases}


def _raw_doppler(registry, sequence, contract: dict, output: Path, timing: dict,
                 generation: dict, rtklib_root: Path | None) -> tuple[dict, dict, dict]:
    shared = registry.clean_root / "stages/CLEAN5_SHARED_TOOLCHAIN/rtklib_pinned"
    explicit = rtklib_root or (shared if shared.exists() else None)
    source_root, source_mode = formal.resolve_pinned_rtklib_source(
        explicit_root=explicit, materialize_root=None if explicit else shared)
    tools = output / "tools"
    tools.mkdir()
    build_root = tools / "rtklib_convbin_source"
    build_root.mkdir()
    # Preserve the pinned makefile and compiler flags while leaving source/toolchain roots untouched.
    for relative in formal.CONVBIN_SOURCE_FILES:
        destination = build_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        _copy_exclusive(source_root / relative, destination)
    convbin_dir = build_root / "app/consapp/convbin/gcc"
    formal._run(["make"], cwd=convbin_dir, label="CLEAN5 exact pinned convbin build")
    convbin = convbin_dir / "convbin"
    if not convbin.is_file():
        raise SequenceProviderError("Pinned convbin build produced no executable")
    backend = output / "raw_doppler_backend"
    backend.mkdir()
    raw_csv = sequence.fix_root / "gnss1-raw.csv"
    gnss1_status = sequence.fix_root / "gnss1-status.csv"
    ubx = backend / "gnss1_rebuilt.ubx"
    rebuild = formal.rebuild_csv_to_ubx(raw_csv, ubx)
    if not rebuild.get("rebuilt_ubx_available") or int(rebuild.get("rawx_frame_count") or 0) <= 0 or int(rebuild.get("sfrbx_frame_count") or 0) <= 0:
        raise SequenceProviderError("Sequence GNSS1 raw did not rebuild RAWX/SFRBX UBX")
    rinex = backend / "rinex"
    rinex.mkdir()
    obs, nav = rinex / "gnss1.obs", rinex / "gnss1.nav"
    command = [str(convbin), "-r", "ubx", "-v", "3.04", "-od", "-os", "-oi", "-ot", "-ol",
               "-o", str(obs), "-n", str(nav), "-g", str(rinex / "gnss1.gnav"),
               "-h", str(rinex / "gnss1.hnav"), "-q", str(rinex / "gnss1.qnav"),
               "-l", str(rinex / "gnss1.lnav"), "-b", str(rinex / "gnss1.cnav"),
               "-i", str(rinex / "gnss1.inav"), str(ubx)]
    formal._run(command, cwd=rinex, label="CLEAN5 fresh pinned convbin conversion")
    if not all(path.is_file() and path.stat().st_size for path in (obs, nav)):
        raise SequenceProviderError("Fresh pinned convbin did not produce nonempty OBS/NAV")
    helper = formal._build_exact_rtklib_doppler_helper(source_root, backend / "helper")
    if helper.get("helper_compile_status") != "success" or helper.get("runtime_patch_applied") != []:
        raise SequenceProviderError("Pinned RTKLIB helper compile failed or applied a patch")
    helper_exe = Path(helper["helper_executable_path"])
    source_position = formal._first_source_position_and_time(gnss1_status, raw_csv)
    helper_run = formal.run_rtklib_doppler_velocity_provider(
        obs_path=obs, nav_path=nav, helper_exe=helper_exe,
        approx_position_source={key: source_position[key] for key in ("lat_deg", "lon_deg", "height_m")},
        output_dir=backend / "helper_run", min_sat=int(generation["raw_doppler_min_sat"]),
    )
    if helper_run.get("helper_run_status") != "success":
        raise SequenceProviderError("Fresh pinned RTKLIB Doppler helper yielded no valid epochs")
    obs_hash, nav_hash = sha256_file(obs), sha256_file(nav)
    conversion = {
        "rtklib_remote": formal.PINNED_RTKLIB_REMOTE, "rtklib_commit": formal.PINNED_RTKLIB_COMMIT,
        "convbin_options": command[1:-1], "min_sat": int(generation["raw_doppler_min_sat"]),
        "std_floor_mps": float(generation["raw_doppler_std_floor_mps"]),
        "time_conversion_formula": formal.RAW_DOPPLER_TIME_CONVERSION,
        "utc_date": [source_position["utc_year"], source_position["utc_month"], source_position["utc_day"]],
        "gps_week": source_position["gps_week"], "leap_seconds": source_position["leap_seconds"],
        "approx_position_geodetic_deg_m": [source_position[key] for key in ("lat_deg", "lon_deg", "height_m")],
        "selected_status_row_number": source_position["selected_status_row_number"],
        "selected_status_fields_sha256": source_position["selected_status_fields_sha256"],
        "covariance_policy": generation["raw_doppler_covariance_policy"], "first_epoch_fit_used": False,
    }
    conversion_hash = sha256_text(json.dumps(conversion, sort_keys=True, separators=(",", ":")))
    utc_csv = backend / "RAW_DOPPLER_VELOCITY_UTC_DAY.csv"
    counts = formal._write_formal_raw_doppler(
        Path(helper_run["helper_raw_csv_path"]), utc_csv, source_position=source_position,
        obs_hash=obs_hash, nav_hash=nav_hash, conversion_config_hash=conversion_hash,
        min_sat=int(generation["raw_doppler_min_sat"]), std_floor_mps=float(generation["raw_doppler_std_floor_mps"]),
        covariance_policy=generation["raw_doppler_covariance_policy"],
    )
    raw_epochs = int(rebuild["rawx_frame_count"])
    if raw_epochs < int(counts["valid_epoch_count"]):
        raise SequenceProviderError("Raw Doppler valid epoch count exceeds source RAWX epochs")
    counts.update(raw_epoch_count=raw_epochs, invalid_epoch_count=raw_epochs - int(counts["valid_epoch_count"]))
    final_path, rebase = _rebase_exclusive(utc_csv, output, "RAW_DOPPLER_VELOCITY.csv", timing["auxiliary_rebase_offset_seconds"])
    helper_sources = ["src/legsa_gins/raw_gnss/ubx_raw_binary_rebuilder.py",
                      "src/legsa_gins/raw_gnss/rtklib_doppler_helper_builder.py",
                      "src/legsa_gins/raw_gnss/rtklib_doppler_velocity_provider.py",
                      "src/legsa_gins/raw_gnss/rtklib_solution_velocity_parser.py",
                      "src/legsa_gins/paper_rebuild/formal_generation.py"]
    rtklib_sources = list(dict.fromkeys([f"src/{name}" for name in formal.REQUIRED_SOURCE_FILES] + list(formal.CONVBIN_SOURCE_FILES)))
    raw_relative, status_relative = (f"{sequence.fix_prefix}/{name}" for name in ("gnss1-raw.csv", "gnss1-status.csv"))
    locked_hashes = contract["identity"]["raw_files_sha256"]
    for relative in (raw_relative, status_relative):
        value = locked_hashes.get(relative)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise SequenceProviderError(f"Sequence backend source is absent from verified contract: {relative}")
    retained_paths = {"helper_executable": helper_exe, "helper_source": Path(helper["helper_source_path"]),
                      "convbin_executable": convbin, "rebuilt_ubx": ubx, "rinex_obs": obs, "rinex_nav": nav,
                      "formal_raw_doppler_provider": utc_csv}
    retained = {role: {"relative_path": path.relative_to(output).as_posix(), "sha256": sha256_file(path)}
                for role, path in retained_paths.items()}
    report = {
        "schema_version": "paper-rebuild-raw-doppler-backend-v1", "dataset_id": sequence.dataset_id,
        "data_mode": sequence.data_mode, "raw_doppler_backend_lineage_proven": True,
        "raw_doppler_backend_id": formal.RAW_DOPPLER_BACKEND_ID,
        "raw_doppler_backend_source_files": [raw_relative, status_relative],
        "raw_doppler_backend_source_hashes": {name: locked_hashes[name] for name in (raw_relative, status_relative)},
        "helper_source_files": helper_sources,
        "helper_source_hashes": {name: sha256_file(registry.code_root / name) for name in helper_sources},
        "rtklib_source_files": rtklib_sources,
        "rtklib_source_hashes": {name: sha256_file(source_root / name) for name in rtklib_sources},
        "helper_compiled_rtklib_source_files": helper["exact_compiled_rtklib_source_files"],
        "convbin_compiled_source_files": list(formal.CONVBIN_SOURCE_FILES),
        "helper_executable_hash": sha256_file(helper_exe), "obs_source_hash": obs_hash, "nav_source_hash": nav_hash,
        "conversion_config_hash": conversion_hash, "conversion_contract": conversion, **counts,
        "covariance_policy": generation["raw_doppler_covariance_policy"], "rtklib_source_mode": source_mode,
        "rtklib_remote": formal.PINNED_RTKLIB_REMOTE, "rtklib_commit": formal.PINNED_RTKLIB_COMMIT,
        "rtklib_tracked_source_dirty": bool(formal._git_value(source_root, ["status", "--porcelain", "--untracked-files=no"])),
        "rtklib_untracked_build_outputs_present": bool(formal._git_value(source_root, ["status", "--porcelain", "--untracked-files=normal"])),
        "external_ephemeris_downloaded": False, "time_conversion_formula": formal.RAW_DOPPLER_TIME_CONVERSION,
        "time_conversion_inputs_source_backed": True, "approx_position_source_relative_path": status_relative,
        "approx_position_source_hash": locked_hashes[status_relative],
        "approx_position_geodetic_deg_m": conversion["approx_position_geodetic_deg_m"],
        "selected_status_row_number": source_position["selected_status_row_number"],
        "selected_status_fields_sha256": source_position["selected_status_fields_sha256"],
        "gps_week": source_position["gps_week"], "first_epoch_fit_used": False,
        "rtklib_position_solution_used_as_solver_input": False, "nav_pvt_velocity_used_as_raw_doppler": False,
        "gnss_velocity_used_as_raw_doppler": False, "status_fallback_used": False,
        "tracked_provider_generation": generation, "legacy_provider_used": False,
        "convbin_executable_hash": sha256_file(convbin), "rebuilt_ubx_hash": sha256_file(ubx),
        "runtime_patch_applied": [], "source_discovery_used": False,
        "sat_count_semantics": "distinct_satellites_with_nonzero_doppler_observation",
        "helper_source_hash": helper["helper_source_hash"],
        "compiler_version": formal._run(["gcc", "--version"], cwd=source_root, label="gcc version").stdout.splitlines()[0],
        "convbin_build_command": ["make"], "convbin_clean_build": True, "convbin_preexisting_output_count": 0,
        "helper_compile_command": helper["compile_command"], "retained_backend_artifacts": retained,
        "retained_backend_bundle_hash": sha256_text(json.dumps(retained, sort_keys=True, separators=(",", ":"))),
        "rebasing": rebase,
    }
    if report["rtklib_tracked_source_dirty"]:
        raise SequenceProviderError("Pinned RTKLIB tracked source changed during generation")
    if sequence.dataset_id == "BY2":
        formal.validate_raw_doppler_backend_report(report, verified_raw_hashes=locked_hashes)
    _write_json_exclusive(output / "RAW_DOPPLER_BACKEND_REPORT.json", report)
    return _provider_entry(final_path, timing["window"], csv_format=True), report, rebuild


def generate_sequence_payloads(registry, sequence, contract: dict, output_root: str | Path, *, rtklib_root: str | Path | None = None) -> dict:
    """Generate one sequence once; the physical gate precedes every other payload."""
    output = Path(output_root)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    if contract["identity"]["dataset_id"] != sequence.dataset_id or contract["identity"]["data_mode"] != sequence.data_mode:
        raise SequenceProviderError("Sequence contract dataset/data_mode differs from the registry")
    generation = validate_frozen_parameters(contract, registry.code_root)
    _progress(sequence.dataset_id, "validate source-derived R1 and frozen window")
    timing = validate_sequence_time(sequence, contract)
    output.mkdir(parents=True, exist_ok=False)
    _progress(sequence.dataset_id, "physical dual-yaw gate")
    physical_rows, physical = _physical_gate(sequence, output, timing["base_time"])
    _progress(sequence.dataset_id, "exact 7-column IMU and 15-column GNSS inputs")
    imu, gnss, imu_rows, gnss_rows, input_audit = _exact_runtime_inputs(
        sequence, output, timing["base_time"], stage_id=contract["identity"]["stage_id"])
    start, end = timing["window"]
    a1_times = input_audit.pop("exact_a1_times")
    input_audit["exact_a1_in_window_count"] = sum(start <= t <= end for t in a1_times)
    result = {"imu_runtime_input": _provider_entry(imu, timing["window"]),
              "gnss_runtime_input": _provider_entry(gnss, timing["window"])}
    _progress(sequence.dataset_id, "formal 18-column source-quality scratch")
    quality, quality_audit = _source_quality(sequence, output, gnss, timing)
    utc_window = [t + timing["auxiliary_rebase_offset_seconds"] for t in timing["window"]]
    result["source_quality_metadata"] = _provider_entry(quality, utc_window, csv_format=True, time_origin="UTC_day_midnight")
    _progress(sequence.dataset_id, "pinned RTKLIB Raw Doppler and time-only rebasing")
    raw, backend, rebuild = _raw_doppler(registry, sequence, contract, output, timing, generation,
                                        Path(rtklib_root) if rtklib_root else None)
    result["raw_doppler_provider"] = raw
    _progress(sequence.dataset_id, "frozen Go2 weak priors and time-only rebasing")
    go2_providers, go2_audit = _go2(sequence, output, timing, generation)
    result.update(go2_providers)
    runtime_input_immutability = _assert_runtime_input_hashes(result)
    counts = {"imu_increment_count": len(imu_rows), "gnss_full_count": len(gnss_rows),
              "gnss_in_window_count": result["gnss_runtime_input"]["in_window_count"],
              "physical_a1_count": len(physical_rows), "exact_a1_count": input_audit["exact_a1_row_count"],
              "exact_a1_in_window_count": input_audit["exact_a1_in_window_count"],
              "raw_doppler_count": raw["row_count"],
              "go2_roll_pitch_count": result["go2_attitude_prior"]["row_count"],
              "go2_horizontal_velocity_count": result["go2_horizontal_velocity_prior"]["row_count"]}
    payloads = {"dataset_id": sequence.dataset_id, "stage_id": contract["identity"]["stage_id"], "data_mode": sequence.data_mode,
                "output_root": str(output), "providers": result, "artifacts": result, "counts": counts, "time_contract_audit": timing,
                "physical_yaw_gate": physical, "input_audit": input_audit, "source_quality_audit": quality_audit,
                "raw_doppler_backend": backend, "raw_rebuild_report": rebuild, "go2_audit": go2_audit,
                "runtime_input_immutability": runtime_input_immutability,
                "synthetic_data_used": False, "semisynthetic_data_used": False, "trace_used_online": False,
                "receiver_imu_as_body_imu": False, "final_v23_output_solver_input": False,
                "LegSA_output_solver_input": False, "per_case_tuning": False, "output_only_correction": False,
                "epoch_deleted_for_metric": False, "old_runtime_input_count": 0,
                "provider_generation": generation, "solver_invocation_count": 0, "evaluator_invocation_count": 0}
    _write_json_exclusive(output / "PROVIDER_GENERATION_REPORT.json", payloads)
    _progress(sequence.dataset_id, "provider payload generation complete")
    return payloads
