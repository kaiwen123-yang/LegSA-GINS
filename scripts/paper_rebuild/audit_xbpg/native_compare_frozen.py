#!/usr/bin/env python3
"""Compare frozen binary synthetic outputs with the unmodified current build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import yaml

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-config", type=Path, required=True)
    parser.add_argument("--frozen-binary", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    assert sha(args.frozen_binary) == args.expected_sha256
    paths = yaml.safe_load(args.local_config.read_text())["paths"]
    scratch = Path(paths["audit_scratch"])
    destination = scratch / "native_frozen_comparison"
    destination.mkdir(exist_ok=False)
    receipts = []
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    for mode in ["synthetic-math", "raw-doppler-toy", "source-aware-toy", "quality-state-toy", "go2-weak-prior-toy", "qa-fallback-toy"]:
        out = destination / mode
        command = [str(args.frozen_binary), "--dry-run-"+mode, "--output-dir", str(out)]
        begin = time.perf_counter()
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=60)
        row = {"mode":mode, "returncode":result.returncode, "elapsed_seconds":time.perf_counter()-begin,
               "stdout":result.stdout, "stderr":result.stderr, "files":[]}
        for name in ["LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv"]:
            old, current = out/name, scratch/"native_initial"/mode/name
            row["files"].append({"name":name, "frozen_sha256":sha(old) if old.exists() else None,
                                 "current_sha256":sha(current) if current.exists() else None,
                                 "byte_identical":old.exists() and current.exists() and sha(old)==sha(current)})
        for label, root in [("frozen",out),("current",scratch/"native_initial"/mode)]:
            path=root/"RUN_MANIFEST.json"
            if path.exists():
                manifest=json.loads(path.read_text())
                row[label+"_manifest_data_flags"]={key:manifest.get(key,"ABSENT") for key in ["data_mode","synthetic_data_used","semisynthetic_data_used"]}
        receipts.append(row)
    output = {"data_mode":"synthetic", "synthetic_data_used":True,"semisynthetic_data_used":False,
              "frozen_binary_sha256":args.expected_sha256, "frozen_source_commit":"ca73cb1fb48a020fd2a450d79e520562c34eeb24",
              "current_binary_sha256":sha(scratch/"native_build/legsa_v23_port_core_demo"),"results":receipts}
    (destination/"RECEIPT.json").write_text(json.dumps(output,indent=2)+"\n")
    (ROOT/"docs/paper_rebuild/audit_xbpg_20261001/NATIVE_FROZEN_COMPARISON.json").write_text(json.dumps(output,indent=2)+"\n")
    for row in receipts: print(row["mode"],row["returncode"],sum(x["byte_identical"] for x in row["files"]),"/ 3 exact",row.get("frozen_manifest_data_flags"))


if __name__=="__main__":main()
