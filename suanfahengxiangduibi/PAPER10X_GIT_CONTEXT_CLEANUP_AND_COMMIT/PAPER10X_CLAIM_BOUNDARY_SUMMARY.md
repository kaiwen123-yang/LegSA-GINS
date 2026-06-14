# PAPER10X Claim Boundary Summary

## Allowed Claims

- `LegSA_full_EKF` is the verified current main algorithm.
- `final_v23_dual_antenna_EKF` is the strong external Dual-Antenna GNSS/INS EKF baseline.
- Raw Doppler is active in the EKF chain.
- source-aware LSIM/OIM is active through R scaling.
- BY2 source-aware 120 x 5 is complete.
- BY3 source-aware 120 x 5 is complete as poor-heading stress with yaw diagnostic-only.
- DA/LC horizontal comparisons are bounded completed comparisons.
- OiSAM-FGO is included in the LC high-quality unique-paper count.

## Forbidden Claims

- universal source-aware superiority;
- comprehensive outperform-final_v23;
- BY3 ordinary yaw generalization;
- complete nine-factor FGO;
- completed `LegSA_QA_Fallback_EKF`;
- full contact-aided InEKF or full FK leg odometry;
- source-aware equals complete multi-state quality management;
- external DA/LC official exact reproduction unless proven;
- trace online;
- receiver `imu-data.csv` as Go2 body IMU;
- per-case tuning.

## Safe Wording

Use "bounded main innovation" for source-aware LSIM/OIM. Use "position/up generalization and poor-heading stress" for BY3. Use "future candidate" for `LegSA_QA_Fallback_EKF` and complete active FGO. Use "Go2 high-level weak priors" until PAPER10C closes the evidence.
