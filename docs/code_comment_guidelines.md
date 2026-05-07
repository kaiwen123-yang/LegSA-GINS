# Code Comment Guidelines

## Comment Goals

- Improve code readability for later development and paper-oriented review.
- Make baseline/proposed boundaries explicit.
- Make coordinate frames and data-source roles explicit.
- Make forbidden actions visible near high-risk code.
- Prevent later misuse of trace, receiver internal IMU, or final_v23 baseline
  outputs.

## Comment Style

- C++ key logic should use short Chinese + English comments.
- Python modules should use Chinese module docstrings or top-level comments, with
  short function-level comments at high-risk boundaries.
- Do not add line-by-line mechanical noise.
- Do not write performance conclusions unless the repository contains matching
  evidence and the phase allows such claims.

## High-Risk Points That Must Stay Commented

- final_v23 is baseline/oracle/backbone reference, not proposed.
- Output standardization must not change numerical values.
- trace is evaluation-only and must not enter solver paths.
- receiver internal IMU is not Go2 body IMU.
- Go2 body-state uses the Go2 FLU frame and must pass through a frame adapter.
- no double FLU-to-FRD transform.
- no output-only correction.
- no trace tuning.
- no raw data commit.
- no final_v23 output substitution or proposed solver contamination.

## Review Rule

N3D comments document responsibilities and boundaries only. They must not change
algorithm logic, output schemas, manifest fields, tests, or numerical behavior.
