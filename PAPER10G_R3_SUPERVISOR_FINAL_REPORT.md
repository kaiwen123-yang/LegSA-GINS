# PAPER10G_R3 Supervisor Final Report

Final status: `CONDITIONAL_PASS_URDF_LOCKED_RAW_JOINT_BLOCKED`.

R3 found and hash-locked the Go2 URDF zip, extracted it runtime-only, parsed the primary URDF, and locked four Go2 leg FK chains. The fidelity upgrade stops at URDF/FK-chain lock because BY2/BY3 raw lowstate motor q/dq data was not found.

## Required Answers

| question | answer |
| --- | --- |
| C1-C9 每条是否已修 | 已生成 claim repair table；C1-C5 blocked/proxy-bounded，C6-C9 forbidden retained |
| 是否找到 Go2_URDF.zip | True |
| Go2_URDF.zip sha256 | 690d6863813cd2854c90e0afef3cc8102e3613c91e8f53e4850b85be916852c5 |
| URDF 是否解压成功 | true |
| URDF 是否解析成功 | True |
| Go2 四条腿 FK 链是否锁定 | True |
| joint name / foot frame 是否锁定 | URDF joint/foot frame locked; lowstate order unconfirmed without raw lowstate |
| 是否找到 raw lowstate/joint q/dq | false |
| 是否构建 raw FK provider | false; RAW_FK_BLOCKED_WITH_PROOF |
| raw FK 与 high-level proxy 差异 | not applicable because raw FK provider blocked |
| LSE01 是否 official adapter | false; official exact blocked |
| LSE02 是否 raw FK | false; raw FK blocked |
| LSE03 是否 raw FK point-foot | false; raw FK blocked; flatfoot N/A |
| LSE04 是否 GTSAM/iSAM2 | false; local GTSAM missing and raw FK blocked |
| LSE05 tracking-camera branch 是否闭合 | false; no tracking-camera/VIO input found |
| absolute yaw 是否仍 N/A | true |
| Go2 yaw/position 是否仍 forbidden | true |
| BY3 yaw 是否仍 diagnostic-only | true |
| 是否运行外部 DA/LC | false |
| 是否 trace online | false |
| 是否 per-case tuning | false |
| 是否建议进入 PAPER10H | true |

## C1-C9 Claim Repair

| claim_id | status | reason |
| --- | --- | --- |
| C1 | BLOCKED_WITH_PROOF | official exact code not run for all methods; Hartley official example is Matlab/Simulink and MATLAB is forbidden; other official adapters not locked |
| C2 | BLOCKED_WITH_PROOF | URDF parsed and FK chains locked, but BY2/BY3 raw lowstate motor q/dq not found |
| C3 | BLOCKED_WITH_PROOF | official code found online but sample/adapter not run; MATLAB forbidden and raw FK blocked |
| C4 | BLOCKED_WITH_PROOF | local GTSAM missing and raw FK blocked |
| C5 | BLOCKED_WITH_PROOF | no tracking-camera/VIO velocity input found |
| C6 | REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT | no global heading reference in LSE inputs; yaw about gravity remains unobservable |
| C7 | REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT | task mismatch: LegSA-GINS is global GNSS/INS PNT with dual-yaw, LSE is local proprioceptive odometry |
| C8 | REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT | Go2 yaw/position are diagnostic-only |
| C9 | REMAINS_FORBIDDEN_BY_PHYSICS_OR_DATA_CONTRACT | BY3 yaw remains diagnostic-only without new ordinary-yaw reference evidence |
