# N7C1 Go2 Horizontal Velocity Visual Validation

N7C1 is a visual-validation and plotted-data coverage stage for the existing N7C controlled Go2 horizontal velocity weak prior.

It does not change solver math, tune parameters, delete epochs, apply output-only correction, implement FGO, or create a paper performance claim.

Inputs are referenced by role alias only:

- `N7C_RUNTIME_REPORT_ROOT`
- `N7B5_RUNTIME_REPORT_ROOT`
- `N5B_RUNTIME_REPORT_ROOT`
- `N6B_RUNTIME_REPORT_ROOT`
- `DUAL_FINAL_V23_ARTIFACT_ROOT`

N7C1 checks that clean curves, prior signals, residual/update timelines, stress variants, and vertical-disabled evidence are visible and backed by non-empty plotted source data.

Boundary:

- Go2 velocity is a weak prior, not truth.
- Go2 vertical velocity remains disabled.
- Go2 position and yaw priors remain disabled.
- Trace and final_v23 outputs remain evaluation-only and are not solver input.
- No outperform-final_v23 claim is made.
