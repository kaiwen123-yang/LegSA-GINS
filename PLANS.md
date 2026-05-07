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
