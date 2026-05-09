# N4H4D5 Update Block Contribution

N4H4D5 writes `UPDATE_BLOCK_TRACE.csv` in the runtime-only debug directory.
The trace records position, velocity, and yaw block residuals, gain norms, covariance changes, and the incremental contribution to `dx`.

The purpose is to identify whether a single measurement block overdrives attitude feedback, or whether the divergence is coupled across blocks.
The trace is diagnostic-only and must not be treated as an improved solver result.

No raw Doppler, Go2 prior, LSIM/OIM, source-aware weighting, or FGO factor is enabled in this stage.
