# Ideal bias-free observability derivation

## 1. Linear invariant system

For one active contact, the paper's right-invariant error ordering is

`xi = [xi_R, xi_v, xi_p, xi_d]`.

IJRR Eq. 14 gives

```text
xi_R_dot = 0
xi_v_dot = g_x xi_R
xi_p_dot = xi_v
xi_d_dot = 0.
```

Thus

```text
A = [[0,0,0,0],
     [g_x,0,0,0],
     [0,I,0,0],
     [0,0,0,0]].
```

The relative point-contact measurement from IJRR Eq. 20 is

`H = [0, 0, -I, I]`.

## 2. State transition

`A^3 = 0`, so the exponential terminates exactly:

`Phi(t) = I + A t + 1/2 A^2 t^2`.

Expanding yields

```text
Phi(t) = [[I, 0, 0, 0],
          [g_x t, I, 0, 0],
          [1/2 g_x t^2, I t, I, 0],
          [0, 0, 0, I]].
```

## 3. Windowed observability matrix

At sample times `t_j` measured from the window origin,

`H Phi(t_j) = [-1/2 g_x t_j^2, -I t_j, -I, I]`.

Stacking these rows exposes two dependencies.

First, the `p` and `d` blocks always appear as `-I` and `+I`. For any translation `tau`,

```text
H Phi(t_j) [0; 0; tau; tau] = 0
```

for every `j`, producing three independent global-translation gauges.

Second, let `e_g = g/||g||`. Since `g_x e_g = 0`,

```text
H Phi(t_j) [e_g; 0; 0; 0] = 0
```

for every `j`, producing one gravity-axis rotation gauge. In a world frame whose gravity is aligned to its vertical axis, this is yaw.

## 4. Generic rank

The one-contact state has 12 coordinates. Under nonzero gravity and a window containing enough distinct times, roll/pitch contribute rank 2, velocity rank 3, and relative contact-to-body position rank 3. Therefore the generic rank is `2 + 3 + 3 = 8`, leaving nullity `12 - 8 = 4`.

For `N` contact positions, each additional independently represented and observed relative point contributes three columns and three observable relative coordinates. The state dimension becomes `9 + 3N`, rank becomes `5 + 3N`, and nullity remains four.

## 5. Gauge interpretation

The four null directions are symmetry directions, not merely low-information directions:

- Translate `p` and all `d_i` by the same world vector. IMU dynamics and relative kinematics are unchanged.
- Left-rotate `R`, `v`, `p`, and all `d_i` by a constant rotation about gravity. Gravity is unchanged and body-frame IMU/kinematic measurements are unchanged.

No proprioceptive observation in the selected model distinguishes members of either equivalence class.

## 6. What this derivation does not prove

- It does not claim every bias state is observable under arbitrary motion.
- It does not determine numerical conditioning for a particular gait.
- It does not permit stacking across contact-state resizing without a state map.
- It does not apply after an independent absolute heading or position observation is fused.
- It does not use yaw drift or any trajectory error as evidence.

The future BY2 gauge ensemble is a numerical equivariance demonstration of this result, not a replacement for the analytical proof.
