# 第二轮 heading / body-z pilot 独立审查

审查范围：已预注册 runner、实际隔离源码、构建与 loader 记录、旧结果和输入哈希。审查者未调用导航 solver、评价器或原始 reference，也未改动 runner、算法或 Git。首次静态审查时新 native 完成数为 0；后续一次 C00 M3 已传播但在输出前被旧计数门拒绝，详见下文。本文件的静态通过只表示允许按既定合同执行，不表示结果或论文创新已成立。

## 静态结论与身份

首次静态审查遗漏了输出前的 formal runtime counter 检查；运行暴露该问题后，已独立核查仅隔离副本中的身份适配。当前 ATTEMPT_02 未发现阻止固定 6 个探索性试验执行的问题。复核版本：[pilot.py](../../../scripts/paper_rebuild/heading_reassessment_20261006/pilot.py) SHA256 `b740f80482d0861a07834f8c5b4a39791e181eb2788b9a4c187a680abd6de529`；实际 PLAN SHA256 `9d712bdd126c8d51f749ee69023700f34c6821d876fe5db7e59e8073d7f2bf36`。报告中的程序链接以仓库根目录为准：`scripts/paper_rebuild/heading_reassessment_20261006/pilot.py`。

- 原 M0/M2 二进制：`3805d2d2b0f52063da48d52b23fca2f88c4b5f9ef19adc9bfd48f5fe920701e7`。
- 首次被 runtime gate 拒绝的 M3 二进制：`20eb97b47707ad01c9a935fbf4301f21e93018dda04ba909810d33938c48e72e`；当前 ATTEMPT_02 的 M3 二进制：`1bf81d76f74f10511ca0f49988a800e2593cbdced791fd48bbc63e5ec8463509`。
- 独立重新读取并核对 13 个输入文件、6 组配置与二进制、6 组继承 NAV / STD / error-series 哈希：全部一致。六个旧 NAV 的数值时间键相同。CSV 原先经 pandas 浮点往返的准备副本已归档 PREPARATION_00_CSV_ROUNDTRIP，未运行算法；当前使用 token 保真版，二进制未变。
- 旧 C00 / D61 / D62 的 M0、M2 共 6 个结果是复用；新调用为三场景 M3 和 H20 的 M0/M2/M3，共 6 native + 6 evaluation。不得报告为 12 个新运行。
- [预注册](PILOT_PREREGISTRATION.json) 保存父源码、父 seal、输入、配置和模型身份；[合同](PILOT_CONTRACT.md) 明确本轮不是正式 V3 替换。

## H20：遮断来源及其派生 HV

runner 的 prepare()按 [196.2,216.2) 仅修改 100 行 GNSS18 的 yaw-valid token，并验证前 17 列数值不变。旧 HV 来源是独立固定的 1 Hz A1 表；删除其中 20 个来源时刻后重新应用原有最大插值间隔 1.2 s，不仅在成品 HV 上裁剪 20 s。

重新形成的无支持区间是 (196,217)，因此包含必要的边界余量；共禁用 3,843 个原先有效的 HV 行。runner 对故障内每个 GNSS 事件验证最近有效 HV 距离大于原更新容差 0.08 s，不能从恢复端取值填补失效段。该设计和合同一致，避免了“yaw 已失效，但 legacy HV 仍携带事先插值 A1”的污染。

解释边界：H20 是 heading-source loss，连带取消依赖该来源的 HV；不是只关一个 yaw 更新函数的纯滤波消融。旧来源在故障之外仍保留原离线插值语义，不能称整个 M0 都是因果处理。M2/M3 的独立 body 观测有自己的过去样本约束。

## M3：三维观测、符号和更新次数

实际隔离 `SOURCE/core/src/kf_gins/gi_engine.cpp` 第 110–117 行只在 M3 生效时检查原传输配置，再设置有效模式 `conditional_body_3d_pilot` 和 `vertical_disabled=false`。正式 parser 与正式 core 未改。原 YAML 的 horizontal 标签是历史 transport，不能单独当作执行模型证明；必须同时使用环境 mode、二进制、源码 pin 和有效维度。

独立逐列比较 `SDK_BODY_3D.csv` 与旧 `ROBOT_REPORTED_BODY_HYPOTHESIS.csv`：只有 `std_vd` 和 `prior_policy` 改变；`vn/ve/vd` 全部原始字符串 token 精确相同；同时独立逐字段核对 H20 两个 63,278 行表，只有支持/状态字段改变，全部数值 token 保真。新增 z sigma 固定 0.132838 m/s，继承比例 1/0.962142；没有参考轨迹选噪声、拟合 z 偏置或另建速度真值。

实际 C++ 第 442、552–554、1374–1417 行确认：M2/M3 不进入 GNSS-event legacy HV，只在独立 5 Hz 调度中各更新一次；M3 使用三行 body 残差和三行 Jacobian。观测为 h=C_bn^T v_n，反馈是 v←v−δv、C←Exp(δφ)C，故 H_v=C_bn^T、H_φ=−C_bn^T[v_n]×。编译后的预注册单位检查最大有限差分误差 2.97396e−10，M3 的前两行 Jacobian 与 M2 完全一致，5 个调度 guard 通过。审查者没有重复运行这些测试。

latest-sample helper 限定 source_time≤state_time、最大 age、source_time>last；RP 0.02 s、HV 0.08 s，且分别消费去重。M3 source-aware metadata 的 active_dimensions 和 innovation dof 都是 3；规则和阈值继承，但三维联合创新可改变统一权重，因此“新增第三维”不等于水平结果完全不变，也不等于三维噪声已校准。


## 首次输出前拒绝与严格计数身份适配

首个 C00 M3 实际调用耗时 7.103748584 s、online reference reads=0，AID 记录延伸至 state_time=339.803054 s。原 `validateFormalRuntimeCounters()` 要求 LegSA 的 horizontal-only 更新数>0；真实 M3 三维更新正确没有增加该计数，于输出 NAV / STD 之前以 `FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH` 拒绝。没有离线评价。该次是**传播后的技术失败**，不是 pre-input failure，也不能从运行预算中消失。

失败日志、INVOCATION 和 aid 记录完整保留。新 ATTEMPT_02 与首次失败的 SOURCE 全树比较，只有 `core/src/runtime/port_runtime.cpp` 改变；gi_engine、观测与反馈、输入数值和参数逐字不变。六组配置的五类输入哈希均与首次计划一致。

独立检查最终 gate：

- 仅环境 mode=3 进入新谓词；其它 mode 保留原 horizontal_count>0 判据。
- M3 若 algorithm_id 不是 LegSA_Paper_V1，或 run_id 不是本 pilot 的 IMUFIX_HEADING_ / IMUFIX_CLAIM_HEADING_ 前缀，则明确抛出身份错误。
- 合法 M3 必须实际 solver_enabled、通用 velocity update_count>0、外层和实际 status 两个 horizontal_count 都为 0、horizontal_only=false、vertical_disabled=false。没有把三维计数伪装成水平计数。
- 原位置、RV、yaw、RD、source-aware、RP 必须活动，以及 FGO、QA、QM、contact 等禁用模块计数条件全部保留。正式 parser 不变。
- 最终二进制的实际 loader 对 6 配置 PASS；原三维 Jacobian 与 5 个调度检查仍 PASS。审查者未重复执行程序。

最终总计已确认是 **7 次 solver 调用=1 次传播后拒绝+6 次成功候选**，另有 6 次新离线评价、6 个既有结果复用。中间计数门提案的准备文件另行归档，没有科学 native 调用。此适配只解除三维诊断与历史模块身份的冲突，不改变科学计算或对照关系。

## 执行后必须核对的证据

runner 的 native()检查 56,642 个有限 NAV / STD 行、全窗稀疏协方差的 15 个活动状态 PSD 和对称性、候选 aid 的过去样本与唯一性，以及新 6 次 NAV 时间键一致；evaluate()要求先 seal 所有新 native，再进行冻结离线评价。

以下事项已反馈给执行者，属于结果汇总要求：

1. 汇总时将新 6 和复用 6 的 NAV 时间键共同核对，并按每个场景核对各模式 error-series 支持；不能仅以相同记录数代替。
2. M3 通用 `go2_velocity_prior_update_count` 才是三维 HV 接受计数；历史 horizontal-only 计数可能为零。独立 tick 计数应与 total source-trace 接受一致，以确认没有 GNSS-event 双更。
3. 在线 reference 打开数须为 0；每次离线评价的 reference 访问单独报告。旧结果复用不得计为新评价。
4. 同时保留 H、V、3D、yaw 和恢复段，以及实际最后受支持的故障样本时间；不把最后样本冒称为精确 216.2 s 端点。
5. 两种候选仍共享双天线 yaw 初始化；本试验不解决 XB 的 NO_INIT_HEADING，也不证明全局 yaw 可观性或新绝对航向观测。

执行后的数值与解释边界如下；本次没有据结果调参或追加场景。

## 执行完成后的独立复核

最终执行 commit 为 `e5a3c412f2690b771402dc87555ec8e9e05e469d`。ATTEMPT_02 的 6 个 native 均 seal，随后 6 次冻结离线评价全部完成；加上保留的首个输出前拒绝，共 **7 次 solver 调用（6 成功、1 传播后失败）、6 次新评价、6 个既有结果复用**。审查者仅读取这些文件和已存误差序列进行复核，没有再启动 solver 或 evaluator。

独立直接读取文件后的检查结果：

- 新 6 个 NAV / STD 哈希与 seal 一致；新 6 加复用 6 的全部 NAV 时间键逐值相等，均 56,642 行。
- 每个新运行在线 reference reads=0；每次新离线评价 reference open count=1，audit 和 consistency 均 PASS。复用误差序列的哈希仍等于预注册记录。
- 6 份原始协方差 CSV 各 275 个样本，全为有限数；直接重算 15 个活动状态的对称化特征值，最小值 4.1524552e−10，最大相对非对称度 1.7347235e−17。
- 新候选 RP / body velocity 各 1,369 次接受，故障 state-time 窗内各 100 次；直接核对源时间均不晚于状态时间、满足各自 age、同一来源时刻只消费一次。
- 4 个 M3 的 source-aware velocity trace 实际 dof=3，各 1,369 次接受，与独立调度及通用 velocity counter 相同；horizontal-only counter=0。历史 source_id 名字仍含 horizontal，不能据此误判有效维度。
- H20 M0 的 RP 总计 1,369、legacy HV 总计 1,265，故障内没有 HV 接受；M2/M3 则各保留 1,369 次 body velocity。旧 HV 比无故障少 104 次符合来源支持边界余量，不应写成只少 100 次。
- source-aware trace 的 time 是来源样本时间。按来源时刻裁故障窗会得到候选 101 行；正确独立故障接受数应按 AID_EVENTS 的 state_time 裁得 100，不能混用。

已将 [PILOT_RESULTS.csv](PILOT_RESULTS.csv) 的 30 行、360 个 RMSE / 最后样本绝对误差 / 最大绝对误差数值与源 error-series 独立重算比较，最大绝对差 7.11e−15；12 份 error-series 时间键全部相同。[执行总账](PILOT_EXECUTION_SUMMARY.json) 的 12 组 NAV / STD / error 哈希全部与原文件一致；[差值表](PILOT_COMPARISONS.csv) 和 [H20 同窗对照](H20_SAME_WINDOW_CONTROL.csv) 的方向与本审查一致。

从既有 error-series 直接重新聚合得到下表。C00 为全窗，其它场景为 [196.2,216.2) 故障窗；H/V 单位 m，yaw 单位度。每个场景三个模式支持时间键完全相同。

| 场景 / 区间 | 指标 | M0 | M2 | M3 |
|---|---|---:|---:|---:|
| C00 全窗 | H RMSE | 0.097560 | 0.099028 | 0.098954 |
| C00 全窗 | V RMSE | 0.049001 | 0.049016 | 0.048866 |
| C00 全窗 | yaw RMSE | 1.902662 | 1.636773 | 1.630865 |
| D61 故障 | H RMSE | 58.292571 | 0.836635 | 1.246703 |
| D61 故障 | V RMSE | 5.118368 | 7.126477 | 0.634415 |
| D61 故障 | yaw RMSE | 2.508905 | 2.007352 | 1.999919 |
| D62 故障 | H RMSE | 0.702330 | 0.748108 | 1.158182 |
| D62 故障 | V RMSE | 7.151547 | 7.122955 | 0.637321 |
| D62 故障 | yaw RMSE | 2.190803 | 1.832567 | 1.826670 |
| H20 故障 | H RMSE | 0.038440 | 0.035812 | 0.035784 |
| H20 故障 | V RMSE | 0.033678 | 0.033581 | 0.033672 |
| H20 故障 | yaw RMSE | 2.488925 | 1.902952 | 1.893358 |

故障窗有 3,678 个共同误差样本，最后受支持时间为 216.197081 s；前 5 s 恢复窗有 804 个，最后时间为 221.197067 s。它们不是精确窗口终点。

### 结果可以支持与不能支持的解释

M3 相对 M2 的 D61/D62 故障垂向 RMSE 从约 7.13 m 降到约 0.64 m，符合“原二维观测没有直接约束第三个 body 分量”的条件性机制；但水平 RMSE 分别升至 1.25/1.16 m，约恶化 49%/55%。因此本轮只能支持继续研究三维观测的建模、测点和各向异性噪声，不能把当前固定各向同性 M3 直接替换正式方法，不能隐去水平代价。

H20 的 M0→M2 yaw 故障 RMSE 下降约 23.5%，但其中含原先无故障的模式差异。补算 **C00 的同一故障时间段** 后：

| 模式 | C00 同窗 yaw RMSE | H20 同窗 yaw RMSE | H20 相对 C00 增量 |
|---|---:|---:|---:|
| M0 | 2.196709 | 2.488925 | +0.292215 |
| M2 | 1.769082 | 1.902952 | +0.133870 |
| M3 | 1.761616 | 1.893358 | +0.131742 |

失效附加代价在候选中较小，是对本场景鲁棒性解释有用的证据；该 RMSE 增量不是独立统计估计、协方差校准或新绝对航向观测证明。M0→M2 同时改变 RP 调度、速度坐标观测及速度调度；M2→M3 增加第三维及其联合创新权重效应。仍需保留这些因果边界。

此外，本次 BY2 试验主接收机在窗口内为 FIX。[R5 的 636 条 GNSS1 FLOAT 准入](R5_FLOAT_ADMISSION_NOTE.md) 是旧输入规则的额外实证，不是本轮 M2/M3 已在 FLOAT 场景完成验证。1 月与 3 月的历史数据日期不同，但重复提供的 1 月文件不是新增独立数据。上述数值使用共享 GNSS 来源的商用融合参考，不独立解决真实性或跨路线泛化。
