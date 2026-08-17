# Hartley observability contract

## The theorem-grade claim

For the bias-free, world-centric, right-invariant contact-aided system with only IMU propagation and relative point-contact forward kinematics:

- global translation nullity is three;
- rotation about the gravity vector nullity is one;
- total known gauge nullity is four.

Equivalently, absolute position and gravity-axis yaw are unobservable. A contact point is a relative static feature; it does not supply an absolute origin or north reference.

## Ideal single-contact system

Use error ordering `x = [xi_R; xi_v; xi_p; xi_d]` and

```text
A = [  0    0   0   0
      g_x   0   0   0
       0    I   0   0
       0    0   0   0 ]

H = [ 0  0  -I  I ]
```

Because `A^3 = 0`,

```text
Phi(dt) = exp(A dt)
        = [ I              0      0  0
            g_x dt         I      0  0
            1/2 g_x dt^2   I dt   I  0
            0              0      0  I ].
```

The `j`th block row of a uniformly sampled observability matrix is

`H Phi(j dt) = [-1/2 g_x (j dt)^2, -I (j dt), -I, I]`.

## Known gauge basis

Let `e_g = g / ||g||`. A basis in right-invariant error coordinates is

```text
G_yaw = [e_g; 0; 0; 0]

G_translation(t) = [0; 0; t; t], for t in R^3.
```

For `N` contacts, the translation vector is repeated in `xi_p` and every `xi_di`; the yaw basis remains nonzero only in `xi_R`. The basis must satisfy `A G = 0` and every active-contact row must satisfy `H_i G = 0` to numerical tolerance.

For one contact, the state dimension is 12, the ideal generic rank is 8, and the known nullity is 4. For `N` simultaneously represented and observed contacts, the ideal generic rank is `5 + 3N` out of `9 + 3N`, again leaving four gauge directions.

## Bias augmentation boundary

The paper's ideal observability derivation is bias-free. Bias augmentation creates an imperfect InEKF and additional conditioning interactions; it does not create an absolute north or origin reference. A later numerical bias-augmented study must distinguish:

- exact projections onto the four known gauge directions;
- weakly conditioned but observable directions;
- any additional rank loss caused by insufficient excitation or measurement geometry.

Large yaw error is not an observability proof. The proof is the invariant-system nullspace calculation and, later, numerical projection against the known gauge basis.

## Contact-switching boundary

An observability matrix may be stacked only across a window with constant state dimension and constant contact identity set. At a contact boundary, either end the window or explicitly transport every state/error direction with the paper's augmentation `F` or marginalization `M` map before stacking. Silent zero padding or column matching by position is forbidden.

## Scope limitation

This claim is restricted to the stated proprioceptive sensor set. A valid magnetometer, dual-antenna heading, known absolute landmark, or another independent heading observation can change the nullspace. The result must not be generalized to such systems.
