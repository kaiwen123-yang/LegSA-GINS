"""Registered finite ARC native synthetic qualification; no real-data runner."""
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
STAGE = SCRATCH / "TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_LOCAL_ATTEMPT01"
PLAN = ROOT / "docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_LOCAL_PLAN.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration-commit", required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "rev-parse", args.registration_commit+"^{commit}"], cwd=ROOT, text=True).strip()
    plan_bytes = subprocess.check_output(["git", "show", commit+":"+str(PLAN.relative_to(ROOT))], cwd=ROOT)
    if plan_bytes != PLAN.read_bytes():
        raise RuntimeError("plan differs from registered Git identity")
    plan = json.loads(plan_bytes)
    if plan["stage"] != str(STAGE) or STAGE.exists() or not STAGE.resolve().is_relative_to(SCRATCH.resolve()):
        raise RuntimeError("exact new registered scratch stage required")
    pins = plan["source_pins"]
    inventory_roots = ("cpp/legsa_v23_port_core/include", "cpp/legsa_v23_port_core/src")
    if plan["source_inventory_roots"] != list(inventory_roots):
        raise RuntimeError("unexpected production inventory scope")
    def check_inventory():
        actual = sorted(str(f.relative_to(ROOT)) for base in inventory_roots
                        for f in (ROOT/base).rglob("*") if f.is_file())
        if actual != plan["production_inventory"] or not set(actual).issubset(pins):
            raise RuntimeError("production source path inventory differs from registration")
    check_inventory()
    for path, expected in pins.items():
        if sha(ROOT/path) != expected:
            raise RuntimeError("source pin mismatch: "+path)
        registered = subprocess.check_output(["git", "show", commit+":"+path], cwd=ROOT)
        if hashlib.sha256(registered).hexdigest() != expected:
            raise RuntimeError("source not bound to registration: "+path)
    STAGE.mkdir()
    (STAGE/"REGISTERED_PLAN.json").write_bytes(plan_bytes)
    save(STAGE/"SOURCE_PINS.json", pins)
    build = STAGE/"BUILD"
    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_PLUGINS", None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT/"src"),
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
               NATIVE_CLONE_TEST_STAGE=str(STAGE), NATIVE_ARC_TEST_STAGE=str(STAGE),
               LEGSA_FOOT_INFORMATION_DIAGNOSTICS="0", LEGSA_ARC_NATIVE_TELEMETRY="0")
    calls = []
    def invoke(name, command, timeout):
        before = time.monotonic()
        save(STAGE/(name+"_INVOCATION.json"), dict(command=command, timeout_s=timeout, registration_commit=commit))
        with (STAGE/(name+"_stdout.log")).open("wb") as out, (STAGE/(name+"_stderr.log")).open("wb") as err:
            try:
                child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=err, start_new_session=True)
            except OSError as exc:
                save(STAGE/"FIRST_FAILURE.json", dict(name=name, command=command, launch_error=str(exc)))
                raise
            try:
                code = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
                code = 124
        row = dict(name=name, command=command, returncode=code, elapsed_s=time.monotonic()-before, timeout_s=timeout)
        calls.append(row)
        save(STAGE/(name+"_EXIT.json"), row)
        save(STAGE/"CALLS.json", calls)
        print(json.dumps(row), flush=True)
        if code:
            save(STAGE/"FIRST_FAILURE.json", row)
            raise RuntimeError("first failure retained; no automatic retry: "+name)
    invoke("01_CONFIGURE", ["cmake", "-S", str(ROOT/"cpp"), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"], 60)
    invoke("02_BUILD", ["cmake", "--build", str(build), "--target", "legsa_v23_port_core_demo", "-j", "4"], 300)
    for number, stem in ((3,"native_attitude_clone_harness"), (4,"native_arc_clone_harness")):
        invoke(f"{number:02d}_COMPILE", ["g++", "-std=c++17", "-O2", "-I"+str(ROOT/"cpp/legsa_v23_port_core/include"),
               str(ROOT/("tests/paper_rebuild/"+stem+".cpp")), str(build/"liblegsa_v23_port_core.a"), "-o", str(STAGE/stem)], 60)
    invoke("05_PYTEST", ["/usr/bin/python3", "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "tests/paper_rebuild/test_native_attitude_clone.py", "tests/paper_rebuild/test_native_arc_clone.py",
           "--basetemp="+str(STAGE/"PYTEST_TMP"), "--junitxml="+str(STAGE/"junit.xml")], 120)
    xml = ET.parse(STAGE/"junit.xml").getroot()
    cases = xml.findall(".//testcase")
    if len(cases) != 24 or xml.findall(".//failure") or xml.findall(".//error") or xml.findall(".//skipped"):
        raise RuntimeError("unexpected fixed 24-item qualification denominator/result")
    counts = {}
    for name, maximum in (("HARNESS_INVOCATIONS.jsonl",28), ("ARC_HARNESS_INVOCATIONS.jsonl",32)):
        rows = [json.loads(line) for line in (STAGE/name).read_text().splitlines() if line.strip()]
        counts[name] = len(rows)
        if len(rows)>maximum:
            raise RuntimeError("synthetic subprocess budget exceeded: "+name)
    if counts["HARNESS_INVOCATIONS.jsonl"] != 28:
        raise RuntimeError("old 16-case harness invocation identity changed")
    check_inventory()
    for path, expected in pins.items():
        if sha(ROOT/path) != expected:
            raise RuntimeError("source changed during local qualification: "+path)
    receipt = dict(status="PASS_24_SYNTHETIC_CASES_ONLY", registration_commit=commit, calls=calls,
        source_pins=pins, pytest_items=len(cases), synthetic_harness_invocations=counts,
        new_full_window_native_calls=0, evaluator_calls=0, real_phase_information_reads=0,
        binary_sha256=sha(build/"legsa_v23_port_core_demo"),
        library_sha256=sha(build/"liblegsa_v23_port_core.a"),
        old_harness_sha256=sha(STAGE/"native_attitude_clone_harness"),
        arc_harness_sha256=sha(STAGE/"native_arc_clone_harness"),
        navigation_gain_established=False, raw_reference_scope="No real-data input in registered commands; access trace audited separately")
    save(STAGE/"RECEIPT.json", receipt)
    save(STAGE/"COMPLETE.json", dict(receipt_sha256=sha(STAGE/"RECEIPT.json")))
    print(json.dumps({k:v for k,v in receipt.items() if k not in ("calls","source_pins")}), flush=True)


if __name__ == "__main__":
    main()
