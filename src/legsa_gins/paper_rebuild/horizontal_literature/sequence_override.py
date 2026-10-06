"""HX-02 sequence override for the Phase-1R/2/3/4 native runners.

A run script activates one declared sequence spec (JSON written by the HX-02
controller) before calling a phase runner in its native-only lifecycle. Without
an active spec every runner keeps its frozen BY2 behaviour unchanged. The spec
carries raw-stream paths, the raw hash lock, the artifact root that replaces the
CLEAN4 stage root, the exact full-file pair count, the start convention, the
selected pair count and the GPS leap seconds. It never contains or opens a
reference trajectory.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

SPEC_SCHEMA = "hx02.sequence_spec.v1"
GPS_EPOCH_UNIX = 315964800.0
WEEK_SECONDS = 604800.0
GPS_EPOCH = datetime(1980, 1, 6)
_ACTIVE: dict[str, Any] | None = None
REQUIRED = (
    "sequence_id", "data_mode", "raw_root", "fix_root", "gnss1_raw", "gnss2_raw", "raw_hash_lock",
    "base_time", "window", "start_convention", "native_start_rel_s", "full_pair_count",
    "selected_pair_count", "artifact_root", "method_id", "leap_seconds",
)


class SequenceOverrideError(RuntimeError):
    """The declared HX-02 sequence spec is malformed or inconsistent."""


def activate(spec_path: str | Path) -> dict[str, Any]:
    """Load and freeze the spec for this process; a second activation is refused."""
    global _ACTIVE
    if _ACTIVE is not None:
        raise SequenceOverrideError("a sequence override is already active in this process")
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    if spec.get("schema") != SPEC_SCHEMA:
        raise SequenceOverrideError("sequence spec schema mismatch")
    missing = [key for key in REQUIRED if key not in spec]
    if missing:
        raise SequenceOverrideError(f"sequence spec lacks {missing}")
    if spec["start_convention"] not in ("FILE_START", "CONTRACT_START"):
        raise SequenceOverrideError("unknown start convention")
    if (spec["start_convention"] == "CONTRACT_START") != (spec["native_start_rel_s"] is not None):
        raise SequenceOverrideError("start convention and native start disagree")
    for key in ("raw_root", "fix_root", "gnss1_raw", "gnss2_raw", "raw_hash_lock", "artifact_root"):
        if not Path(spec[key]).is_absolute():
            raise SequenceOverrideError(f"{key} must be absolute")
        if "trace" in Path(spec[key]).name.lower():
            raise SequenceOverrideError("reference trajectory paths are outside the native spec")
    spec["spec_path"] = str(Path(spec_path).resolve())
    _ACTIVE = spec
    return spec


def active() -> dict[str, Any] | None:
    return _ACTIVE


def path(key: str) -> Path:
    if _ACTIVE is None:
        raise SequenceOverrideError("no active sequence override")
    return Path(_ACTIVE[key])


def full_pair_count(default: int) -> int:
    return default if _ACTIVE is None else int(_ACTIVE["full_pair_count"])


def expected_pair_count(default: int) -> int:
    return default if _ACTIVE is None else int(_ACTIVE["selected_pair_count"])


def data_mode(default: str) -> str:
    return default if _ACTIVE is None else str(_ACTIVE["data_mode"])


def option(key: str, default: Any = None) -> Any:
    return default if _ACTIVE is None else _ACTIVE.get(key, default)


def _unix(epoch) -> float:
    return GPS_EPOCH_UNIX + int(epoch.gps_week) * WEEK_SECONDS + float(epoch.gps_tow_seconds) - int(epoch.leap_seconds)


def select_pairs(pairs: Sequence[Any]) -> list[Any]:
    """FILE_START keeps every exact pair; CONTRACT_START keeps pairs at/after the start."""
    if _ACTIVE is None or _ACTIVE["native_start_rel_s"] is None:
        return list(pairs)
    start = float(_ACTIVE["native_start_rel_s"])
    base_time = float(_ACTIVE["base_time"])
    if not math.isfinite(start) or not math.isfinite(base_time):
        raise SequenceOverrideError("nonfinite native start")
    return [pair for pair in pairs if _unix(pair[0]) - base_time >= start]


def gpst_epoch_arguments(option: str, gps_week: int, gps_tow_seconds: float) -> list[str]:
    """RTKLIB ``-ts``/``-te`` value pair for one GPST epoch, millisecond resolution."""
    epoch = GPS_EPOCH + timedelta(weeks=int(gps_week), seconds=float(gps_tow_seconds))
    return [option, epoch.strftime("%Y/%m/%d"), epoch.strftime("%H:%M:%S.%f")[:-3]]


def rtklib_start_arguments(first_selected: tuple[int, float] | None) -> list[str]:
    """``-ts`` at the first selected exact pair for a CONTRACT_START spec; nothing otherwise.

    Starting at the first selected pair (not at base_time + start) keeps RTKLIB's start
    tolerance from admitting the RAWX epoch 2 ms before the contract start, so an in-run
    RTKLIB diagnostic covers exactly the selected epochs.
    """
    if _ACTIVE is None or _ACTIVE["native_start_rel_s"] is None:
        return []
    if first_selected is None:
        raise SequenceOverrideError("CONTRACT_START RTKLIB start needs the first selected pair")
    return gpst_epoch_arguments("-ts", *first_selected)


def echo() -> Mapping[str, Any] | None:
    """The spec fields recorded in native summaries (paths are provenance only)."""
    if _ACTIVE is None:
        return None
    return {key: _ACTIVE[key] for key in (*REQUIRED, "spec_path") if key in _ACTIVE}
