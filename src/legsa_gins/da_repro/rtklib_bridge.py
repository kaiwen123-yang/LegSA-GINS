"""Runtime-only RTKLIB bridge for UBX -> RINEX -> relative baseline."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import rebuild_fix_root


def rebuild_ubx(receiver_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    return rebuild_fix_root(receiver_root, output_dir)


def run_convbin(convbin: str | Path, ubx_path: str | Path, obs_path: str | Path, nav_path: str | Path) -> dict[str, Any]:
    convbin = Path(convbin)
    obs_path = Path(obs_path)
    nav_path = Path(nav_path)
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(convbin), str(ubx_path), "-r", "ubx", "-od", "-os", "-oi", "-ot", "-ol", "-o", str(obs_path), "-n", str(nav_path)],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "tool": "convbin",
        "returncode": proc.returncode,
        "obs_path": str(obs_path),
        "nav_path": str(nav_path),
        "obs_ready": obs_path.exists() and obs_path.stat().st_size > 0,
        "nav_ready": nav_path.exists() and nav_path.stat().st_size > 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def run_rnx2rtkp_moving_base(
    rnx2rtkp: str | Path,
    rover_obs: str | Path,
    base_obs: str | Path,
    nav_files: list[str | Path],
    output_pos: str | Path,
) -> dict[str, Any]:
    output_pos = Path(output_pos)
    output_pos.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(rnx2rtkp),
        "-p",
        "4",
        "-a",
        "-f",
        "2",
        "-v",
        "3",
        "-i",
        "-t",
        "-d",
        "3",
        "-s",
        ",",
        "-y",
        "2",
        "-o",
        str(output_pos),
        str(rover_obs),
        str(base_obs),
        *[str(path) for path in nav_files],
    ]
    proc = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "tool": "rnx2rtkp",
        "returncode": proc.returncode,
        "output_pos": str(output_pos),
        "solution_ready": output_pos.exists() and output_pos.stat().st_size > 0,
        "command": " ".join(cmd),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }
