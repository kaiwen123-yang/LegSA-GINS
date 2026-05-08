# N4H2C yaw config parity audit prompt

Task:

Plan and then implement a bounded yaw configuration parity audit after N4H2.
N4H2 replay passed the position gate but failed yaw, so the next work should
isolate yaw convention/configuration issues before any full EKF stage.

Scope:

- audit `yaw_sign`;
- audit `yaw_install_offset_deg`;
- audit `yaw_std_mode`;
- audit A1_dual_diff formula;
- audit `yaw_ned = 90 - yaw_body`;
- audit trace yaw convention;
- audit antlever / antenna order evidence;
- verify trace remains evaluation-only;
- verify no formal offset selection is made without physical evidence.

Hard boundaries:

- do not use trace as solver input;
- do not perform output-only correction;
- do not delete epochs for metrics;
- do not tune to final_v23;
- do not implement raw Doppler;
- do not implement Go2 priors;
- do not implement source-aware weighting;
- do not implement LSIM/OIM;
- do not implement FGO;
- do not implement full EKF;
- do not claim formal numerical performance.

Expected first PR:

- planning document;
- audit skeleton;
- test that the skeleton enforces the scope and boundary strings;
- no real generated data committed;
- no local absolute BY2 paths committed.
