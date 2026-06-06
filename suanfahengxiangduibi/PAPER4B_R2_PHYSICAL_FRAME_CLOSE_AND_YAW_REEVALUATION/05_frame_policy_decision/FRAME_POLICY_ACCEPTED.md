# FRAME_POLICY_ACCEPTED

PAPER4B_R2 accepts the physical antenna-to-body frame geometry from the user's confirmation and the official GNSS extrinsics relation.

Accepted physical chain:

1. The receiver front faces the Go2 forward direction.
2. Official GNSS extrinsics are used.
3. GNSS1 has negative y and is physically the robot-right antenna.
4. GNSS2 has positive y and is physically the robot-left antenna.
5. In Go2 FLU, GNSS1->GNSS2 is therefore body +Y_left.

Fixed transform:

`body_yaw_NED_deg = wrap360(baseline_heading_NED_deg + 90 deg)`

The +90 deg transform is a fixed physical transform from a left-pointing lateral baseline to the robot forward axis. It is not chosen from RMSE, trace fitting, method-specific tuning, or per-case offsets.

The physical geometry is closed. Method-level yaw metric promotion remains conditional on native yaw semantics, baseline direction, and trace-offline-only provenance.
