# N8E Module Contribution Summary

N8E summarizes these module roles:

- Raw Doppler EKF: active effective front-end factor.
- Raw Doppler FGO: active solver factor with low marginal value in current
  no-feedback FGO.
- Source-aware LSIM/OIM: active R scaling layer with limited stress evidence.
- Go2 proprioceptive joint: active EKF factor; Go2 fields are observations, not
  truth.
- Contact probability: weighting candidate, not a direct formal factor.
- Foot kinematic velocity: diagnostic candidate with slip-risk caveat.
- Yaw-rate / relative odometry: FGO candidates, diagnostic only.
- No-feedback FGO: framework ready, but no feedback/substitution and no paper
  performance claim.
