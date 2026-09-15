# Hartley Contact-Aided InEKF full method card

## Closed identity

- Comparison identity: `LSE01_HARTLEY_CONTACT_AIDED_INEKF`.
- Algorithm core: `FAITHFUL_ALGORITHM_REPRODUCTION`.
- Declared future BY2 adaptation: `WITH_DECLARED_GO2_HIGH_LEVEL_FK_PROXY`.
- Mathematical authority: Hartley et al., IJRR 2020 / arXiv:1904.09251v2.
- Original-method cross-check: Hartley et al., RSS 2018 / arXiv:1805.10410v1.
- Selected formulation: world-centric state, right-invariant error, contact-aided InEKF, IMU-bias augmentation, and switching point contacts.
- Absolute-yaw metric role: `NOT_APPLICABLE_WITH_OBSERVABILITY_PROOF`.

This identity does not permit substitution of the left-invariant formulation, the robo-centric formulation, a landmark-aided filter, a single permanently fixed foot, a zero-velocity-update-only filter, or an onboard robot state estimate.

## Scientific statement

For the purely proprioceptive IMU + discrete point-contact + forward-kinematic measurement system, global translation and rotation about the gravity vector are unobservable. The ideal bias-free linearized invariant system has a four-dimensional gauge nullspace: three global-translation directions and one gravity-axis rotation direction. The contact measurements add no absolute north reference. This is not the weaker empirical statement that yaw accuracy is poor, and it does not apply after a valid external heading observation is added.

## State and error

With `N` current contacts, the group state is

`X = (R, v, p, d_1, ..., d_N) in SE_{N+2}(3)`

where `R = R_WB` maps body-frame vectors to the paper world frame, `v = ^W v_B`, `p = ^W p_WB`, and each `d_i = ^W p_WC_i`. The Euclidean augmentation is `theta = [b_g; b_a] in R^6`.

The selected error is

`eta^r = X_bar X^{-1}` and `zeta = theta_bar - theta`.

The covariance ordering frozen for the selected method is

`[xi_R, xi_v, xi_p, xi_d1, ..., xi_dN, zeta_g, zeta_a]`,

with three coordinates per block. The covariance dimension is `15 + 3N`.

## Process contract

For each propagation interval:

1. Subtract estimated IMU biases: `omega_bar = omega_tilde - b_g_bar` and `a_bar = a_tilde - b_a_bar`.
2. Propagate orientation with body-frame angular velocity: `R_dot = R (omega_bar - w_g)_x`.
3. Propagate world velocity: `v_dot = R (a_bar - w_a) + g`.
4. Propagate world position: `p_dot = v`.
5. Model every active contact position as fixed in the deterministic system and Brownian in the stochastic system: `d_i_dot = -R h_R_i(alpha_tilde_i) w_v_i`.
6. Model `b_g` and `b_a` as independent Brownian random walks.
7. Propagate the augmented right-invariant covariance using Eq. 28 and the mapped process covariance.

Without bias augmentation, the deterministic right-invariant error dynamics are autonomous and log-linear. With bias augmentation, the filter is the paper's explicitly named imperfect InEKF: the group-affine guarantee no longer holds exactly because bias errors introduce estimate dependence.

## Forward-kinematic contact update

For active contact `i`, the paper measurement is

`h_p_i(alpha_tilde_i) = R^T (d_i - p) + J_p_i w_alpha_i`.

It is a right-invariant observation in the world-centric formulation. Its linearized invariant observation row is

`H_i = [0_R, 0_v, -I_p, 0, ..., +I_di, ..., 0_bg, 0_ba]`.

The paper maps encoder covariance into the invariant residual frame as

`N_bar_i = R_bar J_p_i Cov(w_alpha_i) J_p_i^T R_bar^T`.

All simultaneously active point-contact rows are stacked. Compute `S = H P H^T + N_bar`, `K = P H^T S^{-1}`, correct the group on the left with the `SE_{N+2}(3)` exponential, add the Euclidean bias correction, and use the Joseph covariance equation

`P+ = (I-KH)P(I-KH)^T + K N_bar K^T`.

The high-level Go2 translation proxy is not paper-direct encoder/URDF forward kinematics. The H0-H2 BY2 audit closes its body-frame/foot-order mapping on the exact `REAL_BY2_COMPLETE_RECORD_PREFIX_63277`. The raw source remains incomplete, but the exact prefix is filter-eligible. Translation covariance is frozen by the reference-independent input-only residual policy `FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE`; its `1e-8 m^2` eigenfloor dominates all final per-leg matrices and is not an encoder-precision claim.

## Contact lifecycle

- Add: on a new discrete contact event, initialize `d_new_bar = p_bar + R_bar h_p(alpha_tilde)`. Augment covariance with the right-invariant mapping in Eq. 32, including the shared position uncertainty and transformed kinematic noise.
- Maintain: while the contact is active, retain `d_i` in the group state, drive it with contact-position Brownian noise, and include its right-invariant kinematic update row.
- Remove: on a contact-off event, delete the corresponding contact row/column from the group state and apply the selection marginalization `P_new = M P M^T` from Eq. 30.
- Multi-contact: process all legs independently; the state size changes by three for each added or removed point contact.
- Observability windows: never stack matrices across an add/remove boundary without the explicit augmentation or marginalization map.

The future adapter freezes the official-example-compatible message order: the first message performs no propagation; each later message propagates the previous IMU sample over the elapsed interval using the previous contact set, sets the current force-derived contact indicators, and invokes one stacked `CorrectKinematics`. The pinned C++ routine then corrects surviving active contacts together, removes ended contacts, and augments new contacts, in that order (`src/examples/kinematics.cpp:80-153`; `src/InEKF.cpp:382-548`, commit `ef16e8a1df72f9272111a488880e3fe9d161f59f`). This is a frozen adapter tie-break policy, not a universal event order stated by the paper.

No slip rejection rule is part of the selected primary algorithm. Contact-speed gating or pose/velocity rescue would be a separate extension.

## Analytical discretization target

The full IJRR target is not Euler propagation. Under zero-order-held corrected IMU inputs, use Eq. 50 for exact deterministic state integration with `Gamma_0`, `Gamma_1`, and `Gamma_2`. Use the analytical right-invariant state-transition construction in Eqs. 58 or 60, including the bias-coupling terms and stable small-angle evaluation of `Psi_1` and `Psi_2`.

The paper distinguishes two process-noise levels:

- Eq. 52 defines the exact discrete covariance integral `Q_d` and states that an analytical solution exists.
- Eq. 61 gives `Q_d approximately Phi Q_k Phi^T dt`, and the paper explicitly says this approximation was used for all reported results.

Two named later policies are frozen:

- `FULL_IJRR_MATHEMATICAL_TARGET` is the selected primary backend: Eq. 50 exact ZOH mean, analytical right-invariant `Phi` from Eqs. 58 or 60, and a separately verified numerical evaluation of the Eq. 52 integral. The exact-integral label is permitted only after independent high-accuracy quadrature/ODE or equivalent verification.
- `PAPER_REPORTED_EQ61_REGRESSION` is a mandatory companion because the article says its reported results used Eq. 61: Eq. 50 mean, analytical `Phi`, and the Eq. 61 process-noise approximation. It is not the selected primary mathematical target and must never inherit an exact-integral label.

Neither policy is implemented in H0-H2. The pinned official C++ commit instead uses exact `Exp_SO3` orientation propagation away from its `<1e-10` identity branch, frozen-`R_k` velocity/position integration, `Phi = I + A dt`, and `Qd_hat = (Phi Ad_X) Q (Phi Ad_X)^T dt` (`src/LieGroup.cpp:20-69`; `src/InEKF.cpp:125-184`). It is an official early-code/RSS reference, not an unmodified full-IJRR2020 implementation.

## Alternative formulations reviewed but excluded from the selected identity

- World-centric left-invariant error: Section 10; useful for left-invariant observations but not the selected propagation/update form.
- Robo-centric estimator: Section 11; the world/robo left/right dynamics swap as summarized in Tables 2 and 3.
- Additional landmark, magnetometer, and GPS observations: Section 12 and Tables 2-3; excluded from the purely proprioceptive Hartley comparison.
- QEKF baseline: Section 6; not the selected method.

## Paper parameter boundary

Table 1 values reproduce the paper's simulation/experiment settings only. They are discrete noise standard deviations and initial standard deviations for Cassie. They must not silently replace Go2 IMU noise or input-derived FK/contact uncertainty.

The pinned C++ reference closes its own numeric instantiation: `g=[0,0,-9.81] m/s^2`; constructor standard-deviation inputs are gyro `0.01`, accelerometer `0.1`, gyro-bias `1e-5`, accelerometer-bias `1e-4`, landmark `0.1`, and contact `0.1`; the kinematics example overrides contact noise to `0.01`. The setters square these scalar standard deviations into isotropic covariance matrices. These are `OFFICIAL_CODE` example-reproduction values, not automatically selected BY2 values.

The active project config records ARW `0.985 deg/sqrt(h)` (`2.8652488553573575e-4 rad/sqrt(s)`) and VRW `0.077 m/s/sqrt(h)` (`1.2833333333333334e-3 m/s/sqrt(s)`). Its loader uses `D2R/60` and `1/60`, respectively. The same config records gyro-bias standard deviation `9.38 deg/h` (`4.547552328807448e-5 rad/s`), accelerometer-bias standard deviation `77.8 mGal` (`7.78e-4 m/s^2`), and a one-hour correlation time; loader scales are `D2R/3600`, `1e-5`, and `*3600`. Those bias values define Gauss-Markov state standard deviations/correlation time in the existing GNSS/INS model, not Hartley bias random-walk densities, and cannot be frozen as such. Measurement/Allan provenance is absent from active allowlisted material, so even the ARW/VRW values remain provenance-unverified and are not silently proposed for the future Hartley BY2 process model.

The separate input-only audit closes the configured sensor-to-body direction, body/world reporting transforms, `FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY`, and the robust FK-proxy covariance on the 63,277-record complete prefix. The immutable source has 63,278 timestamp starts and ends with `foot_speed_body[4/12]`; the full 1,278-byte trailing record is retained in evidence and excluded whole without imputation or interpolation. `raw_source_complete=false`, `complete_record_prefix_filter_eligible=true`, and foot speed is `DIAGNOSTIC_ONLY` and online-disallowed.

## H0-H2 stop line

This material freezes a future implementation contract. It contains no real BY2 Hartley run, no trace/reference evaluation, no gauge-ensemble execution, and no absolute-yaw score. Official-code build/example evidence is maintained separately in this H0-H2 payload and does not constitute a BY2 filter run.
