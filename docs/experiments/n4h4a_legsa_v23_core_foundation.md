# N4H4A LegSA-v23-core Framework Foundation

N4H4A establishes the LegSA-owned `legsa_v23_core` C++ framework foundation.
It is a full-framework skeleton aligned to a KF-GINS-style EKF runtime shape,
not a `final_v23` wrapper and not `final_v23` output substitution.

## Scope

- Add independent C++ types, options, readers, runtime engine, writers, demo,
  audit, and tests under `cpp/legsa_v23_core`.
- Read process_data-compatible 7-column `.imu` increments and 15-column
  final_v23-style `.gnss` high-level state input.
- Preserve BLH(rad, rad, m), NED(m/s), RPY(rad), and yaw(deg at GNSS reader
  boundary) unit contracts.
- Generate `LegSA_V23_NAV.nav`, `LegSA_V23_STD.csv`, `EVAL_NAV.csv`, and
  `RUN_MANIFEST.json` in toy dry-run or skeleton config mode.
- Require Chinese comments near critical C++ functions.

## Boundaries

N4H4A does not implement complete EKF parity, raw Doppler, Go2 priors, LSIM/OIM,
source-aware weighting, FGO, FGO feedback, output-only correction, bad-epoch
deletion, or numerical-performance claims.

`reference/final_v23_repo` remains a controlled reference submodule. Its source
is not compiled into `legsa_v23_core`, and its outputs are not proposed solver
input.

The older N4 toy filter remains diagnostic/foundation code. It is not the final
LegSA-v23 backbone.

## Follow-Up

N4H4B should fill mechanization and EKF prediction math. N4H4C should fill GNSS
update, EKF update, covariance handling, and state feedback math while
preserving the N4H4A input/output and claim-boundary contracts.
