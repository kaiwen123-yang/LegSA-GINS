# final_v23 to LegSA-v23-core Transplant Plan

## N4H3 Scope

Do not modify the final_v23 submodule.

Create the future LegSA-owned core under `cpp/legsa_v23_core` or `cpp/src/legsa_v23_core`.

final_v23 is not proposed.

final_v23 outputs must not be used as proposed solver input.

No raw data committed.

No raw Doppler yet.

No Go2 prior yet.

No LSIM/OIM yet.

No FGO yet.

No performance claim.

## Future Port/Refactor Targets

- config reader
- `.gnss` / `.imu` reader
- `addImuData`
- `addGnssData`
- `newImuProcess`
- `isToUpdate`
- `imuInterpolate`
- `imuCompensate`
- `insPropagation`
- `F/G/Phi/Qd`
- `EKFPredict`
- `EKFUpdate`
- `stateFeedback`
- GNSS position update
- GNSS velocity update
- GNSS yaw update
- `scheme_C` yaw gate
- NAV / STD / EVAL_NAV writer

## N4H4 First Goal

N4H4 first goal: v23-framework parity on clean status-yaw replay input.

The first N4H4 implementation target is LegSA-owned framework parity against the clean status-yaw replay input, not a paper performance claim and not a proposed-factor experiment.

## Implementation Rule

Every critical function in the LegSA-owned port must include Chinese comments required for data role, frame convention, update boundary, and provenance notes.
