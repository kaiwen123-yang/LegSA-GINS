# Foot-interval displacement kernel: local engineering plan

Authorization: implement a GNSS-free finite-interval displacement kernel and at most 25 independent local synthetic/unit tests in Ubuntu 22.04 WSL. No real-data provider, EKF update, raw input, reference, CILS or navigation execution is authorized by this stage. Git is managed by the parent task.

## Explicit inputs and interpretation

Reuse two FootPositionEpoch endpoints with explicit FLU/FRD frames, source/availability times, stance states and episode tokens. A caller-supplied interval_continuous_support map must confirm the complete observed SDK-support interval. The same limitations as support_arcs apply: classified support does not certify physical no-slip.

Require a fully specified relative rotation R mapping body-1 FRD coordinates into body-0 FRD coordinates, with matching interval times, availability, source identity, explicit GNSS-free declaration and left body-0 FRD perturbation convention. Do not derive or complete R from a rank-deficient contact-rotation representative. The declaration is provenance, not proof of statistical independence from the EKF IMU.

Require the body-origin-to-IMU rigid lever vector l in body FRD, with explicit source identity. Zero is allowed only when supplied explicitly; there is no automatic zero lever. Position-source and covariance-source identities are mandatory.

The physical stationary-foot relation is p0_i = R p1_i + t_body. The measurement is an interval body-origin displacement expressed in body-0 FRD, not an instantaneous velocity. The IMU-point displacement is t_IMU = t_body + (R-I)l. No velocity field or navigation provider is produced.

## Fixed first-order working uncertainty

The caller supplies the entire joint covariance Sigma in the order [all endpoint-0 positions, all endpoint-1 positions, left rotation perturbation delta_theta, lever error]. Position blocks retain their respective explicit endpoint frames; rotation and lever perturbations use FRD. All cross-foot, cross-time, position-rotation and lever cross terms are retained. Zero cross blocks are a caller's model choice, not an independence finding.

Use R_true = Exp([delta_theta]x) R. For y_i = p0_i-R p1_i, the Jacobian is J0=I, J1=-R, J_theta=[R p1_i]x; the body-origin measurement does not directly depend on l. Propagate Q=J Sigma J^T. Sigma may be positive semidefinite (for an explicitly exact rotation/lever model); Q must be positive definite. Reject invalid models instead of flooring eigenvalues.

Estimate the common three-dimensional t_body with full-Q GLS. Freeze the geometry, covariance and GLS weights at the supplied working linearization. Do not refit noise, iterate covariance against residuals or claim a complete nonlinear errors-in-variables likelihood. Preserve the linear map G_body=KJ.

Compute the IMU displacement using the same t_body estimate. Its uncertainty map is G_IMU=G_body+[0, -[R l]x, (R-I)]. Return the joint 6x6 body/IMU displacement covariance, including their cross covariance; do not add an independent rotation correction variance. The model is first-order, conditional on the supplied Sigma, fixed weights, rigid lever and no-slip assumptions. It is not calibrated and does not prove independence from any EKF IMU.

## Observability and validity

Given an explicit full R, one stationary foot supplies three translation components, but has zero residual degrees of freedom: it cannot test slip. With k common feet, residual dimension is 3k-3 under this working model. Differential foot motion can produce a residual; common slip is indistinguishable from translation. No residual acceptance threshold, slip declaration, trusted measurement flag or EKF update is introduced.

Both endpoints and R must be available by the declared decision time. Contact switches, unknown continuity, malformed covariance, invalid SO(3), mismatched intervals/frames or explicitly rank-deficient rotation sources are rejected or returned unavailable as appropriate. Unavailability never becomes a zero displacement measurement.

## Local test budget

At most 25 independent test cases, using synthetic known geometry only. Cover: rigid translation/rotation; nonzero-lever pure rotation; finite-difference position/rotation/lever Jacobians; full correlated covariance and dense GLS oracle; single-foot zero residual degrees of freedom; differential-slip and common-slip counterexamples; contact switch, missing continuity and source availability; FLU/FRD and foot-order changes; invalid covariance and incomplete/invalid rotation; required provenance/lever identities.

Keep persistent pytest logs and source hashes under TRUSTED_HEADING_20261006/FOOT_TRANSLATION. Preserve a first failure and any correction in separate numbered logs. No real measurement accuracy, success probability or calibration claim follows from these tests.
