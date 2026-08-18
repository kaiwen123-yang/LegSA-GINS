# LSE01 H5 contract correction

Status: `PHASE1_IMPLEMENTED_NOT_EXECUTED`.

H5 admits only `HARTLEY_IJRR2020_REPORTED_BACKEND`: exact Eq. 50 mean,
analytical right-invariant transition, and Eq. 61 covariance. Eq. 52 remains an
H3--H4 diagnostic and is unavailable to the real H5 runtime.

The primary run is `H5_PRIMARY_GO2_ALLAN_EQ61_FK10MM`. The two FK sensitivity
runs and `H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY` remain blocked
until the primary gate passes. The Table-1 real-BY2 regression has exactly five
process-side parameters and uses the 10 mm Go2 FK proxy. The one-degree encoder
statistic is `SYNTHETIC_AND_CASSIE_REGRESSION_ONLY` and
`NOT_APPLICABLE_TO_BY2_WITHOUT_RAW_JOINTS_AND_JACOBIAN`; no synthetic Jacobian
or degree-to-meter substitution is admitted.

The five-second input-only window fixes initialization statistics but does not
remove execution rows. Row 0 initializes without propagation; rows 1--63276
propagate the previous IMU and contact state before applying current lifecycle
events. Therefore the frozen counts are 63,277 state rows and 63,276
propagations.

No real BY2 run, reference read, external-stage publication, navigation output,
or performance comparison was performed in this phase.
