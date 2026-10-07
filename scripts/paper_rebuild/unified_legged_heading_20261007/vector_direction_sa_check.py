#!/usr/bin/env python3
"""One synthetic C++ policy/tensor check; never launches solver or evaluator."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


def pin(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = ROOT / "tests/paper_rebuild/native_vector_direction_sa_harness.cpp"
    include = ROOT / "cpp/legsa_v23_port_core/include"
    library = args.build / "liblegsa_v23_port_core.a"
    harness = args.output / "vector_direction_sa_harness"
    command = ["g++", "-std=c++17", "-O2", "-I", str(include), str(source),
               str(library), "-o", str(harness)]
    compile_result = subprocess.run(command, capture_output=True, text=True)
    (args.output / "BUILD.log").write_text(compile_result.stdout + compile_result.stderr)
    compile_result.check_returncode()
    run = subprocess.run([str(harness)], capture_output=True, text=True)
    (args.output / "NATIVE.json").write_text(run.stdout)
    (args.output / "NATIVE.stderr").write_text(run.stderr)
    run.check_returncode()
    evidence = json.loads(run.stdout)
    assert evidence["status"] == "PASS"
    reig = np.linalg.eigvalsh(evidence["R"])
    rreig = np.linalg.eigvalsh(evidence["R_rotated"])
    jeig = np.linalg.eigvalsh(evidence["attitude_information"])
    jreig = np.linalg.eigvalsh(evidence["attitude_information_rotated"])
    np.testing.assert_allclose(reig, [.0001, .0004, .16], atol=1e-14)
    np.testing.assert_allclose(reig, rreig, atol=1e-14)
    np.testing.assert_allclose(jeig, jreig, atol=1e-9)
    assert abs(jeig[0]) < 1e-8 and jeig[1] > 0 and jeig[2] / jeig[1] > 2
    result = {
        "status": "PASS", "synthetic_only": True, "checks": 1,
        "native_solver_runs": 0, "reference_reads": 0,
        "scope": "Actual SourceAwarePolicy and external-carrier vector model; no navigation gain claim",
        "evidence": evidence,
        "covariance_eigenvalues_m2": reig.tolist(),
        "attitude_information_eigenvalues_rad_minus2": jeig.tolist(),
        "old_proxy_information_divisor_after_rotation": 6,
        "source": pin(source), "check_script": pin(Path(__file__)),
        "library": pin(library), "harness": pin(harness),
        "navigation_binary": pin(args.build / "legsa_v23_port_core_demo"),
        "production_sources": [pin(ROOT / p) for p in (
            "cpp/legsa_v23_port_core/include/legsa_v23_port_core/source_aware/measurement_source.hpp",
            "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp",
            "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp")],
    }
    (args.output / "CHECK.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
