# PAPER10Y Current Content Summary

## Closed Evidence

- Main algorithm: `LegSA-GINS / LegSA_full_EKF`.
- Strong baseline: `final_v23_dual_antenna_EKF` as external comparison/sanity, not solver input.
- Short lateral dual-antenna semantic modeling: closed with bounded BY2/BY3 yaw treatment.
- Raw Doppler velocity update: source-backed and active where provider evidence supports it.
- Source-aware LSIM/OIM BY2 120x5 and BY3 120x5: closed as evidence packages.
- Go2 BY2 120x6 and BY3 120x6: closed after R1B.
- Readiness/motion-state LSIM: runtime evidence closed for first-class G03/G05 metadata path.
- DA comparison: formula-level bounded comparison only.
- LC comparison: five high-quality unique papers including OiSAM-FGO, bounded by available reproduction evidence.
- Python3/conda repair and Git context cleanup: completed.

## Still Forbidden

- Universal superiority.
- Complete nine-factor FGO.
- Full contact-aided InEKF or full leg odometry.
- Completed `LegSA_QA_Fallback_EKF`.
- BY3 ordinary yaw generalization.
- Go2 position/yaw as truth.
- External DA/LC author-official exact reproduction unless separately proven.
