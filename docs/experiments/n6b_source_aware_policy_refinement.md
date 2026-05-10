# N6B Source-Aware Policy Refinement

N6A proved that source-aware LSIM/OIM weighting entered the real EKF path as
`R_scaled -> EKFUpdate`, but the policy was too aggressive: normal sources could
sit at the global cap and clean `lsim_oim` degraded versus
`baseline_plus_raw_no_sourceaware`.

N6B keeps the activation path and refines only the policy. OIM uses innovation
covariance, LSIM is metadata-only, per-source caps are conservative, and the
rolling innovation baseline uses only solver-visible innovation history.

Boundary:
- diagnostic engineering evidence only;
- no trace or final_v23 output weight tuning;
- no hardcoded spike-time solver behavior;
- no R shrink;
- no Go2 prior, FGO, smoothing, output-only correction, or epoch deletion;
- no paper performance claim and no outperform final_v23 claim.
