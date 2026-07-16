# CLEAN1R2R1 clean-real final_v23 closeout

Terminal status: `PASS_CLEAN1R2R1_CLEAN_FINAL_V23_PARITY_AND_FOUR_METHOD_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW`.

E001 is retained only as `ARCHIVED_SEMISYNTHETIC_DIAGNOSTIC_REFERENCE_ONLY`. Its `nominal_none` label means no additional degradation beyond its base command; that base command still injected seeded 1.5 degree Gaussian yaw noise and read trace during provider generation. No E001 input, output, row, aggregate, or figure entered the current solver or current metric evidence.

The selected clean profile uses real hash-locked BY2 raw, status A1 dual yaw, `yaw_measurement_std_deg=1.5`, no yaw-value noise injection, no trace during input generation or solving, and Go2 body IMU as the sole propagation IMU. The exact runtime contract is `base_time=1772784000`, window `66..340 s`, initialization `[39.98482973,116.34312609,41.80208107] / [0,0,0] / [0,0,0.688505]`, antlever `[0.03,0.03,-0.30] m`, and IMU install `[-1,0,0] deg`.

Fresh input at code freeze `5c807633f699238aa2244a0496881dff71550273` contains 63,277 IMU increments and 303 15-column GNSS rows. Every required raw checkpoint verified 22/22 files with no mismatch, mutation, or symlink escape. The exact `final-v23-freeze@a906c3a2e704eddbd15ceb3f98f1ba8de85dc410` source was freshly built from an attempt-owned 2,270-file hash-verified copy; no archived binary was executed.

Exact versus active parity passed with 56,642 paired rows, exact timestamps and update actions, and exact counters. Active-minus-exact numerical differences were bounded by the pre-output tolerance freeze: horizontal RMSE `8.1342e-05 m`, up RMSE `1.3205e-04 m`, velocity 3D RMSE `6.3621e-05 m/s`, and yaw RMSE `0.0014129 deg`. Strong dual-yaw is therefore the active clean final_v23 implementation anchor.

The final four-method run used one executable, one common input, one window, and one initialization. Counters and direct same-source offline metrics are recorded in `CLEAN1_STATUS.md` and the external final evidence package. LegSA activated 223 Raw Doppler updates, 1,587 source-aware evaluations (1,337 changed weights), 274 Go2 roll/pitch updates, and 274 Go2 horizontal-velocity updates. FGO, QM, QA, and contact/FK remained zero.

Exact archived evaluator crosschecks passed for all current outputs after the four-output seal. Fixposition trace was opened only during this offline evaluation. It is a same-source reference, not independent ground truth. Historical approximate `1.979` and `1.997` yaw values remain quarantined by metric identity and were not gates or tuning targets.

Clean-normal interpretation is deliberately narrow: final_v23 was restored, strong equals the final_v23 implementation contract, all four methods ran under one public contract, proposed LegSA modules truly activated, and no catastrophic normal-condition regression occurred. This stage does not claim universal superiority, degradation robustness, independent-truth accuracy, multi-dataset generalization, or paper-final readiness.
