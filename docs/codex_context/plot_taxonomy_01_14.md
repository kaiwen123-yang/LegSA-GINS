# Plot Taxonomy 01-14

This taxonomy applies to BY2 normal, later degradation cases, BY3, indoor-outdoor transitions, and poor-GNSS environments.

## 01_trajectory

Examples: local ENU trajectory, baseline vs selected feedback, EKF vs FGO vs feedback EKF, truth/reference/estimate overlay, start/end markers, local zoom, delta vector, global compare.

Requirements: frame alignment gate passed; East/North axes; real delta vectors; real local zoom.

## 02_position_errors

Examples: North/East/Up/horizontal error time series, horizontal/up RMSE, P95, max, CDF/ECDF, outage shading, recovery time.

Requirements: errors from EVAL_NAV or recomputed after frame/time alignment; metric sanity passed.

## 03_velocity

Examples: vN/vE/vD estimate, receiver velocity, Raw Doppler velocity, Go2 horizontal velocity, foot kinematic velocity, residuals, deltas, factor residual P95, Doppler residual.

Requirements: source-specific velocity evidence; no zero-line placeholders; no availability bars.

## 04_attitude

Examples: roll/pitch/yaw estimate/reference/observation, yaw residual, yaw wrap check, yaw-rate residual, attitude RMSE/P95.

Requirements: explicit degree/radian, wrap/unwrap, and yaw convention.

## 05_consistency

Examples: error plus 3 sigma, innovation/residual, whitened residual, NIS proxy, coverage ratio, covariance diagonal, feedback covariance inflation.

Requirements: uncertainty from STD/covariance/residual, not an error proxy.

## 06_observation_quality

Examples: GNSS observation/std, yaw observation/yaw_std, Raw Doppler satellite count/residual/std, Go2 contact weight, foot quality, feedback accepted/rejected, source-aware R scale.

Requirements: source role must be explicit.

## 07_compare

Examples: baseline EKF, Raw Doppler EKF, source-aware EKF, Go2 joint EKF, no-feedback FGO, feedback EKF, reject-all sanity, selected feedback.

Requirements: at least two real algorithm series and metric sanity passed.

## 08_summary_panels

Normal case: algorithm metric summary, source availability summary, data lineage summary.

Degradation heatmaps are not allowed until N9B/N9C has real degradation outputs.

## 09_case_review

Examples: case summary, key metrics, worst intervals, degradation input notes, anomalies, pass/fail, most relevant figures, conclusion.

## 10_fgo_factors

Applicable only when FGO/factor reports exist. EKF-only cases must be documented not-applicable.

## 11_feedback

Applicable only to feedback-capable cases with runtime feedback rows. Baseline no-feedback and no-feedback FGO are documented not-applicable.

## 12_legged_factors

Applicable only when real Go2 contact/foot/legged factor data exists. Availability bars must not be used as contact probability time series.

## 13_degradation_meta

Normal condition is documented not-applicable with reason `normal_condition_no_degradation_injection`. Degradation cases must record injected degradation inputs.

## 14_audit_sanity

Required for every case: row count, time monotonicity, NaN/Inf, input/output alignment, runtime manifest, no future data, no output substitution, path leak check.

## Permission Matrix Required Fields

Every planned figure row must include:

```text
category
filename
required_by_user
required_data_type
required_source
data_available
source_role
row_count
time_overlap_count
alignment_pass
metric_sanity_pass
semantic_sanity_pass
allowed_to_plot
if_not_allowed_reason
should_be_missing
should_be_not_applicable
should_be_redrawn_after_gate
claim_allowed
```
