# LC02 Yin 2023 formal-primary NO-GO

Terminal: `NO_GO_LC02_YIN2023_RAEKF_AS_FORMAL_PRIMARY`.

The NO-GO is narrow. The base 21-state model, position-only measurement identity, improved `PDOP^2 Q r^2` construction, scalar IGGIII thresholds/function, convex state/covariance fusion, and fusion factors are source-closed. Eq. 10 uses component Greek `ω` (U+03C9 omega), Eq. 11 uses a distinct Latin `w(tilde V_i)` middle multiplier, and Eqs. 12–14 use fusion `ϖ` (U+03D6 varpi). The author response closes the Eq.10-weighting-function-to-Eq.11 semantic relation without collapsing the glyphs; legacy `v/omega` is compatibility notation only. LC01-versus-LC02 distinctness and BY2 input availability also remain closed from Y0–Y3.

Formal RAEKF admission fails because the full online mapping is not unique:

- Eq. 6 divides a 3D residual norm by the trace of a covariance described as 21-state; a later related patent instead calls it measurement-vector covariance.
- `L_k` is never equated to `Z_k`.
- Eq. 8 `V_hat_k` is never related to Eq. 9 `bar_V_k`, and Eq. 9 `bar_A_(Xhat_k)` is undefined;
- the standardized residual lacks a numerator/centering/denominator/covariance-stage definition;
- Eq. 11 overloads the same self-referential `bar_A(tilde V_i)`; a conventional base/equivalent split is only paper-derived and does not define a general correlated matrix;
- a zero weight is followed by an inverse without a rejection operation;
- both branches' identical prior and separate-then-fuse relation are source-closed, but fusion-before-feedback, one-reset behavior, and reset-Jacobian placement are not specified for Yin 2023; covariance cross-terms limit Eq. 13's probabilistic interpretation without making its printed convex formula ambiguous.

Niu 2022 and its attributable code provide a credible `S_ii` standardizer and row-deletion policy, but Yin does not uniquely adopt them and changes the IGG function and thresholds. Knight/Yang sources provide other standardization, robust-scale, bifactor, and zero-static-weight candidates; they likewise do not uniquely select Yin's Kalman operation. The related 2024 patent changes the method substantially. Any such completion would therefore be a policy baseline, not faithful Yin reproduction.

Branch levels remain: EKF `FAITHFUL_ALGORITHM_REPRODUCTION`; AKF `FAITHFUL_MODULE_REPRODUCTION`; RKF and RAEKF `PAPER_DERIVED_POLICY_BASELINE`. Formal LC02 admission, implementation, production solver, C00, representative cases, and comparison runs remain unauthorized.
