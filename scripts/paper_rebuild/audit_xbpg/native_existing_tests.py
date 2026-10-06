#!/usr/bin/env python3
"""Run existing native mathematical/loader tests with scratch-only builds."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import json
import os
import sys
import time
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-config", required=True, type=Path)
    args = parser.parse_args()
    paths = yaml.safe_load(args.local_config.read_text())["paths"]
    scratch = Path(paths["audit_scratch"]) / "native_existing_tests"
    scratch.mkdir(parents=True, exist_ok=False)
    out = Path(paths["audit_root"]) / "native" / "existing_tests"
    out.mkdir(parents=True, exist_ok=False)
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
        os.environ[name] = "1"

    class ScratchBuild:
        def pytest_collection_modifyitems(self, items):
            for item in items:
                if item.module.__name__.endswith("test_t5bc_baseline3d"):
                    item.module.BUILD = scratch / "t5bc_build"

    commands = [str(ROOT / "tests/paper_rebuild/test_clean3_math_repairs.py"),
                str(ROOT / "tests/paper_rebuild/test_t5bc_baseline3d.py"),
                "-q", "-s", "-p", "no:cacheprovider", "--basetemp", str(scratch / "pytest_tmp")]
    start = time.perf_counter()
    with (out / "pytest.log").open("w") as log, redirect_stdout(log), redirect_stderr(log):
        status = pytest.main(commands, plugins=[ScratchBuild()])
    receipt = {"data_mode": "synthetic", "synthetic_data_used": True, "semisynthetic_data_used": False,
               "command": commands, "returncode": int(status), "elapsed_seconds": time.perf_counter()-start,
               "notes": "BUILD variable redirected after collection; production test text unchanged; no real inputs"}
    (out / "RECEIPT.json").write_text(json.dumps(receipt, indent=2)+"\n")
    (ROOT / "docs/paper_rebuild/audit_xbpg_20261001/NATIVE_EXISTING_TESTS.json").write_text(json.dumps({k:v for k,v in receipt.items() if k!="command"}, indent=2)+"\n")
    print((out / "pytest.log").read_text()[-6000:])
    raise SystemExit(int(status))


if __name__ == "__main__":
    main()
