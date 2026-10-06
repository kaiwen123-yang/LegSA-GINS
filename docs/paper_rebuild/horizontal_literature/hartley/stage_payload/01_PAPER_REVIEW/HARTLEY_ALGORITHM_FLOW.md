# Hartley world-centric right-invariant algorithm flow

This flow specifies the future faithful algorithm. It is not an execution record.

## Initialization

1. Create `X_bar = (R_bar, v_bar, p_bar)` with no contact columns.
2. Create `theta_bar = (b_g_bar, b_a_bar)`.
3. Create `P` in ordering `[xi_R, xi_v, xi_p, zeta_g, zeta_a]`.
4. Record the paper-world and body-frame identities. Numeric BY2 transforms remain outside this paper-only flow.

## Event loop

The future BY2 adapter uses the human-frozen ordering that matches the pinned official C++ example semantics. The first message only initializes the previous sample and performs no propagation. For each later timestamped message:

```text
validate monotone time and dimensions
  |
  +-- IMU propagation over dt using the previous IMU and contact set
  |      omega_bar <- omega_tilde - b_g_bar
  |      a_bar     <- a_tilde - b_a_bar
  |      X_bar     <- exact ZOH state step         [IJRR Eq. 50]
  |      Phi       <- analytical transition       [IJRR Eqs. 54-60]
  |      Q_d       <- verified numerical integral [IJRR Eq. 52]
  |      P          <- Phi P Phi^T + Q_d           [IJRR Eq. 51]
  |
  +-- set current force-derived binary contact indicators
  |
  +-- invoke one stacked CorrectKinematics with current foot translations
         1. correct every surviving active contact together [IJRR Eq. 29]
              form and stack H_i, residual, and covariance
              S <- H P H^T + N_bar
              K <- P H^T S^-1
              X_bar <- exp(K_xi residual) X_bar
              theta_bar <- theta_bar + K_zeta residual
              P <- (I-KH)P(I-KH)^T + K N_bar K^T
         2. remove every ended contact                  [IJRR Eq. 30]
              P <- M_i P M_i^T
         3. augment every newly active contact          [IJRR Eqs. 31-32]
              d_i_bar <- p_bar + R_bar h_p_i
              P <- F_i P F_i^T + G_i Sigma_alpha G_i^T
```

This is an adapter tie-break policy, not a claim that the paper prescribes a universal asynchronous order. It is frozen from `src/examples/kinematics.cpp:80-153` and the internal `CorrectKinematics` sequence in `src/InEKF.cpp:382-548` at official commit `ef16e8a1df72f9272111a488880e3fe9d161f59f`. The later adapter must test this exact ordering.

## Multi-contact stacking

For contact set `C = {i_1, ..., i_m}`:

- `H = stack(H_i)` with one `3 x (15+3N)` row block per contact.
- The innovation vector stacks `p_bar + R_bar h_p_i - d_i_bar` in the paper's invariant update convention.
- The paper-direct encoder model yields one transformed covariance block per contact. Cross-leg correlations are not specified; the later adapter must not invent them silently.
- One joint correction is the selected primary operation. Sequential updates are permitted only after a documented algebraic/numerical equivalence test and frozen ordering.

## Numerical requirements for the later implementation

- Stable series branches for `Gamma_0`, `Gamma_1`, `Gamma_2`, `Psi_1`, and `Psi_2` near zero angular rate.
- Rotation normalization that preserves `SO(3)` without changing the mathematical update.
- Symmetric positive-semidefinite covariance checks after propagation, correction, augmentation, and removal.
- Solve `S` without an explicit matrix inverse.
- Preserve contact identities across state resizing.
- Fail closed on a forbidden online field or unresolved frame/foot-order contract.

Two propagation policies are mandatory and must never be conflated:

- `FULL_IJRR_MATHEMATICAL_TARGET` is the selected primary backend: Eq. 50 exact ZOH mean, analytical right-invariant `Phi` from Eqs. 58 or 60, and a separately verified numerical evaluation of the Eq. 52 process-noise integral.
- `PAPER_REPORTED_EQ61_REGRESSION` is the mandatory article-result companion: Eq. 50 mean, analytical `Phi`, and the Eq. 61 approximation. Eq. 61 is never labeled an exact integral.

## Explicit stop line

The seven-yaw gauge ensemble and the real BY2 filter are future operations. Neither is executed by this H0-H2 paper payload.
