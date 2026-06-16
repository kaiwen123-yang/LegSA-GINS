# PAPER10G_R2 Supervisor Final Report

Final status: `CONDITIONAL_PASS_REAL_LSE_COMPLETED_WITH_PROXY_BOUNDARIES`

1. 读取 PDF：2104.04238v1 duplicate pair, 1402.5450v2, 1805.10410v1, 1712.05873v2, out.pdf, 1904.09251v2.
2. 重复 PDF：2104.04238v1 pair identical SHA256; 1805/1904 are one Hartley method family; out.pdf is supporting dissertation material, not independent primary method.
3. 文献身份：Teng slippery InEKF, Rotella humanoid point/flat-foot EKF, Hartley contact-aided InEKF, Hartley/Mangelson/Gan FK+contact factor graph, Hartley extended InEKF, Rotella dissertation support.
4. 输入契约：IMU gyro/acc, contact from foot_force, FK-like `foot_position_body` proxy, foot_speed_body, mode/gait/readiness metadata; no GNSS dual-yaw into LSE methods.
5. Go2 provider：built for BY2 and BY3.
6. raw joint FK：false.
7. foot_position_body proxy：true, explicitly bounded.
8. method fidelity：LSE01/LSE02/LSE04 formula-level faithful with Go2 high-level FK proxy; LSE03 adapted point-foot subset; LSE05 adapted camera-off subset.
9. BY2 results:

| short_method | relative_traj_rmse_m | local_drift_per_meter |
| --- | --- | --- |
| LSE01 | 12.606 | 0.0608658 |
| LSE02 | 12.5935 | 0.0609838 |
| LSE03 | 14.6079 | 0.0569918 |
| LSE04 | 12.6168 | 0.0327829 |
| LSE05 | 12.5989 | 0.0603876 |

10. BY3 results:

| short_method | relative_traj_rmse_m | local_drift_per_meter |
| --- | --- | --- |
| LSE01 | 10.725 | 0.049365 |
| LSE02 | 10.6523 | 0.0491092 |
| LSE03 | 13.278 | 0.0469984 |
| LSE04 | 10.7745 | 0.0493794 |
| LSE05 | 10.8391 | 0.0494845 |

11. blocked methods/branches：LSE03 flat-foot rotational branch; LSE05 tracking-camera branch; official exact modes.
12. blocked reasons：missing raw joint encoder FK, no Go2 flat-foot rotational contact, no tracking camera velocity/angular velocity, no compatible official Go2 adapter.
13. Go2 yaw/position truth：false.
14. absolute yaw：`NOT_APPLICABLE_WITH_PROOF`.
15. LSE replace dual-yaw：false.
16. relation to LegSA-GINS：LSE supports local proprioceptive odometry/attitude/velocity and Go2/QM context; LegSA-GINS still needs GNSS/dual-yaw global anchoring.
17. PAPER10H recommended：true.
18. external DA/LC run：false.
19. trace online：false; trace offline evaluation only.
20. per-case tuning：false.
21. render QA：see `21_render_QA/PAPER10G_R2_RENDER_QA_REPORT.md`.
22. Git commit：complete in local branch; current HEAD hash is reported in the final response because a commit cannot embed its own final hash before it exists.
23. commit hash：see final response for current HEAD; runtime/C export copies record the post-commit hash.
24. push：false.
25. C export：`<PAPER10G_R2_C_EXPORT_ROOT>`.
26. Obsidian：`<PAPER10G_R2_OBSIDIAN_SYNC_ROOT>`.
