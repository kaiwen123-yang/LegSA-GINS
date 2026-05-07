# Evaluation Target Gates

N4G target gates are diagnostic readiness checks, not formal performance claims.

- horizontal RMSE <= 2.0 m
- up RMSE <= 3.0 m
- yaw RMSE <= 2.0 deg
- roll RMSE strict <= 1.0 deg
- pitch RMSE strict <= 1.0 deg
- roll/pitch relaxed <= 1.6 deg

`ready_for_factor_stacking` is true only when the strict target gate passes. If
the gate fails, the next step remains diagnostic repair rather than raw Doppler,
Go2 priors, source-aware weighting, LSIM/OIM, or FGO.

