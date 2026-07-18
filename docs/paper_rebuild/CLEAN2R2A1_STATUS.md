# CLEAN2R2A1 execution status

Terminal status: `PASS_CLEAN2R2A1_BY2_CLEAN_MODULE_ABLATION_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW`.

## Frozen scope

- Dataset and mode: BY2 real clean data only.
- Code freeze: `78b1dc12de91dd0e0f0f4e78d9ece390c0dff091`.
- Provider freeze: `91793894a43c8ba83c25d8da698b7ee16e31b80e`.
- Formal methods: `single_antenna_EKF`, `basic_dual_yaw_EKF`, and `AB0000` through `AB1111` with bit order `RD,SA,RP,HV`.
- Formal execution: 18 unique configurations, 18 terminal passes, zero duplicate effective configurations, and zero technical retries.
- All outputs were hash-sealed before the same-source Fixposition trace was opened by the exact offline evaluator.
- `D01_D60_audit_count=0` and `degradation_run_count=0`. The full degradation matrix remains a separate, unexecuted stage.

## Minimum-sufficient Raw Doppler parity

The historical full-file SHA-256 `a40b9933295f6c2c989884d67cc674313f2fe03113c8acdf1d02ddf28734d722` mixed solver-relevant columns with attempt-specific provenance and is retained as audit-only history, not a cross-attempt gate.

The active fresh Raw Doppler provider has 1,248 rows and 21 columns. Solver-semantic SHA-256 is `235694534abfe2fa15b5469cebbeda220469a0d3da7318fdbbdc39b07548fa33`; current actual full-file SHA-256 is `847d6c0ed6c28c59c661b07d59707faf76c3a5adb2b45fac9802a190b8b00fc4`. The semantic hash includes all numerical values, standard deviations, validity, quality, satellite counts, backend identity, and covariance policy, and excludes exactly `obs_source_hash`, `nav_source_hash`, and `conversion_config_hash`.

A static C++ audit proved that these three fields are used only for lineage equality and never as numerical update inputs. No provider row or value was rewritten, no CLEAN1 provider was copied, and no second fresh attempt or expanded RINEX canonicalization was performed.

The other active provider hashes are:

- IMU: `a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b`
- GNSS: `f4070ba795825cc243402e4acb551c62c6aad109e7040582bf57781226420e22`
- Go2 roll/pitch: `2329770b8e9bc61c02fbf943e2e5fd9ea233d6fd8a3550f7a22410a536155c7a`
- Go2 horizontal velocity: `f390c8e51f1bec1162c0f6c628ebbcd0449923cfbf9211bebb36004dc2b2aab0`

All four raw checkpoints passed 22/22 with zero mutation.

## Clean result boundary

`AB0000` is bit-identical to the current strong/final_v23 anchor, and `AB1111` is bit-identical to `LegSA_Paper_V1`. Full minus strong was harmful for horizontal (`+0.002404 m`), Up (`+0.037889 m`), and 3D (`+0.035834 m`) RMSE, while slightly helpful for roll (`-0.004729 deg`), pitch (`-0.001678 deg`), and yaw (`-0.000072 deg`) RMSE. These mixed results were reported without tuning or metric-driven reruns.

All FGO, multi-state QM, QA fallback, and contact/FK counters were zero. This stage supports only descriptive BY2 clean module effects under a same-source offline reference. It does not establish degradation robustness, universal superiority, independent ground-truth accuracy, BY3/XB generalization, or paper-final readiness.

## Evidence closure

- Evidence-manifest rows: 253.
- Evidence-manifest SHA-256: `10ee04d62a78160ff66aaa8b036f18c50fbf1e1b07e6cd322eea578cdf996a4d`.
- Stage manifest sidecar: PASS.
- Final ZIP entries: 255.
- Final ZIP SHA-256: `1dbdd6cdd1a4c7b6ac13356ea6acb3ef6cc22958469d203a674f099e85e3eed8`.
- ZIP integrity, manifest closure, embedded sidecar, and stage/ZIP manifest identity: PASS.
