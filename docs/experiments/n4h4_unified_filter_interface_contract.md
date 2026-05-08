# N4H4 Unified Filter Interface Contract

## Input Contract

- 15-column `.gnss`
- 7-column `.imu`
- config yaml

## Output Contract

- `LegSA_NAV.nav`
- `LegSA_STD.csv`
- `EVAL_NAV.csv`
- `RUN_MANIFEST.json`

## Source Flags

| flag | value |
|---|---|
| `raw_doppler` | `false` |
| `go2_prior` | `false` |
| `lsim_oim` | `false` |
| `fgo` | `false` |
| `trace_solver_input` | `false` |

## Future Extension Points

F1-F9 nine-factor system slots are reserved as extension points only. N4H4 starts with a LegSA-owned v23-framework EKF/unified-filter core before factor stacking.

No raw Doppler yet.

No FGO yet.

No performance claim.
