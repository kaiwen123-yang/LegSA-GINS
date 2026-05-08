# Fresh Replay Evaluation Against Dual Reference

Fresh replay evaluation uses the selected official reference profile reconstructed from dual_final_v23 official NAV plus official error_series.

The evaluator uses direct identity yaw error. It does not use diagnostic `ref=heading_to_math_yaw`, does not tune yaw, and does not relax the strict yaw gate.

Reported gates:

- horizontal_rmse_m <= 2.0
- up_rmse_m <= 3.0
- yaw_rmse_deg <= 2.0
- roll_rmse_deg <= 1.0 strict
- pitch_rmse_deg <= 1.0 strict
- roll/pitch relaxed <= 1.6

These metrics are baseline replay diagnostics only. They are not proposed solver performance and are not a formal paper claim.
