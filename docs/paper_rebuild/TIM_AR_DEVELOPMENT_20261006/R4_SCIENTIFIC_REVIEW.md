# R4 scientific review

Reviewed manuscript: `manuscript/manuscript_tim_r4.md`.

Review scope: Abstract; Sections 2.3, 2.4, 2.6 and 2.7; Section 4.6; Discussion; and the separation of original V3 results from later diagnostics. This was a read-only scientific review in Ubuntu-22.04 WSL. No navigation solver, CILS search, experiment, Monte Carlo simulation or metric aggregation was rerun. Derivatives were checked analytically; numerical statements were compared with existing sealed tables. IEEE citation reformatting was outside this review.

Final snapshot read after all four clarifications:
`139155cc85d9e47e01b00cd35f5ebc09104f4355e72ef29043529022a5e4a438`.
This digest identifies the final reviewed content; it is not a claim that the manuscript cannot subsequently change.

## Findings and disposition

1. **Abstract: implemented weighting versus uncertainty analysis.** The initial wording could imply that V3 had implemented and experimentally validated the full joint receiver/attitude/timing/reference covariance model. The latest snapshot explicitly separates the uncertainty analysis from implemented weighting and limits synthetic checks to selected derivatives and assumed distributions. **Resolved in the reviewed snapshot.**

2. **Section 2.7, Eq. (12): angular-rate convention.** The lever-arm velocity requires body angular rate relative to the chosen navigation frame, expressed in body coordinates. Raw gyro rate cannot be substituted without the applicable frame-rate correction. The latest snapshot supplies this definition and distinguishes timestamp difference from physical acquisition offset. **Resolved in the reviewed snapshot.**

3. **Section 2.4, final paragraph: covariance implementation ambiguity.** The phrase "with their cross-covariances retained" can still sound like an implemented runtime covariance model. The Jacobians are correct for the stated right perturbation, but the cross-blocks are required by the uncertainty analysis and are not supplied by the working covariance. Suggested wording: "their cross-covariances are required in the uncertainty analysis; they are not supplied by the implemented working covariance." **Resolved by the manuscript editor and verified in the final snapshot.**

4. **Discussion, second paragraph: meaning of the inflation cap.** "Its cap limits influence" is technically imprecise. An upper bound on the covariance multiplier bounds maximum inflation and downweighting; it does not itself prove a strict upper bound on measurement influence or a robust-estimation influence function. Suggested replacement: "The cap bounds the applied covariance inflation without proving a calibrated false-alarm or missed-detection rate." **Resolved by the manuscript editor and verified in the final snapshot.**

No additional substantive formula, sign or archived-number discrepancy was found within the stated scope. This is a scoped review, not an independent reproduction or proof of every implementation statement.

## Mathematical checks

- **Original versus later heading model:** Section 2.3 identifies the original scalar Euler-yaw approximation and keeps the later projected-baseline diagnostic separate. The frozen scalar standard-deviation marker is not represented as a propagated per-epoch uncertainty.
- **Baseline covariance:** Eq. (7) correctly includes both antenna cross-covariance blocks. Its heading derivative uses horizontal projection length, requires nonzero projection and a consistent local angle branch, and cannot describe arbitrary wrong-integer modes by itself.
- **Lateral-baseline geometry:** For the declared right-to-left baseline and ZYX body-to-navigation rotation, Eqs. (10) and (11) correctly give the tilt-dependent offset from Euler yaw and the horizontal projection length. A three-dimensional length band does not exclude projection degeneracy.
- **Attitude perturbations:** The transformed-velocity Jacobian in Section 2.4 follows a right perturbation of the rotation before frame conversion. Eq. (13) instead uses the stated left rotation-vector error and prediction-minus-observation residual. The signs are consistent: the prediction derivative has the opposite sign to that residual Jacobian. Neither is a vector of three Euler-angle derivatives.
- **Time:** With acquisition-minus-nominal timing error, the first-order baseline contribution is minus antenna-1 velocity times its error plus antenna-2 velocity times its error. Section 2.6 correctly keeps event delay, clock origin and clock rate separate; one event cannot generally identify all three.
- **Reference comparison:** Eq. (9) is a covariance identity for errors at the same point, time and frame. Shared GNSS lineage prevents interpreting difference RMSE alone as independent absolute accuracy or identified uncertainty.
- **Directional budget:** The reported 6.109 mm and 3.054 mm are correct single-term small-angle design allocations for a 0.35 m horizontal projection. They are not a measured receiver precision or a complete uncertainty budget.

## Existing-evidence checks

The review used the following existing sources, without rerunning their calculations:

- [Measurement validation report](../AR_TIM_EXPLORATION_20261006/04_MEASUREMENT_AND_VALIDATION.md), and its [Jacobian checks](../AR_TIM_EXPLORATION_20261006/measurement_validation/JACOBIAN_CHECKS.csv), [distribution propagation](../AR_TIM_EXPLORATION_20261006/measurement_validation/GAUSSIAN_PROPAGATION.csv), and [directional budget](../AR_TIM_EXPLORATION_20261006/measurement_validation/ANGLE_TARGET_BUDGET.csv). The reported derivative discrepancies, small-angle comparison, near-singular 89-degree-roll example, and distinction between the diagnostic length band and original provider admission are consistent.
- [135-run diagnostic summary](../EXISTING_DATA_R5_20261005/existing_results/DIAGNOSTIC135_PAPER_RESULTS.md). Section 4.6 preserves case-level means, matched support, later-version identity, retained heading, conditional robot-update counts, and the unfavorable vertical effect.
- [Interruption diagnostic summary](../EXISTING_DATA_R5_20261005/existing_results/GAP22_PAPER_RESULTS.md). The epoch counts, exact-common-support comparisons and restart wait agree with archived reporting. The manuscript explicitly calls this a compound version-and-support sensitivity check.
- [Independent D review](D_INDEPENDENT_REVIEW.md). Discussion correctly treats D as a separate candidate-level exploration: nominal help did not become demonstrated protection against the registered bad-prior cases, and a global objective certificate is not integer correctness or accepted-heading integrity.

## Claim boundary

The revision presents standard uncertainty propagation, geometry and timing analysis as an interpretation of the installation and implemented aiding path. It does not claim a new integer-search method or turn the exploratory D selector into part of the original V3 filter. It also acknowledges one installation, three recordings, dependent perturbations, partial development use of transfer sequences, unknown physical covariance inputs and correlated-reference limitations.

These clarifications improve scientific accuracy; they do not by themselves establish methodological novelty for TIM or GPS Solutions, physical uncertainty calibration, cross-platform generalization, or a probability of acceptance. The scientific disposition is **no blocking issue found within this scope; all four reported clarifications are resolved**.
