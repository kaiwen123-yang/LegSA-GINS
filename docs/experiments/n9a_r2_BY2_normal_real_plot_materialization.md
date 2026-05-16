# N9A_R2 BY2 Normal Real Plot Materialization

N9A_R2 is an add-on fix for PR #49 on the existing N9A branch. It corrects the
N9A_R1 boundary: source lineage was fixed, but real BY2 normal-condition
algorithm plotting was not completed.

N9A_R1 confirmed the normal source paths and case model:

- `case_model = BY2_normal_clean`
- `case_count = 1`
- `algorithm_series_count = 10`
- `available_algorithm_series_count = 0`

Those fields mean the R1 source-chain repair succeeded, not that the requested
real algorithm figures exist. Source/proxy curves from raw GNSS, status, trace,
Go2 high-level data, or receiver IMU diagnostics cannot count as algorithm
NAV/EVAL/STD outputs.

N9A_R2 therefore runs algorithm-output discovery before plotting. If no real
algorithm output is found, the decision must be
`N9A_R2_algorithm_outputs_missing`, `ready_for_N9B = false`, and the recommended
next stage is `locate_or_generate_BY2_normal_algorithm_outputs`.

N9A_R2 does not run N9B, does not run the degradation matrix, does not change
algorithms, does not tune trace/final_v23, and makes no performance claim.
