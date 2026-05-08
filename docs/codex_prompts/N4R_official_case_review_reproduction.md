# N4R official case-review reproduction prompt

Goal:
Reproduce official final_v23 case-review metrics and identify yaw evaluator
convention before full framework transplant or factor stacking.

Required boundary:

- do not modify external KF-GINS source;
- do not copy external source;
- do not submit raw data or actual final_v23 artifacts;
- do not use trace as solver input;
- do not perform output-only correction;
- do not delete bad epochs;
- do not tune solver parameters to final_v23;
- do not implement raw Doppler, Go2 priors, source-aware weighting, LSIM/OIM,
  FGO, or full EKF;
- do not make formal numerical performance claims.

Expected outputs:

- OFFICIAL_CASE_REPRODUCTION_REPORT.json
- OFFICIAL_YAW_EVALUATOR_PARITY_REPORT.json
- OFFICIAL_ERROR_SERIES_PARITY_REPORT.json
- REPLAY_OFFICIAL_YAW_PARITY_REPORT.json
- N4R_DECISION_REPORT.json
- official_final_v23_case_review_reproduction.md

Tracked docs must use role aliases only. Runtime reports may contain local
paths under the requested output directory.
