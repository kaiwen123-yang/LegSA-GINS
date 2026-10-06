# Protocol V3 方法与指标说明书

本小项核实“每个名字实际打开了什么、已有数值如何定义”。依据是已读取的 11 份 BY2 C00 runtime config、11 份 native 有效回显、F04 的 v2/v3 评价记录与 capture，以及冻结评价器和调用链源码。没有运行解算器、provider、评价器、聚合入口、bootstrap，没有读取 reference 或 error_series 正文，没有新算 RMSE。配置明细见 [METHOD_CONFIGS.csv](METHOD_CONFIGS.csv)，每项定义的路径、函数和行号见 [METRIC_SOURCE_MAP.csv](METRIC_SOURCE_MAP.csv)。其余结果入口沿用 [V3_RESULTS_START_HERE.md](../v3_results/V3_RESULTS_START_HERE.md)。

源码阅读快照为 `d9763ea40fd19963a71321c2a6ca930a022c159d`。本次对 8 个核心调用链文件做了小文件字节比较，均与 runner freeze `7d43b9af26120ed5dde21f53e515386361072ba6` 相同，文件名单和比较状态在来源映射中。冻结评价器则直接读取合同和实际 capture 所指向的外部 `.py` 文件；其 recorded SHA-256 为 `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`，本小项未重新计算该 hash。这里的源码相同不代表算法数学正确或物理参考无误差。

## 1. 11 个物理配置与五配置展示

`AB` 后四位依次是 **RD、SA、RP、HV**：Raw Doppler 辅助速度、source-aware 权重、Go2 roll/pitch 弱先验、Go2 水平速度弱先验。位为 1 表示相应模块开关启用，不保证每个历元都有输入或通过门控。RV 是接收机速度观测开关，独立于 RD，也不在 AB 四位里。[M01–M03]

| 方法 | 实际 profile / 别名 | 持续双天线 yaw 更新 | RV | RD | SA | RP | HV | 航向回显 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| F01 | single_antenna_EKF | 0 | 1 | 0 | 0 | 0 | 0 | basic=0，scheme-C=0 |
| F02 | basic_dual_yaw_EKF | 1 | 0 | 0 | 0 | 0 | 0 | basic=1，scheme-C=0 |
| F03 | AB0000；A02 | 1 | 1 | 0 | 0 | 0 | 0 | basic=0，scheme-C=1 |
| F04 | AB1111；A01 | 1 | 1 | 1 | 1 | 1 | 1 | basic=0，scheme-C=1 |
| A03 | AB0111；去 RD | 1 | 1 | 0 | 1 | 1 | 1 | scheme-C=1 |
| A04 | AB1011；去 SA | 1 | 1 | 1 | 0 | 1 | 1 | scheme-C=1 |
| A05 | AB1101；去 RP | 1 | 1 | 1 | 1 | 0 | 1 | scheme-C=1 |
| A06 | AB1110；去 HV | 1 | 1 | 1 | 1 | 1 | 0 | scheme-C=1 |
| A07 | AB1100；去两个 Go2 先验 | 1 | 1 | 1 | 1 | 0 | 0 | scheme-C=1 |
| A08 | AB1000；强基线上加 RD | 1 | 1 | 1 | 0 | 0 | 0 | scheme-C=1 |
| A09 | AB0100；强基线上加 SA | 1 | 1 | 0 | 1 | 0 | 0 | scheme-C=1 |

表中开关均逐配置核对了 YAML 与 `RUN_MANIFEST.json` 的对应有效回显，22 份文件全文已读；原始字段名、值和行号在 CSV 中，不靠方法名推断。五配置展示为 F01/F02/F03/A04/F04，另外六个正式物理配置也存在。F03/A02、F04/A01 是同一物理运行的逻辑别名，不能各计一次。[M01–M03]

F01→F02 同时把 RV 从 true 改成 false，并启用 basic yaw；F02→F03 同时恢复 RV 并启用 scheme-C。它们不是仅添加一个模块的严格单因素梯。11 个 C00 回显的 `common_initialization_dual_yaw_used` 都为 true，F01 也如此；“无持续双天线更新”不能写成“完全没有使用过双天线初始化信息”。回显同时记录 `trace_used_for_initialization=false`，初始化来源字符串保留为 `final_v23_static_contract_a906c3a2`；名字本身不能证明读取了同名算法输出。[M02、M03]

正式 Protocol V3 仍是 **scalar yaw + R5/BOTH_FIXED**：GNSS2−GNSS1 精确配对的 raw HPPOSECEF 5 Hz 标量航向，固定物理方向转换；F04 不是 B3。B3、R5SIGMA、R5W 属于候选/敏感性材料，不能替换正式 F04 身份。冻结合同保留 `heading_std_marker_deg=2.933193`；有效回显显示 F02 及 F03/F04/各消融的这一值为 2.933193，F01 为未用于持续 yaw 更新的 1.5。scheme-C 其他阈值从实际 config 读取，不能把 marker 当成全部历元实际后验标准差。正式 V3 没有据此新增 FGO、QM、contact/FK 机制。[M04]

数据角色也要分开：传播输入是 hash-locked Go2 body IMU；接收机 IMU 不是传播 body IMU。GNSS position、RV、RD 是不同观测来源；RP/HV 是弱先验。Go2 状态不是参考真值，短基线 baseline heading 也须按物理安装转换后才是 body yaw。这里核实模块身份和字段，不据开关宣称保护机制已被因果验证。[M05]

## 2. 协议 V3、评价 v3 与物理点

实验协议版本、评价版本、展示版本和物理运行 ID 是四层身份。同一个 `RUN_00004` 原生输出分别进入评价 `v3`、`v2` 两个槽；这是一次 native、两种评价，不是两次算法运行。MAIN 文件后缀 V3 指评价口径时，也不能覆盖行中其他协议/外部来源的身份。[M06]

原生 NAV 的参考点回显是 `propagation_imu_reference_point`。运行 config 的测量杆臂是 `[0.03,0.03,-0.30] m`，它用于求解器测量模型，不等于评价器点转换。评价 v2 直接使用原生 NAV，保留该物理点差异；评价 v3 另写 NAV 副本，只改变 LLH 三列，把 IMU 点按冻结的几何声明转换至 POI/VRTK 参考点：[M07、M08]

\[
p_{POI}=p_{IMU}+C_b^n[0.03,\;0.03-b_{med}/2,\;-0.30]^T.
\]

`C_b^n=R_z(yaw)R_y(pitch)R_x(roll)`，由该方法自己 NAV 的姿态构成，body FRD→navigation NED；实现把 NED 偏移转至 ECEF 后加到原位置，再转回 LLH。BY2 的既有 `b_med=0.356191491865984 m`，评价杆臂为 `[0.03,-0.148095745932992,-0.30] m`。物理依据是人类冻结的 VRTK 位于两天线中点、等高及 POI→VRTK 零平移声明，不是用 reference 最小化误差拟合出来的结果；声明的实物可靠性仍需独立审核。时间、速度、姿态 token 保留不变，没有额外残差校正。[M07、M08]

两种评价都传入同一原生 STD。v3 未把完整协方差传播到 POI，状态为 `UNTRANSPORTED_STD_DIAGNOSTIC_ONLY`；v2 为 `DIAGONAL_ONLY_NOT_FULL_NEES`。冻结 summary 的 3σ 覆盖率不能直接称为完整 NEES、统计校准通过或完整物理点不确定度。[M09]

## 3. 冻结评价器实际采用的时轴与误差

本说明以实际冻结 `evaluate_nav_trace_kfgins_v2.py` 为准。旧 `configs/paper_rebuild/evaluator_contract.yaml` 写有先 ECEF 插值、最大 gap、重复 reference 时间失败等声明；这些不能自动当作这次冻结 `.py` 已实现的行为。[M10–M13]

1. NAV 读取 time/LLH/roll/pitch/yaw，转 numeric 后共同 `dropna`。reference 选择 time/lat/lon/height/roll/pitch/yaw，若选中列不是 aligned_time，则减固定 `base_time`；七列共同清理后按时间排序。BY2 capture 确認实际使用 `lat/lon/height`，并未选择同文件的 `processed_lat/processed_lon/processed_height`。[M10]
2. 取 NAV 与 reference 的首尾时间交集，保留交集内的 **NAV 时刻**；没有建立独立等间距评价网格。reference 的纬度、经度、高度、roll、pitch 各自 `np.interp` 到 NAV 时刻；yaw 先 unwrap，再插值。随后才把已插值 LLH 转为 WGS84 ECEF，再以首个插值 reference 点建立固定 ENU 坐标系。[M11]
3. `--yaw_truth_mode enu` 下，reference yaw 转为 `(90−yaw_ENU) mod 360` 后与 NAV yaw 作差。roll、pitch、yaw 误差均 wrap 到 `[-180,180)`。E/N/U 误差为 estimate−reference，水平范数为 `sqrt(e_E²+e_N²)`，3D 范数再加 `e_U²`；单位分别是 m 和 deg。[M12]
4. 冻结 `.py` 的这些步骤没有实现 max-gap 剔除，也没有 reference 重复时间 fail 检查。外围 `_support` 要求原生 NAV 全有限、时间严格递增且在合同窗内；一致性检查允许 reference 时间不下降（检查 `<0`）。因此不能把旧 YAML 的理想规则补写成已发生的保障。[M13]

记录示例（原值转录，未本轮计算）：F04 BY2 C00 窗为 `[66.0,340.0] s`；实际 matched 时刻从 `66.005054` 到 `339.997056`。`output_epoch_count=56642`、`matched_epoch_count=56642`、`coverage_ratio=1.0`。`reference_epoch_count=5480` 是合同窗内清理后的 reference 点数，而 capture 的 `reference_cleaned_epoch_count=6040` 是全 reference 支持点数；都不是 RMSE 分母。前者少于 NAV 历元数也不意味着匹配率超过 100%：指标是在插值后的 NAV 时刻上计算。[M14]

`coverage_ratio=matched/output` 只表示**已有输出点**被匹配的比例，不证明请求窗完整覆盖、历元连续或采样密度足够。时间包络、gap 和点密度需要分别核查；插值后的匹配点也不是彼此独立的 reference 测量样本。[M14]

## 4. 单次运行、跨案例与配对的指标分母

| 层级/字段 | 实际定义与单位 | 分母/权重 |
|---|---|---|
| 每运行 `horizontal_rmse_m`（展示别名 `h_rmse_m`） | `sqrt(mean(horizontal_err_m²))`，m | 该运行 matched NAV 历元等权 |
| 每运行 `yaw_rmse_deg` | `sqrt(mean(wrap(yaw_est−yaw_ref)²))`，deg | 该运行 matched 历元等权 |
| 每运行 `yaw_p95_absolute_deg`；冻结 summary 名 `yaw_p95_deg` | `percentile(abs(yaw_err_deg),95)`，deg | 该运行逐历元误差；不是跨运行 RMSE 的 P95 |
| 其他轴 `*_bias_*` / `*_signed_mean_*` | 有符号误差均值 | 同一误差轴逐历元等权；不等于绝对误差 |
| 跨案例 summary `mean` | 选定 metric 的成功运行值的算术平均 | 每个完成案例/种子一票；无历元数加权 |
| 跨案例 summary `median` | 同一组成功运行 metric 的中位数 | 每个完成案例/种子一票；不是拼接后的逐历元误差中位数 |
| 跨案例 `p95` / `maximum` | 同一组成功运行 metric 的 P95 / 最大值 | metric 可以已是运行级 RMSE 或运行级 P95 |
| 跨案例 `worst_5pct_mean` | 最大 `ceil(0.05×finite_count)` 个运行指标的均值 | 原表另列 `worst_5pct_count`；不是单次轨迹最差 5% 历元 |
| 配对 `delta_candidate_minus_reference` | 同 case 的 candidate metric−reference metric | 同域、同评价版本，且两方都 COMPLETED 的案例 |
| 配对 `mean_delta` / `median_delta` / `win_rate` | 配对差均值/中位数；负差获胜占比 | 每个配对案例等权；不是独立新采集轨迹数 |

这些运行级轴/范数统计来自 `_axis_stats`、`_norm_stats`，V3 实际通过 `clean5_parity_p04.evaluation.metrics` 调用；不宜把 Canonical `_compute_result` 的所有额外字段都假定为 V3 已生成。它们使用普通 mean/percentile，不是 nanmean；外层 `metrics` 要求所给 error 表整体有限。IAE/ISE 字段另用时间积分，不能与这里等历元权重的 RMSE 混同。[M15–M17]

跨案例 `mean(RMSE)` 不等于把各案例所有误差拼起来求一次 RMSE。各自成功集也可能不同，两个方法的独立均值差不一定等于它们共同成功集的配对均值差。配对函数显式按 case/method 连接、只保留两方 COMPLETED；CORE 的 case_id 已含退化类型和 seed，域和评价版本在外层分组。负差表示这些误差指标较小。现有 bootstrap 是对配对**案例差**有放回抽样 10000 次、PCG64 seed `20260904`、取 2.5/97.5 百分位，mean 与 median 的区间是两个不同目标；本小项没有重算。它未自动处理共享同一 BY2 原始轨迹、故障族或种子层级相关性，不能据此称为跨新场景泛化置信区间。tie 容差为 `1e-12`。[M18、M19]

百分比必须同时写出基准和分母：若称“相对变化”，约定为 `100×(candidate−reference)/reference`；若称“误差降低百分比”，符号相反。两种表述都以指定 reference 指标为分母；分母为 0、缺失或状态不可用时不计算，不填 0%。逐配对百分比的均值与两个组均值的百分比变化也不是同一量。本说明没有新增百分比结果；后续转录既有百分比仍须沿原字段的实际定义。[M25]

失败保留在注册分母、故障分类与状态表中，但没有伪造有限误差值。`absolute_summary` 的 `registered_count` 包含所有注册行，有限统计只用 `COMPLETED`，`failure_rate` 为 ALGORITHM_FAILURE 数/注册行数，其他 unavailable/not-applicable 单列。后续统一故障分类可与 native/evaluator 终态不同，应一起读取各自版本；不能把没有 RMSE 当成 0，也不能把有限统计的好坏替代完成率。[M20]

BY2O 段内/段外表重用既有 error 序列，原规则为全窗闭区间、遮挡闭区间 `[3369.94,3411.95]` 与 `[3495.94,3508.94]`，`inside_union` 是并集，`outside` 是全窗减该并集。段内指标以该段实际历元计，不是从全窗 RMSE 按时长线性拆分；不同段和不同方法均须看自己的 `count`/时间支持。[M21]

全窗、故障注入窗和故障结束后的恢复窗是三种支持集。V3 的实际 `window_metrics` 只产生本次评价支持上的全窗统计和点数，并不因某行有 fault/seed 标签就自动生成 `during`、`post` 或恢复时间指标。Canonical 源码虽另有事件窗函数，V3 这条调用链没有调用其 `_compute_result`；不能把别的协议字段补到 V3。读取故障窗/恢复表须有该表自己的区间、端点、恢复判据及源列，缺失就保留缺失。[M16、M26]

自然三序列没有凭空增加 seeds；541 的跨例分母含一个 C00 与退化案例，A1/A2 是另一注册域；别名、评价双版本、PNG/PDF/SVG 导出均不能增加物理运行分母。外部方法、旧协议和候选敏感性行保持自己的协议、窗口、评价和来源，不能混入 V3 自有运行分母。[M06、M22]

## 5. reference 的解释边界与字段身份

这里的 reference/图中 Truth，是商用低成本双天线 GNSS/INS 接收机 Fixposition Vision-RTK 2 直接输出的融合导航解；它不是独立测量真值。文件访问审计的“估计器不读取该解”回答在线泄漏问题，不能证明 reference 无误差或 reference 误差独立；raw/status 观测与该融合解还可能共享设备及观测来源。Go2 状态也不是真值。故这些 RMSE 是相对于该 reference、指定物理点和时间支持的差异。[M05、M23]

原记录中 `duration_sec` 等字段不一定存在；本说明没有用端点差补写。有效回显里的 `source_commit=5a4471efd4fcfcdc31e258a677af354c652ff16f`、外层 V3 summary 的 `code_commit=7d43b9af26120ed5dde21f53e515386361072ba6`、方法身份表的冻结 native 源码/二进制身份是不同字段。本 CSV 原样分列保留，不把其中任意一个覆盖成“唯一真实提交”，其历史来源解释留给后续身份审核。[M03、M24]

当前结论只到字段和静态调用语义已核实。误差序列能核查已保存误差的统计，不能单独恢复失去的完整 NAV/STD、门控触发、传播状态或证明源模型数学正确。后续逐组解释与保留时序核对另行记录，不覆盖本说明的证据深度。
