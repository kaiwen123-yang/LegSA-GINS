"""HX-02 unmodified RTKLIB moving-base runner (rnx2rtkp, registered configuration).

Inputs are prepared exactly like the EXT03 source backend: both receivers'
checksum-valid UBX frames are reconstructed from the raw CSV (NAV-HPPOSECEF
semantics disabled) and converted by the pinned convbin with the phase-2 argv.
The registered configuration RTKLIB_UNMODIFIED_MOVING_BASE.conf (SHA-256
97f0fe41...) is copied unchanged; the argv form is the EXT03 diagnostic form
(GNSS2 rover, GNSS1 base, GNSS1 then GNSS2 navigation). A CONTRACT_START
sequence adds only ``-ts`` at the first selected exact pair (GPST, ms resolution;
RTKLIB's start tolerance would otherwise admit the RAWX epoch 2 ms before the
contract start). The ENU baseline
(rover minus base = GNSS2 - GNSS1) gives body yaw = baseline heading + 90 deg.
"""
from __future__ import annotations

import csv
import hashlib
import math
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..horizontal_literature import phase2_runner as phase2
from ..horizontal_literature import sequence_override
from ..horizontal_literature.phase3_runner import _associate_rtklib_native_times, _parse_rtklib_enu_pos
from ..horizontal_literature.shared_raw_backend import pair_epochs, reconstruct_ubx_stream
from . import hx02_sequence

CONF_SHA256 = "97f0fe4157ce31909538e696184a7faadad059c3099ab912cbe2e97b0fc9e14f"
RNX2RTKP_SHA256 = "3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda"


class RtklibRunError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hx02_sequence.sha256_file(path)


def gpst_start_arguments(selected_pairs: Sequence[Sequence[Any]]) -> list[str]:
    """``-ts`` at the first selected exact pair (GPST, millisecond resolution)."""
    week, tow = selected_pairs[0]
    return sequence_override.gpst_epoch_arguments("-ts", int(week), float(tow))


def prepare_rinex(sequence: hx02_sequence.HX02Sequence, source_root: Path, convbin: Path) -> dict[str, Any]:
    source_root.mkdir(parents=True, exist_ok=False)
    raw = hx02_sequence.verify_raw(sequence, "gnss1_raw", "gnss2_raw")
    outputs, reconstructions, commands = {}, [], []
    for number, raw_path in ((1, sequence.gnss1_raw), (2, sequence.gnss2_raw)):
        ubx = source_root / f"gnss{number}.ubx"
        obs = source_root / f"gnss{number}.obs"
        nav = source_root / f"gnss{number}.nav"
        reconstruction = reconstruct_ubx_stream(Path(raw_path), ubx, decode_nav_hpposecef_semantics=False)
        commands.append(phase2._run_convbin(convbin, ubx, obs, nav))
        reconstructions.append(reconstruction)
        outputs[f"gnss{number}"] = {"ubx": str(ubx), "obs": str(obs), "nav": str(nav),
                                    "obs_sha256": sha256_file(obs), "nav_sha256": sha256_file(nav)}
    pairs, failures = pair_epochs(reconstructions[0].rawx_epochs, reconstructions[1].rawx_epochs, tolerance_seconds=0.0)
    if failures:
        raise RtklibRunError(f"exact RAWX pairing failed: {len(failures)} failures")
    selected = hx02_sequence.select_pairs(sequence, pairs)
    return {"raw_inputs": raw, "files": outputs, "convbin_commands": commands,
            "full_pairs": len(pairs), "selected_pairs": [(a.gps_week, a.gps_tow_seconds) for a, _ in selected]}


def run_rnx2rtkp(sequence: hx02_sequence.HX02Sequence, prepared: Mapping[str, Any], *, native_root: Path,
                 rnx2rtkp: Path, conf_source: Path) -> dict[str, Any]:
    if sha256_file(rnx2rtkp) != RNX2RTKP_SHA256:
        raise RtklibRunError("rnx2rtkp identity mismatch")
    if sha256_file(conf_source) != CONF_SHA256:
        raise RtklibRunError("registered RTKLIB configuration identity mismatch")
    native_root.mkdir(parents=True, exist_ok=True)
    conf = native_root / "RTKLIB_UNMODIFIED_MOVING_BASE.conf"
    shutil.copyfile(conf_source, conf)
    if sha256_file(conf) != CONF_SHA256:
        raise RtklibRunError("copied RTKLIB configuration differs")
    pos = native_root / "RTKLIB_UNMODIFIED_MOVING_BASE.pos"
    files = prepared["files"]
    argv = [str(rnx2rtkp), "-k", str(conf), "-o", str(pos)]
    if sequence.native_start_rel_s is not None:
        argv += gpst_start_arguments(prepared["selected_pairs"])
    argv += [files["gnss2"]["obs"], files["gnss1"]["obs"], files["gnss1"]["nav"], files["gnss2"]["nav"]]
    started = time.monotonic()
    completed = subprocess.run(argv, capture_output=True, text=True, timeout=3600, check=False)
    runtime = time.monotonic() - started
    (native_root / "rnx2rtkp_stdout.log").write_text(completed.stdout, encoding="utf-8")
    (native_root / "rnx2rtkp_stderr.log").write_text(completed.stderr, encoding="utf-8")
    return {"argv": argv, "returncode": completed.returncode, "runtime_seconds": runtime,
            "pos_exists": pos.is_file(), "pos": str(pos), "stderr_tail": completed.stderr[-4000:]}


def heading_table(prepared: Mapping[str, Any], pos_path: Path, leap_seconds: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One row per selected exact pair; valid = associated Q=1 fix, Q=2 kept as a separate flag."""
    parsed = _parse_rtklib_enu_pos(Path(pos_path).read_text(encoding="utf-8"))
    native = [{"gps_week": str(week), "gps_tow_seconds": repr(tow)} for week, tow in prepared["selected_pairs"]]
    association = _associate_rtklib_native_times(parsed, native)
    by_native: dict[int, dict[str, Any]] = {}
    for row, assoc in zip(parsed, association):
        if str(assoc["association_status"]).startswith("ASSOCIATED"):
            by_native[int(assoc["native_index"])] = row
    rows = []
    for index, (week, tow) in enumerate(prepared["selected_pairs"]):
        solution = by_native.get(index)
        yaw = ""
        quality = -1
        if solution is not None:
            north, east, down = solution["baseline_ned_m"]
            if math.hypot(north, east) > 0.0:
                _heading, _elevation, body_yaw = phase2._baseline_angles([north, east, down])
                yaw = repr(body_yaw)
            quality = int(solution["quality"])
        rows.append({"epoch_index": index, "gps_week": week, "gps_tow_seconds": repr(tow),
                     "time_unix_s": repr(hx02_sequence.unix_time(week, tow, leap_seconds)),
                     "valid": int(quality == 1 and yaw != ""), "body_yaw_deg": yaw, "rtklib_q": quality})
    statuses: dict[str, int] = {}
    for assoc in association:
        statuses[assoc["association_status"]] = statuses.get(assoc["association_status"], 0) + 1
    summary = {"pos_rows": len(parsed), "association_status_counts": statuses,
               "q_counts": {str(q): sum(1 for r in parsed if r["quality"] == q) for q in sorted({r["quality"] for r in parsed})},
               "selected_pairs": len(rows),
               "valid_q1_rows": sum(r["valid"] for r in rows)}
    return rows, summary


def write_heading_table(rows: Sequence[Mapping[str, Any]], path: Path, extra: Sequence[str] = ()) -> str:
    columns = ["epoch_index", "gps_week", "gps_tow_seconds", "time_unix_s", "valid", "body_yaw_deg", *extra]
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
