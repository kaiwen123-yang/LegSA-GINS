"""Compare efficient and dense restricted likelihood on the fixed first50 BY epochs."""
from pathlib import Path
import argparse
import dataclasses
import hashlib
import json
import sys
import time
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--config", type=Path, required=True)
args = parser.parse_args()
config = json.loads(args.config.read_text())
repository = Path(config["repository"])
sys.path.insert(0, str(repository / "src"))
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.source_noise_likelihood import (
    NoiseParameters, prepare_source_noise_likelihood,
    evaluate_source_noise_likelihood, dense_source_noise_likelihood)

plan_path = Path(config["plan_path"])
plan = json.loads(plan_path.read_text())
records = [r for r in plan["records"] if 100.1979 <= r["time_s"] <= 110.0]
assert len(records) == 50
blocks = []
for record in records:
    family = record["families"]["GPS_GAL_BDS_DUAL"]
    assert family["status"] == "BUILT"
    z = np.load(plan_path.parent / family["file"])
    blocks.append(EpochBlock(record["time_s"], z["y"], z["A"], z["B"], z["Q"],
                             tuple(family["ambiguity_labels"]), dict(family["metadata"])))
started = time.monotonic()
problem = prepare_source_noise_likelihood(blocks)
prepare_elapsed = time.monotonic()-started
cases = []
for label, parameters in [("ORIGINAL_Q", NoiseParameters()),
        ("FIXED_WHITE_EXAMPLE", NoiseParameters(0.005, 0.0, 0.8)),
        ("FIXED_COLORED_EXAMPLE", NoiseParameters(0.005, 0.01, 0.8))]:
    started = time.monotonic()
    efficient = evaluate_source_noise_likelihood(problem, parameters)
    efficient_elapsed = time.monotonic()-started
    started = time.monotonic()
    dense = dense_source_noise_likelihood(problem, parameters)
    dense_elapsed = time.monotonic()-started
    names = ["residual_cost", "covariance_log_determinant",
             "integer_information_log_determinant", "restricted_objective"]
    comparisons = {name: {"efficient": getattr(efficient,name),
                         "dense": getattr(dense,name),
                         "absolute_difference": abs(getattr(efficient,name)-getattr(dense,name))}
                   for name in names}
    for name in names:
        np.testing.assert_allclose(getattr(efficient,name), getattr(dense,name), rtol=1e-9, atol=1e-7)
    cases.append({"case":label,"parameters":dataclasses.asdict(parameters),
                  "comparison":comparisons,"efficient_s":efficient_elapsed,"dense_s":dense_elapsed})
original_diagnostic = json.loads((Path(config["output_directory"])/"SUMMARY.json").read_text())
old_cost = original_diagnostic["joint_fit"]["cost"]
np.testing.assert_allclose(cases[0]["comparison"]["residual_cost"]["efficient"], old_cost, rtol=1e-9, atol=1e-7)
module_path = repository/"src/legsa_gins/paper_rebuild/joint_navigation/source_noise_likelihood.py"
receipt = {"status":"PASS_SMALL_WINDOW_MATHEMATICAL_EQUIVALENCE_ONLY",
    "scope":{"window_s":[blocks[0].time_s,blocks[-1].time_s],"epochs":len(blocks),
             "raw_rows":problem.original_rows,"geometry_rank":problem.geometry_rank,
             "fixed_geometry_contrast_rows":problem.contrast_rows,"integer_rank":problem.integer_rank,
             "source_beta_dimension":len(problem.physical_source_signals),"dof":problem.degrees_of_freedom,
             "reference_reads":0,"navigation_calls":0,"optimization_calls":0,"calibration_or_validation_windows_read":False},
    "identity":{"integer_basis_labels":problem.integer_basis_labels,"physical_source_signals":problem.physical_source_signals,
                "beta_identity_uses_integer_arc_tokens":False},
    "method":"Fixed original-Q geometry contrasts; stationary OU beta source states; exact full-epoch Kalman innovations on y and all physical float integer design columns; final QR integrates the fixed-rank integer nuisance coordinates. Covariance and integer-information log determinants included; fixed contrast constants cancel across parameter models.",
    "cases":cases,"integer_annihilator_previous_cost":old_cost,"prepare_s":prepare_elapsed,
    "provenance":{"PLAN_sha256":hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                  "module_sha256":hashlib.sha256(module_path.read_bytes()).hexdigest(),
                  "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
    "boundary":"Fixed example parameters are not estimates or qualified noise models. Lower residual alone is not evidence of better model or valid integer acceptance. No Q or navigation algorithm was changed."}
output = Path(config["output_directory"])/"LIKELIHOOD_EQUIVALENCE.json"
output.write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({"status":receipt["status"],"scope":receipt["scope"],"cases":cases,"output":str(output)}))
