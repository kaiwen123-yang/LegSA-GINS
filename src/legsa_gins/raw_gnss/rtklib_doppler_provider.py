"""RTKLIB-backed N5A raw Doppler provider attempt.

中文说明：本模块实打实调用 convbin/rnx2rtkp 做数据可用性诊断，并扫描 RTKLIB
源码中的 satposs/eph2pos/resdop/estvel 等成熟函数证据。但 rnx2rtkp 的最终定位解
不能直接作为 LegSA solver input；除非存在 satellite-state 或 Doppler velocity 导出
provider，否则 raw Doppler solver activation 必须保持 blocked。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .rtklib_command_runner import run_command


SOURCE_FUNCTIONS = ["estvel", "resdop", "satposs", "eph2pos", "geph2pos", "seleph", "readrnx"]


def _wslpath(path: str | Path) -> str:
    text = str(path)
    try:
        proc = subprocess.run(["wslpath", "-w", text], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except OSError:
        pass
    return text


def _exe_arg(executable: str, path: str | Path) -> str:
    if executable.lower().endswith(".exe"):
        return _wslpath(path)
    return str(path)


def _source_function_hits(candidate_source_files: dict[str, str | None]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {name: [] for name in SOURCE_FUNCTIONS}
    for path_text in candidate_source_files.values():
        if not path_text:
            continue
        path = Path(path_text)
        if not path.exists() or path.suffix.lower() not in {".c", ".h", ".cpp", ".hpp"}:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for fn in SOURCE_FUNCTIONS:
            if fn in content:
                hits[fn].append(str(path))
    return hits


def _best_external_nav(ephemeris_report: dict[str, Any]) -> str:
    return (
        ephemeris_report.get("best_broadcast_nav_candidate")
        or ephemeris_report.get("best_sp3_candidate")
        or ""
    )


def attempt_rtklib_provider(
    *,
    rtklib_report: dict[str, Any],
    ephemeris_report: dict[str, Any],
    rebuild_report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    convbin_path = rtklib_report.get("convbin_path") or ""
    rnx2rtkp_path = rtklib_report.get("rnx2rtkp_path") or ""
    source_hits = _source_function_hits(rtklib_report.get("candidate_source_files", {}))
    obs_generated = False
    nav_generated = False
    convbin_status: dict[str, Any] = {"status": "not_run", "runs": []}
    rnx2rtkp_status: dict[str, Any] = {"status": "not_run", "runs": []}
    generated_obs: list[str] = []
    generated_nav: list[str] = []
    external_nav = _best_external_nav(ephemeris_report)

    if convbin_path and rebuild_report.get("rebuilt_ubx_available"):
        convbin_status["status"] = "attempted"
        for source_name, item in rebuild_report.get("files", {}).items():
            if not item.get("rebuilt_ubx_available"):
                continue
            ubx = Path(item.get("output_ubx", ""))
            if not ubx.exists():
                continue
            stem = source_name.replace("-raw.csv", "")
            obs = output_dir / f"{stem}.obs"
            nav = output_dir / f"{stem}.nav"
            args = [
                "-r",
                "ubx",
                "-od",
                "-os",
                "-oi",
                "-ot",
                "-o",
                _exe_arg(convbin_path, obs),
                "-n",
                _exe_arg(convbin_path, nav),
                _exe_arg(convbin_path, ubx),
            ]
            result = run_command(convbin_path, args, timeout=120.0)
            run_info = result.to_dict()
            run_info["source_name"] = source_name
            run_info["obs_path"] = str(obs)
            run_info["nav_path"] = str(nav)
            convbin_status["runs"].append(run_info)
            if obs.exists() and obs.stat().st_size > 0:
                obs_generated = True
                generated_obs.append(str(obs))
            if nav.exists() and nav.stat().st_size > 0:
                nav_generated = True
                generated_nav.append(str(nav))
        if obs_generated:
            convbin_status["status"] = "success"
        elif convbin_status["runs"]:
            convbin_status["status"] = "failed"
    elif not convbin_path:
        convbin_status["status"] = "convbin_missing"
    else:
        convbin_status["status"] = "rebuilt_ubx_missing"

    if rnx2rtkp_path and generated_obs and (generated_nav or external_nav):
        rnx2rtkp_status["status"] = "attempted"
        nav_arg = generated_nav[0] if generated_nav else external_nav
        for obs in generated_obs[:2]:
            pos = output_dir / (Path(obs).stem + "_rtklib_diag.pos")
            args = ["-o", _exe_arg(rnx2rtkp_path, pos), _exe_arg(rnx2rtkp_path, obs), _exe_arg(rnx2rtkp_path, nav_arg)]
            result = run_command(rnx2rtkp_path, args, timeout=120.0)
            run_info = result.to_dict()
            run_info["obs_path"] = obs
            run_info["nav_or_sp3_path"] = nav_arg
            run_info["pos_path"] = str(pos)
            run_info["diagnostic_only_not_solver_input"] = True
            rnx2rtkp_status["runs"].append(run_info)
        rnx2rtkp_status["status"] = (
            "success"
            if any(Path(run.get("pos_path", "")).exists() and Path(run.get("pos_path", "")).stat().st_size > 0 for run in rnx2rtkp_status["runs"])
            else "failed"
        )
    elif not rnx2rtkp_path:
        rnx2rtkp_status["status"] = "rnx2rtkp_missing"
    else:
        rnx2rtkp_status["status"] = "obs_or_nav_missing"

    # 中文说明：N5A 不把 rnx2rtkp position solution 输入 EKF；需要单独 satellite-state/velocity export provider。
    provider_status = "provider_missing_sat_state_export"
    helper_compile_status = "not_attempted_no_stable_rtklib_helper_api"
    helper_run_status = "not_run_provider_missing_sat_state_export"
    blockers = []
    if not rtklib_report.get("rtklib_provider_available", False):
        blockers.append("rtklib_missing")
    if not ephemeris_report.get("ephemeris_available", False):
        blockers.append("ephemeris_missing")
    if not rebuild_report.get("rawx_frame_count", 0):
        blockers.append("rawx_missing")
    blockers.append(provider_status)

    return {
        "rtklib_found": rtklib_report.get("rtklib_provider_available", False),
        "convbin_run_status": convbin_status,
        "obs_generated": obs_generated,
        "generated_obs_files": generated_obs,
        "nav_generated": nav_generated,
        "generated_nav_files": generated_nav,
        "external_ephemeris_used": bool(external_nav),
        "external_ephemeris_path": external_nav,
        "rnx2rtkp_diagnostic_status": rnx2rtkp_status,
        "rnx2rtkp_output_not_solver_input": True,
        "rtklib_source_functions_found": source_hits,
        "helper_compile_status": helper_compile_status,
        "helper_run_status": helper_run_status,
        "satellite_state_provider_status": provider_status,
        "doppler_velocity_factor_generated": False,
        "raw_doppler_solver_activation_allowed": False,
        "blocker_reasons": sorted(set(blockers)),
        "recommended_next_stage": "N5B_rtklib_satellite_state_export_provider",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_report(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
