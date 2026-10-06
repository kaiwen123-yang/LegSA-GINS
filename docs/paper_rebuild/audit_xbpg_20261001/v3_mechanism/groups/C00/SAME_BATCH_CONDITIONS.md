# C00 同批条件简报：F03 / A04

本简报只读取已完成的 BY2 `C00_clean_normal`：F03=`RUN_00003`、A04=`RUN_00006`，范围沿原配置 66..340 s。两对象的运行身份门由主运行器保存；此处复用其 `replay_observed` 小表和预先保存的分类首见快照，不重开 NAV/STD、完整 events.jsonl 或原输入。F04 未纳入本简报。`data_mode=real_clean`，synthetic/semisynthetic 均 false；本小项新增 native/evaluator/provider 进程及完整事件/输入载荷读取均为 0。

可直接查看 [SAME_BATCH_SNAPSHOT_FIELDS.csv](SAME_BATCH_SNAPSHOT_FIELDS.csv)：9 个现有 N11 witness 的 261 个逐字段入口，数值保留原 JSON 十进制精度、源文件及可解析 JSON pointer。其中 255 个值为原记录，6 个 RV `actual_lever_velocity` 字段原事件没有单独导出，明确 NOT_RECORDED；没有由两速度相减补写。快照按现有调度分析器的类别首见规则保留，不是极值或效果筛选。

## N11：未补偿分支的真实条件已经出现

以下为原 KINEMATICS 小表计数，分母是进入对应运动学计算的事件；`nonzero_gyr_bias` 的原判据为三分量二范数 > 0，不代表达到实用误差阈值。

|对象/源|res=2、compensated=true、bias=0|res=2、compensated=true、bias≠0|res=3、compensated=false、bias≠0|运动学事件合计|
|---|---:|---:|---:|---:|
|F03 RV|1|594|774|1369|
|A04 RV|1|594|774|1369|
|A04 RD|1|462|645|1108|

来源：[F03 KINEMATICS](RUN_00003_KINEMATICS.csv)、[A04 KINEMATICS](RUN_00006_KINEMATICS.csv)。两份完整解析回执均 `stream_complete=true`，各记录 56,642 个 IMU_OPPORTUNITY 和 1,369 个 GNSS_UPDATE_ENTRY；本批没有 res=1 的运动学事件，不能把旧 res=1 合成反例当作本批实测。F03 RD/RP/HV 均配置关闭；缺少 RD 运动学事件是配置负对照。

RV 两对象均接受 1,369 次。A04 RD 的 1,108 次运动学事件后，1,069 次接受、39 次由 `RAW_DOPPLER_RESIDUAL_GATE_SA_OFF` 拒绝；另有 261 次 helper 入口没有时间匹配而尚未进入运动学。因此 **645 次 res=3 RD 运动学条件不等于 645 次接受**；现有分组小表没有将接受结果再按 res 联结，本短报不补猜。见两份 SCHEDULING.csv。

原冻结 `GIEngine::imuInterpolate` 将当前 IMU 拆为 mid 与剩余段，二者都先标 compensated=false。res=3 先对 mid 传播并补偿，但 RV/RD 仍读取尚未传播的剩余 `imucur_`。原 `imuCompensateInPlace` 的逐轴形式为 `dtheta=(dtheta-bg*dt)/(1+sg)`；实际观测使用 `omega=imucur_.dtheta/actual_dt_used`。本简报仅解释原公式与记录条件，不执行补偿影子或闭环修正。

可复查的第一组 res=3 实测快照（都是 t=66.400000095 s、`state_time=66.400000095`，当前 IMU 结束时刻 66.403074，前 IMU 时刻 66.397071）：

|对象/源|event_seq|actual_dt_used (s)|gyr_bias (rad/s)|compensated|
|---|---:|---:|---|---|
|F03 RV|562|0.003073905000007926|[3.033038443986528e-11,2.8425621516878905e-10,1.6359150385403258e-9]|false|
|A04 RV|578|0.003073905000007926|[-6.17028231984871e-9,-3.36135329500084e-10,1.6613002820539526e-9]|false|
|A04 RD|586|0.003073905000007926|[-6.17028231984871e-9,-3.36135329500084e-10,1.6613002820539526e-9]|false|

三条的原 dtheta 都是 `[-0.001194644528412509,0.0006017387943786746,0.0015391492437053572] rad`，原 omega 为 `[-0.38864067965972554,0.19575712143905652,0.5007146426780882] rad/s`。非零杆臂为 `[0.03,0.03,-0.3] m`。这些 witness 的 gyr_scale/acc_scale 为 `[0,0,0]`，不是全运行 scale 范围的统计。A04 RD event586 的实际杆臂速度为 `[-0.07445933364056333,-0.10020072619413638,-0.021873807612379427] m/s`；这是原实现用于观测的完整旋转杆臂项，**不是 bias 导致的误差，也不是修正收益**。first res=2 witness event282/290 的 bias 为零但杆臂速度仍非零，进一步说明二者不能混同。

res=2 的非零 bias 首见见 F03 event1962、A04 RV event2058/RD event2066，t=67.400000095、IMU 67.399036、dt=0.0025210000000015498、compensated=true。两种分支的时间、增量、实际 bias/scale、rpy/Cbn 均在小 CSV；不以不同时刻的原值差当作同状态修正差。结论限定为 **OBSERVED_UNCOMPENSATED_RATE_BRANCH_WITH_NONZERO_BIAS**；偏差大小、对 H/R/接受的后果及闭环轨迹/性能影响未计算。

## N15：这两个 C00 对象的已核直接输入未出现缺值触发条件

复用 [QUALIFIED_INPUTS.csv](../../QUALIFIED_INPUTS.csv)、[INPUT_FIELD_QUALITY.csv](../../INPUT_FIELD_QUALITY.csv) 和 [INPUT_USES.csv](../../INPUT_USES.csv)，未再次读取 provider 正文：

- RD `I003`：1,248 行，`provider_status=available` 和 `valid=1` 各 1,248；time、vn/ve/vd、std_vn/std_ve/std_vd、sat_count 必需数值列均 missing/nonfinite/nonnumeric=0，缺列和畸形行均 0。
- RP `I004`：63,278 行、source_status=active 全部 63,278；time、roll_rad、pitch_rad、std_roll_rad、std_pitch_rad 五列均 missing/nonfinite/nonnumeric=0，缺列和畸形行均 0。
- `INPUT_USES` 的两个 run 共用相应 input_id，recorded/newly_verified hash 为 MATCH。F03 配置关闭 RP/RD；A04 实际接受 RP 1,369 次、RD 1,069 次。文件有 63,278/1,248 行不能当作接受次数。

因此可记 **MISSING_NUMERIC_TRIGGER_NOT_PRESENT_IN_THESE_PINNED_INPUTS**。这不撤销旧 loader 将缺字段默认零的代码缺陷，也不外推其他 case/provider，不能由“本输入没有缺值”宣称 loader 已修好。真实数值 0 与缺值仍分开。输入生成语义与历史继承见 [INPUT_LINEAGE.md](../../INPUT_LINEAGE.md)；本简报没有重新运行 raw 到 provider 的生成链。

## N01/N02：实际倾斜存在，几何与影响证据尚未闭合

以下为保存的 SCHEDULE_RECEIPT 原范围，分母为每对象全部 **1,369 次 yaw attempt**，其中接受 1,348、原硬门拒绝 21；不是只对接受子集的范围。

|对象|roll 最小/最大 (rad)|pitch 最小/最大 (rad)|来源|
|---|---|---|---|
|F03|[-0.13662532248642598,0.1946137669739696]|[-0.11067694519215508,0.0904530210847317]|RUN_00003_SCHEDULE_RECEIPT.json|
|A04|[-0.1581465451482954,0.17303886892505596]|[-0.08343281105276355,0.07265284012476474]|RUN_00006_SCHEDULE_RECEIPT.json|

这是原滤波器实际名义姿态，不是 error_series 中的 roll_err/pitch_err，也不是真值。两个方法已闭环形成不同状态，不能跨方法直接当同状态反事实。冻结 ca73 的标量 yaw 代码预测 `pvacur_.euler_rad[2]`，残差 wrap(pred−obs)，H 只设 PHI_z=-1；本简报未改这些公式。现有实际非零倾角支持 **ACTUAL_TILT_CONDITION_OBSERVED**，但不单凭这些范围重算投影差、雅可比差或宣布有可测性能损害。

具体缺口保留：

1. 此次观察 GNSS 结构没有同历元 GNSS2−GNSS1 三维 raw baseline、原配对 iTOW、相应协方差；`baseline_vector=NOT_IN_GNSS_STRUCT`。不能从 yaw/error 或 `[0.03,0.03,-0.3]` IMU–主天线杆臂反推双天线安装向量。
2. 已给定坐标变换/安装约定没有在本小项做独立物理测量复核；需要有明确天线顺序、b_body、安装轴和同步的原测量/标定证据，不能按 RMSE 挑符号。
3. 当前小 witness 的 yaw 接受记录不含该 yaw 的完整 H/P/dx；虽然完整观察事件已保存矩阵，本短报没有重扫。N02 同事件交叉协方差作用、接受子集的倾角范围及实际更新差尚未在本小表求出。
4. 参考独立性、真实到达时刻、参考点/时间对齐和 STD 坐标传播没有由这些重放状态证明。`available_time=UNKNOWN`，不把测量时刻当到达时刻；不以闭环估计姿态代替独立安装/姿态证据。

旧 N01/N02/N11/N15 findings 保留；本小项只把“适用”推进到上述具体条件和输入排除范围，不回写原性能表，不形成修正后的 RMSE。脚注口径：SAME_BATCH_SNAPSHOT_FIELDS 的 `source_value` 为原 JSON 值的无损转录，源位置指向小 SCHEDULE_WITNESSES.json；完整事件仅作为记录来源路径，未由本 worker 重读。
