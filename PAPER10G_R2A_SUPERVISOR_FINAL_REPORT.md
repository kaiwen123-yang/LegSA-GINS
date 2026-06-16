# PAPER10G_R2A Supervisor Final Report

Final status: `PASS_LSE_METHOD_DISTINCTNESS_REPAIRED_AND_RECOMPUTED`

Distinctness gate: `PASS_LSE_METHOD_DISTINCTNESS_REPAIRED_AND_RECOMPUTED`

## Core Decision

用户怀疑部分成立。PAPER10G_R2 初始实现确实使用了单一 `run_backend(provider, method)` 分发路径，并且 roll/pitch 指标直接来自 Go2 provider 字段，因此 R2 不能继续作为“一篇文献一个独立 backend”的充分证据。PAPER10G_R2A 已触发并完成全量修复重算。

## Required Answers

| question | answer |
| --- | --- |
| 用户怀疑是否成立 | 部分成立：R2 初始 backend 和 roll/pitch metric pipeline 不满足 R2A 方法区分度 gate。 |
| 是否发现 generic backend | 是。R2 使用单一 `run_backend(provider, method)`，D1 gate 触发。 |
| 五个方法是否真实独立 | R2A 修复后是独立 proxy backend；R2 原始版本不是充分独立证据。 |
| 每个方法 backend 文件和函数 | 文件：`scripts/paper10g_r2a_lse_distinctness_audit.py`；函数：`run_lse01_hartley_riekf_proxy`、`run_lse02_qekf_kinematic_proxy`、`run_lse03_rotella_point_foot_proxy`、`run_lse04_fixed_window_factor_proxy`、`run_lse05_teng_velocity_update_proxy`。 |
| 每个方法是否使用 foot_force | LSE01-LSE05 均通过 contact flags / contact_count 间接使用由 foot_force 生成的接触状态。 |
| 每个方法是否使用 foot_position_body | LSE01-LSE04 使用；LSE05 主分支使用 foot_speed_body 和 Go2 velocity proxy，不把 foot_position_body 作为主更新量。 |
| 每个方法是否使用 foot_speed_body | LSE01、LSE02、LSE04、LSE05 主动使用；LSE03 主要使用 point-foot contact anchor，foot_speed_body 不是主更新量。 |
| LSE05 velocity update 是否生效 | 是。禁用 velocity branch 后 BY2/BY3 输出显著改变，velocity_update_count 非零。 |
| LSE04 是否真是 factor graph / smoothing proxy | 是修复后的 fixed-window contact-factor smoothing proxy；不是 full GTSAM/iSAM2 exact reproduction。 |
| roll/pitch/yaw drift 相同原因 | R2 roll/pitch 直接来自 provider，yaw 在 shared loop 中传播；R2A 已改为 method output 指标。relative yaw 仍因无绝对航向源而只能诊断，不能作为 absolute yaw RMSE。 |
| metric 是否来自 method output | R2A 是。R2 中 roll/pitch 不是，已 supersede。 |
| 是否进行了 perturbation test | 是。contact-off、foot-position perturb、foot-speed perturb、LSE05 velocity-disable、LSE04 window-change、LSE01-vs-LSE02 swap 均执行。 |
| 是否短片段重跑 | 是。BY2/BY3 normal、contact-rich、turn/rough 短片段均重跑。 |
| 是否需要 full recompute | 需要。R2A gate 判定 `RECOMPUTE_REQUIRED_FULL` 并已执行。 |
| 如果重算，重算了哪些 | BY2/BY3 x LSE01-LSE05 全部重算。 |
| 重算后 BY2/BY3 结果 | 详见 `16_BY2_BY3_recomputed_comparison/PAPER10G_R2A_RECOMPUTED_METHOD_SUMMARY.csv` 和根目录 `PAPER10G_R2A_RECOMPUTED_RESULTS_SUMMARY.md`。 |
| absolute yaw N/A 是否仍成立 | 成立。所有 LSE 方法未输入 GNSS dual-yaw 或其他 global heading reference。 |
| 是否使用 Go2 yaw/position truth | 否。 |
| 是否 trace online | 否。trace 仅 offline evaluation。 |
| 是否 per-case tuning | 否。 |
| 是否建议进入 PAPER10H | 是，建议进入 XB/PG severe-boundary QM state/action/recovery 诊断。 |
| render QA 是否通过 | 通过；PNG/PDF 成对存在且 nonblank proxy 通过。 |
| Git commit 是否完成 | 待提交后由最终回复报告实际 commit hash；本 tracked 文件不能自包含最终 commit hash 而不产生循环。 |
| commit hash | 提交后见最终回复和 runtime/export QA 后验记录。 |
| push 是否 false | true。 |
| C export 路径 | `<PAPER10G_R2A_C_EXPORT_ROOT>`。 |
| Obsidian 路径 | `<PAPER10G_R2A_OBSIDIAN_SYNC_ROOT>`。 |

## Recomputed Metrics

| dataset | method_id | relative_rmse_m | relative_yaw_drift_deg | roll_rmse_deg | pitch_rmse_deg | velocity_rmse_mps | absolute_yaw_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | LSE01 | 7.744115 | 19.839442 | 1.364323 | 3.317072 | 1.436941 | NOT_APPLICABLE_WITH_PROOF |
| BY2 | LSE02 | 9.642736 | 19.841537 | 1.673101 | 3.276192 | 1.391940 | NOT_APPLICABLE_WITH_PROOF |
| BY2 | LSE03 | 8.920317 | 19.841013 | 1.498992 | 3.284349 | 1.393933 | NOT_APPLICABLE_WITH_PROOF |
| BY2 | LSE04 | 9.228072 | 19.840489 | 2.069610 | 3.284100 | 1.567321 | NOT_APPLICABLE_WITH_PROOF |
| BY2 | LSE05 | 7.897221 | 19.833158 | 1.673101 | 3.276192 | 1.429950 | NOT_APPLICABLE_WITH_PROOF |
| BY3 | LSE01 | 6.817879 | 26.550259 | 1.402884 | 3.245813 | 3.006849 | NOT_APPLICABLE_WITH_PROOF |
| BY3 | LSE02 | 8.947104 | 26.615985 | 1.697035 | 3.138057 | 2.984426 | NOT_APPLICABLE_WITH_PROOF |
| BY3 | LSE03 | 8.184031 | 26.599553 | 1.532115 | 3.179529 | 2.986742 | NOT_APPLICABLE_WITH_PROOF |
| BY3 | LSE04 | 8.498254 | 26.583122 | 2.071616 | 3.079316 | 3.075744 | NOT_APPLICABLE_WITH_PROOF |
| BY3 | LSE05 | 6.983076 | 26.353080 | 1.697035 | 3.138057 | 3.003759 | NOT_APPLICABLE_WITH_PROOF |

## Safety

No DA, LC, GINav, MATLAB, RTKLIB, LegSA final matrix, degradation matrix, or complete FGO was run. No Go2 yaw/position truth, GNSS dual-yaw LSE input, trace online, final_v23/LegSA output solver input, output substitution, bad-epoch deletion, or per-case tuning was used. Figures and full recompute CSVs are runtime/C-export artifacts only and must not be staged.
