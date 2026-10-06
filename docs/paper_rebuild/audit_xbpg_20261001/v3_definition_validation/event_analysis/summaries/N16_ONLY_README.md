# N16_ONLY：C00/F04 与 D15_seed_00/F04 的实际事件结果

N16 两个候选事件流均完成一次全读；两份旧基线复用已有完整缓存，本项旧基线 payload 打开数为 0。两组最早都在首个 HV 更新改变实际 R，随后共同 IMU 43 的末状态分叉；所有配对槽的实际接受状态均保持相同。C00 的 HV 实际 R 有 1369 次差异，D15 为 230 次。D15 的 230 次是新旧闭环的差异，不能当作原同状态影子 40 次之外的 190 次“独立净效应”。

范围仅为 `N16_ONLY/RUN_00004`（BY2 C00/F04，`real_clean`）与 `N16_ONLY/RUN_01401`（BY2 D15_seed_00/F04，`semisynthetic`）。两者 `synthetic_data_used=false`；只有 D15 的 `semisynthetic_data_used=true`。原算法及原 V3 结果保持原身份，本说明不决定候选采用，也不报告新的精度指标。

## 实际维度与保留的原字段

定义见 [V3_DEFINITION_DECISIONS.md](../../V3_DEFINITION_DECISIONS.md) §2.2 与 [候选实现说明](../../candidates/N16_ONLY/README.md)。本候选仅改变 std 质量域：实际 `horizontal_2d` 的 HV 使用 `std_active_axes=[true,true,false]`；maxStd/finiteStd 只检查 active 轴，999 原值保留。其他质量条件、OIM、cap、raw dz 决策创新和调度均沿用原实现，没有同时接入 N12/N09。

从完整 measurement comparison 中逐行核对，两组各 1369 个实际 HV 更新均具有：

|字段|旧观察版|N16 候选|
|---|---|---|
|std_xyz|`[0.132838,0.132838,999]`|`[0.132838,0.132838,999]`|
|实际 R 维数|2×2|2×2|
|std_active_axes 日志|`NOT_RECORDED`|`[true,true,false]`|
|quality_flag|`clean_raw_go2_weak_auxiliary`|`clean_raw_go2_weak_auxiliary`|
|实际 LSIM_R_scale|2|1.5|

旧日志未保存 mask；其三维 maxStd/finiteStd 行为由冻结源码确定，不能把未记录字段填成一份旧实测 mask。候选其余来源的全部 SA 记录均显式为 `[true,true,true]`。LSIM 降至 1.5 而不是 1，是因为保留了原 `lsim_quality_flag_suspicious` 条件；只取消禁用 D 轴的 std-high 贡献。真实日志中的 D 仍是 999，没有写零或变成垂向观测。inactive NaN/Inf 与三维分支的契约测试属于此前独立合成 fixture，本项不把它们转作真实数据事件。

## 全读、同快照核算与实际接受

|对象|本项新读候选行数|候选实际 SA 全部核对|复用旧基线 SA|候选实际更新数|
|---|---:|---:|---:|---:|
|C00/F04|465209|7932/7932|7932|7932|
|D15_seed_00/F04|465201|7930/7930|7930|7930|

两候选合计新读 930410 行、1893327948 字节；各打开/完整读取 1 次，部分读取、失败、重试均为 0。15,862 个候选 SA 事件的 raw-dz NIS、conditional-nu 诊断值、归一化和 effective_R 传播按固定容差核算通过；N16 的实际 policy 仍用 raw dz，并未采用条件创新候选。旧基线的完整核算结果来自已封存缓存，没有重新读取旧 JSONL。`SA_EVALUATION_BEGIN` 不重复计入 SA 次数。

完整性门包括 BEGIN/END、连续 event_seq、EOF、同次读取的全文件 SHA 及前后文件元数据。NIS 容差保持 `1e-9 + 1e-8×|recorded|`，R/倍率保持 `1e-10 + 1e-10×|recorded|`。比较及下述统计只读 cache/既有 comparison CSV；本项新 native/evaluator/provider 调用均为 0，未读 provider/raw/reference/NAV/STD。原候选执行调用仍在其独立运行回执中，不因本分析的调用数为 0 而省略。

两组各 8214 个稳定配对槽，无新增、缺失或重复歧义键；每来源 1369 槽。实际接受由 decision、完成的 EKF_AFTER 与更新计数关联，不能仅凭 SA policy accepted 断言更新发生。

|来源|C00 原版→候选接受|D15 原版→候选接受|C00 实际 R 精确差/超容差|D15 实际 R 精确差/超容差|
|---|---:|---:|---:|---:|
|receiver_position|1369→1369|1369→1369|205/39|1275/1272|
|dual_antenna_yaw|1348→1348|1346→1346|105/100|151/148|
|receiver_velocity|1369→1369|1369→1369|391/391|22/22|
|raw_doppler_velocity|1108→1108|1108→1108|462/461|76/76|
|go2_horizontal_velocity|1369→1369|1369→1369|1369/1369|230/230|
|go2_attitude_roll_pitch|1369→1369|1369→1369|0/0|11/11|

逐槽 2×2 核对也没有相互抵消的接受翻转：C00 双方接受/双方未接受/原接受→候选拒绝/原拒绝→候选接受 = `7932/282/0/0`；D15 = `7930/284/0/0`。yaw reject 为 C00 `21→21`、D15 `23→23`；原 GNSS/position/RV/RD/RP/HV 末计数两侧均为 `1369/1369/1369/1108/1369/1369`。

固定查询子窗 `[196.2,216.2)` 中六来源均为双方接受 100 次。此处是 attempt 记录的事件时轴查询；C00 无注入窗，D15 为全序列位置噪声，不能将它另称两组的故障窗，也不能等同 provider 文件行数。

## 闭环差异次数与首个更新

R 只采用 `EKF_BEFORE.R`。以下矩阵/增量差异均在双方实际更新的共同槽内比较，精确差与固定 R 容差分开；拒绝槽没有补零矩阵。

|量|C00|D15|
|---|---:|---:|
|双侧实际 EKF 更新|7932|7930|
|实际 R 精确不同|2532|1765|
|其中超过固定 R 容差|2360|1759|
|精确不同但在 R 容差内|172|6|
|actual_delta 精确不同|7928|7926|
|累计 dx_after 精确不同|7928|7926|
|进入本次更新的 dx_before 精确不同|6559|6557|
|实际 EKF innovation 精确不同|7927|7925|
|匹配更新前名义状态不同|7926|7924|
|接受状态/EKF 是否发生的变化|0/0|0/0|
|共同 IMU 末状态完全相同/不同|42/56600|42/56600|

每组共同 IMU 共 56642 个。全文核对 `IMU_STATE_COMPARISON.csv` 后，原标签 `DIFFERENT_OR_UNRESOLVED` 的 56600 行均为真实数值不同，无法解析/非有限状态行 0、状态时刻错配 0；没有用全局 event_seq 硬拼或插值。

两组首个实际 R 差异键均为 `[1,"go2_horizontal_velocity",66.200000048]`。这里第三项来自 `MEASUREMENT_ATTEMPT` 的 measurement_time；实际选中 HV provider 的 `metadata.time=66.19904589653`，首共同 IMU 末时刻为 `66.199046`。GNSS 事件、provider 测量及 IMU 状态三个时间字段分别保留；实际 available/arrival time 仍未知，nearest/tolerance 匹配不能证明实时可得。

首个 HV 更新两侧均接受，raw dz-NIS 在同组两侧相同，OIM 也相同：

|量|C00|D15|
|---|---:|---:|
|raw dz-NIS，两侧|25.198662026785208|25.198662026785208|
|conditional nu-NIS，两侧诊断|4.848996806519777|4.846628660606402|
|OIM_R_scale，两侧|1.1512241238161658|1.1512241238161658|
|LSIM/combined，旧→候选|2→1.5|2→1.5|
|source cap，两侧|10|10|
|base_R 的两个对角，两侧|0.017645934244000003|0.017645934244000003|
|实际 R 对角，旧→候选|0.035291868488000006→0.026468901366000004|0.035291868488000006→0.026468901366000004|

R 单位为 `(m/s)^2`，非对角均为 0，每个对角候选减原版为 `-0.008822967122000001`。这次原 OIM 低于 1.5，因此保留的其他 LSIM 条件决定候选最终倍率，没有被 cap 遮蔽。实际 R 来源为原版 EKF_BEFORE event 300、候选 event 343；对应 SA 为 299/342，EKF_AFTER 为 301/344。必须同时使用 run_id 与源路径。

同次 HV 更新的 `actual_delta` 是误差状态更新增量。速度误差三维增量的候选减原版为：

- C00：`[-0.0029700910355740257,-0.017740952409057847,2.4522772923649234e-06] m/s`。
- D15：`[-0.00296712016808069,-0.01773699571504457,2.4515627044256347e-06] m/s`。

二维 HV 更新仍可经既有协方差产生其他状态分量的更新；这不等于添加了 D 维测量。完整 21 维增量原值、dx_before/after、差向量与字节定位保存在两组 `FIRST_DIFFERENCES.json`，没有把混合单位的最大分量称为单一物理误差。

两组首共同 IMU 末分叉均为 `imu_seq=43,time=66.199046`；两侧各传播 1 次、拆分 0 次、反馈 1 次。末状态都来自 FEEDBACK_AFTER（原版 event 312、候选 event 355）。候选减原版为：

|量|C00|D15|
|---|---|---|
|速度 N/E/D，m/s|`[0.002972077016295205,0.017722011597217854,-1.2042270445544734e-06]`|`[0.002969109363161082,0.017718058977829458,-1.2038761650623453e-06]`|
|roll/pitch/yaw，rad|`[2.8677160328685614e-05,-4.188354794713162e-06,-2.6054514880691215e-05]`|`[2.867074332359512e-05,-4.183595513604409e-06,-2.605699055902022e-05]`|
|纬/经/高，rad/rad/m|`[-3.4872105203476167e-13,-1.5898393712632242e-12,1.0052306507191133e-06]`|`[-3.483879851273741e-13,-1.5893952820533741e-12,1.0048926526451396e-06]`|

这些是两条实际执行的状态差，不是相对 reference 的误差或改善。

## D15 的旧同状态负对照仍然成立

旧 [C00 INNOVATION_COMPACT](../../../v3_mechanism/groups/C00/INNOVATION_COMPACT.csv) 与 [D15 INNOVATION_COMPACT](../../../v3_mechanism/groups/D15/INNOVATION_COMPACT.csv) 的 F04/HV 行保留原状态：只在每个旧快照中移除 D 对 maxStd 的贡献、保持旧 OIM/cap、不向后反馈。两组各 1369 次 LSIM 由 2→1.5；C00 1369 次最终影子 R 不同，D15 只有 40 次不同、1329 次被 OIM/cap 遮蔽。原行中的 `actual_R_mutated=False`、`closedloop_not_tested=True` 不被本轮新事实改写；来源原行也抄录在本项读取回执。

旧 [D15 KEY_EVENT_VALUES](../../../v3_mechanism/groups/D15/KEY_EVENT_VALUES.csv) 的 event 595/907 是已预定的来源对照。本项从既有完整比较表取同键实际记录，另保存在 D15 `FIRST_DIFFERENCES.json`，没有为挑选例子重扫事件。

|旧 SA event / 配对键|旧同状态 N16 影子|新实际闭环配对|
|---|---|---|
|595；`[2,go2_horizontal_velocity,66.400000095]`，provider 66.397070884705|旧 OIM=1.0000751203265812，LSIM 2→1.5，最终 R 对角 .035291868488000006→.026468901366000004|候选 SA event679；raw-NIS 已从旧4.805248578488749变为4.304023520285398，候选OIM=1，最终R同样为.026468901366000004，但两侧已不是同一状态|
|907；`[3,go2_horizontal_velocity,66.599999905]`，provider 66.603052139282|LSIM 2→1.5，但 OIM/cap=10，最终 R 对角两者均.17645934244000003|候选 SA event1034；raw-NIS旧732.5602562985654、候选654.5029248427431，OIM均10，实际R也均.17645934244000003|

event907 在两类证据中都展示最终 R 遮蔽；新实际配对的 R 相同也不意味着 actual_delta 或状态相同。旧同状态的 40 次与新闭环的 230 次 HV R 变化不能直接相减、相加或互换。首个不同更新之后，H/P/dx/名义状态参与后续不同的 raw-NIS/OIM；position、yaw、RV、RD、RP 的 R 差异也属于这一实际闭环传播，不能称为 active-axis 接口直接改了这些来源的 std 域。本项始终没有把 N12 与 N16 的单独效果相加。

## P 覆盖和数值边界

两候选每组 56642 个已初始化 IMU 末 P 报告均为 `NONPOSITIVE_DIAGONAL`。本项对两份新 cache 的全部 covariance/report 做只读 SQL 分组，各只有一种模式：441 项全部有限、非正对角索引 `[15,16,17,18,19,20]`、min_diagonal=0。不是从首异常外推。旧基线 C00 的15864、D15的15860个 EKF_BEFORE/AFTER 完整 P 核对与全记录模式查询复用上项证据，不重新扫描旧流。

这些六维是 gyro/acc scale，原七配置的初值与过程噪声 std 均为零，见 [P_MODEL_BOUNDARY.md](../../P_MODEL_BOUNDARY.md)。固定诊断未放宽：正对角门不满足，归一化、对称检验、Cholesky均为 NOT_TESTED，相关最大非对称/最小 pivot 为 NA。`analysis_status=VALIDATED` 不表示 P 正定通过；零 scale 模式不自动等于发散或候选破坏 P，也没有据此证明完整 P 半正定。没有降维、加 jitter、裁剪或写回。原版只有 EKF 快照覆盖，不能宣称与候选每 IMU 末覆盖相同。

## 文件入口和边界

- [本项读取回执](N16_ONLY_READ_RECEIPT.json)：两个新全读、两次旧缓存复用、0 旧 payload 打开、完整 hash/命令/身份门、P 全记录 SQL 结果及旧影子源行。
- [C00 SUMMARY](N16_ONLY__RUN_00004/SUMMARY.json)、[变化计数与全部 mask 模式](N16_ONLY__RUN_00004/ACTUAL_DIFFERENCE_COUNTS.json)、[首事件原值](N16_ONLY__RUN_00004/FIRST_DIFFERENCES.json)、[快照索引](N16_ONLY__RUN_00004/FIRST_DIVERGENCE_SNAPSHOT_INDEX.csv)。
- [D15 SUMMARY](N16_ONLY__RUN_01401/SUMMARY.json)、[变化计数与全部 mask 模式](N16_ONLY__RUN_01401/ACTUAL_DIFFERENCE_COUNTS.json)、[首事件及旧负对照同键原值](N16_ONLY__RUN_01401/FIRST_DIFFERENCES.json)、[快照索引](N16_ONLY__RUN_01401/FIRST_DIVERGENCE_SNAPSHOT_INDEX.csv)。
- 新事件原位：`<VALIDATION_ROOT>/candidates/N16_ONLY/{RUN_00004,RUN_01401}/observer/events.jsonl`；完整缓存及逐更新/逐IMU比较分别在 `<VALIDATION_ROOT>/analysis/event_cache/N16_ONLY__{RUN_00004,RUN_01401}/` 与 `<VALIDATION_ROOT>/analysis/comparisons/N16_ONLY__{RUN_00004,RUN_01401}/`。

本项没有 NAV 首分叉、误差评价、bootstrap 或 reference 资格升级；精度评价由独立小项负责。结果限这两个 F04 身份，不外推其他种子、11配置或原6468运行矩阵，不新增 N09/N12 结论。
