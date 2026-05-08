# Clean input provenance policy

N4H2G uses explicit input provenance labels:

- `historical_noisy_dual_final_v23`: recovered dual_final_v23 artifact with
  likely Gaussian yaw-noise provenance.
- `reconstructed_clean_status_yaw`: process_data-compatible clean variant with
  status yaw, fixed 1.5 deg observation yaw STD, zero yaw-value noise, no
  outliers, and no outage.
- `diagnostic_only`: any trace-yaw or evaluator-only evidence that must not be
  used as solver input.

The noisy historical artifact is valid as noisy/stress provenance evidence. It
must not be called clean nominal. The clean replay is not a historical exact
artifact; it is a reconstructed baseline variant used to decide whether the
final_v23-style backbone closes without synthetic yaw degradation.

Trace remains evaluation-only. Output-only correction and bad-epoch deletion are
not allowed.
