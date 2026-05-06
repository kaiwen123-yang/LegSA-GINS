# AGENTS.md

## Repository Identity

This repository is LegSA-GINS: Legged State-Augmented Source-Aware GNSS/INS Smoothing.

It is a new clean paper-oriented repository.

Do not treat this repository as LegTC-FGO.

Do not import old LegTC-FGO step-chain code, old result naming, old A0/C8 scripts, or old frozen solver logic.

## Main Research Direction

The future method is:

final_v23-style mature GNSS/INS backbone
+ legged-state augmentation
+ source-aware measurement weighting
+ raw Doppler auxiliary factor
+ no-feedback fixed-lag smoothing
+ reference-uncertainty-aware evaluation.

## final_v23 Rule

final_v23 may be used only as:

1. mature GNSS/INS backbone reference;
2. strong baseline;
3. evaluator sanity oracle.

final_v23 must not be represented as the proposed method.

The proposed method must not read final_v23 output trajectory as solver input.

## Phase-I Forbidden Work

Do not implement or claim:

- RTK fixed;
- carrier ambiguity fixing;
- self raw heading;
- full raw pseudorange tight coupling;
- Neural Gate formal module;
- FGO feedback;
- full pose FGO;
- full leg odometry;
- joint-level leg factor;
- output-only correction;
- trace tuning;
- metric passing by deleting bad epochs.

## Frame Rules

Go2 body / IMU frame is FLU:

- X forward;
- Y left;
- Z up.

GNSS/INS navigation frames must be explicitly managed:

- NED;
- ENU;
- ECEF;
- BLH;
- qbn;
- qeb;
- yaw_math;
- yaw_heading.

Do not mix Go2 body, odom, map, ENU, NED, ECEF, and BLH.

Do not apply a second FLU-to-FRD transform.

Any Go2 data must pass through a frame-safe adapter before being used by estimator, factors, or smoother.

## Data Rules

Never commit raw data or large result files.

Forbidden examples:

- rosbag;
- UBX binary;
- RAWX dump;
- RINEX raw files;
- RTCM streams;
- large CSV logs;
- complete raw NAV logs;
- sensor bags;
- binary datasets.

Only commit:

- code;
- documentation;
- small config files;
- small manifest files;
- small metric summaries;
- paper figures/tables when appropriate.

## Git Rules

Use phase branches:

- stage/N0-bootstrap
- stage/N1-final-v23-wrapper
- stage/N2-frame-writer-evaluator
- stage/N3-legsa-eskf
- stage/N4-raw-doppler-factor
- stage/N5-source-aware-weighting
- stage/N6-no-feedback-smoother
- stage/N7-ablation-evaluation
- stage/N8-paper-package

Do not push directly to main.

Use conventional commit messages, for example:

docs(N0): initialize LegSA-GINS repository governance and structure

## Testing Rules

At minimum, maintain tests for:

- no double FLU-to-FRD transform;
- qbn/qeb convention;
- raw Doppler sign convention;
- no-feedback smoother guard;
- writer complete state history;
- no raw data commit audit;
- claim boundary audit.

In N0, placeholder tests are acceptable.
