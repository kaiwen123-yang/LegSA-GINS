# Allowed Claims After R2

Allowed:

- The physical antenna-to-body geometry is closed for the user-confirmed GNSS1-right/GNSS2-left lateral installation.
- GNSS1->GNSS2 points to Go2 body +Y_left under FLU.
- A fixed physical transform is available: `body_yaw_NED_deg = wrap360(baseline_heading_NED_deg + 90 deg)`.
- PAPER3F/PAPER3G/PAPER3H baseline-heading diagnostics with explicit `atan2(E,N)` semantics can be reevaluated offline as derived body-yaw metrics.
- Trace is used only as an offline evaluator reference in derived metrics.
