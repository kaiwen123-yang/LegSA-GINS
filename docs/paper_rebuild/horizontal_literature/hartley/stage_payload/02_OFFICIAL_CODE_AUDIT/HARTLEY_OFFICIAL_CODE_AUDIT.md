# Hartley Official-Code Audit

## Audit result

The pinned C++ repository is a valid primary official reference for the **world-centric, right-invariant-error, contact-aided InEKF with Euclidean IMU-bias augmentation and switching point contacts**. It implements the correct group state, invariant forward-kinematic correction, stacked active-contact update, contact augmentation/removal, bias subtraction/random walks, and Joseph covariance correction.

It is **not** an unmodified full IJRR2020 analytical-discretization implementation. The propagation path contains the explicit early-code approximations

```text
Phi = I + A*dt
Qk_hat = (Phi*Adj(X))*Qk*(Phi*Adj(X))^T*dt
```

and its velocity/position mean propagation does not use the IJRR2020 `Gamma1`/`Gamma2` zero-order-hold equations. The correct identity boundary is therefore:

- official pinned C++: `OFFICIAL_CODE_FAITHFUL_EARLY_RSS_BEHAVIOR`;
- later LSE01 core target: `FAITHFUL_IJRR2020_WORLD_CENTRIC_RIEKF_WITH_ANALYTICAL_MEAN_AND_PHI_DISCRETIZATION`;
- no analytical-discretization repair was implemented in H0-H2.

## Frozen source identities

| Source | Frozen identity | License | Status | Role |
|---|---|---|---|---|
| RossHartley/invariant-ekf | `ef16e8a1df72f9272111a488880e3fe9d161f59f` | BSD-3-Clause | detached, clean, no patch | primary official C++ reference |
| UMich-BipedLab/Contact-Aided-Invariant-EKF | `15f1ee79d40cb9af3875f1c4153dd17414a276b2` | BSD-3-Clause | detached, clean, no patch | historical MATLAB/Simulink cross-check |
| unitreerobotics/unitree_ros2 | `668d1ec5a05d1c38d3306bdca7d59f2ba3581a88` | BSD-3-Clause | detached, clean, no patch | supporting Go2 message/index source |

The exact file hashes are in `../00_SOURCE_REGISTRY/OFFICIAL_SOURCE_HASHES.sha256`. None of these repositories is vendored into LegSA-GINS.

## C++ state and Lie-group representation

`RobotState.cpp:22-36` defaults to `X=I_5`, `Theta=0_6`, and `P=I_15`, and grows the covariance using `3*dimX+dimTheta-6`. Accessors at `RobotState.cpp:97-125` fix the group-column order as rotation, velocity, position, followed by appended columns, with the Euclidean order gyro bias then accelerometer bias.

The library supplies:

- `Exp_SO3` in `LieGroup.cpp:31-40`;
- `Exp_SEK3` in `LieGroup.cpp:42-69`, using the SO(3) left Jacobian for every appended vector;
- `Adjoint_SEK3` in `LieGroup.cpp:71-81`, matching IJRR2020 Eq. 7;
- no group `Log` implementation.

The missing `Log` is not a filter-runtime blocker. Any later Log used for gauge diagnostics must be identified as new project code and tested by Exp/Log round trips.

## Propagation equivalence

### Mean

`InEKF.cpp:125-148` subtracts `b_g` and `b_a`, propagates

- `R_{k+1}=R_k Exp((omega-b_g)dt)`;
- `v_{k+1}=v_k+(R_k(a-b_a)+g)dt`;
- `p_{k+1}=p_k+v_k dt+0.5(R_k(a-b_a)+g)dt^2`;

with `g=[0,0,-9.81]` (`InEKF.cpp:43-52`). Orientation is equivalent to the IJRR2020 Eq. 50 `Gamma0` row. Velocity and position are only a frozen-orientation approximation to the Eq. 50 `Gamma1` and `Gamma2` rows when angular rate is nonzero.

### Continuous invariant-error dynamics

`InEKF.cpp:150-163` contains the bias-free gravity-cross and velocity-to-position blocks from IJRR2020 Eqs. 12-14. The bias blocks match Eqs. 27-28:

- orientation versus gyro bias: `-R`;
- velocity versus gyro/accelerometer bias: `-skew(v)R`, `-R`;
- position/contact/appended-vector versus gyro bias: `-skew(x_i)R`.

The mean biases are constant and their random-walk covariances are inserted at `InEKF.cpp:172-173`, matching Eqs. 24-25 at the continuous-model level.

### Process noise

The C++ code inserts gyro, accelerometer, each active contact, gyro-bias, and accelerometer-bias covariance blocks and maps the group part through `Adjoint_SEK3(X)`. This is structurally consistent with IJRR2020 Eq. 28.

One declared limitation is that `Propagate` receives no per-contact kinematic rotation `h_R`. A single global `Qc` is inserted directly. This is equivalent for isotropic contact Brownian noise, or if a covariance is already expressed in the assumed input frame. It is only partial for a general anisotropic covariance specified in the contact frame, for which the paper model requires `h_R Sigma_v h_R^T` before the world mapping.

## Mandatory discretization-gap audit

The gap is exact and source-localized:

- `InEKF.cpp:177`: `Phi = I + A*dt`;
- `InEKF.cpp:181`: approximate `Qk_hat` based on that first-order `Phi`;
- `InEKF.cpp:184`: structurally correct covariance sum using the approximate terms.

IJRR2020 Appendix A instead provides:

- exact zero-order-hold deterministic dynamics through `Gamma0`, `Gamma1`, and `Gamma2` (Eqs. 47-50);
- the covariance solution and noise integral definitions (Eqs. 51-53);
- analytical world-centric right-invariant `Phi` (Eq. 58) and the adjoint/exponential identity (Eq. 60).

An important paper/code nuance must remain visible: IJRR2020 Eq. 61 itself labels `Qd ~= Phi Qbar_k Phi^T dt` an approximation and states that this approximation was used for the article's results. Thus, “full IJRR2020 analytical discretization” unambiguously requires the analytical **mean and state transition**. It must not be silently described as an exact analytical noise integral unless a separately verified implementation of Eq. 52 is added. The faithful article-result policy is Eq. 61 using the analytical `Phi` and an explicitly framed `Qbar_k`.

## Correction equivalence

### Point-contact observation

For every active, already-augmented contact, `InEKF.cpp:421-463` constructs the paper's right-invariant observation:

- translation from `Kinematics.pose(0:2,3)` as `p_bc`;
- `H=[0,0,-I,I,0,0]` in the dynamic state ordering;
- noise `N=R*covariance(3:5,3:5)*R^T`;
- selection matrix `PI` that takes the three translational innovation rows.

This is algebraically equivalent to IJRR2020 Eqs. 15-20 and Eq. 29 when the supplied translation covariance represents `J_p Cov(w_alpha) J_p^T`. The `Kinematics.pose` rotation and orientation-covariance block are unused by the point-position update.

`InEKF.cpp:471-475` performs one stacked correction for all eligible active contacts. `InEKF.cpp:193-220` computes `Z=BigX*Y-b`, applies `exp(delta_X) X`, adds `delta_theta`, and uses the exact Joseph form. The gain is algebraically correct but explicitly forms `S.inverse()`; the later implementation should use a checked factorization/solve without changing the equation.

### Switching-contact lifecycle

Contact indicator values enter through `setContacts` (`InEKF.cpp:100-113`). On the next kinematic event:

1. active + already estimated: include in the stacked correction;
2. active + absent: queue state augmentation;
3. inactive + present: queue state removal;
4. inactive + absent or unknown: skip.

Removal at `InEKF.cpp:477-513` deletes the group column and its three covariance rows/columns, matching Eq. 30. Augmentation at `InEKF.cpp:516-545` sets `d=p+R p_bc` and applies `F P F^T+G Cov(p_bc)G^T`, matching Eqs. 31-32. Multiple removals update all subsequent indices.

## Historical MATLAB/Simulink cross-check

The pinned historical implementation independently confirms the early right-invariant equations:

- state and bias ordering: `RIEKF.m:265-295`;
- bias-corrected mean propagation: `RIEKF.m:367-391`;
- continuous augmented error matrix: `RIEKF.m:394-413`;
- first-order `Fk=I+Fc*dt` and approximate `Qk`: `RIEKF.m:416-429`;
- invariant correction and Joseph covariance: `RIEKF.m:432-451`;
- right/left-foot forward-kinematic updates: `RIEKF.m:455-505`.

It is not a switching-state reference: two foot-position columns remain in `X`, swing feet are reset through FK, and a large swing covariance is injected (`RIEKF.m:380-384,422`).

The exact pinned commit repairs landmark covariance augmentation by changing `G` from `R_pred*Ql` to `R_pred` before the later multiplication `G*Ql*G^T` (`RIEKF.m:598-599`). The same commit comments out automatic absolute-position/yaw alignment in `plot_results.m:125-143`, exposing rather than hiding gauge states.

MATLAB and Octave were not installed in the audit environment. Static audit is complete; execution was optional and is not an H0-H2 blocker.

## Official Unitree native-index support

The pinned `unitree_ros2` source directly defines:

- `foot_force[4]`, `foot_position_body[12]`, and `foot_speed_body[12]` in `SportModeState.msg:13-15`;
- four consecutive XYZ triples at indices `0:2`, `3:5`, `6:8`, and `9:11` in `read_motion_state.cpp:50-76`.

The same official README example reports the four triple geometries in order:

1. positive longitudinal, negative lateral;
2. positive longitudinal, positive lateral;
3. negative longitudinal, negative lateral;
4. negative longitudinal, positive lateral.

Under the platform body convention this is the static source evidence for `[FR, FL, RR, RL]`. This code lane did not inspect BY2 and therefore does **not** freeze the project `GO2_FOOT_ORDER_CONTRACT`: the BY2 lane must still cross-check the existing validated parser and observed side/front geometry, and must stop on disagreement.

## Exact later IJRR2020 implementation plan

No item below is implemented in H0-H2.

1. Add numerically stable `Gamma0`, `Gamma1`, and `Gamma2`, including series expansions near zero.
2. Replace the early velocity/position mean equations with IJRR2020 Eq. 50.
3. build the right-invariant `Phi` from Eq. 58, or independently from Eq. 60, while retaining an internal cross-check between the two constructions.
4. Implement the article-result `Qd` policy as Eq. 61 using the analytical `Phi` and a declared continuous-noise frame. If an exact Eq. 52 integration is later desired, give it a separate named policy and evidence.
5. Preserve the C++ contact-observation and Eq. 30/32 lifecycle semantics, while supporting a per-contact process-noise frame when anisotropic `Sigma_v` is used.
6. Replace explicit innovation-covariance inversion with a checked symmetric factorization.
7. Keep an `OFFICIAL_EARLY_REFERENCE` backend only for source/example regression; never report it as the 2020 backend.

Required tests:

- Gamma functions versus high-precision matrix exponential/integration, including zero and very small angles;
- Eq. 50 versus dense numerical integration over random states, inputs, and `dt`;
- Eq. 58 versus Eq. 60 and numerical variational-equation integration;
- first-order convergence `Phi_analytic = I+A dt+O(dt^2)`;
- Eq. 61 covariance PSD, symmetry, and linear-in-`dt` small-step behavior;
- optional exact-Qd policy versus fine quadrature/Monte Carlo, if authorized;
- invariant-error finite-difference dynamics with and without biases;
- point-contact innovation/Jacobian finite differences;
- one/multiple simultaneous contact additions/removals and covariance/index integrity;
- Joseph posterior PSD under ill-conditioned but valid measurements;
- identity fail-closed tests excluding left-invariant, robo-centric, landmark-aided, and zero-velocity-only substitutions.

## Audit boundary

This audit built and ran only the official external examples. It did not run the BY2 Hartley filter, inspect trace/reference trajectories, execute any EXT method, start EXT06, run HORIZONTAL18, or execute Canonical-541. Official plots and rounded final stdout values are not treated as numerical truth.
