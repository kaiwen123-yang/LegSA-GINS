# Data Source Roles

This file defines what each BY2 source may and may not support.

## GNSS Raw

Aliases: `<GNSS1_RAW>`, `<GNSS2_RAW>`.

Allowed:

- raw observation audit.
- Raw Doppler source audit.
- satellite count, Doppler residual, GNSS observation quality.
- dual-antenna source lineage and time coverage checks.

Not allowed:

- direct algorithm estimate.
- hidden replacement for NAV/EVAL output.

## GNSS Status

Aliases: `<GNSS1_STATUS>`, `<GNSS2_STATUS>`.

Allowed:

- receiver status.
- GNSS standard deviation / quality fields.
- yaw observation and yaw_std if explicit fields exist.
- receiver velocity only if explicit velocity columns exist.

Not allowed:

- raw GNSS baseline claim for `single_antenna_gnss1_status_KF_GINS`; that baseline is GNSS1-status, not raw GNSS.
- estimate substitution.

## Trace Reference

Alias: `<TRACE_TRUTH>`.

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

## Go2 Body IMU / High-Level

Alias: `<GO2_BODY_IMU_HIGHLEVEL>`.

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

Selected-feedback same-case rule: `selected_feedback` requires feedback generated for the same degraded or clean case. Clean feedback cannot be reused for degraded cases.

EVAL_NAV feedback generation uses state/estimate columns only and must not use trace/error feedback corrections.

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
