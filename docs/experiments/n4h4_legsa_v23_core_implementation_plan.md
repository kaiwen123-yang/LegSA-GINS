# N4H4 LegSA-v23-core Implementation Plan

N4H4 is implementation stage.

N4H4 must implement a LegSA-owned full EKF / unified filter.

It is not a wrapper.

It is not output substitution.

It must not use final_v23 output as solver input.

It must not use trace as solver input.

It must not make a performance claim before validation.

## Planned Core C++ Modules

- `cpp/legsa_v23_core/config/`
- `cpp/legsa_v23_core/io/`
- `cpp/legsa_v23_core/state/`
- `cpp/legsa_v23_core/mechanization/`
- `cpp/legsa_v23_core/filter/`
- `cpp/legsa_v23_core/updates/`
- `cpp/legsa_v23_core/writers/`
- `cpp/legsa_v23_core/runtime/`

Chinese comments required for all critical functions.

First target: reproduce clean replay baseline with clean `.gnss` / `.imu`.

No factors yet.

No raw Doppler yet.

No Go2 prior yet.

No LSIM/OIM yet.

No FGO yet.

No performance claim.
