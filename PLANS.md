# PLANS.md

## Stage N0: Bootstrap

Goal:
Create clean repository structure, governance files, phase log, claim boundary, Git ignore rules, and placeholder tests.

No algorithm implementation.

## Stage N1: final_v23-style baseline wrapper

Goal:
Add final_v23-style baseline wrapper as strong baseline and evaluator oracle.

final_v23 is not proposed.

N1 only creates baseline wrapper, manifest, oracle audit, and separation tests.

No numerical claim is allowed before real final_v23 output is connected.

Completion note:
N1 is complete as a wrapper, manifest writer, oracle audit, and separation-test stage only. It does not implement the proposed LegSA-GINS solver or any numerical performance claim.

## Stage N2: Frame / Writer / Evaluator Infrastructure

Goal:
Implement frame adapters, writer contracts, evaluator contracts, and manifest schemas.

N2 builds frame utilities, writer contracts, manifest contracts, evaluator utilities, and audits.

N2 does not implement LegSA-ESKF or algorithmic factors.

Hard gates:
- no double FLU-to-FRD transform;
- Go2 body/odom/map separation;
- NED/ENU/ECEF/BLH clarity;
- complete state history writer.

## Stage N3A: C++ Runtime Backbone

Status:
completed.

Goal:
Create the standard-library C++ runtime scaffold, executable entrypoint,
engine shell, state types, writer contracts, config skeleton, factor registry
placeholder, run manifest placeholder, dry-run demo, and CMake smoke path.

N3A does not implement mechanization, EKF filtering, innovation factors,
smoothing, final_v23 numerical reproduction, or numerical performance claims.

## Stage N3B: final_v23 / KF-GINS Source Audit and Reproduction Contract

Goal:
Read-only audit of /home/kaiwen/KF-GINS and define N3C reproduction contract.

No algorithm implementation.

## Stage N3C: final_v23-style Reproduction Connection and BY2 Data Contract

Goal:
Connect final_v23/KF-GINS baseline outputs to LegSA-GINS standardized baseline outputs, and define BY2 source-role/path contract.

No proposed solver implementation.

## Stage N3D: Chinese Code Comments and Readability Pass

Goal:
Add Chinese comments to code modules, clarify module responsibility, data roles, frame conventions, and claim boundaries.

No algorithm implementation.

## Stage N3: LegSA-ESKF

Goal:
Implement a legged state-augmented source-aware error-state filter.

## Stage N4: LegSA-GINS C++ Filter Core

Goal:
Implement the first self-owned LegSA-GINS filter core with IMU propagation foundation and receiver-native position/velocity/heading updates.

No raw Doppler, no Go2 priors, no source-aware weighting, no FGO.

## Stage N4E: BY2 Real-Data Input Adapters

Goal:
Create real-data input adapters and source-role manifests for BY2, including receiver-native GNSS status, raw message summaries, trace reference, and Go2 body-state diagnostic source.

No solver performance evaluation.

## Stage N4F: BY2 Filter-Core Diagnostic Trial

Goal:
Run current LegSA-GINS filter core on BY2 real data and generate case_review-style diagnostic evaluation.

No formal performance claim.

## Stage N4G: BY2 Time-Domain and Heading Diagnostics

Goal:
Audit BY2 GNSS/Go2 time-domain usage, Unitree sportmodestate IMU semantics, event-normalized algorithm time, and transverse dual-antenna heading offset candidates.

No physical clock offset claim. No formal heading offset selection. No raw Doppler, Go2 priors, source-aware weighting, LSIM/OIM, or FGO.

## Stage N4H0: Receiver-Native Measurement Floor and Evaluator Sanity

Goal:
Evaluate direct receiver-native GNSS status against trace reference to distinguish input/evaluator issues from filter-core issues.

No proposed solver implementation.

## Stage N4H1: final_v23 Input Source-Chain and Yaw-Generation Audit

Goal:
Audit the two-layer final_v23 input source chain: runtime 15-column .gnss input and upstream generation fields, including gnss1-status position, gnss1-raw UBX-NAV-PVT velocity, and gnss1/gnss2-status A1_dual_diff yaw.

N4H1P:
Add a process_data-compatible input generator that reconstructs final_v23-style
`.gnss` and `.imu` runtime inputs from BY2 upstream fields for baseline/parity
testing only.

N4H1P2:
Match process_data row-retention behavior by keeping `gnss1-status` as the
`.gnss` main table, treating PVT velocity and status yaw as merge-asof
auxiliary fields, applying fill, and reporting coverage.

## Stage N4H2: process_data-Compatible External KF-GINS Replay

Goal:
Use the N4H1P2 real BY2 `.gnss` / `.imu` reconstruction as runtime input for an
external KF-GINS baseline replay, then parse and evaluate outputs.

No proposed solver implementation. No final_v23 parity claim. No trace as
solver input. No generated real-data artifacts committed.

## Stage N4H2C: final_v23 Deep Source and Yaw Config Parity Audit

Goal:
Audit why N4H2 position replay passed while yaw replay failed. Deep audit of
actual final_v23 `input.gnss`, `process_data.py`, run scripts, GNSS loader,
GIEngine yaw/velocity update support, and LegSA vs KF-GINS framework parity.
The yaw-specific checks include `yaw_sign`, `yaw_install_offset_deg`,
`yaw_std_mode`, A1 dual-difference yaw, `yaw_ned = 90 - yaw_body`, trace yaw
convention, and antlever / antenna order.

N4H2C-2 deepens this with actual final_v23 artifact recovery, process_data
runtime-parameter audit, yaw input variant matrix, runtime yaw update audit, and
replay yaw diagnostics.

No full EKF implementation. No trace solver input. No output-only correction.
No formal offset selection without physical antenna-order evidence.

## Stage N4R: official final_v23 Case-Review Reproduction

Goal:
Reproduce official final_v23 case_review metrics and identify yaw evaluator
convention before full framework transplant or factor stacking.

N4R uses actual official artifacts as runtime-only evaluator evidence. It does
not implement proposed solver logic, does not tune yaw, does not use trace as
solver input, and does not make a formal numerical performance claim.

## Stage N4R2: Yaw Evaluator Convention Policy and dual_final_v23 Verification

Goal:
Add a controlled evaluator yaw convention policy and verify the N4R candidate
against dual_final_v23 artifacts before any formal evaluator patch.

N4R2 performs directed dual_final_v23 artifact recovery, dual evaluator parity,
and N4H2 replay profile re-evaluation. It does not modify solver output, does
not relax the yaw gate, does not use trace as solver input, and does not make a
formal numerical performance claim.

## Stage N4R3: dual_final_v23 Manual Artifact Intake and Official Parity Lock

Goal:
Validate a manually provided dual_final_v23 artifact group outside the
repository and lock the official evaluator profile against its official summary
and error_series.

N4R3 does not commit artifact files, does not modify solver output, does not use
trace as solver input, and does not turn near-gate yaw evidence into a formal
pass.

## Stage N4H2C-runtime: Runtime Yaw Update / Config / Source-Version Parity Audit

Goal:
Audit why actual dual_final_v23 yaw passes under the confirmed direct evaluator
profile while N4H2 replay yaw fails under the same formal evaluator.

N4H2C-runtime compares actual and replay input/NAV yaw paths, recovers runtime
config evidence when available, audits current KF-GINS yaw update logic
read-only, and searches yaw update source history for branch/version mismatch
evidence. It is diagnostic only: no solver output modification, no trace solver
input, no yaw-gate relaxation, and no formal performance claim.

## Stage N4H2D: Replay Reference Mapping and Stale Summary Audit

Goal:
Audit why the old N4H2 replay summary reported yaw near 93 deg even though
actual dual_final_v23 NAV and replay NAV are nearly identical.

N4H2D reconstructs the official dual_final_v23 reference from official NAV plus
official error_series, freshly evaluates replay NAV against that reference, and
compares the old summary to the fresh summary. It is evaluation/reference
mapping only: no solver output modification, no trace solver input, no output
correction, no epoch deletion, and no formal proposed solver performance claim.

## Stage N4H2E: dual_final_v23-only Visual Validation

Goal:
Generate a dual_final_v23-only visual validation bundle for fresh replay parity
before treating the numerical result as ready for the next stage.

N4H2E plots trajectory, position error, velocity, attitude, consistency,
observation quality, and summary panels for manual review. It does not draw pure
INS, single-antenna, or multi-line comparison figures; does not modify solver
output; does not commit generated figures; and does not make a formal
performance claim.

## Stage N4H2F: Startup transient and yaw/noise provenance audit

Goal:
Audit the visible startup transient, yaw observation-STD source, and
process_data yaw-noise provenance before PR #15 is considered ready for human
visual review and any N4H3 transition.

N4H2F distinguishes fixed yaw_std observation columns from actual yaw-value
noise injection, treats run_final_mainline degradation batches as provenance
evidence rather than clean nominal proof, and records whether final_v23 nominal
evidence needs a yaw-noise caveat. It does not modify solver output, crop
startup epochs, relax the yaw gate, or make a formal performance claim.

## Stage N5: Raw Doppler Factor

Goal:
Implement raw Doppler auxiliary residual and sign/unit tests.

## Stage N6: Source-Aware Weighting

Goal:
Implement source-aware measurement weighting using GNSS status, Doppler residual, Go2 body-state, and support integrity cues.

## Stage N7: No-Feedback Fixed-Lag Smoother

Goal:
Implement fixed-lag smoothing without feedback to the filter.

## Stage N8: Ablation and Degraded-GNSS Evaluation

Goal:
Run proposed vs pure INS, single-antenna GNSS/INS, final_v23-style baseline, and ablations.

## Stage N9: Paper Package

Goal:
Generate paper-ready figures, tables, manifests, and claim-audit reports.
