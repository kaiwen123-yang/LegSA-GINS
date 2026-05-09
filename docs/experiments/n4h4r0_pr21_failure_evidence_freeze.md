# N4H4R0 PR #21 Failure Evidence Freeze

## Why PR #21 is not merged

PR #21 is the LegSA-v23-core self-written implementation attempt. It proved
that the clean replay runtime can execute end to end, but it did not reach real
clean parity. The branch is therefore retained as `PR21_FAILURE_BRANCH` and is
not promoted into `main`.

The clean replay metrics diverged severely from the `EXTERNAL_CLEAN_REPLAY` and
`DUAL_FINAL_V23_REFERENCE` evaluation references. D1-D6 diagnostics narrowed the
dominant risk to feedback, IMU compensation, covariance/Qc, and bias-scale
coupling. Continuing D7/D8/D9 as point repairs risks becoming an open-ended
patch loop rather than a controlled backbone reconstruction.

## Key PR #21 Evidence

N4H4D baseline:

- horizontal RMSE H ~= 523.827 m
- up RMSE ~= 58.850 m
- yaw RMSE ~= 97.153 deg
- roll RMSE ~= 99.582 deg
- pitch RMSE ~= 35.878 deg

D4 trace/shadow diagnosis:

- first row diff = 0
- first 1s diff is close
- `divergence_after_state_feedback=true`
- `measurement_model_likely_ok_state_diverges=true`
- `feedback_overcorrection=true`

D5 gain/feedback isolation:

- `one_step_mechanization_ok=true`
- `pos_vel_only_feedback` improved the diagnostic replay envelope
- external-state `dx_phi` was small while internal `dx_phi` was huge

D6 IMU error feedback diagnosis:

- `compensation_not_persistent_issue=true`
- `res3_interpolation_compensation_issue=true`
- `corr_time_units_ok=false`
- `Qc_bias_model_ok=false`
- `bias_scale_feedback_primary_suspect=true`

## Decision

- PR #21 is not merged into `main`.
- PR #21 is not closed.
- PR #21 branch is not deleted.
- The next route is source-backed controlled port.
- Current `cpp/legsa_v23_core` is downgraded to diagnostic/self-written attempt.
- Current `cpp/legsa_v23_core` is not the final backbone.
- PR #21 results are not paper performance evidence.

