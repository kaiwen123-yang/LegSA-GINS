# 隔离 pilot 独立复核

审查日期：2026-10-06。审查者为独立于 pilot 实现者的 comparisons 子任务。本审查只读取代码、配置、已生成的单元测试与结果；未调用导航求解器或评价器，未修改 production C++ 或 Git。算法相关检查均经 Ubuntu-22.04 WSL。

## 当前结论与范围

最后的预运行静态审查未发现阻止该**条件性可行性诊断**继续执行的算法问题。修复后的 K_HV、机体系观测雅可比、GNSS 独立调度、因果采样、重复保护、15 维活动状态协方差检查、同 case 配置对照和全部结果封存后评价，形成了可核对的实验合同。

这不等于已证明候选全面提升，也不等于足式里程计完成。SDK velocity 的坐标系、物理输出点、内部信息依赖及机体系噪声尚未独立标定。最终科学结论须以 12 个成功导航运行及对应评价的实际记录为准；运行结果已在本报告末尾单独复核。

直接来源：[pilot helper](../../../scripts/paper_rebuild/research_audit_20261006/pilot.py)、[实验合同](PILOT_CONTRACT.md)、[预注册及源文件哈希](PILOT_PREREGISTRATION.json)、[输入可行性](04_LEG_INPUT_FEASIBILITY.md)、[继续研究判据](05_ONE_WEEK_PLAN.md)。不以既有论文数值倒推新模型或调参。

## 代码与科学合同检查

| 检查项 | 已核事实 | 判断与边界 |
|---|---|---|
| 隔离性 | build 复制 core 到 `<WSL_SCRATCH>/research_audit_20261006/SOURCE/core`；只在那里改 GIEngine/helper/观察输出 writer；保存原始与候选源码逐文件 SHA256，build 后再核原始源码 | 原 scientific C++ 未改变；旧结果未被覆盖。构建 helper 本身不是 production 算法替换 |
| 机体系观测 | 残差为 `(Cbn^T v_n - z_body)[0:2]`；`H_v=Cbn^T`，`H_phi=-Cbn^T skew(v_n)` | 与原 feedback `v<-v-dv`、`C<-Exp(phi)C` 一致；不是将 NED 速度残差直接换名 |
| 雅可比检查 | 实际 C++ helper 在三个姿态对速度与姿态扰动作中心差分；最大误差 `2.97396e-10` | PASS。覆盖当前 2 维观测；运行前要求 mode 2 为 `horizontal_2d`，不授权 3 维路径 |
| GNSS 独立调度 | 在 `newImuProcess` 的全部 GNSS/纯传播分支之后、状态保存之前执行 5 Hz tick | 全字段无效 GNSS 在 `addGnssData` 中 `isvalid=false`；缺记录时纯传播仍到达 tick。两种情况都必须以 runtime 计数验证 |
| 更新次数 | M1 禁用原 GNSS 内 RP；M2 禁用原 GNSS 内 RP/HV；每 tick 后仅在实际 accepted 计数增加时 feedback 一次 | 不会因原 GNSS 内 RP 再执行而重复更新；M1 仍按原 GNSS 逻辑使用旧 HV |
| 因果性与去重 | latest 样本必须 `sample_time<=state_time`、age 分别 RP<=0.02 s / HV<=0.08 s、严格大于该源 last；last 在尝试时推进 | 每源每时间戳至多尝试一次，包括被拒绝样本；不补做错过的 tick。AID_EVENTS 的 last 是最后尝试，不应误称每行都 accepted |
| 原 M0 行为 | 新 HV `!update_flag` guard 对 M0 不增删样本：原 nearest 循环已跳过该 flag=false 的行 | M0 仍需与已保存同诊断 NAV/STD 比较。它是当前修正 IMU 诊断基线，不是原 V3 parity |
| 原噪声与初始化 | 同 case 三模式配置逐字段比较，仅 mode2 HV provider 路径及 run/output 标识不同；QA/QM 均关闭，source-aware policy 同为 clean_v1 | 原初始化、过程噪声、sigma、门限与 GNSS 内容保持；body sigma 0.132838 是继承的工程值，不等于完成 body 噪声标定 |
| K_HV 与轴映射 | raw velocity 乘继承 `1/0.962142=1.0393476222844444` 与 `diag(1,-1,-1)` | 第一版准备遗漏 scale 已在任何科学导航前修正；无误差曲线驱动的再标定 |
| 源有效性 | raw error_code 全 0、velocity 有限；历史源 validity 全 true，仅读取 time/go2_source_valid；新 provider 不读历史 HV 向量或 A1 heading | 不借用 A1valid 来决定 body HV 是否可用；只说明该固定数据条件，不推广为所有 raw 状态处理 |
| quality 标签 | 旧 `clean_raw_go2_weak_auxiliary` 与新 `conditional_body_frame` 均非 nominal/available | 当前 clean_v1 走同一 n6b 分支，两者都受相同 LSIM 1.5 下限；没有仅因标签改名增加 R。frame 标签仍是条件假设，不是物理质量等级 |
| 协方差 | sandbox writer 从首末 2 s 改为完整窗口约 1 Hz 保存 full P；检查有限、全 21 对称、前 15 维特征值 | P/V/PHI/BG/BA 为前 15，SG/SA 为固定零 6 维；不得要求 full21 正定。稀疏检查不能宣称每个 IMU 时刻 PSD 或统计一致性 |
| 支持一致 | native 对同 case 三模式 NAV 时间键哈希作精确相等检查；offline 对 error_series 时间键也相等 | 不以删评价 epoch 改善指标。NO_RECORDS 删的是 100 行 GNSS 输入，评价支持保持 |
| 评价隔离 | strace 保存 native 文件访问；全部 12 输出封存后才读 reference；frozen evaluator/point transformation 未调参 | reference 为共享 GNSS 的商用融合参考，不能称独立真值；“raw_velocity 不读 GNSS/reference”只描述 raw 提取环节，整个 prepare 为构造缺记录实验确实读取 GNSS 输入 |

关键生产源码证据：[GNSS 有效性与更新](../../../cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp)、[source-aware 策略](../../../cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp)、[状态索引](../../../cpp/legsa_v23_port_core/include/legsa_v23_port_core/types.hpp)、[原观察输出范围](../../../cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp)。实际候选源码哈希见预注册。

## 主张限制

1. M0→M1 同时改变 RP 的调度、只取过去样本和去重；M1→M2 同时改变 HV 坐标观测模型与调度。因此是复合可行性干预，不能从单次差值把贡献完全归因于某个方程。
2. 新 CSV 的 `vn/ve/vd` 仅为兼容传输列名，mode2 实际为 FRD 分量；只消费 forward/right。不得把它描述成已验证的 NED 速度。零 SDK 输出点到 IMU 杆臂也只是显式假设。
3. SDK velocity 是机器人报告量；没有实现 contact/FK 里程计及其滑移协方差传播。SDK 内部 GNSS/外部融合依赖尚无厂商级证明，所能实证的是本次 provider 构造不使用 A1 或 reference。
4. 普通 GNSS 更新和共同双天线初始航向仍存在。可写“运动辅助更新不再依赖 GNSS epoch”，不可写“整个定位算法完全与 GNSS 解耦”。
5. 该 pilot 没有修改或新执行模糊度固定核心；不能用其导航效果声称短基线 AR 改进。
6. 固定 BY2 与一个 outage 放置位置只支持下一周研究优先级判断。clean/fault 工程判据不构成统计显著性、泛化或安全认证。

## 已暴露的执行身份问题及处理

第一次 `C00_M0` 程序调用在 `bd8adcb54bc8444be80376af4242dbf9b45369e1` 下返回 1，约 0.0167 s。stderr：`FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: formal stage/protocol/case/data_mode/run identity mismatch`。这是输入解析前的 formal 身份白名单拒绝；没有导航输出，不能列为算法发散，也不能漏记为零次程序调用。

根任务授权保留该失败现场，再仅修正 transport metadata 以沿用原 stage/protocol/case 解析标签，不放宽 scientific gate、不更换数据或参数。独立复核进一步发现 run_id 也受 `IMUFIX_` / `IMUFIX_CLAIM_` 前缀约束，并已告知实现者与根任务；但 ATTEMPT_02 执行与该复核发生交错，第二次程序调用也在相同身份门被拒绝。只保留 protocol 不足以通过该门。最终修复采用 `IMUFIX_RESEARCH_AUDIT_*` / `IMUFIX_CLAIM_RESEARCH_AUDIT_*` 前缀，并先让独立 loader-only checker 对 12 个配置全部通过。checker 不进行 IMU 传播，不计入科学 native run，但单独留存调用记录。科学 pilot 身份以 PLAN、mode、run_id、候选 binary、config/input hashes 联合确定，并在合同中披露。目标为 **2 次保留的 pre-input 失败 + 12 次科学导航调用 = 14 次程序调用**；任何额外调用都必须另记，不能静默替代。原失败的绝对路径由后续执行清单记录。第二次失败执行 commit 为 `5541f5852b94cbb5ca2177f5c7109826f4a90bf8`，运行约 0.0163 s，同样未读 reference。

ATTEMPT_03 的 12 个实际配置已独立核对原 stage/protocol、两类合法 run 前缀、run_label、case/data_mode、8 列 IMU、STOP_AND_REINITIALIZE 和算法开关；其 config SHA256 与 PLAN 一致。已读取真实 loader checker 12/12 PASS、returncode=0、stderr 为空的记录，checker SHA256 为 `a791d6601d2f41f460399d7e2acbd3f9b363024bc7e52754aa24fcdacbe690b1`。有效 PLAN SHA256 为 `f96251d9d53e6c0323f3f931a56432cef5686ef702a562cf61f74ea80495d3f8`，候选 binary 仍为 `3805d2d2b0f52063da48d52b23fca2f88c4b5f9ef19adc9bfd48f5fe920701e7`。这些修正只更正运行身份，不改变数值模型。

## 运行与结果复核

**复核结论：该 12-run pilot 的执行、支持和指标计算通过；支持继续一周的限定研究，不支持直接替换现有主结果。**

直接来源：[全部 30 行指标](PILOT_RESULTS.csv)、[完整执行摘要与逐运行计数](PILOT_EXECUTION_SUMMARY.json)。本 reviewer 读取 `<WSL_SCRATCH>/research_audit_20261006/ATTEMPT_03` 的 12 个 RESULT/RUN_MANIFEST、NAV/STD、AID_EVENTS、P、SOURCE_AWARE_TRACE 及 error_series，只做独立读取/计算，未重启 solver/evaluator。

- 实际为 14 次 solver 程序调用：2 次 pre-input 身份拒绝、12 次完成科学导航；另有 1 次 loader checker 进程检查 12 个配置、2 次构建时 native helper 单元测试进程。离线评价 12 次，native reference 读取 0 次。
- 科学执行 commit 为 `dfc0ff8639d6bcf41ca24647a515fe9954d56acf`；全部封存后才离线评价。native seal SHA256=`ef75b9afa3630123f71ff48bcd1a36bc3a41287288ce411afd131bad8172de58`。
- 每个 run 输出 56,642 个 NAV/STD 样本；同 case 三模式的 native 与评价时间键相同。四个 M0 的 NAV/STD 与对应保留的旧诊断输出 **字节相同**，并非仅通过浮点阈值。
- 对每个 M0/M1/M2，D61 invalid 与 NO_RECORDS 的 NAV/STD **分别字节相同**。这验证缺记录和无效记录两种分发路径；它们不是两组独立精度证据。
- 每个 run 保存 275 个全窗 P 样本，覆盖 outage（至少 19 个）；独立重新计算 active15 特征值均正，最小值约 `4.15249e-10`，最大相对不对称约 `1.81e-15`。全部 runtime `cov_health_fail_count=0`。仍只称稀疏数值健康，不称 NEES/置信度校准。
- 每个 M1 的独立 RP、每个 M2 的独立 RP/HV 都有 1,369 次 accepted；样本唯一且不取未来，最大 age 为 `0.0179541793 s`。按 **state_time** 的 20 s outage 计，M1 RP=100、M2 RP/HV 各 100。
- `AID_EVENTS.hv_accepted` 是独立 tick 增量；M1 中值为 0 不表示传统 GNSS 事件内总 HV=0，尤其 D62 仍有旧 HV。SOURCE_AWARE trace 的 time 为 source sample time，恢复后引用 outage 内过去样本会使简单区间计数成为 101，甚至 D61 M0 的 RP 显示 1；不能把它当作 outage 内 state-time 调度计数。
- 全部 12 个 evaluator audit/consistency 通过。本 reviewer 从 12 个 `error_series.csv` 独立重算全部 30 行 H/V/3D/yaw RMSE 和 outage terminal 指标，最大绝对差 `7.11e-15`；输入/评价支持没有因候选结果被删减。完整表 SHA256=`e6a26c66c866d5bb2d42706082d98150280c21327abad72d51a9583526c3bf95`。

| 指标与统计范围 | M0 | M1 | M2 | 解释 |
|---|---:|---:|---:|---|
| C00 全窗 H RMSE (m) | 0.097560 | 0.097557 | 0.099028 | M2 增加 0.001468 m / 1.50% |
| C00 全窗 yaw RMSE (deg) | 1.902662 | 1.902591 | 1.636773 | M2 降低 0.265889 deg |
| D61 outage H RMSE (m) | 58.292571 | 40.766848 | 0.836635 | M1 降低 30.07%；M2 对 M0 降低 98.56% |
| D61 outage V RMSE (m) | 5.118368 | 6.030063 | 7.126477 | M2 增加 39.23%，必须披露 |
| D61 outage terminal H (m) | 135.025304 | 87.143520 | 1.538838 | 最后实际匹配样本，不是插值的精确 20 s 端点 |
| D61 outage terminal V (m) | 8.218696 | 10.885590 | 12.197357 | 垂向漂移未解决，且恶化 |
| D62 outage H RMSE (m) | 0.702330 | 0.702379 | 0.748108 | M2 增加 6.52%，不能声称所有故障情形改善 |
| D62 outage V RMSE (m) | 7.151547 | 7.151021 | 7.122955 | 变化很小，不能解读为垂向鲁棒性突破 |

outage 统计为 3,678 个实际匹配样本；恢复前 5 s 为 804 个；全窗为 56,642 个。D61_NO_RECORDS 所有指标与 D61 对应模式相同，不重复扩充样本量。完整 30 行还保留全窗、3D、yaw 和恢复指标，未只报有利的 H。

候选 M2 通过预先登记的继续研究判据：clean H 代价小于 0.02 m 阈值、yaw 未恶化、D61 H 降低超过 50%、因果/唯一/新鲜度及 absent-GNSS 分发通过。值得的一周工作应围绕**坐标/时间/物理点合同、GNSS 独立的运动辅助更新、垂向失效边界和接触/滑移鲁棒性**，而不是把当前条件性 SDK 速度诊断立刻命名为新足式里程计。无需为了追求更好图表继续扫 frame、噪声或 outage 位置。
