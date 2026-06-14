# Dataset Role And Evidence Boundary

## BY2

BY2 is the main full-metric dataset for current paper evidence. It supports controlled degradation, source-aware LSIM/OIM ablation, Raw Doppler and Go2-prior evidence review, and final proposed-method comparison.

Current status:

- main dataset;
- BY2 120 controlled degradation family exists;
- PAPER10B_R1 closed source-aware 120 x 5 ablation;
- safe for bounded main-method source-aware claims after final PAPER10E review.

## BY3

BY3 is an independent same-site repeat dataset used for position/up generalization and poor-heading stress. PAPER10B_R2B closed BY3 source-aware 120 x 5 rows.

Current boundary:

- position/up generalization can be discussed;
- poor-heading stress can be discussed;
- yaw remains diagnostic-only;
- BY3 must not be written as ordinary yaw generalization.

## XB / PG

XB and PG datasets are severe-GNSS boundary and quality-aware motivation evidence. They are useful for explaining why a future `LegSA_QA_Fallback_EKF` may matter.

Allowed wording:

- severe-GNSS boundary;
- fallback behavior motivation;
- future quality-aware branch motivation.

Forbidden wording:

- high-precision poor-GNSS performance;
- broad robustness proof;
- completed QA fallback mainline claim.

## External Comparisons

External DA and LC comparisons are bounded literature-facing comparisons, not official exact reproductions unless official code and exact evaluation are proven. OiSAM-FGO is included in the LC high-quality unique-paper count.

## Trace And Source Data

Trace is evaluation-only. GNSS raw/status and Go2 high-level data are source observations, not truth. Receiver `imu-data.csv` is not Go2 body IMU.
