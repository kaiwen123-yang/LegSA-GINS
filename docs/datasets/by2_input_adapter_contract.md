# BY2 Input Adapter Contract

N4E creates BY2 real-data input adapters and a source-role manifest. It prepares receiver-native GNSS status, raw message summaries, trace reference rows, and Go2 body-state diagnostic rows for later stages.

N4E does not run solver performance evaluation and does not implement raw Doppler, Go2 priors, source-aware weighting, LSIM/OIM, or FGO smoothing.

## Source Roles

- `gnss1-status.csv` and `gnss2-status.csv`: `receiver_native_gnss_status`.
- `gnss1-raw.csv` and `gnss2-raw.csv`: `raw_gnss_message_stream_scanned_only`.
- `trace_*.csv`: `evaluation_reference_only`.
- `imu-data.csv`, `imu-biases.csv`, and `imu-temp.csv`: receiver internal IMU, not Go2 body IMU.
- `by2.txt`: `go2_body_state_diagnostic`.

## Solver Policy

N4E generated artifacts are role-declared inputs, not performance evidence.

- `trace_solver_input: false`
- `trace_evaluation_only: true`
- `trace_used_for_tuning: false`
- `receiver_imu_as_body_imu: false`
- `raw_doppler_extracted: false`
- `output_only_correction: false`
- `final_v23_output_substitution: false`

Raw data, large CSV outputs, rosbag, RINEX, RTCM, UBX, RAWX dumps, and local absolute paths must not be committed. Local BY2 paths may be used only for `/tmp` probe outputs.

## Evidence Boundary

The raw message scanner records message names and small bounded samples. It does not parse pseudorange, Doppler, or carrier phase, and it does not create a raw GNSS factor.

The trace adapter writes evaluation-only reference rows. Trace is forbidden as solver input, tuning input, or output-only correction input.

The Go2 body-state parser writes diagnostic rows only. These rows require frame adapter validation before any future estimator use.
