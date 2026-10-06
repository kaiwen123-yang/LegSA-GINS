#!/usr/bin/env python3
"""Run native synthetic audit in alias-resolved scratch; never opens real data.

This is an observation runner: an observed defect is retained in receipts, not
turned into a successful scientific validation. The unmodified target is built
and smoked separately from the capture-only measurement instrumentation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

import yaml

ROOT = Path(__file__).resolve().parents[3]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-config", type=Path, required=True)
    parser.add_argument("--run-id", default="native_initial")
    args = parser.parse_args()
    paths = yaml.safe_load(args.local_config.read_text())["paths"]
    work = Path(paths["audit_scratch"]) / args.run_id
    if work.exists():
        raise SystemExit(f"refuse overwrite: {work}")
    work.mkdir(parents=True)
    output = Path(paths["audit_root"]) / "native" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    build = Path(paths["audit_scratch"]) / "native_build"
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    calls = []

    def run(label: str, command: list[str], timeout: float = 120.0) -> dict:
        start = time.perf_counter()
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
            row = dict(label=label, command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        except subprocess.TimeoutExpired as exc:
            row = dict(label=label, command=command, returncode=None, status="TIMEOUT", stdout=str(exc.stdout or ""), stderr=str(exc.stderr or ""))
        row["elapsed_seconds"] = time.perf_counter() - start
        calls.append(row)
        (output / "CALLS.json").write_text(json.dumps(calls, ensure_ascii=False, indent=2)+"\n")
        print(label, row["returncode"], row.get("status", "EXITED"), flush=True)
        return row

    for label, command in [
        ("configure", ["cmake", "-S", "cpp", "-B", str(build), "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]),
        ("build", ["cmake", "--build", str(build), "--target", "legsa_v23_port_core_demo", "-j4"]),
    ]:
        if run(label, command, 180)["returncode"] != 0:
            raise SystemExit(label+" failed; receipt retained")
    source = ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp"
    original = source.read_text()
    signature = "void GIEngine::EKFUpdate(const std::vector<double>& dz, const Matrix& H, const Matrix& R) {"
    assert original.count(signature) == 1
    replacement = signature + "\n  extern void audit_capture(const std::vector<double>&, const Matrix&, const Matrix&);\n  audit_capture(dz,H,R);"
    instrumented = work / "gi_engine_capture_only.cpp"
    instrumented.write_text(original.replace(signature, replacement))
    executable = work / "native_audit"
    compile_cmd = ["g++", "-std=c++17", "-O2", "-I", str(ROOT / "cpp/legsa_v23_port_core/include"),
                   str(ROOT / "tests/paper_rebuild/audit_xbpg/native_audit.cpp"), str(instrumented),
                   str(build / "liblegsa_v23_port_core.a"), "-o", str(executable)]
    if run("compile_capture_harness", compile_cmd)["returncode"] != 0:
        raise SystemExit("capture harness compilation failed")
    for mode in ["numeric", "jacobians", "scheduler", "nisreset", "performance", "integration"]:
        run(mode, [str(executable), mode])
    for mode in ["wrap", "wrap2pi"]:
        for value in ["inf", "-inf", "1e308", "nan", "7"]:
            run(mode+"_"+value, [str(executable), mode, value], timeout=0.5)
    imu, gnss = work / "truncated.imu", work / "truncated.gnss"
    imu.write_text("1 0 0 0 0 0 -0.098\nTRUNCATED 1\n1 0 0 0 0 0 -0.098\n0.5 0 0 0 0 0 -0.098\n")
    gnss.write_text("1 0.5 1 20 1 1 1 0 0 0 1 1 1 0 1\nBROKEN 2\n")
    run("truncated_duplicate_reversed_and_small_degree_lat", [str(executable), "loader", str(imu), str(gnss)])
    config = work / "parser.yaml"
    config.write_text("data_mode: synthetic\nsynthetic_data_used: true\nstarttime: -1e-3\nendtime: 1e2\nendtime: 2e2 # last wins\nunknown_key: 42\nenable_dual_yaw_update: TRU\nantlever: [1e-2, -2e-2, 3e-2]\nimupath: '中文路径/传感器#1.imu'\n")
    run("yaml_like_parser", [str(executable), "config", str(config)])
    for mode in ["synthetic-math", "raw-doppler-toy", "source-aware-toy", "quality-state-toy", "go2-weak-prior-toy", "qa-fallback-toy"]:
        run("formal_target_"+mode, [str(build / "legsa_v23_port_core_demo"), "--dry-run-"+mode, "--output-dir", str(work / mode)])
    receipt = {
        "data_mode": "synthetic", "synthetic_data_used": True, "semisynthetic_data_used": False,
        "real_data_open_count": 0, "reference_open_count": 0,
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": digest(source), "capture_copy_sha256": digest(instrumented),
        "harness_sha256": digest(ROOT / "tests/paper_rebuild/audit_xbpg/native_audit.cpp"),
        "binary_sha256": digest(build / "legsa_v23_port_core_demo"), "capture_binary_sha256": digest(executable),
        "compiler": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0],
        "platform": platform.platform(), "build_type": "Release", "threads": 1,
        "production_source_modified": False, "instrumentation": "one capture-only hook before EKFUpdate body in scratch copy",
        "call_count": len(calls), "calls": calls,
    }
    (output / "RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    summary = {row["label"]: {key: row.get(key) for key in ["returncode", "status", "elapsed_seconds", "stdout", "stderr"]} for row in calls if row["label"] not in ["configure", "build", "compile_capture_harness"]}
    (ROOT / "docs/paper_rebuild/audit_xbpg_20261001/NATIVE_TEST_RESULTS.json").write_text(json.dumps({"data_mode": "synthetic", "binary_sha256":receipt["binary_sha256"], "results": summary}, indent=2, ensure_ascii=False)+"\n")


if __name__ == "__main__":
    main()
