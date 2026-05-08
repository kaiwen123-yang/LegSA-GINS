# dual_final_v23 official parity lock

N4R3 locks the evaluator profile against the confirmed dual_final_v23 official
summary and official error_series.

Profile confirmation requires:

- horizontal summary diff <= 0.05 m;
- up summary diff <= 0.05 m;
- yaw summary diff <= 0.2 deg;
- official error_series yaw_error RMSE diff <= 0.5 deg when error_series is
  available.

The lock is evaluator-only. It does not select a physical antenna offset, does
not tune solver yaw, does not rewrite output, and does not delete epochs.

Trace remains evaluation-only and is not solver input.
