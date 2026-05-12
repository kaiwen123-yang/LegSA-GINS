# N6B1 Plot Catalog

Required figure groups:

- `01_clean_validation`: clean no-source-aware versus N6B horizontal, up, yaw,
  roll/pitch, and time-delta curves.
- `02_weight_traces`: N6B R-scale time series, histograms, OIM normalized
  innovations, LSIM scores, and p95 scale by source.
- `03_spike_response`: raw Doppler spike zooms and response table.
- `04_stress_validation`: receiver-velocity disabled, std-scale, outage, and
  noise stress comparisons plus stress delta summary.
- `05_policy_diagnostics`: N6A versus N6B R-scale and metric deltas, and N6B
  deadband diagnostics.
- `06_summary`: visual decision and metric summary panels.
- `07_case_review`: runtime-only JSON reports and markdown review.

Figure files are runtime-only and must not be committed.
