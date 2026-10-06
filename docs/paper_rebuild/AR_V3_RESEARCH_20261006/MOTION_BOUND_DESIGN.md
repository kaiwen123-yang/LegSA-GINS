# Two-epoch motion bound: derivation before implementation

Status: proposed research kernel, not an implemented or validated AR method.
V3/main is unchanged. GPS Solutions primary, TIM alternate. No performance or novelty claim.

## Fixed scientific problem

Use the same observation rows, integer labels/domains, complete within-epoch Q,
independent-epoch working covariance and fixed equal length L as the comparison.
For a fixed integer N, normal-equation completion gives
J(N,b)=J_float+J_ambiguity(N)+sum_i f_i(b_i), where
f_i(b)=(b-c_i)^T W_i (b-c_i), W_i=C_bi_given_N^-1.
The baseline pair must additionally satisfy angle(b1,b2) in [beta_lo,beta_hi].
The prior is a relative rotation with unknown initial absolute attitude.
This kernel only treats two epochs, with no cross-epoch conditional covariance.
It does not make a multi-epoch Gram test sufficient for a shared SO(3) trajectory.

## A cheap lower bound that retains the old sphere cost

Let s_i be the global minimizer on ||b||=L. Its sphere multiplier lambda_i satisfies
(W_i+lambda_i I)s_i=W_i c_i and H_i=W_i+lambda_i I is positive semidefinite.
For any other vector on the SAME sphere, stationarity and equal norm imply

    f_i(b)-f_i(s_i)=(b-s_i)^T H_i (b-s_i)
                  >= mu_i ||b-s_i||^2,
    mu_i=lambda_min(H_i)>=0.

Let gamma=angle(s1,s2) and delta=distance(gamma,[beta_lo,beta_hi]).
If d_i=angle(s_i,b_i), the spherical triangle inequality gives d1+d2>=delta.
As 4 L^2 sin^2(d_i/2) increases for d_i in [0,pi], its least weighted sum
under that constraint has d1+d2=delta. Therefore

    J_shape(N) >= J_independent(N) + D,
    D=2 L^2 [mu1+mu2-sqrt(mu1^2+mu2^2+2 mu1 mu2 cos(delta))].

For nonzero denominator use the cancellation-resistant expression

    D=8 L^2 mu1 mu2 sin^2(delta/2) /
        [mu1+mu2+sqrt((mu1-mu2)^2+4 mu1 mu2 cos^2(delta/2))].

If either mu is zero, D=0. The hard case is retained, not regularized away.
This is a necessary geometric bound derived from standard constrained quadratic
identities; no novelty claim is assigned to the algebra itself.

The identity is exact in real arithmetic; implemented spectral/root residuals
must be checked and numerical uncertainty conservatively included in bounds.
Do not clip a materially negative eigenvalue and then claim certification.

## Feasible upper bound and integer search

Rotate the two independent sphere solutions in their common plane until their
relative angle reaches the closest permitted endpoint; split angular displacement
by the scalar minimizer above (or a deterministic feasible choice when degenerate).
Antiparallel/parallel baselines need an explicit deterministic perpendicular axis.
These are genuine feasible pairs, hence their full observation objective is an
UPPER bound. Optional local SO(3) refinement remains only an upper bound.

The search must explore all integer branches whose admissible lower bound can
beat the current second feasible upper bound. Reusing only the old top-two is
not sufficient. The old independent-sphere branch lower bound remains safe
under the unchanged problem. The new increment applies to fully specified N;
it must not be applied to partially specified branches without another proof.

At termination retain candidate lower/upper intervals. A certified best INTEGER
identity requires its feasible upper bound below every competing lower bound,
including remaining frontier. This does not certify the continuous minimum.
Overlapping intervals remain UNRESOLVED; do not inherit old global certificates,
ratio risk calibration, acceptance or actual integer correctness.
Any finite exhaustive oracle must state its domain and bound excluded integers.

## Required independent checks before real-data use

1. Direct full residual equals completed objective; sphere multiplier identity.
2. Known feasible pairs never violate the bound; correlated Q, anisotropic
   metrics, hard/near-hard and parallel/antiparallel geometries.
3. Small-domain exhaustive oracle, plus finite range exclusion proof; compare
   all candidates, including a possible new winner beyond old top-two.
4. Correct prior, weak/no baseline-direction excitation, intentionally wrong
   bias/timing/extrinsic prior and too-small error interval; expose exclusion
   of truth rather than counting fewer candidates as better performance.
5. Frame/pivot/receiver reversal consistency and arc/half-cycle qualification.
6. Report actual search cost and unresolved cases. Synthetic checks remain
   outside all V3 real-data tables and cannot qualify a navigation improvement.

The mechanism could improve integer discrimination but cannot repair invalid
carrier observations. A shared gyro later creates dependence with the EKF;
a successful kernel test does not resolve that fusion covariance question.

## Identifiability limitation found before the first prototype run

With unchanged full-column-rank satellite geometry H and shared integers,

    phase_k = Lambda N + H b_k,
    phase_2-phase_1 = H(b_2-b_1).

Exact phase time differences determine Delta b independently of N. Equal known
lengths then give b1^T b2 = L^2-||Delta b||^2/2. An angle-only prior therefore
either permits all exact-phase/length solutions or excludes all of them; it
does not distinguish their integers.

More explicitly, an integer alias d with H v=Lambda d yields
N'=N+d, b_i'=b_i-v. If both original and shifted baselines have length L, then
b_i^T v=||v||^2/2 and b_1'^T b_2'=b_1^T b_2. A nonzero exact integer alias is
not guaranteed to exist for general overdetermined H. Also, noise-free full-rank
code observations already determine b, so this is NOT a claim of unavoidable
ambiguity in the complete noiseless code+phase model.

For two vectors, equal Gram matrices admit a proper rotation between the two
pairs; unknown R0 and nonplanar body motion do not alone break this ambiguity.
For K vectors the same translation alias preserves all pairwise Gram terms.
When three baselines span R^3, the alias reflection has det=-1 and a common
SO(3) constraint can distinguish chirality; pairwise Gram tests still cannot.
That larger problem is not silently substituted for this two-epoch experiment.

With finite measurement noise or different H1/H2 the motion constraint can
change continuous profile costs and possibly integer ordering. This remains
a possible regularization benefit, not proof of added exact-phase integer
identifiability. Midpoint code observations can give equal cost at two specified
alias points, without forcing their finite-weight profiled minima to be equal.
The registered prototype must preserve this distinction and the wrong-prior
counterexample before deciding whether a navigation matrix is justified.

Implementation review adjustment: the first motion search uses only the Gaussian
integer quadratic metric at internal tree nodes. It does not reuse a numerical
sphere optimizer value as a certified lower bound. Full-N motion intervals include
stationarity/spectral/completion margins; all ordering is numerical/model-conditional,
not an interval-arithmetic proof or calibrated integer acceptance.
