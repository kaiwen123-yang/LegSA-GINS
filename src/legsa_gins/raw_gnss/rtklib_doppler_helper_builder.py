"""Build a runtime-only RTKLIB Doppler velocity helper for N5B.

中文说明：helper 源码和编译产物只写入 runtime output dir。必要时复制 RTKLIB
源码到 runtime 目录并补丁 pntpos.c，使 Doppler velocity 估计真正调用；不修改本机
RTKLIB 根目录，不提交复制结果。
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any


REQUIRED_SOURCE_FILES = [
    "rtklib.h",
    "pntpos.c",
    "rtkcmn.c",
    "ephemeris.c",
    "rinex.c",
    "preceph.c",
    "options.c",
    "solution.c",
    "geoid.c",
    "lambda.c",
    "sbas.c",
    "ionex.c",
]
HELPER_C_FILES = [name for name in REQUIRED_SOURCE_FILES if name.endswith(".c")]
SOURCE_FUNCTIONS = ["pntpos", "estvel", "resdop", "satposs", "eph2pos", "geph2pos", "seleph", "readrnx"]


HELPER_SOURCE = r'''
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rtklib.h"

/* 中文说明：该 helper 只输出 RTKLIB Doppler-derived velocity，不输出位置解作为 LegSA 输入。 */
static int same_epoch(gtime_t a, gtime_t b) {
    return fabs(timediff(a, b)) < 1E-9;
}

static int doppler_count(const obsd_t *obs, int n) {
    int count = 0;
    for (int i = 0; i < n; ++i) {
        for (int f = 0; f < NFREQ + NEXOBS; ++f) {
            if (obs[i].D[f] != 0.0) {
                ++count;
                break;
            }
        }
    }
    return count;
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: %s obs nav output_csv\n", argv[0]);
        return 2;
    }
    obs_t obs = {0};
    nav_t nav = {0};
    sta_t sta = {0};
    if (!readrnx(argv[1], 1, "", &obs, &nav, &sta)) {
        fprintf(stderr, "read obs failed: %s\n", argv[1]);
        return 3;
    }
    if (!readrnx(argv[2], 1, "", &obs, &nav, &sta)) {
        fprintf(stderr, "read nav failed: %s\n", argv[2]);
        return 4;
    }
    sortobs(&obs);
    uniqnav(&nav);
    FILE *fp = fopen(argv[3], "w");
    if (!fp) {
        perror("open output csv");
        return 5;
    }
    fprintf(fp, "time,vecef_x,vecef_y,vecef_z,std_vx,std_vy,std_vz,sat_count,doppler_obs_count,provider_status,source_epoch_time,quality_flag\n");
    prcopt_t opt = prcopt_default;
    opt.mode = PMODE_SINGLE;
    opt.navsys = SYS_ALL;
    int rows = 0;
    for (int i = 0; i < obs.n;) {
        int j = i + 1;
        while (j < obs.n && same_epoch(obs.data[i].time, obs.data[j].time)) {
            ++j;
        }
        const int n = j - i;
        sol_t sol = {0};
        double azel[MAXOBS * 2] = {0};
        ssat_t ssat[MAXSAT];
        char msg[1024] = "";
        memset(ssat, 0, sizeof(ssat));
        const int ok = pntpos(obs.data + i, n, &nav, &opt, &sol, azel, ssat, msg);
        const double tow = time2gpst(sol.time, NULL);
        const int dop = doppler_count(obs.data + i, n);
        if (ok && sol.stat != SOLQ_NONE && isfinite(sol.rr[3]) && isfinite(sol.rr[4]) && isfinite(sol.rr[5]) &&
            fabs(sol.rr[3]) + fabs(sol.rr[4]) + fabs(sol.rr[5]) > 1E-9) {
            const double svx = sqrt(fmax(sol.qv[0], 0.04));
            const double svy = sqrt(fmax(sol.qv[1], 0.04));
            const double svz = sqrt(fmax(sol.qv[2], 0.04));
            fprintf(fp, "%.3f,%.9f,%.9f,%.9f,%.6f,%.6f,%.6f,%d,%d,available,%.3f,%d\n",
                    tow, sol.rr[3], sol.rr[4], sol.rr[5], svx, svy, svz, sol.ns, dop, tow, sol.stat);
            ++rows;
        }
        i = j;
    }
    fclose(fp);
    fprintf(stderr, "rows=%d obs=%d nav_eph=%d\n", rows, obs.n, nav.n);
    return rows > 0 ? 0 : 6;
}
'''


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if text else ""


def _find_source_dir(rtklib_root: str | Path) -> Path | None:
    root = Path(rtklib_root).expanduser()
    if not root.exists():
        return None
    for current, _, files in os.walk(root):
        if "rtklib.h" in files and "pntpos.c" in files:
            return Path(current)
    return None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def discover_rtklib_source_layout(rtklib_root: str | Path) -> dict[str, Any]:
    root = Path(rtklib_root).expanduser()
    source_dir = _find_source_dir(root)
    files: dict[str, str | None] = {name: None for name in REQUIRED_SOURCE_FILES}
    if source_dir:
        for name in REQUIRED_SOURCE_FILES:
            candidate = source_dir / name
            if candidate.exists():
                files[name] = str(candidate)
    hits: dict[str, list[str]] = {name: [] for name in SOURCE_FUNCTIONS}
    for name, path_text in files.items():
        if not path_text or not name.endswith((".c", ".h")):
            continue
        content = _read(Path(path_text))
        for fn in SOURCE_FUNCTIONS:
            if fn in content:
                hits[fn].append(path_text)
    pntpos = _read(Path(files["pntpos.c"])) if files.get("pntpos.c") else ""
    return {
        "rtklib_root_exists": root.exists(),
        "source_dir": str(source_dir) if source_dir else "",
        "required_source_files": files,
        "missing_source_files": [name for name, path_text in files.items() if not path_text],
        "rtklib_source_functions_found": hits,
        "pntpos_velocity_call_disabled": "estvel_muti" in pntpos and "//    estvel_muti" in pntpos,
    }


def _patch_header(header: Path) -> bool:
    text = _read(header)
    patched = text.replace(
        "#define WIN32\n",
        "/* LegSA runtime-only helper patch: build under WSL/Linux, not Windows API. */\n/* #define WIN32 */\n",
    )
    if patched != text:
        header.write_text(patched, encoding="utf-8")
        return True
    return False


def _patch_pntpos(pntpos: Path) -> bool:
    text = _read(pntpos)
    old = "//if (stat) {\n    //    estvel_muti(obs,n,rs,dts,nav,&opt_,sol,azel_,vsat,ssat);\n    //}"
    new = "if (stat) {\n        estvel_muti(obs,n,rs,dts,nav,&opt_,sol,azel_,vsat,ssat);\n    }"
    if old in text:
        pntpos.write_text(text.replace(old, new), encoding="utf-8")
        return True
    return False


def _classify_compile_failure(stderr: str, missing: list[str]) -> list[str]:
    blockers: list[str] = []
    if missing:
        blockers.append("missing_source_files")
    lower = stderr.lower()
    if "no such file or directory" in lower or "fatal error" in lower:
        blockers.append("missing_headers")
    if "undefined reference" in lower or "ld returned" in lower:
        blockers.append("link_errors")
    if "static" in lower and ("estvel" in lower or "resdop" in lower):
        blockers.append("static_function_access")
    if "windows.h" in lower or "winsock" in lower:
        blockers.append("windows_toolchain_issue")
    return sorted(set(blockers or ["unknown"]))


def _wsl_path(path: Path) -> str:
    path_text = str(path.resolve()).replace("\\", "/")
    proc = subprocess.run(
        ["wsl", "wslpath", "-a", path_text],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"wslpath failed for {path}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _wsl_gcc_available() -> bool:
    if os.name != "nt" or not shutil.which("wsl"):
        return False
    proc = subprocess.run(
        ["wsl", "bash", "-lc", "command -v gcc >/dev/null 2>&1"],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode == 0


def _run_compile(command: list[str], helper_exe: Path, source_copy: Path, helper_source: Path, c_files: list[str]) -> tuple[subprocess.CompletedProcess[str], list[str], str]:
    if shutil.which(command[0]):
        proc = subprocess.run(command, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return proc, command, "native_gcc"
    if _wsl_gcc_available():
        source_copy_wsl = _wsl_path(source_copy)
        helper_exe_wsl = _wsl_path(helper_exe)
        helper_source_wsl = _wsl_path(helper_source)
        c_files_wsl = [_wsl_path(Path(path)) for path in c_files]
        inner = " ".join(
            [
                "gcc",
                "-O2",
                "-I",
                shlex.quote(source_copy_wsl),
                "-o",
                shlex.quote(helper_exe_wsl),
                shlex.quote(helper_source_wsl),
                *[shlex.quote(path) for path in c_files_wsl],
                "-lm",
                "-lpthread",
            ]
        )
        wsl_command = ["wsl", "bash", "-lc", inner]
        proc = subprocess.run(wsl_command, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return proc, wsl_command, "wsl_gcc"
    raise FileNotFoundError(command[0])


def build_rtklib_doppler_helper(rtklib_root: str | Path, build_dir: str | Path | None, output_dir: str | Path) -> dict[str, Any]:
    layout = discover_rtklib_source_layout(rtklib_root)
    out = Path(output_dir)
    helper_root = out / "tmp_rtklib_helper"
    source_copy = helper_root / "rtklib_src"
    helper_root.mkdir(parents=True, exist_ok=True)
    source_copy.mkdir(parents=True, exist_ok=True)
    helper_source = helper_root / "legsa_rtklib_doppler_helper.c"
    helper_exe = helper_root / "legsa_rtklib_doppler_helper"
    patches: list[str] = []
    blockers: list[str] = []

    if layout["missing_source_files"]:
        blockers.append("missing_source_files")
        report = {
            **layout,
            "helper_source_generated": False,
            "helper_compile_attempted": False,
            "helper_compile_status": "failed",
            "helper_executable_path": "",
            "helper_uses_rtklib_source": False,
            "runtime_patch_applied": [],
            "compile_command": [],
            "compile_stdout_tail": "",
            "compile_stderr_tail": "",
            "blocker_reasons": blockers,
        }
        return report

    for name, path_text in layout["required_source_files"].items():
        shutil.copy2(Path(path_text), source_copy / name)
    if _patch_header(source_copy / "rtklib.h"):
        patches.append("rtklib_h_disable_WIN32_for_wsl_runtime_build")
    if _patch_pntpos(source_copy / "pntpos.c"):
        patches.append("pntpos_enable_estvel_muti_doppler_velocity_runtime_only")
    helper_source.write_text(HELPER_SOURCE.strip() + "\n", encoding="utf-8")

    c_files = [str(source_copy / name) for name in HELPER_C_FILES]
    command = [
        "gcc",
        "-O2",
        "-I",
        str(source_copy),
        "-o",
        str(helper_exe),
        str(helper_source),
        *c_files,
        "-lm",
        "-lpthread",
    ]
    try:
        proc, compile_command, compiler_mode = _run_compile(command, helper_exe, source_copy, helper_source, c_files)
    except FileNotFoundError:
        blockers.append("compile_tool_missing")
        return {
            **layout,
            "build_dir_argument": str(build_dir) if build_dir else "",
            "helper_source_generated": helper_source.exists(),
            "helper_compile_attempted": True,
            "helper_compile_status": "failed",
            "helper_executable_path": "",
            "helper_uses_rtklib_source": True,
            "runtime_patch_applied": patches,
            "compile_command": command,
            "compile_stdout_tail": "",
            "compile_stderr_tail": "gcc executable not found",
            "compiler_mode": "missing",
            "blocker_reasons": sorted(set(blockers)),
        }
    success = proc.returncode == 0 and helper_exe.exists()
    if not success:
        blockers.extend(_classify_compile_failure(proc.stderr, layout["missing_source_files"]))
    return {
        **layout,
        "build_dir_argument": str(build_dir) if build_dir else "",
        "helper_source_generated": helper_source.exists(),
        "helper_compile_attempted": True,
        "helper_compile_status": "success" if success else "failed",
        "helper_executable_path": str(helper_exe) if success else "",
        "helper_uses_rtklib_source": True,
        "runtime_patch_applied": patches,
        "compile_command": compile_command,
        "compile_stdout_tail": _tail(proc.stdout),
        "compile_stderr_tail": _tail(proc.stderr),
        "compiler_mode": compiler_mode,
        "blocker_reasons": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rtklib-root", required=True)
    parser.add_argument("--build-dir")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    report = build_rtklib_doppler_helper(args.rtklib_root, args.build_dir, args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
