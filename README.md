# LegSA-GINS

Legged State-Augmented Source-Aware GNSS/INS Smoothing.

LegSA-GINS is a clean research repository for a new paper-oriented GNSS/INS fusion framework for high-vibration quadruped robots.

## Project Positioning

This repository is a new project.

It is not a continuation of LegTC-FGO.

LegTC-FGO is treated as a frozen evidence/prototype/failure-boundary project and will be restarted later as a separate paper after new high-quality data collection.

## Backbone

The project uses a final_v23-style mature GNSS/INS backbone as:

- a mature implementation reference;
- a strong baseline;
- an evaluator sanity oracle.

final_v23 is not the proposed method.

## Proposed Direction

LegSA-GINS will be developed as:

- LegSA-ESKF: legged state-augmented source-aware error-state filtering;
- raw Doppler auxiliary factors;
- Go2 yaw-rate and attitude weak priors;
- gait/contact/support integrity features;
- source-aware measurement weighting;
- no-feedback fixed-lag smoothing;
- reference-uncertainty-aware evaluation.

## Phase Status

Current completed phase:

N4E BY2 real-data input adapters and source-role manifest.

Current working phase:

N4F BY2 filter-core diagnostic trial.

N1 only provides the final_v23-style baseline wrapper, manifest writer, oracle audit, and separation tests. It does not implement the proposed LegSA-GINS solver or any numerical performance claim.

N2 builds frame utilities, writer contracts, manifest contracts, evaluator utilities, and audits. N2 does not implement the proposed solver.

N3A adds a C++ runtime skeleton with dry-run NAV/STD/EVAL_NAV output contracts. It does not implement a validated navigation solver, final_v23 reproduction, or any numerical performance claim.

N3B reads external source only for audit and reproduction planning. N3B does not copy external source into LegSA-GINS. N3B does not implement proposed factors or numerical performance evaluation.

N3C creates baseline output parsers/standardizers and a BY2 data source-role contract only. N3C does not implement proposed factors or numerical performance claims.

N3D improves code readability with Chinese comments only. N3D does not implement new algorithms or make performance claims.

N4 implements a toy-run-capable receiver-native position/velocity/heading filter core only. N4 does not implement raw Doppler, Go2 priors, source-aware weighting, or FGO smoothing.

N4E standardizes BY2 receiver-native GNSS status, raw-message summaries, trace evaluation-only reference, and Go2 body-state diagnostic data. N4E does not implement raw Doppler, Go2 priors, source-aware weighting, or FGO.

N4F runs the current filter core on BY2 real data for diagnostic evaluation only. It does not implement raw Doppler, Go2 priors, source-aware weighting, or FGO.

## Strict Phase-I Non-goals

- No RTK fixed claim.
- No carrier ambiguity fixing.
- No self raw heading claim.
- No full raw pseudorange tight coupling claim.
- No Neural Gate formal module.
- No FGO feedback.
- No full pose FGO claim.
- No full leg odometry claim.
- No trace tuning.
- No output-only correction.
- No deletion of bad epochs to pass metrics.
- No final_v23 output substitution.
- No raw data committed to Git.
