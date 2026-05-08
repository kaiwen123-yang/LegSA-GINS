# N4R error_series parity

N4R parses official error_series.csv with tolerant schema aliases:

- time, timestamp, aligned_time, tow
- north_error_m, error_n, err_n_m, dn
- east_error_m, error_e, err_e_m, de
- up_error_m, error_u, err_u_m, du
- roll_error_deg, roll_err_deg
- pitch_error_deg, pitch_err_deg
- yaw_error_deg, yaw_err_deg

If a field is missing, the report preserves evidence_missing. It does not fill
or fabricate missing error fields.

The parity report aligns official and recomputed rows by time and compares
horizontal, up, roll, pitch, and yaw error definitions. The yaw error-series
RMSE difference is the primary signal for identifying whether the official yaw
definition has been reproduced.

Boundary:

- official error_series is evaluator evidence only
- trace remains evaluation-only
- no bad epoch deletion
- no proposed solver performance claim
