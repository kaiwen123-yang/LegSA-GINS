"""Satpos/LOS readiness summaries for RTKLIB-backed DA3R2 runs."""

from __future__ import annotations

from pathlib import Path


def rinex_satpos_los_summary(obs_paths: list[str | Path], nav_paths: list[str | Path], rtklib_solution_rows: int) -> dict[str, object]:
    obs = [Path(path) for path in obs_paths]
    nav = [Path(path) for path in nav_paths]
    return {
        "rinex_obs_files": [path.name for path in obs],
        "rinex_nav_files": [path.name for path in nav],
        "rinex_obs_ready": all(path.exists() and path.stat().st_size > 0 for path in obs),
        "rinex_nav_ready": all(path.exists() and path.stat().st_size > 0 for path in nav),
        "satpos_los_ready": rtklib_solution_rows > 0,
        "satpos_los_backend": "RTKLIB rnx2rtkp relative carrier processor",
        "direct_python_satpos_implemented": False,
        "notes": "LOS/satellite-state evidence is mediated through RTKLIB relative processing; method claims remain non-exact.",
    }
