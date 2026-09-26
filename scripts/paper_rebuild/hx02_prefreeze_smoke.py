#!/usr/bin/env python3
"""HX-02 pre-freeze technical smoke: every native path on a truncated input, never evaluated.

Purpose: exercise the sequence adaptation layer, the runner overrides, the heading/NAV
adapters, the parameter echo and the native open audit before the code freeze, so an
adapter defect cannot surface for the first time inside a registered run. Inputs are
truncated, so no output is a registered run and none is evaluated:

  EXT01-EXT04  BY2H CONTRACT_START, first 20 selected exact pairs (selection exercised, then cut);
               EXT01's committed-source check is bypassed, its fixed worker-determinism subset
               (epochs 0,1,2,100,431,432,994,last) is clipped to the cut input and its in-run
               RTKLIB diagnostic gets -te at the last kept pair, here only; the registered run
               follows the code-freeze commit and uses all three unchanged
  RTKLIB       BY2H, registered -ts plus -te 10 s later
  Hartley-S/LIT BY2 FILE_START pinned cache cut to its first 3000 records
  GINav        BY2 pinned inputs, derived configuration with end_time = start_time + 120 s

Everything runs under the same openat/execve audit as the registered runs. Outputs stay
in <HX02_SCRATCH>/PREFREEZE_SMOKE and are deleted after the summary is written to
$HX02/00_CONTROL/PREFREEZE_SMOKE_SUMMARY.json. No evaluator runs; no reference is opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import struct
import sys
from datetime import datetime, timedelta
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from legsa_gins.paper_rebuild.hext import (  # noqa: E402
    hx02_execution as ex, hx02_ginav, hx02_hartley, hx02_heading_tables, hx02_params_echo, hx02_rtklib, hx02_sequence)

EXT_PAIRS = 20
HARTLEY_RECORDS = 3000
GINAV_SECONDS = 120
RTKLIB_SECONDS = 10.0


def ext_wrapper(args: argparse.Namespace) -> int:
    """Inside the audited process: cut the selected pairs to N, then run the runner script unchanged."""
    from legsa_gins.paper_rebuild.horizontal_literature import sequence_override
    original = sequence_override.select_pairs
    kept_last: list = []

    def truncated(pairs):
        kept = list(original(pairs))[:args.pairs]
        kept_last[:] = [kept[-1][0]] if kept else []
        return kept
    sequence_override.select_pairs = truncated
    original_start = sequence_override.rtklib_start_arguments

    def start_and_end(first_selected):
        # the in-run RTKLIB diagnostic ends 0.1 s after the last kept pair (smoke only)
        epoch = kept_last[0]
        return [*original_start(first_selected),
                *sequence_override.gpst_epoch_arguments("-te", epoch.gps_week, float(epoch.gps_tow_seconds) + 0.1)]
    sequence_override.rtklib_start_arguments = start_and_end
    if Path(args.script).name == "run_horizontal_literature_phase1r.py":
        import subprocess
        from legsa_gins.paper_rebuild.horizontal_literature import phase1r_runner

        def smoke_code_freeze(paths):
            root = paths.base.code_root
            sources = (root / "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py",
                       root / "src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py",
                       root / "src/legsa_gins/paper_rebuild/horizontal_literature/phase1r_runner.py",
                       root / "scripts/paper_rebuild/run_horizontal_literature_phase1r.py", paths.contract)
            return {"code_commit": subprocess.run(["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=root,
                                                  capture_output=True, text=True, check=True).stdout.strip(),
                    "source_hashes": {str(Path(p).relative_to(root)): hx02_sequence.sha256_file(Path(p)) for p in sources},
                    "tracked_and_staged_diff_clean": False, "prefreeze_smoke_bypass": True,
                    "untracked_files_are_not_a_runtime_dependency": True,
                    "canonical541_files_opened_by_runner": False, "canonical541_files_modified_by_runner": False}
        phase1r_runner._code_freeze = smoke_code_freeze
        original_parts = phase1r_runner._run_epoch_parts

        def smoke_parts(paths, fingerprint, pairs, positions, spp_failures, navigation_paths, workers, indices=None):
            # the fixed worker-determinism subset (0,1,2,100,431,432,994,last) is clipped to the cut input
            if indices is not None:
                indices = [index for index in indices if index < len(pairs)]
            return original_parts(paths, fingerprint, pairs, positions, spp_failures, navigation_paths, workers, indices)
        phase1r_runner._run_epoch_parts = smoke_parts
    sys.argv = [args.script, *args.rest]
    try:
        runpy.run_path(args.script, run_name="__main__")
    except SystemExit as exc:
        return int(exc.code or 0) if not isinstance(exc.code, str) else 1
    return 0


def rtklib_wrapper(args: argparse.Namespace) -> int:
    from legsa_gins.paper_rebuild.horizontal_literature import sequence_override
    original = hx02_rtklib.gpst_start_arguments

    def with_end(selected_pairs):
        week, tow = selected_pairs[0]
        return original(selected_pairs) + sequence_override.gpst_epoch_arguments("-te", week, float(tow) + RTKLIB_SECONDS)
    hx02_rtklib.gpst_start_arguments = with_end
    from legsa_gins.paper_rebuild.hext import hx02_native_cli
    return hx02_native_cli.main(["rtklib", "--sequence", "BY2H", "--run-dir", args.run_dir, "--conf", args.conf])


def ginav_wrapper(args: argparse.Namespace) -> int:
    prepared = json.loads(Path(args.prepared).read_text(encoding="utf-8"))
    template = Path(prepared["config"]["config"])
    start = datetime.strptime(prepared["config"]["replaced"]["start_time"]["new"], "%Y/%m/%d %H:%M:%S")
    lines = template.read_bytes().decode("ascii").splitlines(keepends=True)
    smoke = Path(args.run_dir) / "native" / "SMOKE_GINAV.ini"
    out = []
    for line in lines:
        match = hx02_ginav.LINE_RE["end_time"].match(line.rstrip("\r\n"))
        if match:
            ending = line[len(line.rstrip("\r\n")):]
            line = match.group(1) + (start + timedelta(seconds=GINAV_SECONDS)).strftime("%Y/%m/%d %H:%M:%S") + match.group(3) + ending
        out.append(line)
    smoke.write_bytes("".join(out).encode("ascii"))
    prepared["config"] = {**prepared["config"], "config": str(smoke)}
    listing = json.loads(Path(args.pinned_listing).read_text(encoding="utf-8"))["items"]
    result = hx02_ginav.run_ginav(prepared, run_root=Path(args.run_dir) / "native" / "GINAV_RUN",
                                  mirror_manifest_items=listing, external_root=Path(args.external_root))
    (Path(args.run_dir) / "native" / "GINAV_RUN.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    return 0 if result.get("returncode") == 0 else 2


def _audit(roots, seq, run_dir: Path, declared) -> dict:
    log = run_dir / "native" / "SMOKE_OPENAT.strace"
    audit = ex.audit_native_strace(log, roots, seq, declared)
    return {k: audit[k] for k in ("reference_open_count", "old_runtime_input_count", "old_runtime_input_paths",
                                  "undeclared_raw_paths", "executed_programs")}


def run(args: argparse.Namespace) -> int:
    os.chdir(REPOSITORY_ROOT)
    roots = ex.load_roots(Path(args.paths_config))
    pins = json.loads((roots.pins / "INPUT_PINS.json").read_text(encoding="utf-8"))
    reference_echo = json.loads((roots.pins / "PARAMS_ECHO_REFERENCE.json").read_text(encoding="utf-8"))
    base = roots.scratch / f"PREFREEZE_SMOKE{args.attempt}"
    base.mkdir(parents=True, exist_ok=False)
    wanted = set(args.methods.split(",")) if args.methods else None
    by2h = hx02_sequence.load_sequence("BY2H", roots.contract)
    by2 = hx02_sequence.load_sequence("BY2", roots.contract)
    summary: dict = {"utc_start": ex.utc(), "purpose": __doc__.split("\n\n")[1].replace("\n", " "),
                     "evaluator_calls": 0, "reference_opened": False, "runs": {}}
    me = str(Path(__file__).resolve())
    for method in ("EXT01", "EXT02", "EXT03", "EXT04"):
        if wanted is not None and method not in wanted:
            continue
        run_dir = base / method
        (run_dir / "native").mkdir(parents=True)
        spec = ex.sequence_spec(roots, by2h, method, run_dir / "native" / "ARTIFACT", pins["pairing"]["BY2H"])
        spec["selected_pair_count"] = EXT_PAIRS
        hx02_sequence.write_spec(run_dir / "native" / "SEQUENCE_SPEC.json", spec)
        script, extra = ex.RUNNER_SCRIPTS[method]
        argv = [sys.executable, me, "ext-wrapper", "--pairs", str(EXT_PAIRS), "--script", str(roots.code / script), "--",
                "--paths-config", str(roots.paths_config), "--sequence-spec", str(run_dir / "native" / "SEQUENCE_SPEC.json"),
                *extra]
        result = ex.launch(argv, cwd=roots.code, run_dir=run_dir, env_extra={}, timeout_s=3600, label="SMOKE")
        entry = {"returncode": result["returncode"], "runtime_seconds": result["runtime_seconds"],
                 "stderr_tail": result["stderr_tail"][-1500:],
                 "audit": _audit(roots, by2h, run_dir, [by2h.gnss1_raw, by2h.gnss2_raw])}
        heading = run_dir / "native" / "ARTIFACT" / ex.NATIVE_HEADING_CSV[method]
        entry["heading_csv_present"] = heading.is_file()
        entry["freeze_present"] = (run_dir / "native" / "ARTIFACT" / ex.NATIVE_FREEZE[method]).is_file()
        if heading.is_file():
            tables = hx02_heading_tables.ADAPTERS[method](heading, by2h.leap_seconds)
            entry["heading_tables"] = {label: {"rows": len(rows), "valid": sum(r["valid"] for r in rows)}
                                       for label, rows in tables.items()}
            try:
                echo = getattr(hx02_params_echo, method.lower())(run_dir / "native" / "ARTIFACT")
                entry["params_echo"] = hx02_params_echo.compare(echo, reference_echo[method])
            except Exception as exc:  # recorded; examined before the freeze
                entry["params_echo"] = {"error": f"{type(exc).__name__}: {exc}"}
        summary["runs"][method] = entry
    run_dir = base / "RTKLIB"
    if wanted is not None and "RTKLIB" not in wanted:
        run_dir = None
    if run_dir is not None:
        _smoke_rtklib(roots, by2h, base, me, reference_echo, summary)
    for method, config in (("HARTLEY_S", "S"), ("HARTLEY_LIT", "LIT")):
        if wanted is None or method in wanted:
            _smoke_hartley(roots, by2, base, pins, reference_echo, summary, method, config)
    if wanted is None or "GINAV" in wanted:
        _smoke_ginav(roots, by2, base, me, summary)
    summary["utc_end"] = ex.utc()
    out = roots.control / f"PREFREEZE_SMOKE_SUMMARY{args.attempt}.json"
    ex.write_json(out, summary)
    print(json.dumps({k: {kk: v.get(kk) for kk in ("returncode", "heading_tables", "params_echo", "audit", "nav_present",
                                                    "native_output_count", "fopen_ledger_lines", "q_counts")}
                      for k, v in summary["runs"].items()}, indent=1, default=str)[:12000])
    return 0


def _smoke_rtklib(roots, by2h, base, me, reference_echo, summary):
    run_dir = base / "RTKLIB"
    (run_dir / "native").mkdir(parents=True)
    argv = [sys.executable, me, "rtklib-wrapper", "--run-dir", str(run_dir),
            "--conf", str(roots.pins / "RTKLIB_UNMODIFIED_MOVING_BASE.conf")]
    result = ex.launch(argv, cwd=roots.code, run_dir=run_dir, env_extra={}, timeout_s=3600, label="SMOKE")
    entry = {"returncode": result["returncode"], "stderr_tail": result["stderr_tail"][-1500:],
             "audit": _audit(roots, by2h, run_dir, [by2h.gnss1_raw, by2h.gnss2_raw])}
    pos = run_dir / "native" / "RTKLIB_UNMODIFIED_MOVING_BASE.pos"
    if pos.is_file():
        prepared = json.loads((run_dir / "native" / "RTKLIB_PREPARED.json").read_text(encoding="utf-8"))
        rows, association = hx02_rtklib.heading_table(prepared, pos, by2h.leap_seconds)
        run_json = json.loads((run_dir / "native" / "RTKLIB_RUN.json").read_text(encoding="utf-8"))
        entry.update(argv_tail=run_json["argv"][5:10], selected_pairs=len(prepared["selected_pairs"]),
                     table_rows=len(rows), q_counts=association["q_counts"],
                     params_echo=hx02_params_echo.compare(hx02_params_echo.rtklib(run_dir / "native" / "RTKLIB_UNMODIFIED_MOVING_BASE.conf"),
                                                          reference_echo["RTKLIB"]))
    summary["runs"]["RTKLIB"] = entry


def _smoke_hartley(roots, by2, base, pins, reference_echo, summary, method, config):
    cache = roots.pins / "HARTLEY" / "BY2" / "H5_INPUT_CACHE.bin"
    runner = Path(pins["hartley_runner"]["runner"])
    run_dir = base / method
    (run_dir / "native" / "provider").mkdir(parents=True)
    payload = cache.read_bytes()
    header = bytearray(payload[:256])
    count = struct.unpack_from("<I", header, 28)[0]
    records = payload[256:256 + HARTLEY_RECORDS * 192]
    struct.pack_into("<I", header, 28, HARTLEY_RECORDS)
    struct.pack_into("<q", header, 48, struct.unpack_from("<q", records, (HARTLEY_RECORDS - 1) * 192)[0])
    truncated = run_dir / "native" / "provider" / "H5_INPUT_CACHE.bin"
    truncated.write_bytes(bytes(header) + records)
    digest = hashlib.sha256(truncated.read_bytes()).hexdigest()
    cfg, _config_hash = hx02_hartley.write_config(
        run_dir / "native" / "run", config=config, record_count=HARTLEY_RECORDS, cache_sha256=digest,
        code_commit=ex.git_head(roots.code), scoped=hx02_hartley.scoped_manifest(roots.code),
        runner_sha256=pins["hartley_runner"]["runner_sha256"])
    result = ex.launch([str(runner), str(truncated), str(cfg), str(run_dir / "native" / "run")], cwd=roots.code,
                       run_dir=run_dir, env_extra={}, timeout_s=1800, label="SMOKE")
    entry = {"pinned_cache_records": count, "truncated_records": HARTLEY_RECORDS, "returncode": result["returncode"],
             "stderr_tail": result["stderr_tail"][-1500:], "audit": _audit(roots, by2, run_dir, [])}
    nav = run_dir / "native" / "run" / "NAV.csv"
    summary_json = run_dir / "native" / "run" / "NATIVE_SUMMARY.json"
    entry["nav_present"] = nav.is_file()
    if nav.is_file():
        gate = hx02_hartley.divergence_gate(nav)
        entry["divergence_gate_passed"] = gate["passed"]
        entry["nav_rows"] = gate["row_count"]
    if summary_json.is_file():
        entry["params_echo"] = hx02_params_echo.compare(hx02_params_echo.hartley(summary_json), reference_echo[method])
    summary["runs"][method] = entry


def _smoke_ginav(roots, by2, base, me, summary):
    run_dir = base / "GINAV"
    (run_dir / "native").mkdir(parents=True)
    argv = [sys.executable, me, "ginav-wrapper", "--run-dir", str(run_dir),
            "--prepared", str(roots.pins / "GINAV" / "BY2" / "GINAV_INPUT_PREPARATION.json"),
            "--pinned-listing", str(roots.control / "METHOD_BODY_SHA256_BEFORE.json"), "--external-root", str(roots.external)]
    result = ex.launch(argv, cwd=roots.code, run_dir=run_dir, env_extra={}, timeout_s=3600, label="SMOKE")
    entry = {"returncode": result["returncode"], "stderr_tail": result["stderr_tail"][-1500:],
             "audit": _audit(roots, by2, run_dir, [])}
    record = run_dir / "native" / "GINAV_RUN.json"
    if record.is_file():
        ginav = json.loads(record.read_text(encoding="utf-8"))
        entry.update({k: ginav.get(k) for k in ("returncode", "runtime_seconds", "native_output_count",
                                                "fopen_ledger_lines", "native_pos_sha256")})
        entry["mirror_files"] = ginav.get("mirror", {}).get("copied_file_count")
        ledger = run_dir / "native" / "GINAV_RUN" / "MATLAB_FOPEN_LEDGER.tsv"
        text = ledger.read_text(encoding="utf-8", errors="replace") if ledger.is_file() else ""
        entry["fopen_reference_like_hits"] = [line for line in text.splitlines()
                                              if ex.REFERENCE_NAME.search(Path(line.split("\t")[-1].replace("\\", "/")).name)]
    summary["runs"]["GINAV"] = entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("run")
    one.add_argument("--paths-config", default="configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")
    one.add_argument("--methods", default="", help="comma-separated subset (default: all)")
    one.add_argument("--attempt", default="", help="suffix for the smoke directory and summary, e.g. _R2")
    two = sub.add_parser("ext-wrapper")
    two.add_argument("--pairs", type=int, required=True)
    two.add_argument("--script", required=True)
    two.add_argument("rest", nargs=argparse.REMAINDER)
    three = sub.add_parser("rtklib-wrapper")
    three.add_argument("--run-dir", required=True)
    three.add_argument("--conf", required=True)
    four = sub.add_parser("ginav-wrapper")
    for name in ("--run-dir", "--prepared", "--pinned-listing", "--external-root"):
        four.add_argument(name, required=True)
    args = parser.parse_args()
    if args.command == "ext-wrapper" and args.rest and args.rest[0] == "--":
        args.rest = args.rest[1:]
    return {"run": run, "ext-wrapper": ext_wrapper, "rtklib-wrapper": rtklib_wrapper,
            "ginav-wrapper": ginav_wrapper}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
