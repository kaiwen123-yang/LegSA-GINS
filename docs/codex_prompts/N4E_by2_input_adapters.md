# N4E BY2 Input Adapters

Stage N4E adds BY2 input adapters and a source-role manifest.

It standardizes receiver-native GNSS status, scans GNSS raw message streams without extracting raw Doppler, converts trace to evaluation-only reference rows, and parses Go2 body-state diagnostic data.

Boundary flags:

- `trace_solver_input: false`
- `trace_evaluation_only: true`
- `receiver_imu_as_body_imu: false`
- `raw_doppler_extracted: false`
- `body_state_requires_frame_adapter: true`

N4E does not implement raw Doppler, Go2 priors, source-aware weighting, LSIM/OIM, FGO smoothing, final_v23 numerical reproduction, or real BY2 performance evaluation.
