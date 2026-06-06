# Limitations Section Draft Bullets

- The current evidence does not close the physical body-yaw frame; body-yaw RMSE and yaw superiority claims are therefore excluded.
- External literature algorithms are not claimed as exact reproductions. They are reported as module, proxy, native diagnostic, or backend-level implementations with explicit boundaries.
- Provider v4 is GPS+BDS LOS/covariance/residual-ready, but Galileo, GLONASS, and SBAS remain blocked by documented system-specific issues.
- BY3 is not used for ordinary yaw generalization; yaw is diagnostic-only.
- XB/PG severe poor-GNSS evidence motivates quality-aware fallback work but does not prove high-precision performance under severe GNSS degradation.
- Same-evaluator superiority over final_v23, LegSA_QA, or LegSA_full is not claimed because the internal join and provenance gates are incomplete.
- Trace is evaluation-only and is not used online, for tuning, or as a solver/provider input.
- Receiver imu-data.csv is diagnostic-only and is not used as Go2 body IMU.
