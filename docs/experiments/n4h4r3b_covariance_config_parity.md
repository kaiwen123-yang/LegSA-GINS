# N4H4R3B Covariance/Config Parity

The covariance/config audit checks whether R3A's too-good metrics could be caused by an overly tight P/R/Qc/config setup rather than valid source-backed behavior.

The checked surface includes initial position/velocity/attitude covariance, IMU bias/scale noise, corrtime, GNSS measurement standard deviations, velocity and yaw standard deviations, antlever, scheme_C gates, and clean/noisy provenance.

This audit does not tune R, P, Qc, yaw gates, or start/end windows. If a mismatch is found, the next stage must be a source-backed parity fix, not trace tuning.
