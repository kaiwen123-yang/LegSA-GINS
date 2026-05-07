# LegSA-GINS Filter Core Design

Stage N4 adds the first self-owned LegSA-GINS C++ filter core.

N4 is not a final_v23 wrapper and does not read final_v23 output. It does not
use trace as solver input, and it does not use receiver internal IMU files as
Go2 body-state IMU.

## Scope

- Implements lightweight math utilities for the C++ runtime.
- Defines the 21-state error-state contract:
  `P / V / PHI / BG / BA / SG / SA`.
- Implements a diagonal covariance foundation.
- Implements simplified IMU propagation foundation.
- Implements receiver-native position, velocity, and heading updates.
- Connects the filter core to `LegSAEngine` through `--dry-filter-demo`.
- Writes `LegSA_NAV.nav`, `LegSA_STD.csv`, `EVAL_NAV.csv`, and
  `RUN_MANIFEST.json` for a toy run.

## Boundaries

- N4 is not final_v23 numerical reproduction.
- N4 does not claim final_v23 parity.
- N4 does not run real BY2 metrics.
- N4 does not make a numerical performance claim.
- N4 does not implement raw Doppler.
- N4 does not implement Go2 yaw-rate or attitude priors.
- N4 does not implement support-foot factors, LSIM/OIM, or source-aware
  weighting.
- N4 does not implement FGO or smoothing.
- N4 does not implement RTK fixed, carrier ambiguity fixing, or self raw
  heading.

N5/N6/N7 may add innovation factors later, but N4 is only the receiver-native
filter foundation.
