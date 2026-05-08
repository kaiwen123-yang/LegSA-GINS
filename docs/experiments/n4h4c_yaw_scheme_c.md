# N4H4C Yaw Scheme C

scheme_C is a deterministic yaw measurement gate used by the LegSA-v23-core
GNSS yaw update. It is not a Neural Gate and is not an evaluator relaxation.

Default thresholds:

- `soft_deg = 6.0`
- `hard_deg = 15.0`
- `downweight_scale = 2.5`

Decision table:

| residual | mode | accepted | effective std |
|---|---|---|---|
| `abs(residual) <= soft` | `YAW-NORMAL` | true | `yaw_std` |
| `soft < abs(residual) <= hard` | `YAW-DOWNWEIGHT` | true | `yaw_std * downweight_scale` |
| `abs(residual) > hard` | `YAW-REJECT` | false | not used |

The demo manifest records `yaw_normal_count`, `yaw_downweight_count`, and
`yaw_reject_count`. These counts only prove that the gate branch executed in a
toy update run. They are not performance evidence.

N4H4C keeps raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, FGO, and
FGO feedback disabled.
