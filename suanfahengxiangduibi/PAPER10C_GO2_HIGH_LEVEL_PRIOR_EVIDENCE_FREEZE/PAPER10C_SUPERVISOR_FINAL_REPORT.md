# PAPER10C Supervisor Final Report

final_status: CONDITIONAL_PASS_GO2_BY2_CLOSED_BY3_PARTIAL

## Summary

PAPER10C imported PAPER10X/PAPER10A/PAPER10B_R1/PAPER10B_R2B/N7C6 evidence, audited Go2 code and field policy, ran BY2 normal smoke and BY2 120 Go2 ablation for runnable modes, and produced blocked proof for unsupported readiness metadata and missing BY3 Go2 prior provider.

## Key Results

- Go2 roll/pitch weak prior enters EKFUpdate: yes.
- Go2 horizontal velocity weak prior enters EKFUpdate: yes.
- Go2 readiness/contact motion-state as first-class LSIM metadata: no, blocked with proof.
- Go2 position/yaw as truth: no.
- Go2 vertical velocity: disabled/diagnostic only.
- BY2 normal: G00/G01/G02/G04 completed; G03/G05 blocked.
- BY2 120: 720 planned rows; 480 completed-evaluable; 240 blocked-with-proof for readiness modes.
- BY3: not run; required BY3 Go2 prior provider not found; yaw diagnostic-only.
- External DA/LC/GINav/MATLAB/RTKLIB/contact-aided/complete FGO: not run.
- Trace online/final_v23 output/LegSA output/per-case tuning: not used.
- Claim decision: BY2-supported bounded auxiliary weak-prior innovation; not standalone main innovation yet.

## BY2 Method Summary

| dataset | go2_mode | completed_rows | position_rmse_h_mean | position_rmse_h_median | up_rmse_mean | up_rmse_median | roll_rmse_mean | roll_rmse_median | pitch_rmse_mean | pitch_rmse_median | yaw_rmse_mean | yaw_rmse_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | G00_NO_GO2 | 120 | 1.4410323767505917 | 0.8317470530843916 | 1.517179959099703 | 1.0249555515409874 | 1.6145136604685122 | 1.1274904210528218 | 1.9942267808594143 | 1.5985692854307412 | 11.053623865806363 | 2.824758323741648 |
| BY2 | G01_GO2_RP_ONLY | 120 | 1.437855813025 | 0.8315548616117692 | 1.5138980590371187 | 1.0241663218650716 | 1.5876293073893424 | 1.122617645310582 | 1.982559282714242 | 1.59758633813479 | 11.141683258455975 | 2.8029316001790185 |
| BY2 | G02_GO2_HVEL_ONLY | 120 | 1.4407746121014695 | 0.8317220428855929 | 1.5170577126773694 | 1.0249221006095897 | 1.6136823790888395 | 1.1273992749747548 | 1.993709338309048 | 1.598490404719538 | 11.056251833704223 | 2.8245133640433115 |
| BY2 | G04_GO2_RP_HVEL | 120 | 1.4376256955474118 | 0.8315300642766523 | 1.513788583644577 | 1.0241378196147304 | 1.5868763381781672 | 1.1225438915428518 | 1.982095837816989 | 1.597521470775677 | 11.145221702393505 | 2.8029980166952906 |

## Decision

If multi-state quality management remains a claimed contribution, run PAPER10B2 to implement and validate first-class readiness/motion-state LSIM metadata. Otherwise proceed to PAPER10E with Go2 as bounded auxiliary weak-prior evidence.
