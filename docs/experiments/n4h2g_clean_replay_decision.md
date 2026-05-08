# N4H2G clean replay decision

N4H2G generates and evaluates a clean status-yaw no-noise replay, compares it
with noisy historical dual_final_v23 evidence, and records the clean/noisy
provenance policy.

Decision rules:

- `passed`: clean replay horizontal/up/yaw gates pass.
- `near_gate`: clean replay yaw is above 2.0 deg but no higher than 2.2 deg.
- `failed_yaw`: clean replay yaw is above the near-gate region.
- `failed_position_or_up`: clean replay position or up gates fail.

The decision report chooses the next stage from those diagnostic results. It
does not make a formal performance claim and does not implement proposed solver
logic.
