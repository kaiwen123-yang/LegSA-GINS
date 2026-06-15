# PAPER10C_R1B Go2 Claim Decision Summary

Decision: Go2 high-level state priors/readiness metadata can be used as a bounded auxiliary or supporting innovation, not as a universal superiority or standalone main-performance claim.

Allowed wording: Go2 roll/pitch, horizontal velocity, and readiness/motion-state metadata are integrated as source-aware weak priors and first-class LSIM metadata, with BY2/BY3 six-mode ablations closed.

Boundary:

- Go2 position/yaw are not truth.
- BY3 yaw is diagnostic-only.
- Not full contact-aided InEKF.
- Not full leg odometry.
- Not complete nine-factor FGO.
- No trace online and no per-case tuning.
- Performance is mixed, so do not claim universal superiority.

## BY3 Method Summary

| go2_mode | completed_rows | position_rmse_h_mean | up_rmse_mean | roll_rmse_mean | pitch_rmse_mean | yaw_rmse_diagnostic_mean |
| --- | --- | --- | --- | --- | --- | --- |
| G00_NO_GO2 | 120 | 2.461410518461481 | 12.000693291399536 | 2.410195111892081 | 2.740381541119808 | 73.86751873105645 |
| G01_GO2_RP_ONLY | 120 | 2.462975539176875 | 12.004460896303238 | 2.1558402310505054 | 2.4417159206056005 | 102.4620425185496 |
| G02_GO2_HVEL_ONLY | 120 | 2.492567796476299 | 12.003611425251211 | 2.4887130543504057 | 2.794812936995823 | 74.96831844233557 |
| G03_GO2_READINESS_ONLY | 120 | 2.532972941756825 | 12.01345954722598 | 2.420135732713723 | 2.7432767367691624 | 75.80963700183614 |
| G04_GO2_RP_HVEL | 120 | 2.470374142545885 | 12.000212570581974 | 2.1579052728759907 | 2.47521821568776 | 100.63802561706903 |
| G05_GO2_FULL_AUX | 120 | 2.5408895192523144 | 12.012802795928923 | 2.170336246008747 | 2.481125596834001 | 100.75239833787684 |
