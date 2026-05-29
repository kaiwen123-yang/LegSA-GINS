# Data Source Roles

This file defines what each BY2 and BY3 source may and may not support.

## GNSS Raw

Aliases: `<GNSS1_RAW>`, `<GNSS2_RAW>`, `<BY3_GNSS1_RAW>`, `<BY3_GNSS2_RAW>`.

Allowed:

- raw observation audit.
- Raw Doppler source audit.
- satellite count, Doppler residual, GNSS observation quality.
- dual-antenna source lineage and time coverage checks.

Not allowed:

- direct algorithm estimate.
- hidden replacement for NAV/EVAL output.

## GNSS Status

Aliases: `<GNSS1_STATUS>`, `<GNSS2_STATUS>`, `<BY3_GNSS1_STATUS>`, `<BY3_GNSS2_STATUS>`.

Allowed:

- receiver status.
- GNSS standard deviation / quality fields.
- yaw observation and yaw_std if explicit fields exist.
- receiver velocity only if explicit velocity columns exist.
- dual-antenna baseline heading diagnostics, with lateral mounting correction documented separately.

Not allowed:

- raw GNSS baseline claim for `single_antenna_gnss1_status_KF_GINS`; that baseline is GNSS1-status, not raw GNSS.
- estimate substitution.
- selecting a lateral dual-antenna plus/minus 90 degree yaw correction by RMSE alone.

## Trace Reference

Aliases: `<TRACE_TRUTH>`, `<BY3_TRACE_TRUTH>`.

Allowed:

- truth/reference overlay.
- error computation after frame/time alignment.
- EVAL sanity.
- frame alignment and time alignment audit.

Not allowed:

- solver input.
- tuning parameters, gates, weights, covariance, or feedback.
- EVAL_NAV feedback corrections.

## Fixposition Receiver IMU

Aliases: `<FIXPOSITION_IMU_DATA>`, `<FIXPOSITION_IMU_BIASES>`, `<FIXPOSITION_IMU_TEMP>`.

Allowed:

- receiver IMU diagnostics.
- source lineage audit.
- receiver sensor status and time range checks.

Not allowed:

- fused body IMU.
- replacement for `by2.txt`.
- truth or algorithm estimate.

BY3 receiver IMU alias: `<BY3_FIXPOSITION_IMU_DATA>`. It is diagnostic only and must not be used as the BY3 Go2 body IMU source.

## Go2 Body IMU / High-Level

Aliases: `<GO2_BODY_IMU_HIGHLEVEL>`, `<BY3_GO2_BODY_SOURCE>`.

Allowed when fields are explicitly parseable:

- Go2 body IMU / high-level source audit.
- Go2 roll/pitch.
- Go2 horizontal velocity.
- contact / foot source audit.
- legged factor source audit.
- proprioceptive candidate factor evidence.

Not allowed:

- truth.
- algorithm NAV.
- GNSS receiver IMU replacement.
- absolute position truth.

BY3 `by3.txt` has the same source role as BY2 `by2.txt`: Go2 body/high-level/body-IMU source for inventory, kick-event detection, and candidate algorithm input generation when fields are parseable. It is not truth and does not authorize retuning against trace.

## Algorithm Outputs

NAV, STD, EVAL_NAV, summary files, and RUN_MANIFEST records are the core algorithm output and evaluation chain. Feedback observation CSVs, smoothed FGO NAV, and factor tables are runtime/factor diagnostics. All must be classified by role before plotting:

- estimate.
- covariance/uncertainty.
- evaluation.
- source observation.
- runtime diagnostic.
- factor diagnostic.
- forbidden/substitution risk.

None of these runtime outputs are committable by default.

Final-only metrics rule: metrics must come from final algorithm output/evaluation files for the same case, not from intermediate source diagnostics or source observations.

Current active global metrics source after N9C0: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.

The N9C0 active final-only metrics table has 825 rows. It is the current global metric source for context and planning, but it is not paper-claim authorization.

BY3A0_TO_BY3E produced candidate BY3 input files and blocked solver/evaluator execution before BY3 normal metrics. Those candidate files are not paper evidence and do not authorize BY3 degradation planning until the solver/evaluator gate is repaired and reviewed.

Selected-feedback same-case rule: `selected_feedback` requires feedback generated for the same degraded or clean case. Clean feedback cannot be reused for degraded cases.

EVAL_NAV feedback generation uses state/estimate columns only and must not use trace/error feedback corrections.

BY3A4A yaw rule: BY2/BY3 dual-antenna yaw evaluation must account for lateral antenna mounting. The antenna baseline is perpendicular to robot forward/head direction, so baseline heading is not body heading. Body heading requires a plus/minus 90 degree correction depending on antenna order and coordinate/frame convention; unwrap yaw before interpolation and wrap after differencing. BY3A4A did not accept repaired yaw metrics.

BY3A4C yaw-reference rule: do not repeat blind plus/minus 90 searches. First recover the historical N4H2C/N4H2D/N4R/N4R2/N4R3 reference mapping. BY2 old yaw around 93 deg was invalidated by N4H2D through `official_ref_sign_minus` and direct identity against the reconstructed dual official reference. BY3A4C did not find a BY3 yaw truth/reference profile that transfers, so BY3 yaw is `not_evaluable`; position/up metrics can be used only for position/up-only planning, and yaw degradation claims remain false.

## Baseline Roles

- `single_antenna_gnss1_status_KF_GINS`: GNSS1-status baseline, not raw GNSS.
- `pure_INS_reference_initialized`: fixed/reference baseline.
- `final_v23_dual_antenna_EKF`: `external_reference_baseline` only.
- `true_no_feedback_FGO`: diagnostic unless full comparable output exists.

## final_v23 / KF-GINS Reference

Allowed:

- reference comparison after role classification and alignment.
- sanity oracle for scale and convention checks.
- evaluation boundary when documenting what LegSA-GINS does or does not match.

Not allowed:

- solver input.
- tuning source for gates, weights, covariance, or feedback.
- hidden output substitution.
- basis for outperforming or paper-performance claims without a later approved audit.

The external final_v23 baseline is integrated into N9C0 for reference comparison only. It must not become LegSA solver input, tuning source, hidden target, or the sole basis for paper-facing claims.
## BY3A5/BY3A5B Dual Yaw Input Source Repair

BY3A5 audits the BY3 dual-yaw input source and correctly confirms the old BY3 15-column yaw was wrong-source. BY3A5's HDT replacement policy is diagnostic/rejected/superseded for mainline BY3.

BY3A5B repairs the mainline dual-yaw input with GNSS1/GNSS2 A1_dual_diff short-baseline absolute positions, BY2 sign/lateral conversion, and fixed_1p5 yaw_std. GNSS status long-baseline `rel_pos_n/e/d` and NMEA HDT must not be used as mainline solver yaw sources. HDT is diagnostic/legacy only unless a later human-approved stage explicitly changes the policy.

BY3A6 validated that the BY3 trace file is the evaluation truth reference and that the current evaluator uses raw numeric trace fields with valid base_time alignment. Processed trace lat/lon fields are unsafe for blind evaluation.

BY3A6 confirmed and repaired stale first-row initatt for stage1/LegSA by using the first dual GNSS/A1 yaw row at or after requested starttime. Trace remains evaluation-only and must not be used for solver initatt or tuning.

BY3A6 completed BY3 normal-only solver/evaluator reruns after initatt repair. Position/up remained sane, but yaw still failed before BY3A7; this is now historical pre-BY3A7 evidence.

## BY3A7 IMU Preprocessing Repair

BY3A7 keeps the BY3 trace as evaluation-only and keeps A1_dual_diff as the mainline short-baseline yaw observation source with dynamic-quality caution. A1 invalid epoch criteria are source quality only: baseline-length and yaw-jump checks, not trace RMSE or final metrics.

BY3A7 identifies the BY3 Go2 body IMU as a source observation stream that must be converted FLU-to-FRD exactly once. The repaired BY3A7 IMU input changes only the preprocessing bias source: gyro bias comes from the pre-motion BY3 body-state segment before selected Go2 start, rather than from a moving segment after selected Go2 start. This is not a Go2 truth claim and not a trace-tuned correction.

BY3A7 normal-only yaw sanity passed for dual-yaw algorithms. BY3 degradation planning can proceed only after human review; paper claims remain false.
