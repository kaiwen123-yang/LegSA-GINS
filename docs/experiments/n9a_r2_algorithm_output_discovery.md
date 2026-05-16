# N9A_R2 Algorithm Output Discovery

`N9A_R2_ALGORITHM_OUTPUT_DISCOVERY_REPORT.json` is the first gate for the stage.
It searches runtime-only roots supplied on the runner command line and records
one row for each target algorithm series:

- `pure_INS`
- `single_antenna_original_KF_GINS`
- `final_v23_dual_antenna_EKF`
- `source_backed_EKF`
- `Raw_Doppler_EKF`
- `source_aware_EKF`
- `Go2_joint_EKF`
- `no_feedback_FGO`
- `selected_feedback_EKF`
- `reject_all_sanity`

Each row records NAV, STD, EVAL, RUN_MANIFEST, metrics, feedback, and FGO factor
paths if present, plus row counts and plot-capability booleans. Formal ablation
plot archives may be scanned as context, but they are not BY2 normal cases and
do not make the normal plot materialization complete.

Trace is reference/evaluation-only. Source GNSS/status, Go2 high-level data, and
receiver IMU diagnostics may support source-quality or audit figures only; they
must not be promoted into algorithm estimates or algorithm error bars.
