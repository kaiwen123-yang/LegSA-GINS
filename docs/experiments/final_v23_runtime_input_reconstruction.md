# final_v23 runtime input reconstruction

N4H1P separates two source layers.

Runtime actual input:

- final_v23-style runtime consumes a 15-column `.gnss` file:
  `time lat lon height std_n std_e std_d vn ve vd std_vn std_ve std_vd yaw yaw_std`.
- The reconstructed file is named `BY2_PROCESS_DATA_COMPAT.gnss`.
- The reconstructed IMU increment file is named `BY2_PROCESS_DATA_COMPAT.imu`.
- The reconstructed coverage report is named `PROCESS_DATA_COVERAGE_REPORT.json`.

Upstream generation fields:

- `gnss1-status.csv` provides the main `.gnss` time axis, position, and
  position standard deviation.
- `gnss1-raw.csv` `UBX-NAV-PVT` provides `vn/ve/vd/sAcc` as merge-asof
  auxiliary fields.
- `gnss1-status.csv` and `gnss2-status.csv` provide A1 dual-difference status
  yaw through `rel_pos_n/e/d` and validity fields as merge-asof auxiliary
  fields.
- BY2 sportmodestate text provides Go2 body IMU gyroscope and accelerometer for
  process_imu-compatible increments.

The uploaded `process_data.py` keeps `gnss1-status` as the main table, merges
PVT velocity and status yaw into that table, then applies `ffill().bfill()` to
merged velocity/yaw fields. Therefore reconstructed `.gnss` rows should not be
directly capped by PVT row count.

If a historical `final_status_fixed1p5_case*.gnss` file is missing, reports must
write:

- `historical_final_v23_gnss_file_status=evidence_missing`.
- `reconstructed_process_data_compat_available=true` when N4H1P generation
  succeeds.
- `reconstructed_process_data_compat_coverage_status=<status>` from the
  coverage report.

The reconstructed file is not a historical exact final_v23 input file. It is a
process_data-compatible runtime input reconstruction from upstream BY2 fields.
It does not use trace as solver input and does not make a performance claim.
It is not a historical exact final_v23 input unless the historical file exists
and an explicit comparison passes.
