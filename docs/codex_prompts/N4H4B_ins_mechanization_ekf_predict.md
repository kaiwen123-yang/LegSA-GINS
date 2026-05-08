# Codex Prompt: N4H4B INS Mechanization and EKF Predict

Goal:
Implement the LegSA-owned v23-core INS mechanization and EKF prediction
foundation after N4H4A has been merged and tagged.

Allowed:

- Earth and Rotation math utilities.
- IMU compensation.
- INS velocity, position, and attitude propagation.
- `F/G/Phi/Qd` builder.
- `EKFPredict`.
- Covariance checks and STD writer covariance sqrt output.
- `--dry-run-propagation-toy`.

Forbidden:

- GNSS position/velocity/yaw measurement update.
- `EKFUpdate`.
- `stateFeedback`.
- final_v23 output as proposed solver input.
- compiling or copying `reference/final_v23_repo` source.
- raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, FGO, FGO feedback.
- trace solver input, output-only correction, epoch deletion, or performance
  claims.

Validation:

- `python3 scripts/audit_n4h4b_ins_mechanization_predict.py`
- `python3 -m pytest tests`
- `cmake -S cpp -B build/cpp`
- `cmake --build build/cpp`
- `./build/cpp/legsa_v23_core_demo --dry-run-propagation-toy --output-dir <tmp-output>`
