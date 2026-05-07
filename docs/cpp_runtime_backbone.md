# C++ Runtime Backbone

Stage N3A creates a C++ runtime skeleton for LegSA-GINS.

The scaffold follows a KF-GINS-style engineering shape: a CMake project, a
single command-line app, an engine class, typed navigation samples, output
writers, a runtime config object, factor registry placeholders, and a run
manifest placeholder.

This is not KF-GINS, not final_v23, and not a final_v23 proposed-method fork.
final_v23 remains a baseline/backbone reference and evaluator sanity oracle.

## Implemented In N3A

- `cpp/apps/legsa_gins.cpp` dry-run executable.
- `LegSAEngine` runtime skeleton.
- `NavState`, `StdState`, `ImuSample`, and `GnssNativeMeasurement` types.
- `RuntimeConfig` defaults and a YAML config skeleton.
- `LegSA_NAV.nav` writer.
- `LegSA_STD.csv` writer.
- `EVAL_NAV.csv` writer bridge.
- Factor registry enable/disable state.
- `RUN_MANIFEST.json` placeholder writer.
- Toy dry-run with two receiver-native measurement rows.
- CMake smoke-build path using only the C++ standard library.

## Explicit Non-Goals

N3A does not implement full INS mechanization, a complete EKF, raw Doppler
factors, Go2 yaw-rate or attitude factors, source-aware weighting, LSIM/OIM,
FGO smoothing, RTK fixed, pseudorange tight coupling, numerical performance
claims, or final_v23 numerical reproduction.

Dry-run files are contract artifacts only. They must not be used as performance
evidence.

## Output Contract

The runtime writes generated artifacts only to the selected output directory.
The repository must not commit raw data, large data, generated NAV files, or
runtime CSV output.

N3A establishes the C++ output-file shape:

- `LegSA_NAV.nav`
- `LegSA_STD.csv`
- `EVAL_NAV.csv`
- `RUN_MANIFEST.json`

## Next Phases

N3B connects the final_v23 reproduction path as a baseline/backbone reference.
It must keep final_v23 separate from the proposed LegSA-GINS runtime.

N4, N5, and N6 are the later stages for innovation factors and smoothing.
Those stages are where raw Doppler, Go2 priors, source-aware weighting, and
no-feedback fixed-lag smoothing can be opened under their own audits.
