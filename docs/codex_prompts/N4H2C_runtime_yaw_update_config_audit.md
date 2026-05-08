# N4H2C Runtime Yaw Update Config Audit Prompt

Goal: audit why actual dual_final_v23 yaw passes under confirmed `direct_identity` evaluator while N4H2 replay yaw fails under the same profile.

Use runtime-only role aliases:

- `DUAL_FINAL_V23_ARTIFACT_ROOT`
- `N4H2_ARTIFACTS_ROOT`
- `EXTERNAL_KFGINS_ROOT`

Do:

- compare actual and replay `input.gnss`
- compare actual and replay NAV
- classify actual and replay input-to-NAV yaw relation
- search runtime config evidence
- audit current KF-GINS yaw update source read-only
- search yaw update git history read-only
- write diagnostic JSON and Markdown reports

Do not:

- modify external KF-GINS source
- copy external source
- commit artifacts or raw data
- use trace as solver input
- perform output-only correction
- tune yaw to chase final_v23
- relax yaw above 2 deg
- implement raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, FGO, or full EKF
- make a formal performance claim
