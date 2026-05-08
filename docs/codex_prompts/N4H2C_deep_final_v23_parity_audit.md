# N4H2C Deep final_v23 Parity Audit Prompt

Goal:
Audit actual final_v23 runtime input, process_data generation evidence, KF-GINS
runtime velocity/yaw support, and LegSA vs KF-GINS framework parity.

Inputs:

- `ACTUAL_FINAL_V23_CASE_ROOT`
- `N4H2_ARTIFACTS_ROOT`
- `EXTERNAL_KF_GINS_ROOT`

Required runner:

```bash
python3 scripts/experiments/run_final_v23_deep_parity_audit.py \
  --final-v23-case-root "$ACTUAL_FINAL_V23_CASE_ROOT" \
  --n4h2-artifacts-root "$N4H2_ARTIFACTS_ROOT" \
  --external-source-root "$EXTERNAL_KF_GINS_ROOT" \
  --output-dir /tmp/legsa_n4h2c_deep_parity_audit
```

Required boundaries:

- do not merge PR #13
- do not create tag
- do not modify external KF-GINS source
- do not copy external source
- do not commit raw data or generated runtime outputs
- do not commit local absolute paths
- do not implement raw Doppler, Go2 prior, source-aware weighting, LSIM/OIM,
  FGO, or full EKF
- do not use trace as solver input
- do not formal-select yaw offset from trace minimum error
- no formal performance claim
