#!/usr/bin/env python3
"""Bounded HX-02D diagnostics; no native program launch and no source mutation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records, write_scope_audit
from legsa_gins.paper_rebuild.hext import hx02_evaluation_process as launcher
from legsa_gins.paper_rebuild.hext.hx02d_reference_free import dump


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run(args):
    w, hx, scratch = args.code_root, args.hx02, args.scratch
    control = scratch / "00_CONTROL"
    assert (control / "HX02_TREE_START.json").exists()
    ledger = control / "CALLS.jsonl"
    assert not ledger.exists()
    new_sources = ["src/legsa_gins/paper_rebuild/hext/hx02d_reference_free.py",
                   "src/legsa_gins/paper_rebuild/hext/hx02d_reference_evaluation.py",
                   "scripts/paper_rebuild/hx02d_execute.py"]
    frozen_sources = ["src/legsa_gins/paper_rebuild/hext/hx02_evaluation_process.py",
                      "src/legsa_gins/paper_rebuild/hext/hx02_relative_pose_evaluation.py",
                      "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7.py",
                      "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7c.py"]
    pins = {p: sha(w / p) for p in new_sources + frozen_sources}
    module = "legsa_gins.paper_rebuild.hext.hx02d_reference_evaluation"
    dump(control / "DIAGNOSTIC_CHILD_REGISTRATION.json", {
        "kind": "HX02D", "module": module, "source_sha256": pins,
        "registered_before_any_child": True, "registration_scope": "Current controller process only; launcher source bytes unchanged",
        "expected_reference_children": 2, "expected_reference_opens_per_child": 1,
        "native_calls_budget": 0, "B_raw_access": "Pinned Go2 message logs only",
        "C_reference_access": "Pinned HX-02 trace only, one read-only open; all C calculations in this module"})
    launcher.REGISTERED_CHILDREN["HX02D"] = module
    counters = {"legsa_native": 0, "external_native": 0, "reference_free_children": 0,
                "registered_reference_children": 0, "reference_opens": 0}

    def record(value):
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    for seq, start in [("BY2", "C00"), ("BY2O", "FILE_START")]:
        provider = hx / "01_INPUT_PINS/HARTLEY" / seq
        cache_manifest = json.loads((provider / "H5_INPUT_CACHE_MANIFEST.json").read_text())
        original, branches = {}, {}
        for cfg in ["S", "LIT"]:
            label = f"HARTLEY_{cfg}"
            run = hx / "RUNS" / f"{seq}__{label}__{cfg}__{start}__NA"
            metrics_path = run / "eval/RELATIVE_POSE/OUTPUT/RELATIVE_POSE_METRICS.json"
            metrics = json.loads(metrics_path.read_text())
            old_spec = json.loads((run / "eval/RELATIVE_POSE/SPEC.json").read_text())
            original[label] = metrics["branches"][label]
            nav = run / "native/run/NAV.csv"
            assert sha(nav) == metrics["nav_sha256"][label]
            branches[label] = {"nav": str(nav), "nav_sha256": metrics["nav_sha256"][label],
                               "metrics_source": str(metrics_path)}
        common = {"sequence_id": seq, "base_time": old_spec["base_time"], "window": old_spec["window"],
                  "reference_path_length_m": original["HARTLEY_S"]["reference_path_length_m"]}
        bdir = scratch / "B_REFERENCE_FREE" / seq
        bdir.mkdir(parents=True, exist_ok=False)
        bspec = {**common, "cache": str(provider / "H5_INPUT_CACHE.bin"),
                 "cache_manifest": str(provider / "H5_INPUT_CACHE_MANIFEST.json"),
                 "branches": branches, "outdir": str(bdir / "OUTPUT")}
        dump(bdir / "SPEC.json", bspec)
        environment = {**os.environ, **launcher.child_environment(w, bdir / "OUTPUT")}
        argv = ["strace", "-f", "-yy", "-s", "4096", "-e", "trace=openat,execve", "-o", str(bdir / "B_OPENAT.strace"),
                sys.executable, "-m", "legsa_gins.paper_rebuild.hext.hx02d_reference_free", "--spec", str(bdir / "SPEC.json")]
        counters["reference_free_children"] += 1
        record({"state": "CALL_INTENT", "role": "B_REFERENCE_FREE", "sequence": seq, "argv": argv})
        done = subprocess.run(argv, cwd=w, env=environment, capture_output=True, text=True)
        (bdir / "stdout.log").write_text(done.stdout)
        (bdir / "stderr.log").write_text(done.stderr)
        records = audited_open_records(bdir / "B_OPENAT.strace", w)
        raw_opens = [r for r in records if args.raw_root in Path(r["path"]).parents]
        forbidden = [r for r in records if Path(r["path"]).name.startswith("trace_vrtk") or Path(r["path"]).suffix in {".bag", ".fpl"}]
        scope = write_scope_audit(records, raw_root=args.raw_root, clean_root=args.clean_root, allowed_write_roots=[bdir / "OUTPUT"])
        programs = [m[1] for line in (bdir / "B_OPENAT.strace").read_text().splitlines() if (m := launcher.EXECVE_RE.search(line))]
        okay = done.returncode == 0 and not forbidden and scope["pass"] and len(raw_opens) == 1 and all(
            r["path"] == cache_manifest["source_identity"]["source"] and r["return_code"] >= 0 and "O_RDONLY" in r["flags"] for r in raw_opens)
        okay = okay and all(Path(p).name.startswith("python") for p in programs)
        audit = {"passed": okay, "exit_code": done.returncode, "reference_open_count": len(forbidden),
                 "raw_open_records": raw_opens, "write_scope": scope, "execve_programs": programs,
                 "strace_sha256": sha(bdir / "B_OPENAT.strace")}
        dump(bdir / "B_STRACE_AUDIT.json", audit)
        record({"state": "CALL_TERMINAL", "role": "B_REFERENCE_FREE", "sequence": seq, "passed": okay})
        assert okay, done.stderr[-4000:]
        print(f"{seq} B complete; audit PASS", flush=True)
        btables = json.loads((bdir / "OUTPUT/B_TABLES.json").read_text())
        cspec = {**common, "b_arrays": str(bdir / "OUTPUT/B_ARRAYS.npz"), "b_arrays_sha256": btables["array_sha256"],
                 "baseline_median_m": old_spec["baseline_median_m"], "trace": old_spec["trace"],
                 "trace_sha256": old_spec["trace_sha256"], "original_metrics": original,
                 "leg_integration_gaps": btables["leg_integration_gaps"]}
        for rel, expected in pins.items():
            assert sha(w / rel) == expected
        counters["registered_reference_children"] += 1
        record({"state": "CALL_INTENT", "role": "C_REGISTERED", "sequence": seq, "module": module})
        result = launcher.run_child("HX02D", cspec, workdir=scratch / "C_REFERENCE" / seq,
                                    code_root=w, raw_root=args.raw_root, clean_root=args.clean_root,
                                    trace=Path(old_spec["trace"]), timeout_seconds=600)
        counters["reference_opens"] += result["audit"]["trace_open_count"]
        record({"state": "CALL_TERMINAL", "role": "C_REGISTERED", "sequence": seq, "passed": result["audit"]["passed"]})
        print(f"{seq} C complete; single reference open audit PASS", flush=True)
    dump(control / "EXECUTION_COUNTERS.json", counters)
    assert counters["registered_reference_children"] == counters["reference_opens"] == 2
    assert all(sha(w / rel) == expected for rel, expected in pins.items())


def main():
    def guard(event, values):
        if event == "open" and isinstance(values[0], (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(values[0]))
            if p.name.startswith("trace_vrtk") or p.suffix.lower() in {".bag", ".fpl"}:
                raise RuntimeError("Controller cannot open reference/bag/fpl")
        if event == "subprocess.Popen":
            executable = Path(os.fsdecode(values[0])).name
            if executable not in {"env", "strace"}:
                raise RuntimeError(f"Unregistered subprocess: {executable}")
    sys.addaudithook(guard)
    parser = argparse.ArgumentParser()
    for name in ["code-root", "hx02", "scratch", "raw-root", "clean-root"]:
        parser.add_argument("--" + name, type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
