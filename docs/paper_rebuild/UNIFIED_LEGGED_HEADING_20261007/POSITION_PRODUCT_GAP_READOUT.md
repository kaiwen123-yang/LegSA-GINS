# 位置产品缺失：局部 partial × 足式政策四臂读出

局部 partial 在 31.8 s 位置产品空窗中将 yaw RMSE 降低约 10%，并通过共同状态产生 18.47/29.47 mm 的原生水平位置差；这一作用大于离线杆臂几何差。但相对参考的水平净收益仍很小：SDK 背景微恶化 0.386 mm，足式背景改善 2.813 mm。更重要的是，在同样保留 partial 时，足式替代政策的 gap H RMSE 为 **0.790029 m**，SDK 背景为 **0.398009 m**，接近两倍；整套足式方案尚未获得导航净增益。

## 1. 冻结条件与归因资格

- 这是受控半合成 receiver POSITION 产品缺失，非自然 GNSS 失效。原完整 BY2O 窗为 3186–3563 s；仅严格开区间 `(3278.598000049591, 3310.3980000019073)` 内的 POSITION 产品被撤去。GNSS18 receiver velocity、raw Doppler、RP、IMU 与足端源保持原输入。
- carrier 维度为局部消融：`GAP_PARTIAL` 保留原 MOTION，`GAP_FULL_ONLY` 仅把空窗内 30 条 partial 替为同历元 invalid FULL 行。区间外 87 条 partial 和所有共同 FULL 输入相同，不能称整窗 FULL 与 ROLLING 算法比较。
- 足式维度为 `SDK_NULL` 与原 `body0_xy REPLACE_SUPPORT` 完整政策；它包含 SDK 抑制和足端更新，不能解释成纯足端信息贡献，也不是本轮引入 XYZ 模型。
- 首个受影响 carrier 历元固定为 `3279.99799990654`。每个足式背景此前 **20026** 个保存历元的 PVA、全部 IMU 偏置/尺度和 STD 完全相同；首次保存状态/偏置差均在 `3280.003072`。故局部 partial 对照的 prefix 条件成立。足式背景之间则本来就全窗不同。
- 分层不按结果选段：gap 如上；恢复段 `[3310.3980000019073, 3330.3980000019073]`；remaining 是前两段的完整补集。每臂 full/gap/recovery/remaining 分母分别为 **76548/6592/4300/65656**，评价覆盖率均为 1，非有限误差行均为 0。

PLAN SHA256：`874a047481a3609e92e38268e082b8aaa120b20f94f460d807c98c6f547c6943`。输入、二进制、配置和完整评价身份由该 PLAN、`ALL_NATIVE_SEALED.json`、`EVALUATION_COMPLETE.json` 及 `READOUT.json` 的 input pins 绑定。

## 2. 全分母导航结果

下表 H/Up 单位为 m，yaw 为 deg；均为冻结评价器的参考相对 RMSE。H p99 保留尾部，完整 p95/p99/max、末个匹配误差与覆盖列见 `POSITION_PRODUCT_GAP_METRICS.csv`。

| arm | 分层 | N | H | Up | yaw | H p99 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| SDK_GAP_FULL_ONLY | full_window | 76548 | 0.128960028 | 0.046417627 | 3.194257761 | 0.542668189 |
| SDK_GAP_FULL_ONLY | position_product_gap | 6592 | 0.397622993 | 0.066746747 | 2.091754605 | 0.628970601 |
| SDK_GAP_FULL_ONLY | recovery_20s | 4300 | 0.050135266 | 0.022707782 | 8.668103246 | 0.084308118 |
| SDK_GAP_FULL_ONLY | remaining | 65656 | 0.057888166 | 0.045066147 | 2.556517059 | 0.211795294 |
| SDK_GAP_PARTIAL | full_window | 76548 | 0.128952358 | 0.046430685 | 3.018355403 | 0.545335778 |
| SDK_GAP_PARTIAL | position_product_gap | 6592 | 0.398008866 | 0.066839057 | 1.862896501 | 0.634005927 |
| SDK_GAP_PARTIAL | recovery_20s | 4300 | 0.049299751 | 0.022708931 | 8.379358614 | 0.083138047 |
| SDK_GAP_PARTIAL | remaining | 65656 | 0.057648501 | 0.045068055 | 2.382209679 | 0.211772811 |
| FOOT_GAP_FULL_ONLY | full_window | 76548 | 0.238881036 | 0.045967930 | 3.196508394 | 1.167141976 |
| FOOT_GAP_FULL_ONLY | position_product_gap | 6592 | 0.792842236 | 0.063363025 | 2.109125113 | 1.367156714 |
| FOOT_GAP_FULL_ONLY | recovery_20s | 4300 | 0.048088526 | 0.022699211 | 8.709791018 | 0.080197150 |
| FOOT_GAP_FULL_ONLY | remaining | 65656 | 0.057155171 | 0.045019417 | 2.549073625 | 0.211586137 |
| FOOT_GAP_PARTIAL | full_window | 76548 | 0.238040651 | 0.046013085 | 3.076328436 | 1.166097211 |
| FOOT_GAP_PARTIAL | position_product_gap | 6592 | 0.790029182 | 0.063725604 | 1.901448549 | 1.365260182 |
| FOOT_GAP_PARTIAL | recovery_20s | 4300 | 0.047537317 | 0.022698821 | 8.514399423 | 0.079505173 |
| FOOT_GAP_PARTIAL | remaining | 65656 | 0.057008234 | 0.045021828 | 2.433697364 | 0.211586140 |

gap 内保留 partial 的 yaw 改善在 SDK/FOOT 背景分别为 0.228858°（10.94%）和 0.207677°（9.85%）。对应 H 改变分别为 **+0.385873 mm** 和 **−2.813054 mm**，Up 改变为 +0.092310/+0.362579 mm。足式背景下局部 partial 对 H 的差值相对 SDK 背景多改善 3.198927 mm，仅是两种完整政策下效果的描述性交互，不能作可加的因果分解。

gap 的 H p99 在 SDK 背景为 0.628971→0.634006 m，在 FOOT 背景为 1.367157→1.365260 m；末个 gap 匹配点（3310.397052 s）H 分别为 SDK 0.596259→0.602184 m、FOOT 1.356097→1.355014 m。不能用均值上的小改善掩盖绝对尾部误差。固定恢复 20 s 的 H 改善约 0.836/0.551 mm；全窗 H 改善约 0.00767/0.84038 mm，仍不支持稳定、实质的位置净收益。

## 3. 航向确实进入共同 R/v/p 与偏置

下面是各背景内“保留 gap partial − 撤去 gap partial”的 **原生状态差**，不是参考精度。位置/速度通过 ECEF 转到同一瞬时局部 NED；姿态量为两姿态的 SO(3) 旋转角；偏置差为导出原生状态。没有合格速度参考，本轮不报告 velocity RMSE。评价杆臂几何位移单列，未拿它替代 IMU 点位置作用。

| 背景/分层 | 原生 pH RMS mm | vH RMS mm/s | 姿态差 RMS deg | gyro bias差 RMS deg/h | accel bias差 RMS m/s² | 评价杆臂 H RMS mm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GAP_PARTIAL_WITH_SDK/full_window | 5.424133 | 0.710123 | 0.263398648 | 3.209694262 | 0.000668211 | 0.641373 |
| GAP_PARTIAL_WITH_SDK/position_product_gap | 18.472266 | 1.792905 | 0.351648975 | 5.453685201 | 0.001836410 | 0.786206 |
| GAP_PARTIAL_WITH_SDK/recovery_20s | 0.266108 | 0.987746 | 0.343518234 | 4.754857845 | 0.001125710 | 0.780442 |
| GAP_PARTIAL_WITH_SDK/remaining | 0.194294 | 0.448655 | 0.246464106 | 2.746684440 | 0.000314626 | 0.614532 |
| GAP_PARTIAL_WITH_FOOT_POLICY/full_window | 8.649513 | 0.816547 | 0.184050510 | 2.506413530 | 0.000830090 | 0.438254 |
| GAP_PARTIAL_WITH_FOOT_POLICY/position_product_gap | 29.470410 | 2.293649 | 0.315056309 | 5.546942695 | 0.002077862 | 0.688200 |
| GAP_PARTIAL_WITH_FOOT_POLICY/recovery_20s | 0.243322 | 1.044679 | 0.248085616 | 3.609707690 | 0.001467499 | 0.529862 |
| GAP_PARTIAL_WITH_FOOT_POLICY/remaining | 0.147476 | 0.421527 | 0.159679051 | 1.838934023 | 0.000478361 | 0.397479 |

两组 partial 对照在 gap 入口状态差为零。到出口前最后保存行 3310.397052 s，SDK/FOOT 的 Δp_NE 分别为 (−11.004, +33.123)/(−17.044, +53.401) mm，Δyaw 为 −0.395303/−0.348773°；Δbg_z 为 +5.702279/+5.652077 deg/h，Δba_y 为 −0.001167/−0.001380 m/s²。因此不是仅杆臂换算或独立后处理 yaw 造成的表象。恢复段原生 pH 差降至 0.266/0.243 mm RMS，需与恢复的位置更新和其他来源共同解释；本读出不把整段差分当某一次更新的增量。

逐观测直接作用由独立只读报告 [POSITION_PRODUCT_GAP_CARRIER_CROSS.md](POSITION_PRODUCT_GAP_CARRIER_CROSS.md) 重建：保留全部 30 个来源槽（含 3 条拒绝实际增量 0），SDK/FOOT 的单次 carrier→位置水平修正 RMS 为 0.417220/0.689994 mm。该结果使用真实 pre-carrier Ppφ 与含 QA/SA 缩放的 R，支持共同 cross 的实际消费；不能把这些单次增量求和当最终位置差或精度收益。

完整足式政策的代价也不是较大 yaw 误差即可解释：在保留 partial 条件下，FOOT−SDK 的 gap pH 差 RMS 为 **0.405100 m**，vH 差 RMS 为 **0.035507 m/s**，而 yaw 差 RMS 只有 **0.066564°**。入口 Δp_NE≈(−0.000211,−0.002554) m、Δv_NE≈(−0.003415,−0.011449) m/s；出口 Δp_NE≈(+0.765642,+0.111294) m，而 Δyaw 仅 +0.016011°。gap 平均 Δv_N≈+0.020717 m/s。这是足式替代政策下的平移分歧证据，不能说它已由 partial 航向改善解决，也不能在本四臂中把足端约束、SDK 移除及进入 gap 前的偏置/协方差影响单独分离。

`BOUNDARY_STATE_DIFFERENCES.csv` 使用边界之前最后保存行；与请求边界分别相差约 −0.939/−0.948/−0.936 ms，不是精确单观测跳变。

## 4. 实际供给、接受、足式消费与撤销

gap 有 158 个冻结 carrier 槽：30 个被局部干预的 partial + 128 个共同无效槽。FULL_ONLY 两臂的 30 个干预槽均 provider-invalid、不尝试；PARTIAL 两臂均 valid/attempt **30/30**，接受 **27**、前级 `NIS_3DOF_REJECT` **3**。进入 source-aware 的 27 条均接受，26 条 R scale=1，另 1 条仅轻微 OIM 放大（SDK 1.0008910787，FOOT 1.0011249887）。空窗内没有共同有效 FULL 槽。

| arm | 全窗 carrier 尝试/接受/前级拒绝 | gap carrier 尝试/接受/前级拒绝 | 全窗 SDK 接受/抑制 | gap SDK 接受/抑制 | 全窗 foot END 供给/尝试/接受 | gap foot END 供给/尝试/接受 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SDK_GAP_FULL_ONLY | 255/222/33 | 0/0/0 | 1881/0 | 159/0 | 1158/0/0 | 75/0/0 |
| SDK_GAP_PARTIAL | 285/250/35 | 30/27/3 | 1881/0 | 159/0 | 1158/0/0 | 75/0/0 |
| FOOT_GAP_FULL_ONLY | 255/221/34 | 0/0/0 | 1010/871 | 93/66 | 1158/1157/1157 | 75/75/75 |
| FOOT_GAP_PARTIAL | 285/248/37 | 30/27/3 | 1010/871 | 93/66 | 1158/1157/1157 | 75/75/75 |

共同供给 255 条在 SDK 背景的全窗接受从 222 变为 223，属于局部干预之后共同状态改变的下游结果；FOOT 背景共同供给接受均为 221。全窗 provider 分母 1885 不删：255 共同有效 + 30 干预 + 1600 共同无效。实际 provider-invalid 诊断中共同无效为 1599，末个无效槽 3562.99799990654 s 未见对应 carrier 调用诊断，仍保留在供给分母；另有 1884 行 `missing_exact_time` 调用诊断，不虚增来源机会或拒绝数。

足式全窗 START/END/RETIRE 为 1779/1158/621；初始 START 未消费，对应一个 END 为 `NO_MATCHING_POSE_CLONE`，因此 FOOT 实际尝试/接受 1157。gap 的 START/END/RETIRE 为 143/75/68，两 FOOT 臂足端均实际更新。全窗与 gap REVOKE 均为 0；所有臂 replay_batches、replayed_IMU_intervals、expired_factors_without_restoration 均为 0。0.5 s 回放缓冲实际存在，但本自然输入没有触发撤销，不能把零撤销数称为失效恢复验证。

四臂全窗其他 SA 接受相同：receiver position **1725**、receiver velocity **1884**、raw Doppler **927**、RP **1877**。严格 gap 中为 position **0**、receiver velocity **159**、raw Doppler **95**、RP **159**，均到达 SA 并接受。故本实验不是“仅 IMU+foot/carrier 的 GNSS 全失效”。

### 事件时间精度修正记录

`SOURCE_AWARE_WEIGHT_TRACE.csv` 的时间仅打印 10 位小数，恰好使两个 FULL 边界分别偏入严格 gap 约 +9/−7 ps；初次表误列 FULL_ONLY/PARTIAL 的 SA carrier 数为 2/29。仅将该来源唯一匹配回冻结 carrier provider 的精确历元后，正确为 **0/27**。四臂共 8 条事件改变分层，12 个汇总行改变（gap/recovery/remaining）；全窗计数、其他来源计数、17 位 carrier 诊断、NAV/评价指标、原生状态差均未变。此操作是读出分层修正，不是算法/原生日志修改。

首次 script、READOUT.json、SOURCE_AWARE_COUNTS.csv 原样保存在 `READOUT/INITIAL_SA_ROUNDING_READOUT/`；修正脚本及逐项前后记录为 `CORRECT_SA_EVENT_TIMES.py`、`SOURCE_COUNT_CORRECTION.json`、`SA_TIME_BOUNDARY_CORRECTION.csv`。正式 script 已包含相同唯一来源匹配逻辑，完整读出没有重跑。

另需区分时刻语义：SDK SA 按来源时刻分层，gap 为 158/92；BODY_VELOCITY_EVENTS 按真实消费 `state_time` 分层，gap 为 159/93。它们不是同一统计时刻，不把 1 条差异当漏消费。足端按 `event_time_s`，carrier 按精确来源历元分层，不采用最近 IMU 点移动事件。

## 5. 结论与边界

本轮闭合了一个具体作用条件：撤去位置产品后，partial 方向不只改 yaw，还实质进入共同姿态、速度、IMU 点位置与偏置，且局部对照 prefix 完全一致。然而，现有 receiver velocity/raw Doppler 持续保留，方向对相对参考 H 的净影响仍为毫米级；足式替代政策则出现显著水平代价。不能据此声称“三个创新点已统一并稳定改善组合导航”，也不支持扩大同类参数/场景矩阵。下一实质问题仍是足式共同平移信息与保留速度来源的匹配及资格，不应再把航向→状态链未接通作为解释。

该对照不独立分解 carrier→R、bias、SDK/足端再更新及传播的各项贡献；姿态/速度差是共同轨迹的可观察结果，不是新增真值。Fixposition 参考为相关来源，本轮严格沿用冻结评价合同，没有调时钟、坐标、杆臂、噪声或删段。

本读出新增 **native=0、evaluator=0、reference payload读取=0**；根任务唯一执行为 **4 native + 4 冻结评价**，均 COMPLETED、在线参考读取为 0。完整读出一次，随后只做 SA 精度分层修正。未新增测试矩阵。

完整机器结果：`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/POSITION_PRODUCT_GAP_BY2O_01/READOUT/READOUT.json`。关键同行表：`POSITION_PRODUCT_GAP_METRICS.csv`、`POSITION_PRODUCT_GAP_NATIVE_STATE_EFFECT.csv`、`POSITION_PRODUCT_GAP_DESCRIPTIVE_INTERACTION.csv`、`POSITION_PRODUCT_GAP_PREFIX_IDENTITY.csv`。源计数、边界状态、恢复交互等完整表保存在同一 READOUT 目录。


## 6. 参考误差对微小H排名的影响

沿用固定时刻、坐标和评价点，不重新拟合参考。令两臂H平方误差均值差为D、配对二维误差向量差为d，共同参考偏移为u，则 D_true=D−2mean(d·u)。允许任意时变共同偏移时，使排名可能并列所需的最小RMS为|D|/(2RMS(d))。这不是实际参考误差估计，也不是偏移推荐；没有更换参考或重跑评价。

- SDK_GAP_PARTIAL vs SDK_GAP_FULL_ONLY：条件并列阈值 0.008377 m RMS。
- FOOT_GAP_PARTIAL vs FOOT_GAP_FULL_ONLY：条件并列阈值 0.075849 m RMS。
- FOOT_GAP_PARTIAL vs SDK_GAP_PARTIAL：条件并列阈值 0.574960 m RMS。

没有已认证的真实参考误差硬界，故毫米级H排名不能升格为真实精度改善。足式政策的大幅平移分歧也不能仅以参考不可靠推翻；其条件阈值与局部partial微小差值的阈值不同。完整连续数值及原误差输入身份见 POSITION_PRODUCT_GAP_REFERENCE_SENSITIVITY.json。该附加代数只复用四份已完成error_series，不新增native/evaluator/reference读取。
