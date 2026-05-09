# N4H4R2 Clean Replay Readiness

N4H4R2 prepares the port-core for clean replay but does not run or claim clean
replay parity.

R3 plan:

- Use the clean replay input role alias rather than tracked local absolute
  paths.
- Run the R2 port-core on clean high-level IMU/GNSS inputs.
- Compare against the external clean reference and dual_final_v23 official
  reference.
- Report pass/fail honestly.
- Preserve all bad epochs unless a later stage explicitly defines a diagnostic
  screen; no epoch deletion is allowed for metrics.

No performance claim is allowed before N4H4R3 produces a clean replay parity
report.
