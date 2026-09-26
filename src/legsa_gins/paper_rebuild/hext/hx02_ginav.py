"""HX-02 GINav (official SPP/INS LC) inputs, derived configuration and MATLAB run.

Inputs per sequence follow the registered BY2 route (ginav2021 package, unchanged
functions): GNSS1 RAWX/SFRBX -> reconstructed UBX -> convbin RINEX 3.04 +
broadcast ephemeris; single-constant RAWX/NAV-PVT epoch normalization; Go2 body
IMU (FLU->RFU format-2 increments) from the sequence's complete-record prefix.

Configuration: the BY2 derived ini (SHA-256 688ea8ac...) cloned line by line;
only data_dir, start_time and end_time are replaced (start/end = integer-second
RINEX/IMU overlap as in the BY2 route; CONTRACT_START additionally starts at the
contract start). Every other byte is identical.

Run: a mirror of the pinned $EXTERNAL/GINav working tree (excluding .git, data,
result) is copied from the pinned file listing and verified file by file; no git
command touches the pinned tree. MATLAB is the single executable registered under
the local path key ``hx02_matlab_executable`` (<MATLAB_EXE>, SHA-256 6dc32276...);
there is no PATH fallback. The official exepos route is invoked through the
registered harness with an fopen ledger.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..horizontal_literature.ginav2021.imu_adapter import adapt_go2_imu
from ..horizontal_literature.ginav2021.matlab import (
    build_matlab_batch_command,
    render_official_run_script,
    run_matlab_script,
    write_harness_files,
)
from ..horizontal_literature.ginav2021.rinex_adapter import convert_gnss1_raw_to_rinex
from ..horizontal_literature.ginav2021.time_contract import (
    extract_same_receiver_time_events,
    normalize_rinex_epochs,
    parse_rinex_epochs,
    prove_single_constant_normalization,
)
from ..horizontal_literature.ginav2021.transaction import _gps_overlap_datetimes
from . import hx02_sequence

LOCAL_PATHS_CONFIG = Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")
MATLAB_LOCAL_KEY = "hx02_matlab_executable"
MATLAB_SHA256 = "6dc32276086121e44edf4846f033066ba5b0fae9bad002d8917a411e0a59afa9"
BY2_DERIVED_CONFIG_SHA256 = "688ea8acaa910971b9cc3a37861328d6be1b678e82f8a409a1385207ebc66975"
MIRROR_EXCLUDED_TOP = (".git", "data", "result")
REPLACED_KEYS = ("data_dir", "start_time", "end_time")
LINE_RE = {
    "data_dir": re.compile(r"^(data_dir\s*=\s*)(\S+)(.*)$"),
    "start_time": re.compile(r"^(start_time\s*=\s*1\s+)(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})(.*)$"),
    "end_time": re.compile(r"^(end_time\s*=\s*1\s+)(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})(.*)$"),
}


class GinavRunError(RuntimeError):
    pass


def matlab_executable(paths_config: Path = LOCAL_PATHS_CONFIG) -> Path:
    """The registered MATLAB executable from the ignored local path config (no PATH fallback)."""
    try:
        local = yaml.safe_load(Path(paths_config).read_text(encoding="utf-8"))["paths"]
        return Path(local[MATLAB_LOCAL_KEY])
    except (OSError, KeyError, TypeError) as exc:
        raise GinavRunError(f"RUN_FAILED_ENVIRONMENT: MATLAB executable not registered ({exc})") from exc


def sha256_file(path: Path) -> str:
    return hx02_sequence.sha256_file(path)


def go2_identity(inventory: Mapping[str, Any], sequence_id: str) -> dict[str, Any]:
    return {"raw_size_bytes": int(inventory["size_bytes"]), "raw_sha256": inventory["raw"]["sha256"],
            "prefix_bytes": int(inventory["prefix_end_exclusive"]), "prefix_sha256": inventory["prefix_sha256"],
            "complete_records": int(inventory["record_separator_count"]),
            "data_identity": f"REAL_{sequence_id}_COMPLETE_RECORD_PREFIX_{int(inventory['record_separator_count'])}"}


def contract_start_gpst(sequence: hx02_sequence.HX02Sequence) -> datetime:
    """Integer GPST second at or after base_time + contract start (UTC Unix)."""
    unix = sequence.base_time + float(sequence.native_start_rel_s)
    gpst = datetime.fromtimestamp(unix, tz=timezone.utc).replace(tzinfo=None) + timedelta(seconds=sequence.leap_seconds)
    if gpst.microsecond:
        gpst = gpst.replace(microsecond=0) + timedelta(seconds=1)
    return gpst


def derive_config(template: Path, destination: Path, *, data_dir: Path, start: datetime, end: datetime) -> dict[str, Any]:
    """Line-wise clone of the BY2 derived ini; only data_dir/start_time/end_time values change."""
    if sha256_file(template) != BY2_DERIVED_CONFIG_SHA256:
        raise GinavRunError("BY2 derived configuration identity mismatch")
    original = template.read_bytes().decode("ascii")
    values = {"data_dir": str(data_dir), "start_time": start.strftime("%Y/%m/%d %H:%M:%S"),
              "end_time": end.strftime("%Y/%m/%d %H:%M:%S")}
    lines = original.splitlines(keepends=True)
    replaced = {}
    output = []
    for line in lines:
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        for key, pattern in LINE_RE.items():
            match = pattern.match(body)
            if match:
                if key in replaced:
                    raise GinavRunError(f"duplicate {key} line")
                replaced[key] = {"old": match.group(2), "new": values[key]}
                body = match.group(1) + values[key] + match.group(3)
                break
        output.append(body + ending)
    if set(replaced) != set(REPLACED_KEYS):
        raise GinavRunError("derived configuration lacks a replaceable sequence field")
    text = "".join(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as handle:
        handle.write(text.encode("ascii"))
    changed = [index for index, (a, b) in enumerate(zip(lines, output)) if a != b]
    if len(lines) != len(output) or len(changed) > len(REPLACED_KEYS):
        raise GinavRunError("configuration clone changed more than the declared lines")
    diff = "".join(difflib.unified_diff(lines, output, fromfile="BY2_GINAV_SPP_LC.ini (688ea8ac)",
                                        tofile=destination.name))
    return {"config": str(destination), "config_sha256": sha256_file(destination), "replaced": replaced,
            "changed_line_numbers_1based": [index + 1 for index in changed], "unified_diff": diff}


def prepare_inputs(sequence: hx02_sequence.HX02Sequence, *, go2_inventory: Mapping[str, Any], root: Path,
                   rtklib_root: Path, convbin: Path, template: Path, data_dir: Path | None = None) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=False)
    gnss = convert_gnss1_raw_to_rinex(sequence.gnss1_raw, rtklib_root=rtklib_root, convbin=convbin,
                                      output_root=root / "02_GNSS_ADAPTER")
    epochs = parse_rinex_epochs(Path(gnss["observation_path"]))
    rawx_times, pvt_times = extract_same_receiver_time_events(Path(gnss["ubx_path"]).read_bytes())
    proof = prove_single_constant_normalization(rawx_times, pvt_times, epochs)
    time_root = root / "04_TIME_CONTRACT"
    time_root.mkdir()
    normalized = time_root / "BY2_GNSS1_NORMALIZED.rnx"
    normalized_rows = normalize_rinex_epochs(Path(gnss["observation_path"]), normalized, proof)
    selected_epochs = parse_rinex_epochs(normalized)
    imu_csv = root / "03_IMU_ADAPTER" / "BY2_GINAV_IMU.csv"
    imu = adapt_go2_imu(sequence.go2_body, imu_csv, identity=go2_identity(go2_inventory, sequence.sequence_id))
    start, end = _gps_overlap_datetimes(selected_epochs, imu_csv)
    overlap = {"start_gpst": start.isoformat(sep=" "), "end_gpst": end.isoformat(sep=" ")}
    if sequence.native_start_rel_s is not None:
        start = max(start, contract_start_gpst(sequence))
    config = derive_config(template, root / "05_CONFIG" / f"{sequence.sequence_id}_GINAV_SPP_LC.ini",
                           data_dir=data_dir or root, start=start, end=end)
    summary = {
        "sequence_id": sequence.sequence_id, "start_convention": sequence.start_convention,
        "gnss_adapter": {key: gnss[key] for key in ("source_sha256", "rawx_epoch_count", "command", "ubx_sha256",
                                                    "observation_path", "navigation_path")},
        "observation_sha256": sha256_file(Path(gnss["observation_path"])),
        "navigation_sha256": sha256_file(Path(gnss["navigation_path"])),
        "selected_navsys_from_data_not_used": gnss["rinex"].get("selected_navsys"),
        "normalization": {key: proof[key] for key in proof if key != "ledger"},
        "normalized_observation": str(normalized), "normalized_observation_sha256": sha256_file(normalized),
        "normalized_row_count": len(normalized_rows), "selected_epoch_count": len(selected_epochs),
        "imu": {key: imu[key] for key in imu if key not in ("stdout", "stderr")}, "imu_csv": str(imu_csv),
        "imu_csv_sha256": sha256_file(imu_csv), "overlap": overlap,
        "config": config, "trace_open_count": 0, "gnss2_open_count": 0,
    }
    (root / "GINAV_INPUT_PREPARATION.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    return summary


def build_mirror(pinned_items: Mapping[str, str], external_root: Path, mirror: Path) -> dict[str, Any]:
    """Copy the pinned GINav working tree (minus .git/data/result) and verify every file hash."""
    mirror.mkdir(parents=True, exist_ok=False)
    copied = {}
    prefix = "$EXTERNAL/GINav/"
    for key, digest in sorted(pinned_items.items()):
        if not key.startswith(prefix):
            continue
        relative = key[len(prefix):]
        if relative.split("/", 1)[0] in MIRROR_EXCLUDED_TOP or digest.startswith("SYMLINK:"):
            continue
        source = Path(external_root) / "GINav" / relative
        target = mirror / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha256_file(target) != digest or sha256_file(source) != digest:
            raise GinavRunError(f"GINav mirror file differs from pinned listing: {relative}")
        copied[relative] = digest
    (mirror / "result").mkdir()
    return {"copied_file_count": len(copied), "listing_sha256": hashlib.sha256(
        json.dumps(copied, sort_keys=True).encode()).hexdigest(), "excluded_top": list(MIRROR_EXCLUDED_TOP)}


def run_ginav(prepared: Mapping[str, Any], *, run_root: Path, mirror_manifest_items: Mapping[str, str],
              external_root: Path, timeout_seconds: float = 3600.0) -> dict[str, Any]:
    executable = matlab_executable()
    if not executable.is_file():
        raise GinavRunError(f"RUN_FAILED_ENVIRONMENT: MATLAB executable absent at {executable}")
    if sha256_file(executable) != MATLAB_SHA256:
        raise GinavRunError("RUN_FAILED_ENVIRONMENT: MATLAB executable identity mismatch")
    mirror = run_root / "source_mirror"
    mirror_manifest = build_mirror(mirror_manifest_items, external_root, mirror)
    harness = run_root / "matlab_harness"
    fopen_log = run_root / "MATLAB_FOPEN_LEDGER.tsv"
    config = Path(prepared["config"]["config"])
    observation = Path(prepared["normalized_observation"])
    navigation = Path(prepared["gnss_adapter"]["navigation_path"])
    imu = Path(prepared["imu_csv"])
    main = render_official_run_script(mirror_root=mirror, harness_root=harness, config_path=config,
                                      observation_path=observation, navigation_path=navigation,
                                      imu_path=imu, windows=True)
    script = write_harness_files(harness, main_script=main, fopen_log=fopen_log, windows=True)
    command = list(build_matlab_batch_command(executable, script))
    try:
        result = run_matlab_script(executable, script, timeout_seconds=timeout_seconds)
    except Exception as exc:  # recorded as a failed native attempt; never retried
        result = {"command": command, "returncode": -1, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}",
                  "runtime_seconds": None, "pass": False}
    outputs = sorted((mirror / "result").glob("*.pos"))
    native_pos = None
    if len(outputs) == 1:
        native_pos = run_root / outputs[0].name
        shutil.copyfile(outputs[0], native_pos)
    fopen = fopen_log.read_text(encoding="utf-8", errors="replace") if fopen_log.is_file() else ""
    declared = {str(path) for path in (config, observation, navigation, imu)}
    return {**result, "matlab_sha256": MATLAB_SHA256, "mirror": mirror_manifest, "native_pos": str(native_pos) if native_pos else None,
            "native_pos_sha256": sha256_file(native_pos) if native_pos else None, "native_output_count": len(outputs),
            "fopen_ledger_lines": len([line for line in fopen.splitlines() if line.strip()]),
            "fopen_ledger_sha256": sha256_file(fopen_log) if fopen_log.is_file() else None,
            "declared_inputs": sorted(declared)}
