# CLEAN1R2R1 parity tolerance freeze

`CLEAN1R2R1_PRE_OUTPUT_FLOAT64_FORMAT_BOUND_V1` was frozen before any clean
BY2 solver output was generated or inspected. No historical 1.979/1.997 metric
and no current trace result was used.

Both solvers consume the same rounded 7/15-column input, use float64 state and
covariance arithmetic, and publish the same nine-decimal common-unit writer
view. The gate therefore requires exact row count, exact update-action sequence
and `1e-9 s` timestamp agreement. It also gates position, velocity, attitude,
and all 21 common-unit STD columns, with small bounds for floating evaluation
order and text quantization. The machine-readable values are frozen in
`configs/paper_rebuild/final_v23_parity_contract.yaml` and mirrored by
`ParityTolerances`; either side drifting makes tests fail.
