# N4H4R3A Config Overlap Parity

The config audit checks that the runtime config uses the clean status-yaw IMU
and GNSS roles, preserves clean input provenance, and covers the effective
overlap between IMU, GNSS, and configured start/end times.

The tracked repository does not store runtime configs or local absolute paths.
Runtime configs are generated only in the runtime output directory.

The audit also verifies antlever and IMU noise fields because missing config
fields can masquerade as filter math divergence. This is a diagnostic contract,
not a proposed factor or paper performance result.
