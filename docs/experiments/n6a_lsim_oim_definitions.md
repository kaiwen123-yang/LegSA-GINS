# N6A LSIM/OIM Definitions

The definition probe found no earlier concrete LSIM/OIM implementation. N6A
therefore adopts auditable definitions:

- LSIM: Local Source Integrity Metric / Source-Level Integrity Metric based on
  source metadata visible to the solver.
- OIM: Observation Innovation Metric based on residual consistency against R
  and optional HPH.

LSIM uses status, validity, covariance availability, time alignment, standard
deviation, dual-yaw antenna state, and raw Doppler provider/satellite metadata.
OIM uses normalized residual / NIS-like innovation consistency.

中文说明：N6A 定义不读取评价误差、不读取 trace、不读取 final_v23 output，也不根据
N5D1 spike 时间调门限。

The definition probe report is runtime-only:
`SOURCE_AWARE_DEFINITION_PROBE_REPORT.json`.
