# N4H4C Measurement Models

N4H4C adds conservative loose-coupled measurement blocks for LegSA-v23-core.
All inputs are high-level process-data-compatible `.gnss` fields, not raw GNSS
messages.

## Position

Position residual:

```text
antenna_pos = pos + DRi(pos) * Cbn * antlever
dz_pos = DR(pos) * (antenna_pos - gnss.blh)
```

`H_pos` maps to `P_ID` with an identity block and to `PHI_ID` with
`skew(Cbn * antlever)`. `R_pos` uses `std_n/std_e/std_d` squared. The residual
is predicted antenna position minus observed GNSS position, so state feedback
uses the negative position correction.

## Velocity

Velocity residual:

```text
dz_vel = nav.vel_ned_mps - gnss.vel
```

`H_vel` maps to `V_ID` with an identity block. `R_vel` uses
`std_vn/std_ve/std_vd` squared. Lever-arm velocity correction remains disabled
in N4H4C because the read-only formula audit did not provide enough direct
evidence for a LegSA-owned implementation.

## Yaw

Yaw residual defaults to obs-minus-pred:

```text
dz_yaw = wrap(gnss.yaw_deg - nav.yaw_deg)
```

The formula audit records this as `evidence_missing_default_obs_pred` when the
source sign cannot be confirmed directly. `H_yaw` uses a conservative mapping
to `PHI_ID + 2`, and `R_yaw` uses the effective scheme_C yaw standard deviation
in radians squared.

Yaw comes from status-yaw high-level input, not self raw heading. The gate is a
solver measurement gate only and does not relax any evaluator yaw threshold.
