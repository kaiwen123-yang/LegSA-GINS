# BY2 Data Path and Source Role Contract

Stage N3C defines path and role contracts only. It does not implement a solver,
does not tune with trace, and does not make numerical performance claims.

## Receiver Data Roles

- `gnss1-raw.csv` and `gnss2-raw.csv` are dual-antenna GNSS receiver raw data
  sources.
- `gnss1-status.csv` and `gnss2-status.csv` are dual-antenna GNSS receiver
  status, position, and quality sources.
- GNSS raw/status files are only candidates for later receiver-native or
  raw-GNSS input stages.
- `trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv` is
  reference/evaluation-only.
- `trace_solver_input: false`
- `trace_evaluation_only: true`

## IMU And Body-State Roles

- `imu-data.csv`, `imu-biases.csv`, and `imu-temp.csv` are receiver internal IMU
  files. They are not the LegSA-GINS body-state IMU.
- `receiver_imu_as_body_imu: false`
- Go2/body-state high-level data comes from the local `by2.txt` body-state text
  file.
- Body-state data must enter through a frame adapter before any future use.
- Go2 body, odom, map, and navigation frames must not be mixed.

## Storage And Evidence Rules

- Raw data must not be committed.
- `raw_data_committed: false`
- Real local paths must live only in ignored local config such as
  `configs/local/by2_fixposition.local.yaml`.
- Tracked examples may name files and roles, but must not store machine-local
  absolute paths.
- If any path or header check is missing, the evidence status must be
  `evidence_missing`.
