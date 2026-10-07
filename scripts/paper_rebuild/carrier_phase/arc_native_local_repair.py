"""One preregistered fixture-only ARC qualification repair, no real inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = Path("/home/kaiwen/research/LegSA-GINS-SCRATCH")
STAGE = SCRATCH / "TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_LOCAL_REPAIR01"
PLAN = ROOT / "docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_LOCAL_REPAIR_PLAN.json"

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, data):
    p.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registration-commit", required=True)
    args = ap.parse_args()
    commit = subprocess.check_output(["git", "rev-parse", args.registration_commit+"^{commit}"], cwd=ROOT, text=True).strip()
    registered = subprocess.check_output(["git", "show", commit+":"+str(PLAN.relative_to(ROOT))], cwd=ROOT)
    if registered != PLAN.read_bytes():
        raise RuntimeError("registered plan mismatch")
    plan = json.loads(registered)
    if str(STAGE) != plan["stage"] or STAGE.exists() or not STAGE.resolve().is_relative_to(SCRATCH.resolve()):
        raise RuntimeError("new exact registered stage required")
    def check():
        actual = sorted(str(f.relative_to(ROOT)) for base in plan["source_inventory_roots"]
                        for f in (ROOT/base).rglob("*") if f.is_file())
        if actual != plan["production_inventory"]:
            raise RuntimeError("production inventory drift")
        for name, expected in plan["source_pins"].items():
            if sha(ROOT/name) != expected:
                raise RuntimeError("source changed: " + name)
        for name, expected in plan["first_attempt_pins"].items():
            if sha(Path(name)) != expected:
                raise RuntimeError("first attempt changed: " + name)
    check()
    for name, expected in plan["source_pins"].items():
        frozen = subprocess.check_output(["git", "show", commit+":"+name], cwd=ROOT)
        if hashlib.sha256(frozen).hexdigest() != expected:
            raise RuntimeError("unregistered source: " + name)
    STAGE.mkdir()
    (STAGE/"REGISTERED_PLAN.json").write_bytes(registered)
    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_PLUGINS", None)
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT/"src"),
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
               NATIVE_ARC_TEST_STAGE=str(STAGE), LEGSA_ARC_NATIVE_TELEMETRY="0", LEGSA_FOOT_INFORMATION_DIAGNOSTICS="0")
    calls = []
    def invoke(name, command, timeout):
        save(STAGE/(name+"_INVOCATION.json"), dict(command=command, timeout_s=timeout, registration_commit=commit))
        t = time.monotonic()
        with (STAGE/(name+"_stdout.log")).open("wb") as out, (STAGE/(name+"_stderr.log")).open("wb") as err:
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=err, start_new_session=True)
            try:
                rc = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
                rc = 124
        row = dict(name=name, returncode=rc, elapsed_s=time.monotonic()-t, command=command, timeout_s=timeout)
        calls.append(row)
        save(STAGE/(name+"_EXIT.json"), row)
        save(STAGE/"CALLS.json", calls)
        print(json.dumps(row), flush=True)
        if rc:
            save(STAGE/"FIRST_FAILURE.json", row)
            raise RuntimeError("repair failure retained; no automatic retry")
    invoke("01_COMPILE", ["g++", "-std=c++17", "-O2", "-I"+str(ROOT/"cpp/legsa_v23_port_core/include"),
           str(ROOT/"tests/paper_rebuild/native_arc_clone_harness.cpp"), plan["sealed_library"], "-o", str(STAGE/"native_arc_clone_harness")], 60)
    invoke("02_PYTEST", ["/usr/bin/python3", "-m", "pytest", "-q", "-p", "no:cacheprovider", *plan["test_items"],
           "--basetemp="+str(STAGE/"PYTEST_TMP"), "--junitxml="+str(STAGE/"junit.xml")], 60)
    xml = ET.parse(STAGE/"junit.xml").getroot()
    if len(xml.findall(".//testcase")) != 2 or any(xml.findall(".//"+k) for k in ("failure", "error", "skipped")):
        raise RuntimeError("unexpected qualification denominator/result")
    rows = [json.loads(x) for x in (STAGE/"ARC_HARNESS_INVOCATIONS.jsonl").read_text().splitlines()]
    if [r["op"] for r in rows] != ["ordering_mid", "ordering_end", "identity", "identity"] or any(r["returncode"] for r in rows):
        raise RuntimeError("repair process budget/identity mismatch")
    check()
    receipt = dict(status="PASS_TWO_AFFECTED_SYNTHETIC_CASES", registration_commit=commit,
        first_registration_commit=plan["first_registration_commit"], source_pins=plan["source_pins"],
        first_attempt_pins=plan["first_attempt_pins"], calls=calls, pytest_items=2, harness_calls=4,
        harness_sha256=sha(STAGE/"native_arc_clone_harness"), junit_sha256=sha(STAGE/"junit.xml"),
        production_rebuilds=0, new_full_window_native_calls=0, evaluator_calls=0,
        first_attempt_status="23_PASS_1_FAIL_RETAINED", unique_local_cases_with_passing_evidence=24,
        total_local_test_executions=26, navigation_gain_established=False)
    save(STAGE/"RECEIPT.json", receipt)
    save(STAGE/"COMPLETE.json", dict(receipt_sha256=sha(STAGE/"RECEIPT.json")))
    print(json.dumps({k:v for k,v in receipt.items() if k not in ("calls","source_pins","first_attempt_pins")}), flush=True)

if __name__ == "__main__":
    main()
