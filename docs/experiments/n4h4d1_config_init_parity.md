# N4H4D1 Config/Init Parity

This diagnostic checks whether LegSA-v23-core parsed initialization and noise configuration into the intended internal units.

The primary checks are deg/rad conversion for BLH and attitude, height staying in meters, initial attitude back-conversion, initial covariance scale, IMU noise plausibility, antenna lever arm scale, and start/end overlap with clean input.

The report is diagnostic evidence only. If it flags `config_units_issue`, `initatt_yaw_mismatch`, `antlever_mismatch`, `imunoise_unit_issue`, or `start_end_mismatch`, the next stage may repair config handling, but N4H4D1 itself does not repair or retune anything.
