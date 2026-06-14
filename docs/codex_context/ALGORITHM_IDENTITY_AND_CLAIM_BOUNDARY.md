# Algorithm Identity And Claim Boundary

## Current Main Algorithm

`LegSA_full_EKF` is the verified main algorithm identity for the current paper route. It is an EKF-centered GNSS/INS fusion chain with Raw Doppler, source-aware LSIM/OIM R scaling, Go2 high-level weak priors, and same-case selected feedback evidence where provenance is proven.

Allowed wording:

- main proposed algorithm identity is `LegSA_full_EKF`;
- Raw Doppler velocity update is active in the EKF chain;
- source-aware LSIM/OIM contributes through online R scaling;
- selected feedback is bounded and provenance-dependent;
- Go2 high-level priors are present but require PAPER10C evidence freeze before final wording.

Forbidden wording:

- complete active nine-factor FGO;
- direct FGO NAV overwrite;
- output-only correction;
- trace-derived feedback;
- final_v23-derived feedback;
- full contact-aided InEKF or full FK leg odometry.

## Strong External Baseline

`final_v23_dual_antenna_EKF` is a strong Dual-Antenna GNSS/INS EKF baseline and external reference. It is not the proposed method, not solver input, not a tuning source, and not a hidden target.

Allowed uses:

- external baseline comparison;
- sanity check;
- evaluation-only comparison.

Forbidden uses:

- solver input;
- parameter tuning;
- feedback generation;
- output substitution;
- comprehensive outperform-final_v23 claim basis by itself.

## Future Or Bounded Candidates

`LegSA_QA_Fallback_EKF` is a separate future quality-aware candidate, not the completed main algorithm. It may motivate future poor-GNSS work, but it is not a finished paper contribution unless a later implementation and full validation stage closes it.

`LegSA_9F_FGO_EKF` is a separate active-FGO candidate. It cannot be claimed complete without active backend evidence, residual/Jacobian/cost or equivalent logging, estimator feed-in proof, and ablation contribution proof.

## Source-Aware Claim

Source-aware LSIM/OIM R scaling is a bounded main innovation after PAPER10B_R1 and PAPER10B_R2B. BY2 supports the main controlled-degradation claim. BY3 extends the stress evidence but must keep poor-heading and yaw diagnostic-only wording.

Forbidden source-aware wording:

- universal superiority;
- complete multi-state quality management;
- BY3 ordinary yaw generalization;
- per-case tuned improvement.
