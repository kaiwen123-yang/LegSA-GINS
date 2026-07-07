"""Run RTKLIB convbin and summarize RINEX observations for DA01."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _run(command: list[str], *, timeout: float = 180.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "returncode": 127, "stdout_tail": "", "stderr_tail": str(exc)}


def summarize_rinex_obs(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists() or source.stat().st_size == 0:
        return {"path": str(source), "exists": source.exists(), "epoch_count": 0, "satellite_observation_count": 0, "systems": {}}
    in_header = True
    epochs = 0
    sat_obs = 0
    systems: dict[str, int] = {}
    for line in source.read_text(encoding="utf-8", errors="ignore").splitlines():
        if in_header:
            if "END OF HEADER" in line:
                in_header = False
            continue
        if line.startswith(">"):
            epochs += 1
            continue
        if line and line[0].isalpha():
            sat_obs += 1
            systems[line[0]] = systems.get(line[0], 0) + 1
    return {
        "path": str(source),
        "exists": True,
        "file_size_bytes": source.stat().st_size,
        "epoch_count": epochs,
        "satellite_observation_count": sat_obs,
        "systems": dict(sorted(systems.items())),
    }


def convert_ubx_to_rinex(convbin_path: str | Path, ubx_files: dict[str, str | Path], output_dir: str | Path) -> dict[str, Any]:
    convbin = Path(convbin_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    obs_files: dict[str, str] = {}
    nav_files: dict[str, str] = {}
    for label, ubx_path in ubx_files.items():
        ubx = Path(ubx_path)
        obs = out / f"{label}.obs"
        nav = out / f"{label}.nav"
        if not convbin.exists():
            runs.append({"label": label, "returncode": 127, "stderr_tail": "convbin_missing", "obs_path": str(obs), "nav_path": str(nav)})
            continue
        if not ubx.exists():
            runs.append({"label": label, "returncode": 127, "stderr_tail": "ubx_missing", "obs_path": str(obs), "nav_path": str(nav)})
            continue
        command = [str(convbin), "-r", "ubx", "-od", "-os", "-oi", "-ot", "-o", str(obs), "-n", str(nav), str(ubx)]
        run = _run(command)
        run.update({"label": label, "obs_path": str(obs), "nav_path": str(nav)})
        runs.append(run)
        if obs.exists() and obs.stat().st_size > 0:
            obs_files[label] = str(obs)
        if nav.exists() and nav.stat().st_size > 0:
            nav_files[label] = str(nav)
    obs_summaries = {label: summarize_rinex_obs(path) for label, path in obs_files.items()}
    return {
        "convbin_path": str(convbin),
        "runs": runs,
        "obs_files": obs_files,
        "nav_files": nav_files,
        "obs_generated": len(obs_files) == len(ubx_files) and bool(obs_files),
        "nav_generated": bool(nav_files),
        "obs_summaries": obs_summaries,
        "blocker_reasons": []
        if len(obs_files) == len(ubx_files) and bool(obs_files)
        else ["rinex_obs_generation_incomplete"],
    }
