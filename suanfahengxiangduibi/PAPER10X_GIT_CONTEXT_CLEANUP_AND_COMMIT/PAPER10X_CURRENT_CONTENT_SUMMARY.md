# PAPER10X Current Content Summary

## Current Algorithm And Baselines

Current main algorithm: `LegSA-GINS / LegSA_full_EKF`.

Strong baseline: `final_v23_dual_antenna_EKF`, written as Dual-Antenna GNSS/INS EKF baseline and external reference, not as solver input or hidden target.

Confirmed mainline modules:

- short lateral dual-antenna body-yaw semantic modeling;
- Raw Doppler velocity update;
- source-aware LSIM/OIM R scaling.

Modules that still need evidence freeze before final manuscript wording:

- Go2 roll/pitch weak prior;
- Go2 horizontal velocity weak prior;
- Go2 contact/readiness and candidate-factor evidence;
- selected FGO feedback.

Modules that must not be written as completed:

- `LegSA_QA_Fallback_EKF` full state machine;
- complete nine-factor FGO;
- full contact-aided InEKF or full FK leg odometry.

## Dataset Roles

BY2 is the main full-metric dataset. BY2 controlled degradation and source-aware full ablation are complete for PAPER10B_R1.

BY3 is independent position/up generalization and poor-heading stress. BY3 120 x 5 source-aware rows are complete from PAPER10B_R2B, but yaw remains diagnostic-only.

XB/PG are severe-GNSS boundary and quality-aware motivation datasets, not high-precision performance proof.

## External Comparisons

DA comparison is formula-level faithful or bounded where official exact closure is unavailable.

LC comparison has five high-quality unique papers after adding OiSAM-FGO. GINav remains diagnostic, and the Yin fallback is downgraded.

## Environment And Git

PAPER10B_R2C repaired default `python3` and reinstalled conda without creating a new default environment.

PAPER10X cleans the main repository dirty state by committing only context docs, `.gitignore`, and lightweight PAPER10X reports. Runtime directories remain untracked or ignored.
