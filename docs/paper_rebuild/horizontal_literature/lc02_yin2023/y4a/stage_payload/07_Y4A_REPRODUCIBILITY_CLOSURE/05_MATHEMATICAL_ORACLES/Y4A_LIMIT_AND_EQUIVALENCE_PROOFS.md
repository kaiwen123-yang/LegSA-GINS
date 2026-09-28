# Deterministic linear-oracle proofs

These are standalone small-matrix algebra checks. They read no BY2, trace, reference, native navigation output, or prior result. A passing oracle demonstrates that an ambiguity is materially consequential or that a stated limit is mathematically valid; it never selects a missing paper semantic.

All 28 deterministic rows pass. The externally required identities are explicitly registered: 1D and 3D EKF updates; AKF `alpha=1`; nominal inlier information under an explicitly declared `PAPER_DERIVED` conventional Eq. 11 split; finite positive Eq. 10 middle factor; the absence of a unique Yin zero policy plus limit checks; exact Eq. 12/13 fusion; N/E/D permutation equivariance; and preservation of `m^2` units.

The oracle `ZERO_WEIGHT_NO_UNIQUE_YIN_POLICY` is deliberately epistemic: it records one non-executable printed singular path and at least two executable but unselected completions—row omission and a positive infinite-variance limit. Its PASS means the fail-closed statement was retained, not that a zero-weight operation was solved.

## AKF statistic

For residual `V=[4,2]^T`, prior covariance `diag(4,9,16)`, `H=[e1^T;e2^T]`, and `R=diag(1,4)`, the printed state-trace statistic is `sqrt(20/29)=0.830454798537`. Replacing the incompatible denominator with the measurement-space innovation trace gives `sqrt(20/18)=1.05409255339`. At `k=1`, the two interpretations select different adaptive factors by more than 0.05. Thus denominator semantics change the update.

## Standardized residual and IGGIII

For residual component 3, `R_ii=0.25` yields magnitude 6, above `k1=4.45`, while `S_ii=4` yields magnitude 1.5, inside the middle band. Their Yin Eq. 10 factors differ by `0.547684953298`. The scalar function is continuous at `k0=1.15` and reaches zero at `k1=4.45`. Eq. 11 prints Latin `w(tilde V_i)`, not Eq. 10 Greek `ω`; the author response says the Eq. 10 weighting function enters Eq. 11 but does not collapse the glyphs. The paper's Eq. 11 is self-referential and does not uniquely define the base/equivalent information split; the oracle's `A_equivalent=w(tilde V_i) A_base` mapping is explicitly derived and unselected. Any subsequent zero-information inverse still requires a specified operation.

For correlated `R=[[4,1.2],[1.2,1]]` and unequal weights, left-multiplying `R^-1` by a diagonal weight matrix is nonsymmetric. A square-root sandwich remains PSD but differs numerically. Both are algebraically possible; neither is printed by Yin.

## Zero-weight limit

For a scalar update, replacing `R` by `R/epsilon` and taking positive `epsilon` toward zero makes the posterior approach the prior, which equals omitting that observation. The same equivalence holds componentwise for the constructed diagonal two-dimensional case. For correlated covariance, a symmetric inflation path retains off-diagonal interactions and differs from direct row/column deletion by `0.0927096604992`; the operation must be specified.

## RAEKF covariance

For `P_ak=I`, `P_rk=4I`, and fusion factor `ϖ=0.85`, Yin's convex Eq. 13 gives minimum eigenvalue 1.45. The covariance of an independent linear combination differs by norm `0.901561146013`; a mixture covariance including branch-mean spread differs by `0.51`. Eq. 13 is executable when both branch covariances exist, but these alternatives show why a probabilistic interpretation cannot be inferred.

Independent exact evaluations confirm Eq. 12 state fusion and Eq. 13 covariance fusion. Cross-covariance remains an interpretation boundary; it is not an ambiguity in either printed convex equation.

## Nominal, axis, and unit identities

The 1D and diagonal 3D EKF checks reproduce their analytical gain, posterior state, and posterior covariance. Setting `alpha=1` in the printed AKF equations returns the EKF result. A common permutation of N/E/D state, measurement, and covariance inputs produces the correspondingly permuted result. The unit oracle computes the exponent explicitly: `2*PDOP(0) + Q(0) + 2*r(1) = 2`, so each diagonal `PDOP^2 Q r_i^2` term remains in `m^2`.

## Symbol identity

Two observation vectors `L` and `Z` can produce different innovations against the same prediction. Algebra cannot prove they are aliases. Only an attributable source statement could close `L_k=Z_k`; none was found.
