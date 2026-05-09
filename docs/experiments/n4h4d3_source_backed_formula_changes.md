# N4H4D3 Source-Backed Formula Changes

The default LegSA-v23-core formula contract is:

- `DRi(2,2) = -1` and `DR(2,2) = -1` because NED Down and BLH height have opposite signs.
- GNSS position residual is predicted antenna position minus observed GNSS BLH, mapped through `DR`.
- GNSS position `H_phi` uses `+skew(Cbn * antlever)`.
- EKFUpdate uses `dx = dx + K * (dz - H * dx)` and Joseph-form covariance.
- stateFeedback uses `pos -= DRi(pos) * dx[P]`, `vel -= dx[V]`, positive `dx[PHI]`, and left multiplication `qpn * qbn`.
- IMU bias and scale states use plus feedback, then `dx` is reset to zero.

The D2 yaw H mapping evidence remains secondary and is deferred unless a later
source-backed stage reopens it.

