# PAPER10G Supervisor Final Report

Final status: `PASS_LEGGED_OBSERVABILITY_DIAGNOSTIC_READY`

1. 前置证据读取：是，已读取/导入 PAPER10B/B_R1/B_R2B、PAPER10C/C_R1B、PAPER10B2/B2_R1、PAPER10Y 的轻量 C export。
2. 代码读取：是，审计 GIEngine、Go2 weak prior、source-aware、QM、dual-yaw update。
3. 主要文献：已找到 Hartley contact-aided InEKF、Barrau/Bonnabel invariant EKF、Bloesch leg kinematics+IMU、Pronto 等 primary sources。
4. 理论不可观测状态：global position/global translation 与绕重力方向 global yaw。
5. global yaw 不可观测原因：绕 gravity 的 yaw 旋转不改变 IMU body-frame residual 或 contact/FK relative residual。
6. global position 不可观测原因：整体平移 body/contact positions 不改变 IMU 或 relative contact residual。
7. Go2 不能替代双天线 yaw：Go2 yaw/yaw_speed 是高层/内部状态或局部积分，保留任意 global offset，不是独立全球航向参考。
8. Go2 可用字段：roll/pitch weak prior、horizontal velocity weak constraint、mode/gait/foot_force/yaw_speed 等 readiness/motion-state metadata。
9. Go2 禁止字段：position as truth、rpy yaw as truth、yaw_speed as absolute yaw。
10. symmetry/gauge demo：已完成，残差在 global translation/yaw offset 下保持数值不变。
11. yaw-rate diagnostic：已完成，显示不同初始 yaw offset 下 yaw-rate integration 同样成立，global yaw offset 不可唯一确定。
12. 诊断结果：Go2 high-level 可作为弱先验/metadata，不能给 absolute yaw/global position。
13. 与短横向双天线语义建模关系：dual-yaw 是打破 yaw gauge 的 absolute heading source，横向安装需要 body-yaw semantic conversion。
14. 与 source-aware/QM 关系：source-aware/QM 管理异质源 reliability/observability，不做 output replacement。
15. 主文可写：legged sensing boundary、Go2 weak prior/metadata role、dual-yaw necessity、QM motivation。
16. 附录可放：literature table、symmetry demo numerical table、Go2 BY2/BY3 field inventory、forbidden claims。
17. forbidden claims：Go2 yaw/position truth、full contact-aided InEKF、full leg odometry、legged-only absolute yaw、BY3 ordinary yaw generalization、universal superiority、trace online、final_v23/LegSA output solver input、complete 9F FGO。
18. 是否建议 PAPER10H：是，建议进入 XB/PG severe boundary + QM state/action 展示。
19. 是否运行大实验：否。
20. trace online：否。
21. Go2 yaw/position truth：否。
22. render QA：见 `15_render_QA/PAPER10G_RENDER_QA_REPORT.md`。
23. Git commit：local commit created after this report package; final HEAD hash is reported in the closing response because a commit cannot embed its own final hash.
24. commit hash：reported in final response.
25. push：false。
26. C export：`<PAPER10G_C_EXPORT_ROOT>`。
27. Obsidian：`<PAPER10G_OBSIDIAN_SYNC_ROOT>`。
