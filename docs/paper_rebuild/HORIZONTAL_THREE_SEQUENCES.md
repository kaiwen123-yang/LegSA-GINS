# 三序列外部横向对比：H-EXT-02 硬停部分记录

状态：`HARD_STOP_EVALUATOR`。14 个比较 native 均已完成并归档；评估预算 28 个槽位中，17 个已调用，16 个通过，1 个失败，11 个未调用。第 17 次评估触发冻结的一致性门，随后停止；没有评估重试、参数调整或继续生成完整对比产物。本文件是失败交接与已通过项的部分记录，不能作为三序列横向对比完成证明。

科学代码冻结 commit：`c9e5133d244e0e3ab1e1385f322fbbf5948ee6d5`。合约 SHA-256：`bbe0ca4d82fead5bc154281d0c53df5445b08e27e7e0c34fd22a9efd40712f3d`。协议 v2.1 仍是论文唯一主链，F04 仍是 Proposed；本任务仅新增外部比较证据，不改变冻结主链。授权定义见 [H_EXT_CONTRACT_V1.yaml](../../configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml)，执行与交接登记见 [H_EXT_02_EXECUTION_RECORD.md](hext/H_EXT_02_EXECUTION_RECORD.md)。

## 1. 运行与停止状态

本文件使用 `<HEXT_ROOT>` 表示 `<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/`，使用 `<HEXT_SCRATCH>` 表示 ignored local YAML 的 `hext_scratch`。路径通过 `configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml`与 [序列 registry](../../configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml)解析。运行记录位于 `<HEXT_ROOT>/04_NATIVE_RUNS/`，成功评估记录位于 `<HEXT_ROOT>/07_OFFLINE_EVALUATION/`。

| 序列 | native 完成并归档 | 计划评估 | 已调用 | PASS | FAIL | NOT_RUN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BY2 | 2 | 4 | 4 | 4 | 0 | 0 |
| BY2H | 8 | 16 | 13 | 12 | 1 | 3 |
| BY2O | 4 | 8 | 0 | 0 | 0 | 8 |
| 合计 | 14 | 28 | 17 | 16 | 1 | 11 |

BY2 的 LC01/EXT05C 文献默认值在新 H02 路径上另有 2 次身份复验，两个 exact NAV 均与冻结原文件逐字节相同；该验证为 2 native / 0 evaluator / 0 trace，单列于上述 14 个比较 native 之外，不新增 BY2 文献性能行。对应 SHA-256 为 LC01 `ccd25c2e1309ba2870e57e2208f476a6b48eaba69f0d038f26be2f168bb2c695`、EXT05C `915192d6fcefaf7bef33c4028b571d1b723f7e0759063e2955aebd3d1ee7ace8`。

| 失败检查 | 原始结果 |
| --- | --- |
| 槽位 | `BY2H / EXT05C-S / FILE_START / v3` |
| evaluator 进程退出码 | `0` |
| capture `horizontal_max_m` | `3.0600994997077376e17` |
| capture `up_max_m` | `5.487427392938392e17` |
| capture `yaw_max_deg` | `1.003047600534046e-08` |
| 位置一致性阈值 | `0.01 m` |
| yaw 一致性阈值 | `0.01 deg` |
| capture `matched_epoch_count` | `59934` |
| capture `passed` | `false` |
| trace 哈希 | 与冻结声明相符 |
| trace 打开次数 | `1`，评估器单句柄 |
| 后续动作 | 停止；无重试、无参数修改、无后续评估 |

以上是 capture 一致性检查值，不能转写为方法的 RMSE。退出码为 0、trace 身份正确、native 完成均不替代 capture 门。失败证据原始位置为 `<HEXT_SCRATCH>/H_EXT_02/07_OFFLINE_EVALUATION/v3/BY2H__EXT05C-S__FILE_START/EXACT_EVALUATOR_OUTPUT/EVALUATOR_CAPTURE.json` 及同次评估的访问审计。保留该失败原貌，不从这些值推断未经核验的数值故障原因。

BY2H 已完成评估的组合为 LC01、EXT05C、LC01-S 各自的 FILE_START / CONTRACT_START × v3 / v2，共 12 项。EXT05C-S 的 FILE_START/v3 失败；FILE_START/v2 和 CONTRACT_START/v3、v2 共 3 项未运行。BY2O 全部 8 项未运行。

## 2. 已通过评估的局部记录

以下是 16 个成功 `EVALUATION_RESULT.json` 的直接摘录，不是完整三序列主表，也不代表整项 H-EXT-02 通过。每个单元按 **H / 3D / Up / yaw / yaw P95 / roll / pitch / coverage** 排列；前三项为位置 RMSE，单位 m；yaw、roll、pitch 为 RMSE，yaw P95 为绝对误差第 95 百分位，单位 deg；coverage 无量纲。显示值四舍五入至 6 位小数，完整精度与其他指标保留在各自 JSON。

### v3：8 个通过项

| 序列 | 配置 | 起点 | H / 3D / Up / yaw / yaw P95 / roll / pitch / coverage |
| --- | --- | --- | --- |
| BY2 | LC01-S | FILE_START | 0.103525 / 0.112982 / 0.045250 / 1.539239 / 2.842700 / 4.243478 / 2.990040 / 1.000000 |
| BY2 | EXT05C-S | FILE_START | 0.114228 / 0.123518 / 0.046998 / 9.722098 / 12.493120 / 4.423635 / 3.090938 / 1.000000 |
| BY2H | LC01 | FILE_START | 0.097453 / 0.112212 / 0.055628 / 2.173936 / 4.450770 / 1.186399 / 2.515824 / 1.000000 |
| BY2H | LC01 | CONTRACT_START | 0.074606 / 0.087026 / 0.044804 / 2.208612 / 4.538323 / 1.167988 / 1.825420 / 1.000000 |
| BY2H | EXT05C | FILE_START | 0.197284 / 0.212416 / 0.078735 / 55.609934 / 85.609983 / 1.769179 / 1.995584 / 1.000000 |
| BY2H | EXT05C | CONTRACT_START | 0.069190 / 0.085745 / 0.050646 / 20.108223 / 25.624327 / 1.039422 / 1.819008 / 1.000000 |
| BY2H | LC01-S | FILE_START | 0.106709 / 0.114216 / 0.040726 / 1.794054 / 3.460853 / 4.487734 / 2.585795 / 1.000000 |
| BY2H | LC01-S | CONTRACT_START | 0.083733 / 0.092954 / 0.040364 / 1.943003 / 3.757132 / 4.364596 / 2.725064 / 1.000000 |

### v2：8 个通过项

| 序列 | 配置 | 起点 | H / 3D / Up / yaw / yaw P95 / roll / pitch / coverage |
| --- | --- | --- | --- |
| BY2 | LC01-S | FILE_START | 0.176521 / 0.382728 / 0.339590 / 1.539239 / 2.842700 / 4.243478 / 2.990040 / 1.000000 |
| BY2 | EXT05C-S | FILE_START | 0.176732 / 0.375457 / 0.331260 / 9.722098 / 12.493120 / 4.423635 / 3.090938 / 1.000000 |
| BY2H | LC01 | FILE_START | 0.176895 / 0.377758 / 0.333780 / 2.173936 / 4.450770 / 1.186399 / 2.515824 / 1.000000 |
| BY2H | LC01 | CONTRACT_START | 0.165280 / 0.370420 / 0.331502 / 2.208612 / 4.538323 / 1.167988 / 1.825420 / 1.000000 |
| BY2H | EXT05C | FILE_START | 0.233234 / 0.411502 / 0.339022 / 55.609934 / 85.609983 / 1.769179 / 1.995584 / 1.000000 |
| BY2H | EXT05C | CONTRACT_START | 0.172680 / 0.374217 / 0.331993 / 20.108223 / 25.624327 / 1.039422 / 1.819008 / 1.000000 |
| BY2H | LC01-S | FILE_START | 0.186355 / 0.381061 / 0.332384 / 1.794054 / 3.460853 / 4.487734 / 2.585795 / 1.000000 |
| BY2H | LC01-S | CONTRACT_START | 0.174088 / 0.374664 / 0.331763 / 1.943003 / 3.757132 / 4.364596 / 2.725064 / 1.000000 |

每行原始记录：`<HEXT_ROOT>/07_OFFLINE_EVALUATION/{v3,v2}/<SEQ>__<CONFIG>__<START>/EVALUATION_RESULT.json`。BY2 每项 `output_epoch_count=matched_epoch_count=58014`；BY2H 每项均为 `59934`。`coverage_ratio=1` 表示该方法自身已输出 NAV 历元的匹配比例，不表示不同方法拥有相同时间支撑，也不是对共同参考历元全集的覆盖率。

### BY2 预注册版本选择：部分结果足以确定，三序列交付仍未完成

BY2 LC01-S 的 v3 yaw RMSE 为 `1.5392385536245534 deg`，冻结 P-07 LC01 文献值为 `2.9948274600591076 deg`。依预注册的 BY2 选择规则，选择结果为 **S**。此选择不是调参，也不允许按序列另外选择版本。预定正文统一使用 S、另一版本完整列入补充材料的三序列交付尚未完成；BY2O 没有新评估值，不能声称 S 已在三序列上得到比较验证。BY2 文献行继续引用 P-07 冻结值，不使用身份复验输出重新评估。

BY2H 表内仅有 LC01、EXT05C、LC01-S 的三个有效 FILE_START / CONTRACT_START 对照。LC01 的 v3 yaw RMSE 分别为 2.173936 / 2.208612 deg，EXT05C 为 55.609934 / 20.108223 deg，LC01-S 为 1.794054 / 1.943003 deg。它们是起点诊断的局部事实；缺失 EXT05C-S 对照，不能作为完整起点对照表或完整主结果。未根据该诊断重新选择初始化或改变参数。

## 3. native、IMU 间断与几何状态

D1 按原始相邻 IMU 时间戳判断无效区间；`dt>0.1 s` 的整个源区间不传播，仍在原 GNSS 事件时刻更新，不补点、不增加协方差。无效右端样本不成为保持样本；下一有效源区间仅传播该区间自身 dt，并使用最后保留的间断前样本，之后恢复原方法的前一样本保持方式。原始非正 dt 样本同样丢弃且不回拨状态时钟；只有倒退后续正区间与已处理时间线重叠才记技术失败。本次实际源数据没有非正 dt。

D2 的 FILE_START 在文件首个 common GNSS1 HPPOSECEF 历元初始化，固定 NED 原点同样使用该文件首个 common 历元；标定仍取 IMU 文件前 5 s。本次三序列静态检查均通过，没有触发静态失败后的主行替换。BY2H 的 CONTRACT_START 仅为诊断，在首个不早于 413 s 的 common 历元初始化，位置用该历元、yaw 用该历元及其后首个有效基线、初速度为零；固定 NED 原点及前 5 s 标定不变。

| 序列 / 起点 | 配置数 | 初始化相对秒 | 每配置窗口 NAV 行数 | 原始 `dt>0.1 s` 数 | 每配置间断内 GNSS 更新数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BY2 / FILE_START | 2 | 55.800000 | 58014 | 0 | 0 |
| BY2H / FILE_START | 4 | 401.200000 | 59934 | 4 | 31 |
| BY2H / CONTRACT_START | 4 | 413.000000 | 59934 | 4 | 1 |
| BY2O / FILE_START | 4 | 3143.400000 | 78441 | 6 | 5 |

原始间断相对秒以各序列自己的 base_time 为零点，显示至 6 位小数：

| 序列 | 间断起点 s | 间断终点 s | 时长 s | 相对评估窗 |
| --- | ---: | ---: | ---: | --- |
| BY2H | 407.017058 | 411.757064 | 4.740006 | 窗前 |
| BY2H | 411.757064 | 412.479048 | 0.721983 | 窗前 |
| BY2H | 412.479048 | 413.037092 | 0.558044 | 跨窗口起点 |
| BY2H | 414.905067 | 415.080782 | 0.175715 | 窗内 |
| BY2O | 3240.749053 | 3241.017060 | 0.268008 | 窗内 |
| BY2O | 3301.289052 | 3301.399059 | 0.110007 | 窗内 |
| BY2O | 3362.013048 | 3362.359046 | 0.345999 | 窗内 |
| BY2O | 3392.541158 | 3392.649062 | 0.107904 | 窗内 |
| BY2O | 3483.751066 | 3483.917063 | 0.165997 | 窗内 |
| BY2O | 3544.833067 | 3544.987060 | 0.153993 | 窗内 |

14 个 native 均保留 `<HEXT_ROOT>/04_NATIVE_RUNS/<SEQ>/<CONFIG>/<START>/GAP_EVENTS.json` 与 CSV，逐间断记录原始端点、时长、窗口分类、GNSS 更新次数、位置/速度/yaw 状态变化和恢复约定。初始化之前未处理的间断，其状态变化为 `null`，不替换为零。这里记录的是 native 元数据；完成间断处理不保证后续评估通过。

| native 几何审计 | 状态 | 可报告统计 |
| --- | --- | --- |
| BY2 LC01-S / FILE_START | PASS | median `1.5735499467836576 deg`；P95 `6.497373860597976 deg` |
| BY2H LC01、LC01-S / 两种起点 | UNAVAILABLE | `geometric audit baseline has inadequate horizontal length`；median/P95 未产生 |
| BY2O LC01 / FILE_START | PASS | median `0.9546242815300161 deg`；P95 `4.401636337504192 deg` |
| BY2O LC01-S / FILE_START | PASS | median `2.6038946687862676 deg`；P95 `9.66122113611422 deg` |
| EXT05C、EXT05C-S / 所有已完成 native | NOT_APPLICABLE_SINGLE_RECEIVER | 单接收机诊断，无双接收机基线几何统计 |

BY2H 的冻结审计要求水平基线长度大于 0.1 m；该前置条件未满足，审计在计算 median/P95 之前结束。因此只能报告 `UNAVAILABLE` 和原错误，不能虚构统计值或写成零误差。D6 所登记的上层可用性分类 `AVAILABLE_GEOMETRIC_AUDIT_FAIL` 与 native 原始 `UNAVAILABLE` 分属不同字段，不改写 native JSON，也不等价于已计算出的 median/P95 超阈值。完整聚合因硬停未执行。

## 4. 三条序列的事实性说明

**BY2。** 本次完成 LC01-S、EXT05C-S 两个比较 native 与各自 v3/v2 共 4 次评估；该 IMU 文件没有 `dt>0.1 s` 间断。LC01-S 的 BY2 v3 yaw RMSE 满足预注册 S 版本选择条件。文献默认路径的两次新身份复验只证明 exact NAV 字节继承，不生成新的文献性能行，不构成三序列普遍优越性结论。

**BY2H（same-day poor-heading run）。** 四个配置各完成 FILE_START 和 CONTRACT_START，共 8 个 native；源数据含 4 个间断。前三配置的两种起点评估共 12 项通过，EXT05C-S FILE_START/v3 在 capture 位置一致性门失败，之后 3 项未运行。LC01/LC01-S 的原生几何统计因水平基线前置条件不满足而不可得。保留起点诊断的已有数值，不从失败项产生准确度或失效原因结论。

**BY2O（same-day single-antenna occlusion run）。** 四个 FILE_START native 已完成，IMU 源数据有 6 个间断；评估器未调用，准确度指标为 `NOT_RUN`。冻结状态记录的 GNSS2 RTK float 为 57 个历元，不是数据流中断；HPPOSECEF 的 pAcc 超 BY2 中位数 3 倍计数为 52 个 5 Hz 历元，统计源和采样率不同，不能将二者当作同一个 57 历元集合。本次没有完成遮挡分段性能结论。

## 5. 未完成产物与不可比项

| 预注册产物 | 本次状态 / 原因 |
| --- | --- |
| 完整三序列 v3 主表（含文献与 S 两版） | `NOT_PRODUCED_HARD_STOP` |
| 完整三序列 v2 平行表 | `NOT_PRODUCED_HARD_STOP` |
| 完整文献版补充表、统一版本正文对比 | `NOT_PRODUCED_HARD_STOP` |
| 完整 delta / body-frame bias 汇总 | `NOT_PRODUCED_HARD_STOP` |
| BY2H 四配置 FILE_START / CONTRACT_START 完整对照 | `NOT_PRODUCED_HARD_STOP`；仅 §2 三对局部记录可用 |
| BY2O 遮挡分段 `3369.94–3411.95 s` | `NOT_PRODUCED_HARD_STOP` |
| BY2O 遮挡分段 `3495.94–3508.94 s` | `NOT_PRODUCED_HARD_STOP` |
| 新图 `FIG02S` | `NOT_PRODUCED_HARD_STOP` |
| `<HEXT_ROOT>/08_AGGREGATE/` 完整聚合 | 未生成 |
| `09` LegSA 间断行为诊断 | `UNAVAILABLE`：冻结完整 NAV 不在保留目录；不以稀疏 NAV 替代 |

09 的只读登记已归档至 `<HEXT_ROOT>/09_LEGSA_GAP_DIAGNOSTIC/LEGSA_GAP_DIAGNOSTIC.{json,csv,md}`。四项均为 `UNAVAILABLE`，原因为 `Exact frozen native NAV is absent or symlink; no substitute`；各间断条目标记 `WHOLE_NATIVE_NAV_ITEM_UNAVAILABLE`。

| 09 序列 | 冻结方法 | 与窗口相交的原始间断数 | 完整 NAV 诊断 |
| --- | --- | ---: | --- |
| BY2H | F04 | 2 | UNAVAILABLE |
| BY2H | A04 | 2 | UNAVAILABLE |
| BY2O | F04 | 6 | UNAVAILABLE |
| BY2O | A04 | 6 | UNAVAILABLE |

这些缺失项只作可用性登记，不重跑 LegSA，不以 `NAV_10HZ` 或 P-06 输出替代。内部体坐标偏差若缺少同一冻结身份的完整证据也保持 `UNAVAILABLE`。16 个通过项、1 个失败 capture 以及 11 个未运行槽位均保留各自身份；不存在用旧结果填补本次未运行槽位的对比表。

下表为冻结 **BY2 注册表上下文**，不是本次新增主性能表。来源 P-07 `HORIZONTAL_TABLE_V3.csv`，SHA-256 `d91f53aaf855efc8c533a6f15a9c6c933e87bafb2bcc9bd169ba862163c82c01`；原因字符串逐字保留。BY2H/BY2O 本次未执行这些方法，不能把 BY2 原因推演为 H/O 的运行结果。

| 方法 | 冻结 BY2 不可比原因 | 本次 BY2H / BY2O |
| --- | --- | --- |
| EXT01 C-LAMBDA | `UNAVAILABLE_NO_IMU_POINT_NAV` | NOT_RUN / NOT_RUN |
| EXT02 C-WLS | `UNAVAILABLE_NO_IMU_POINT_NAV` | NOT_RUN / NOT_RUN |
| EXT03 Yang 2024 DD-KF + M-LAMBDA | `UNAVAILABLE_NO_IMU_POINT_NAV` | NOT_RUN / NOT_RUN |
| EXT04 constrained FAR/PAR | `UNAVAILABLE_NO_IMU_POINT_NAV_ZERO_ACCEPTED_EPOCHS` | NOT_RUN / NOT_RUN |
| Hartley contact-aided InEKF | `UNAVAILABLE_ABSOLUTE_METRICS_UNANCHORED_TRANSLATION_AND_YAW_GAUGE` | NOT_RUN / NOT_RUN |
| LC02_GINAV | `UNAVAILABLE_EVALUATION_FAILED` | NOT_RUN / NOT_RUN |
| EXT05B | `UNAVAILABLE_NOT_IMPLEMENTED` | NOT_RUN / NOT_RUN |

LC02_GINAV 原记录状态为 `FAILED_EVALUATOR`，failure 原字符串为 `External evaluator audit failed: `（冒号后一个空格）。缺少兼容 IMU-point NAV、评估失败或未实现均不代表零误差，也不从注册表中删除方法。

## 6. 限制项

共享参数版本 S 只施加预注册的陀螺 PSD、加计 PSD 与加计标度；陀螺 `arw=0.985 deg/sqrt(h)` 对应三轴 PSD `8.209651003126647e-08 rad^2/s`，加计 q 与 `(vrw/60)^2` 互验，标度 `1.0308398903907543` 沿 V2s 已安装 FRD 向量的约定施加。D1 间断策略对本次 H02 各配置统一生效。方法仍保持各自的信息结构：LC01/EXT05C 使用 `R=pAcc^2 I_3`、无零偏状态；未改初始协方差、过程噪声注入方式、静态标定规则或几何阈值。因此“共享参数”不等价于两算法完全同构，也不能将观察到的差异单独归因于一个参数。

陀螺随机游走参数的可辨识性不足同时限制 LegSA 与外部 S 版本，不能只作为一侧方法的限制。静态一致性和输入标定不能替代对该参数的独立辨识；本次不按结果调参。配置差异详见 [H_EXT_CONFIG_PARITY_AUDIT.md](hext/H_EXT_CONFIG_PARITY_AUDIT.md)，序列原始探针详见 [H_EXT_01_AUDIT_PROBE_ADAPTER.md](hext/H_EXT_01_AUDIT_PROBE_ADAPTER.md)。

参考量的正文表述沿用冻结约定：*the fused navigation solution output directly by the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2); the estimator under test never reads it (file-access audit).* 它不是独立真值。trace 只属于离线评估；native 的输入选择、初始化、参数和间断处理不读取 trace。外部评估继续沿用 `STD: OMITTED_AS_FROZEN_EXTERNAL_CONTRACT`，不新增完整协方差或不确定性校准已验证的结论。

### 写法建议

论文方法名沿用 [CONVERSATION_HANDOFF.md §§2–4](CONVERSATION_HANDOFF.md)：F01 **Single**、F02 **Dual-basic**、F03 **Backbone**（消融，不称 strong baseline）、A04 **Core / no-SA**（保留 v1 决策与消融身份）、F04 **Full / Proposed**（协议 v2.1 唯一论文主链）。BY2H/BY2O 分别采用 same-day poor-heading run / same-day single-antenna occlusion run，不扩大为跨平台或独立环境泛化结论。所有关于三序列外部准确度与正文版本的完整主张均待缺失证据获得另行授权后才可能闭合。

本次交接类别为 `HARD_STOP_PARTIAL_EVIDENCE`：移交冻结代码身份、已完成 native、16 个通过评估、原始失败证据及未运行槽位清单，不宣称完整实验、完整图表或三序列交付完成。最终包约定命名为 `<HANDOFF_ROOT>/hext_three_sequences_handoff.zip`；其真实状态与 receipt 身份由执行记录登记。本文不预填包哈希，不授予重试或继续执行权限。
