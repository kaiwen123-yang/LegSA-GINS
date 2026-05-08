# PHASE_LOG.md

| Phase | Branch | Status | Solver Modified | Large Files Allowed | Main Output | Notes |
|---|---|---|---|---|---|---|
| N0 Bootstrap | stage/N0-bootstrap | done | no | no | repo structure + governance docs | completed |
| N1 final_v23 wrapper | stage/N1-final-v23-wrapper | done | no | no | baseline wrapper | completed; final_v23 not proposed |
| N2 frame/writer/evaluator | stage/N2-frame-writer-evaluator | done | no | no | frame + writer + evaluator | frame/writer/evaluator infrastructure completed as lightweight standard-library utilities |
| N3A C++ runtime backbone | stage/N3A-cpp-runtime-backbone | done | no | no | C++ runtime scaffold | dry-run NAV/STD/EVAL_NAV contracts only; not a validated solver |
| N3B final_v23 / KF-GINS source audit | stage/N3B-final-v23-source-audit | done | no | no | source map + reproduction contract | read-only external source audit; no external source copied |
| N3C final_v23 reproduction connection + BY2 data contract | stage/N3C-final-v23-reproduction-connection | done | no | no | baseline standardizer + path contract | parser/standardizer and data-role contract only; no numerical claim |
| N3D Chinese code comments and readability pass | stage/N3D-chinese-code-comments | done | no | no | Chinese comments + audit | comments/readability only; no logic or output-format change |
| N3 LegSA-ESKF Python skeleton | stage/N3-legsa-eskf | side_branch_not_mainline | yes | no | source-aware ESKF skeleton | not merged into mainline N3A path |
| N4 LegSA-GINS C++ filter core | stage/N4-legsa-filter-core | done | yes | no | C++ filter core toy run | receiver-native position/velocity/heading only; no performance claim |
| N4E BY2 real-data input adapters | stage/N4E-by2-input-adapters | done | no | no | BY2 source-role manifest | input adapters and diagnostic standardization only; no performance claim |
| N4F BY2 filter-core diagnostic trial | stage/N4F-by2-filter-core-trial | done | yes | no | BY2 diagnostic trial report | diagnostic runtime/evaluation only; no formal performance claim |
| N4G BY2 time/IMU/heading diagnostics | stage/N4F-by2-filter-core-trial | done | yes | no | event-normalized candidate reports | diagnostic only; no clock-sync/heading/performance claim |
| N4H0 receiver-native measurement floor sanity | stage/N4H0-measurement-floor-sanity | done | no | no | measurement floor sanity reports | direct receiver status vs trace evaluation-only; no proposed solver performance claim |
| N4H1 final_v23 input source-chain, yaw audit, and process_data-compatible input reconstruction | stage/N4H1-final-v23-input-yaw-audit | done | no | no | final_v23 source-chain + N4H1P/N4H1P2 input reconstruction reports | N4H1P2 row-retention coverage done; diagnostic input/yaw audit and runtime input reconstruction only; no proposed solver implementation |
| N4H2 process_data-compatible KF-GINS replay | stage/N4H2-process-data-replay-evaluation | done | no | no | external KF-GINS replay report | generated process_data-compatible inputs, ran external KF-GINS, parsed NAV/STD/IMU_ERR, evaluation-only trace report; no final_v23 parity or proposed performance claim |
| N4H2C final_v23 deep source and yaw config parity audit | stage/N4H2C-yaw-config-parity-audit | done | no | no | deep input/source/runtime parity audit | N4H2C deep parity audit updated with artifact recovery, process_data runtime-parameter audit, yaw variant matrix, runtime yaw update audit, and replay yaw diagnostics; next recommended stage determined by N4H2C_DECISION_REPORT |
| N4R official final_v23 case-review reproduction and yaw evaluator parity | stage/N4H2C-yaw-config-parity-audit | done | no | no | official evaluator parity report | N4R done on PR #13 if validation passes; next recommended stage determined by N4R_DECISION_REPORT |
| N4R2 yaw evaluator convention policy and dual_final_v23 artifact verification | stage/N4H2C-yaw-config-parity-audit | done | no | no | yaw convention policy + dual verification report | N4R2 done on PR #13 if validation passes; next recommended stage determined by N4R2_DECISION_REPORT |
| N4R3 dual_final_v23 manual artifact intake and official evaluator parity lock | stage/N4H2C-yaw-config-parity-audit | done | no | no | manual dual artifact intake + parity lock | N4R3 done on PR #13; next recommended stage determined by N4R3_DECISION_REPORT |
| N4H2C-runtime yaw update/config/source-version parity audit | stage/N4H2C-runtime-yaw-update-config-audit | done | no | no | runtime yaw path/config/source audit | N4H2C-runtime done; next recommended stage determined by N4H2C_RUNTIME_YAW_DECISION_REPORT |
| N4H full KF-GINS-style EKF reconstruction | stage/N4H-full-kfgins-style-ekf | not_started | yes | no | EKF reconstruction | N4H full KF-GINS-style EKF reconstruction not_started |
| N5 raw Doppler factor | stage/N5-raw-doppler-factor | not_started | yes | no | Doppler factor | sign convention required |
| N6 source-aware weighting / Go2 weak priors | stage/N6-source-aware-weighting | not_started | yes | no | weighting module | no trace tuning |
| N7 no-feedback smoother | stage/N7-no-feedback-smoother | not_started | yes | no | fixed-lag smoother | no feedback |

## N0 Completion Criteria

- Repository structure exists.
- Governance files exist.
- Claim boundary exists.
- .gitignore blocks raw data.
- Placeholder tests exist.
- No raw data or large files committed.
- Git branch stage/N0-bootstrap is ready to push.
