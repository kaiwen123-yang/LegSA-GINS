# PAPER4G Evidence Consistency Check

Frozen hard facts:
- PAPER4B_R2: physical installation closed.
- GNSS1 = robot-right antenna.
- GNSS2 = robot-left antenna.
- GNSS1 -> GNSS2 = Go2 FLU +Y_left lateral baseline.
- Physical transform for canonical GNSS1->GNSS2 NED baseline heading: `body_yaw_NED_deg = wrap360(baseline_heading_NED_deg + 90 deg)`.
- PAPER4C: direct GNSS status/LLH baseline sanity failed; status rel_pos and LLH position-diff are not valid physical short-baseline truth.
- PAPER4D: trace.yaw source closed to `user_io-out-poi_geodetic.csv:ypr.vector3.x`, but status rel_pos invalid.
- PAPER4E: Fixposition message semantics support FP_POI/output-frame orientation, but actual BY2 Step 6 output rotation/translation config was not found.
- PAPER4F_R2: user-declared minimal-export yaw policy applied: `trace_body_yaw_NED_deg = wrap360(trace_yaw_deg + 90 deg)`.

PAPER4F_R2 checks:
- row-level rows: `2160`
- valid evaluated rows: `2160`
- method summary rows: `18`
- method semantics rows: `21`
- median previous-policy RMSE: `94.648918` deg
- median user-policy RMSE: `106.093095` deg
- 90-degree-like systematic case ratio: `0.987500`

Conclusion:
The user-declared +90deg trace-body policy was evaluated and did not remove the systematic yaw discrepancy. Body-yaw external-method claims remain diagnostic-only.
