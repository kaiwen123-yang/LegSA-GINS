# N4H4E Visual Plot Catalog

Mandatory plot groups:

- `01_trajectory`: trajectory XY, height over time, port-minus-final_v23 zoom,
  and trajectory error to reference.
- `02_position_errors`: horizontal/up errors for port and dual_final_v23, plus
  port-minus-final_v23 position differences and p95 visual window.
- `03_attitude_errors`: roll, pitch, yaw errors, parity attitude differences,
  and yaw wrap sanity.
- `04_port_finalv23_parity`: parity horizontal/up/attitude time series and
  parity histograms.
- `05_absolute_reference`: absolute error comparisons against the evaluation
  reference.
- `08_summary_panels`: absolute summary, parity summary, and gate status.

Optional evidence-backed groups:

- `06_update_timeline`: update counts, yaw scheme modes, and yaw residuals. If
  runtime traces are missing, the runner records `evidence_missing`.
- `07_std_consistency`: port/final_v23 STD and error-vs-3sigma figures. If STD
  is missing, the runner records `evidence_missing`.

No generated `.png`, `.pdf`, `.svg`, `.jpg`, or `.jpeg` files may be committed.
