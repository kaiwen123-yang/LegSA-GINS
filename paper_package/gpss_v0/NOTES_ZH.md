# 长版母稿逐节说明与作者决定项

本稿保留主表、失败、反例和不确定度。正式结果没有重算；新图仅画既有误差或表内数值。数字的逐出现位置索引见本文末尾及 NUMBER_LEDGER.csv；表格的来源、行选择和格式化见 TABLE_MAP.csv。引用先使用主题明确的 [REF: …]，不补造书目。

## 标题与总体写法

采用指定第一个标题。另两个备选为：

1. Short-baseline dual-antenna GNSS/INS navigation on a walking robot with receiver-state-gated heading and redundant velocity aiding
2. Resilient GNSS/INS navigation for quadruped robots with a 0.35 m dual-antenna baseline: design and a 541-case fault evaluation

【待拍板】沿用 GPS Solutions 长版结构，正文为作者–年份引用占位，参考文献尚未由作者确认。没有为满足页数压缩必须展示的内容。

## Abstract 与第 1 节

摘要写平台、四项构成、三序列结果、LC01 区间判词、BY2O 主段、A2 和全部失败分母。数字来自 MAIN_TABLE_V3 的各序列主行、UNC_DISTINGUISHABILITY 的 LC01-F04/full/yaw 行、BY2O_SEGMENT_TABLE 的 primary 行及 DEGRADATION_MANUSCRIPT 的 A2 行。固定率上限使用 RTKLIB BY2H 的 availability=0.132593 换成近似整数百分数，不能将 EXT01/EXT02 的所有 valid 输出率解释成整数固定率。

引言按 C1（航向进入条件）、C2（速度辅助冗余）、C3（证据与分母）展开。所选写法是“usable heading”；另一种可行但本证据不支持的写法是“普遍优于所有外部方法”。后者被 BY2O 全窗、LC01-S 及俯仰反例排除。

## 第 2 节

按双天线、GNSS/INS、腿式状态估计、质量与残差检查四部分组织。书目来自 HX_INVENTORY 的 reference 字段，按原文放入 REFERENCE_REQUESTS。没有从其旧结果列取性能数字。

【待拍板】提示词要求所有外部方法都使用作者代码，但库存明确包含本项目的文献复现和官方库两类身份。因此稿中写“available original implementations are kept unmodified”，其余保留实际实现身份；不能把全部 EXT01–EXT04 与 LC01 都称为论文作者官方代码。

## 第 3 节

T01 的 F04 历元数选 MAIN_TABLE_V3 的 matched_epoch_count；路程解析 HX05 主表 LEG-DR 的 reference_path_length_m；速度和偏航率来自 UNC01 §3 已有摘要，未从 provider 再计算。窗长为端点相减。正文明确 BY2H 使用合约窗。

几何采用 GNSS1 右、GNSS2 左。基线指向 FLU 的 +Y，在 FRD 中则是 −Y，避免把左右约定与 FRD 混写。b_med 从 HX05_PREREG 的完整数值舍入，杠杆来自合约；图 1 是示意图，不能替代安装尺寸图。

【待拍板】时标要求中的 0.205 s 未在指定 closeout 文件中找到同值。CLEAN5_PARITY_PLAN §B.1 给出的 sys−header 均值是 0.206685656/0.206682866/0.206804496 s。没有把其他位置残差中的相近数值当作时标证据；保留 [NEED]，现正文描述改用观测历元标签。

【待拍板】配置声明 500 Hz，但它不能代替采集流实际输出率。正文留 [NEED]；不打开 IMU 数据重新统计。

参考描述逐字使用指定句，并说明原始 GNSS 与融合参考来自同一单元、参考非独立。另一种较短写法只写“commercial reference”，但会遗漏依赖关系，未采用。

## 第 4 节

公式逐项对应 gi_engine.cpp 的预测、Joseph 更新、位置杠杆、yaw 残差符号和状态反馈。HV 的 FLU→FRD、负 pitch 及旋转次序取指定 sensor-correction 节；source-aware 用 metadata 与 innovation 两分支的最大 inflation，并同时受 source/global cap 约束，不缩小 R。

T02 从 methods.yaml 和 canonical ablation 映射转写开关。F02 不启用 receiver velocity；F03 启用该路径和门控，但不启用 RP/HV/RD/SA。因此没有采用“F02→F03 单独证明 RP”的写法。消融 bits 的 RP 是后续层的真实开关，不能从错误口述补入 F03。

【待拍板】校准常数只在 S1，门控阈值按要求在方法中给出。S1 参数保留原字面精度，包括 2.933193 标记；对参数强制三位小数会损害复现，三位小数仅用于结果表。

## 第 5 节

区分每方法的原始评估支撑、线性参考插值与两方法误差序列的精确共同历元。T03 从故障 YAML 按 family 选型并计数；S2 保留全部类型和锚点。A1/A2 明确为注入中断，不写成自然实录。

UNC03 §1 原文完整保留。随后加数学限定：共同加性误差 c 在两个带误差量的差中抵消，但平方差含 2c(a−b) 交叉项，因此不能声称在 MSE/RMSE 差中一般严格抵消。另一写法是直接改掉指定原文；因本任务要求逐字使用而未采用。

【待拍板】指定原文的 “identical for all thirteen estimators” 是概括性写法；源摘要实际为 BY2 13 个、BY2H/BY2O 各 12 个，fast std 也并非逐值相同。“about half” 对 BY2/BY2H 的描述不能泛化到 BY2O。请作者后续修改原文时一并收紧这些句子。现稿不据此进行方差扣除。

## 第 6 节

6.1：T04 各序列 F01/F02/F03/A04/F04、LC01、EXT05C；外部 BY2H 限 CONTRACT_START，其他限 FILE_START。F04–LC01 的负向区间由 UNC 配对表 LC01−F04 两端取负并交换，DERIVED 账本记录输入 claim_id。LC01-S 不替换主行。

6.2：T05a 只选 evaluator_contract_v3、primary/secondary/outside，保留内部 PROTOCOL_V3 与 LC01 文献行。源文件同时含另一评估口径，初稿重复选行已在首次提交前修正。T05b 是航向法切片。F04 主段更低、段外 LC01 更低都写明。

6.3：配对 F03−F02 实际约 −0.316/−0.342°，按差值两位显示 −0.32/−0.34°。提示词的 −0.35° 对应 F04−F02，不能套用到 F03−F02。RD/HV/SA 的标称航向价值不夸大；BY2O F02 更低照报。

【待拍板】“LC01 横滚俯仰优于 F04”需要限定。MAIN_TABLE_V3 中 BY2H pitch 为 LC01 1.825°、F04 1.698°；LC01 roll 三序列更低，但 pitch 仅 BY2/BY2O 更低。正文与 S5c 保留这个反例。

6.4：失败总数来自 replacement 文档；分配置分母来自 CORE_541_SUMMARY，配对摘要与按型区间来自 UNC01 §5。UNC01 给 F04−F03 的胜率但没有配对分母，白名单也没有该 UA01 配对输出。保留 [NEED: paired denominator]，没有读取未授权文件或把 F04−F02 的 497 套用过去。典型种子离散与跨型尾部不混淆。

6.5：Fig.6 改为逐例 RMSE 点，直接读 ADDENDUM_TABLE 的已有值；不为画图重算 median/P95。另一可行写法是从已有 duration 汇总表画 median/P95，但该表未列入白名单。已给出的 D62 均值差、方向、种子数和中位数引用 UNC01。A1 图中值并非各配置逐字相同，正文只写同样的漂移增长和失去有效辅助，不能写数值相同。

6.6：T07 全部 14 个身份保留，输出型分开。RTKLIB 有限可用率、官方 Hartley 漂移、LC01、EXT05C/GINav 和 LEG-DR 均有来源数字；LEG-DR 明写 no filter。自写移植只保留 accuracy validation failed，不抄诊断过程。

6.7：T08 保留九族的原有 median/P95 与配对支持。F02 A2 P95 源值为 17.077198 m，因此正文写 17.077 m，而不是将提示词的两位近似 17.08 写成虚假的三位 17.080。位置偏差 F04/LC01 均约 1.611 m。D31 与 D06 按输入关闭范围解释，时间戳只作为不等暴露局限。

6.8：只指向 S6/S7，不给校准常数，也不把敏感性变体替换主行。

## 第 7–9 节

讨论让 C1 对应分段和绝对航向，C2 对应保留航向时的水平速度冗余，C3 对应分母、失败和可复现范围。LC01-S 的 BY2 0.35° 优势正面回应，BY2O 4.016° 和三序列更大的 roll/pitch 同时保留；偏置归因安装偏航是现有分析的解释，不冒充独立安装测量。

D15、D27、D57 分别说明错误拒绝、过度自信输入导致发散、精确匹配规则导致整段无有效航向。D15 的机制解释不是新做的因果识别。另一可行写法只列 failure class，会丢失设计启示，因此采用有限定的机制解释。

局限逐字保留 UNC03 §2，另写 HV 准备依赖、噪声标记未独立重估、约 40 ms 候选、多维基线未来模型、单平台单场地和容差匹配。结论不声称所有维度统一最优，也不声称独立绝对精度。

## 图、补充材料及尚缺信息

新图采用统一 Okabe–Ito 颜色，并用线型/标记区分；A04 取该色板的紫色，避免与复制图中 LC01 的蓝色重复。图 7/8、S1/S2 按现有版本复制，未发现需要将 Truth 改为 Reference 的标签。图中 “F04 reference” 表示比较线，图注已澄清不是评估参考。

【待拍板】图内评估参考统一称 Reference，是本稿的编辑决定。图 1 的照片位须作者补；不以生成图片冒充真实平台照片。复制图保留原尺寸，新图双栏宽度按 174 mm 导出。

S1–S10 均有独立 CSV 与嵌入表。S5c 额外给出完整姿态对比。S9 包含全部 56 条配对区间和 111 条单窗区间，保持原 verdict；这些区间不是本任务重新 bootstrap 的结果。S10 只给 observer 投影更正的结论，不复述过程。

待补：[NEED: photo]；观测时间修正的准确可引用字段；实际 IMU 流频率；F04−F03 故障配对分母；正式作者–年份书目；repository/DOI；基金；作者贡献；利益冲突确认。上述缺口均保留，未填造事实。

## 逐数字来源索引

下面自动列出每次数字出现的 claim_id、章节、值及原始文件定位。CSV 定位为列名加唯一行条件；文档定位为原始行号；派生量给输入 claim_id 与运算。表格单元不重复登记，其来源在 TABLE_MAP.csv。结构编号、方法/型号中的数字与代数恒等式的常数不属于结果量值。

<!-- NUMERIC_INDEX -->

| claim_id | 章节 | 值与单位 | 原始文件 | 定位 / 派生 |
| --- | --- | --- | --- | --- |
| N00001 | Main: Abstract | 0.35 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.35", "display_digits": 2} |
| N00002 | Main: Abstract | 1.886 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00003 | Main: Abstract | 0.098 m | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "h_rmse_m", "display_digits": 3} |
| N00004 | Main: Abstract | 1.934 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2H", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00005 | Main: Abstract | 0.068 m | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2H", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "h_rmse_m", "display_digits": 3} |
| N00006 | Main: Abstract | 2.434 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00007 | Main: Abstract | 0.055 m | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "h_rmse_m", "display_digits": 3} |
| N00008 | Main: Abstract | 1.11 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2", "segment": "full", "pair_A_minus_B": "LC01-F04", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00009 | Main: Abstract | 0.27 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2H", "segment": "full", "pair_A_minus_B": "LC01-F04", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00010 | Main: Abstract | 0.233 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "F04", "segment_id": "occlusion_primary", "variant": "PROTOCOL_V3", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00011 | Main: Abstract | 4.008 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "LC01", "segment_id": "occlusion_primary", "variant": "", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00012 | Main: Abstract | 0.177 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "A2"}, "column": "F04", "display_digits": 3, "regex": "horizontal_rmse_m=([-+\\d.eE]+)/"} |
| N00013 | Main: Abstract | 1.407 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "A2"}, "column": "LC01", "display_digits": 3, "regex": "horizontal_rmse_m=([-+\\d.eE]+)/"} |
| N00014 | Main: Abstract | 6468 count | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 68, "line_end": 68, "literal": "6,468", "display_digits": 0} |
| N00015 | Main: Abstract | 283 count | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 78, "line_end": 78, "literal": "283", "display_digits": 0} |
| N00016 | Main: Abstract | 193 count | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 78, "line_end": 78, "literal": "193", "display_digits": 0} |
| N00017 | Main: Abstract | 90 count | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 79, "line_end": 79, "literal": "90", "display_digits": 0} |
| N00018 | Main: Abstract | 0.133 fraction | docs/paper_rebuild/hext/HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv | {"where": {"method": "RTKLIB_UNMODIFIED_MOVING_BASE"}, "column": "BY2H", "display_digits": 3, "regex": "availability=([-+\\d.eE]+)"} |
| N00019 | Main: Abstract | 13 % | docs/paper_rebuild/hext/HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv | {"display_digits": 0}；{"inputs": ["N00018"], "expression": "100*N00018"} |
| N00020 | Main: 3.1 Walking platform and antenna geometry | 0.35 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.35", "display_digits": 2} |
| N00021 | Main: 3.1 Walking platform and antenna geometry | 0.03 m | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 282, "line_end": 282, "literal": "0.03", "display_digits": 2} |
| N00022 | Main: 3.1 Walking platform and antenna geometry | 0.03 m | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 282, "line_end": 282, "literal": "0.03", "display_digits": 2} |
| N00023 | Main: 3.1 Walking platform and antenna geometry | -0.30 m | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 282, "line_end": 282, "literal": "-0.30", "display_digits": 2} |
| N00024 | Main: 3.1 Walking platform and antenna geometry | 0.356 m | docs/paper_rebuild/hext/HX05_PREREG.md | {"line_start": 23, "line_end": 23, "literal": "0.356191491865984", "display_digits": 3} |
| N00025 | Main: 3.1 Walking platform and antenna geometry | 0.354 m | docs/paper_rebuild/hext/HX05_PREREG.md | {"line_start": 23, "line_end": 23, "literal": "0.35418777593777223", "display_digits": 3} |
| N00026 | Main: 3.1 Walking platform and antenna geometry | 0.350 m | docs/paper_rebuild/hext/HX05_PREREG.md | {"line_start": 23, "line_end": 23, "literal": "0.35013463864843675", "display_digits": 3} |
| N00027 | Main: 3.1 Walking platform and antenna geometry | 0.03 m | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 282, "line_end": 282, "literal": "0.03", "display_digits": 2} |
| N00028 | Main: 3.1 Walking platform and antenna geometry | 0.03 m | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 282, "line_end": 282, "literal": "0.03", "display_digits": 2} |
| N00029 | Main: 3.1 Walking platform and antenna geometry | -0.30 m | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 282, "line_end": 282, "literal": "-0.30", "display_digits": 2} |
| N00030 | Main: 3.2 Observation streams and reference | 5 Hz | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 7, "line_end": 7, "literal": "5", "display_digits": 0} |
| N00031 | Main: 3.3 Sequence preparation and motion | 5 Hz | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 7, "line_end": 7, "literal": "5", "display_digits": 0} |
| N00032 | Main: 3.3 Sequence preparation and motion | 413 s | docs/paper_rebuild/hext/HX05_PREREG.md | {"line_start": 23, "line_end": 23, "literal": "413", "display_digits": 0} |
| N00033 | Main: 3.3 Sequence preparation and motion | 683 s | docs/paper_rebuild/hext/HX05_PREREG.md | {"line_start": 23, "line_end": 23, "literal": "683", "display_digits": 0} |
| N00034 | Main: 4.3 Receiver-status-driven heading validity and residual gating | 90 deg | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 211, "line_end": 211, "literal": "90", "display_digits": 0} |
| N00035 | Main: 4.3 Receiver-status-driven heading validity and residual gating | 0.5 deg | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 293, "line_end": 293, "literal": "0.5", "display_digits": 1} |
| N00036 | Main: 4.3 Receiver-status-driven heading validity and residual gating | 3.0 deg | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 294, "line_end": 294, "literal": "3.0", "display_digits": 1} |
| N00037 | Main: 4.3 Receiver-status-driven heading validity and residual gating | 6.0 deg | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 295, "line_end": 295, "literal": "6.0", "display_digits": 1} |
| N00038 | Main: 4.3 Receiver-status-driven heading validity and residual gating | 6.0 deg | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 295, "line_end": 295, "literal": "6.0", "display_digits": 1} |
| N00039 | Main: 4.3 Receiver-status-driven heading validity and residual gating | 15.0 deg | configs/paper_rebuild/final_v23_parity_contract.yaml | {"line_start": 297, "line_end": 297, "literal": "15.0", "display_digits": 1} |
| N00040 | Main: 4.4 Velocity-aiding redundancy and robot priors | 1.2 s | docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md | {"line_start": 20, "line_end": 20, "literal": "1.2", "display_digits": 1} |
| N00041 | Main: 5.3 Controlled faults and interruption families | 541 count | configs/paper_rebuild/degradation_60types_9seeds.yaml | {"key_path": ["matrix", "total_case_count"], "display_digits": 0} |
| N00042 | Main: 5.3 Controlled faults and interruption families | 540 count | configs/paper_rebuild/degradation_60types_9seeds.yaml | {"key_path": ["matrix", "degraded_case_count"], "display_digits": 0} |
| N00043 | Main: 5.3 Controlled faults and interruption families | 60 count | configs/paper_rebuild/degradation_60types_9seeds.yaml | {"key_path": ["matrix", "degradation_type_count"], "display_digits": 0} |
| N00044 | Main: 5.3 Controlled faults and interruption families | 9 count | configs/paper_rebuild/degradation_60types_9seeds.yaml | {"key_path": ["matrix", "seeds_per_type"], "display_digits": 0} |
| N00045 | Main: 5.3 Controlled faults and interruption families | 27 count | docs/paper_rebuild/hext/HX05_PREREG.md | {"line_start": 87, "line_end": 87, "literal": "27", "display_digits": 0} |
| N00046 | Main: 5.3 Controlled faults and interruption families | 18 count | docs/paper_rebuild/hext/HX05_PREREG.md | {"line_start": 39, "line_end": 39, "literal": "18", "display_digits": 0} |
| N00047 | Main: 5.5 Measurement uncertainty | 2 model identifier | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 3, "line_end": 3, "literal": "2", "display_digits": 0} |
| N00048 | Main: 5.5 Measurement uncertainty | 1.1 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "1.1", "display_digits": 1} |
| N00049 | Main: 5.5 Measurement uncertainty | 0.4 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.4", "display_digits": 1} |
| N00050 | Main: 5.5 Measurement uncertainty | 1 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 3, "line_end": 3, "literal": "1", "display_digits": 0} |
| N00051 | Main: 5.5 Measurement uncertainty | 0.35 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.35", "display_digits": 2} |
| N00052 | Main: 5.5 Measurement uncertainty | 0.9 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.9", "display_digits": 1} |
| N00053 | Main: 5.5 Measurement uncertainty | 1.0 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "1.0", "display_digits": 1} |
| N00054 | Main: 5.5 Measurement uncertainty | 0.02 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.02", "display_digits": 2} |
| N00055 | Main: 5.5 Measurement uncertainty | 0.05 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.05", "display_digits": 2} |
| N00056 | Main: 5.5 Measurement uncertainty | 5 s | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 3, "line_end": 3, "literal": "5", "display_digits": 0} |
| N00057 | Main: 5.5 Measurement uncertainty | 1.1 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "1.1", "display_digits": 1} |
| N00058 | Main: 5.5 Measurement uncertainty | 1.4 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "1.4", "display_digits": 1} |
| N00059 | Main: 5.5 Measurement uncertainty | 0.06 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.06", "display_digits": 2} |
| N00060 | Main: 5.5 Measurement uncertainty | 0.03 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.03", "display_digits": 2} |
| N00061 | Main: 5.5 Measurement uncertainty | 0.04 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.04", "display_digits": 2} |
| N00062 | Main: 5.5 Measurement uncertainty | 0.3 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.3", "display_digits": 1} |
| N00063 | Main: 5.5 Measurement uncertainty | 1.4 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "1.4", "display_digits": 1} |
| N00064 | Main: 5.5 Measurement uncertainty | 95 % | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "95", "display_digits": 0} |
| N00065 | Main: 5.5 Measurement uncertainty | 0.3 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.3", "display_digits": 1} |
| N00066 | Main: 5.5 Measurement uncertainty | 1 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 3, "line_end": 3, "literal": "1", "display_digits": 0} |
| N00067 | Main: 5.5 Measurement uncertainty | 0.05 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.05", "display_digits": 2} |
| N00068 | Main: 6.1 Nominal navigation on the three sequences | 1.886 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00069 | Main: 6.1 Nominal navigation on the three sequences | 1.934 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2H", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00070 | Main: 6.1 Nominal navigation on the three sequences | 2.434 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00071 | Main: 6.1 Nominal navigation on the three sequences | 0.098 m | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "h_rmse_m", "display_digits": 3} |
| N00072 | Main: 6.1 Nominal navigation on the three sequences | 0.068 m | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2H", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "h_rmse_m", "display_digits": 3} |
| N00073 | Main: 6.1 Nominal navigation on the three sequences | 0.055 m | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "h_rmse_m", "display_digits": 3} |
| N00074 | Main: 6.1 Nominal navigation on the three sequences | 1.11 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2", "segment": "full", "pair_A_minus_B": "LC01-F04", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00075 | Main: 6.1 Nominal navigation on the three sequences | 2.57 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2", "segment": "full", "pair_A_minus_B": "LC01-F04", "metric": "yaw"}, "column": "mbb95_high", "display_digits": 2} |
| N00076 | Main: 6.1 Nominal navigation on the three sequences | -2.57 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"display_digits": 2}；{"inputs": ["N00075"], "expression": "-N00075"} |
| N00077 | Main: 6.1 Nominal navigation on the three sequences | -0.22 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2", "segment": "full", "pair_A_minus_B": "LC01-F04", "metric": "yaw"}, "column": "mbb95_low", "display_digits": 2} |
| N00078 | Main: 6.1 Nominal navigation on the three sequences | 0.22 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"display_digits": 2}；{"inputs": ["N00077"], "expression": "-N00077"} |
| N00079 | Main: 6.1 Nominal navigation on the three sequences | 0.27 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2H", "segment": "full", "pair_A_minus_B": "LC01-F04", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00080 | Main: 6.1 Nominal navigation on the three sequences | 0.51 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2H", "segment": "full", "pair_A_minus_B": "LC01-F04", "metric": "yaw"}, "column": "mbb95_high", "display_digits": 2} |
| N00081 | Main: 6.1 Nominal navigation on the three sequences | -0.51 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"display_digits": 2}；{"inputs": ["N00080"], "expression": "-N00080"} |
| N00082 | Main: 6.1 Nominal navigation on the three sequences | -0.05 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2H", "segment": "full", "pair_A_minus_B": "LC01-F04", "metric": "yaw"}, "column": "mbb95_low", "display_digits": 2} |
| N00083 | Main: 6.1 Nominal navigation on the three sequences | 0.05 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"display_digits": 2}；{"inputs": ["N00082"], "expression": "-N00082"} |
| N00084 | Main: 6.1 Nominal navigation on the three sequences | 2.434 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00085 | Main: 6.1 Nominal navigation on the three sequences | 2.454 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "LC01", "start_convention": "FILE_START"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00086 | Main: 6.1 Nominal navigation on the three sequences | 12.049 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2", "method_id": "EXT05C", "start_convention": "FILE_START"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00087 | Main: 6.1 Nominal navigation on the three sequences | 20.108 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2H", "method_id": "EXT05C", "start_convention": "CONTRACT_START"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00088 | Main: 6.1 Nominal navigation on the three sequences | 5.846 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "EXT05C", "start_convention": "FILE_START"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00089 | Main: 6.1 Nominal navigation on the three sequences | 1.825 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2H", "method_id": "LC01", "start_convention": "CONTRACT_START"}, "column": "pitch_rmse_deg", "display_digits": 3} |
| N00090 | Main: 6.1 Nominal navigation on the three sequences | 1.698 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2H", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "pitch_rmse_deg", "display_digits": 3} |
| N00091 | Main: 6.1 Nominal navigation on the three sequences | 95 % | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "95", "display_digits": 0} |
| N00092 | Main: 6.1 Nominal navigation on the three sequences | 1.60 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "1.60", "display_digits": 2} |
| N00093 | Main: 6.1 Nominal navigation on the three sequences | 2.16 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "2.16", "display_digits": 2} |
| N00094 | Main: 6.1 Nominal navigation on the three sequences | 1.60 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "1.60", "display_digits": 2} |
| N00095 | Main: 6.1 Nominal navigation on the three sequences | 2.04 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "2.04", "display_digits": 2} |
| N00096 | Main: 6.1 Nominal navigation on the three sequences | 1.36 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "1.36", "display_digits": 2} |
| N00097 | Main: 6.1 Nominal navigation on the three sequences | 3.61 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "3.61", "display_digits": 2} |
| N00098 | Main: 6.1 Nominal navigation on the three sequences | 0.045 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "0.045", "display_digits": 3} |
| N00099 | Main: 6.1 Nominal navigation on the three sequences | 0.152 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "0.152", "display_digits": 3} |
| N00100 | Main: 6.1 Nominal navigation on the three sequences | 0.045 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "0.045", "display_digits": 3} |
| N00101 | Main: 6.1 Nominal navigation on the three sequences | 0.085 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "0.085", "display_digits": 3} |
| N00102 | Main: 6.1 Nominal navigation on the three sequences | 0.038 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "0.038", "display_digits": 3} |
| N00103 | Main: 6.1 Nominal navigation on the three sequences | 0.073 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 15, "line_end": 15, "literal": "0.073", "display_digits": 3} |
| N00104 | Main: 6.2 BY2O segment structure | 0.233 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "F04", "segment_id": "occlusion_primary", "variant": "PROTOCOL_V3", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00105 | Main: 6.2 BY2O segment structure | 4.008 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "LC01", "segment_id": "occlusion_primary", "variant": "", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00106 | Main: 6.2 BY2O segment structure | 3.78 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 19, "line_end": 19, "literal": "3.78", "display_digits": 2} |
| N00107 | Main: 6.2 BY2O segment structure | 2.20 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 19, "line_end": 19, "literal": "2.20", "display_digits": 2} |
| N00108 | Main: 6.2 BY2O segment structure | 4.44 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 19, "line_end": 19, "literal": "4.44", "display_digits": 2} |
| N00109 | Main: 6.2 BY2O segment structure | 1.862 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "F04", "segment_id": "occlusion_secondary", "variant": "PROTOCOL_V3", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00110 | Main: 6.2 BY2O segment structure | 6.174 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "LC01", "segment_id": "occlusion_secondary", "variant": "", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00111 | Main: 6.2 BY2O segment structure | 2.589 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "F04", "segment_id": "outside", "variant": "PROTOCOL_V3", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00112 | Main: 6.2 BY2O segment structure | 1.878 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "LC01", "segment_id": "outside", "variant": "", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00113 | Main: 6.3 Configuration ladder and ablations | -0.32 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2", "segment": "full", "pair_A_minus_B": "F03-F02", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00114 | Main: 6.3 Configuration ladder and ablations | -0.34 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2H", "segment": "full", "pair_A_minus_B": "F03-F02", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00115 | Main: 6.3 Configuration ladder and ablations | -0.64 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2", "segment": "full", "pair_A_minus_B": "F03-F02", "metric": "yaw"}, "column": "mbb95_low", "display_digits": 2} |
| N00116 | Main: 6.3 Configuration ladder and ablations | -0.01 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2", "segment": "full", "pair_A_minus_B": "F03-F02", "metric": "yaw"}, "column": "mbb95_high", "display_digits": 2} |
| N00117 | Main: 6.3 Configuration ladder and ablations | -0.82 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2H", "segment": "full", "pair_A_minus_B": "F03-F02", "metric": "yaw"}, "column": "mbb95_low", "display_digits": 2} |
| N00118 | Main: 6.3 Configuration ladder and ablations | -0.01 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2H", "segment": "full", "pair_A_minus_B": "F03-F02", "metric": "yaw"}, "column": "mbb95_high", "display_digits": 2} |
| N00119 | Main: 6.3 Configuration ladder and ablations | -0.03 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2", "segment": "full", "pair_A_minus_B": "F04-F03", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00120 | Main: 6.3 Configuration ladder and ablations | -0.01 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2H", "segment": "full", "pair_A_minus_B": "F04-F03", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00121 | Main: 6.3 Configuration ladder and ablations | 0.00 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2O", "segment": "full", "pair_A_minus_B": "F04-F03", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00122 | Main: 6.3 Configuration ladder and ablations | 2.309 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "F02", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00123 | Main: 6.3 Configuration ladder and ablations | 2.434 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00124 | Main: 6.3 Configuration ladder and ablations | 0.12 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2O", "segment": "full", "pair_A_minus_B": "F04-F02", "metric": "yaw"}, "column": "delta_rmse", "display_digits": 2} |
| N00125 | Main: 6.3 Configuration ladder and ablations | -0.03 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2O", "segment": "full", "pair_A_minus_B": "F04-F02", "metric": "yaw"}, "column": "mbb95_low", "display_digits": 2} |
| N00126 | Main: 6.3 Configuration ladder and ablations | 0.22 deg | docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv | {"where": {"sequence": "BY2O", "segment": "full", "pair_A_minus_B": "F04-F02", "metric": "yaw"}, "column": "mbb95_high", "display_digits": 2} |
| N00127 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 6468 count | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 68, "line_end": 68, "literal": "6,468", "display_digits": 0} |
| N00128 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 283 count | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 78, "line_end": 78, "literal": "283", "display_digits": 0} |
| N00129 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 193 count | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 78, "line_end": 78, "literal": "193", "display_digits": 0} |
| N00130 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 90 count | docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md | {"line_start": 79, "line_end": 79, "literal": "90", "display_digits": 0} |
| N00131 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 519 cases | <V3>/07_AGGREGATE/CORE_541_SUMMARY_V3.csv | {"where": {"method_id": "F04", "metric": "yaw_rmse_deg"}, "column": "finite_count", "display_digits": 0} |
| N00132 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 22 cases | <V3>/07_AGGREGATE/CORE_541_SUMMARY_V3.csv | {"where": {"method_id": "F04", "metric": "yaw_rmse_deg"}, "column": "algorithm_failure_count", "display_digits": 0} |
| N00133 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 541 cases | <V3>/07_AGGREGATE/CORE_541_SUMMARY_V3.csv | {"where": {"method_id": "F04", "metric": "yaw_rmse_deg"}, "column": "registered_count", "display_digits": 0} |
| N00134 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 43 cases | <V3>/07_AGGREGATE/CORE_541_SUMMARY_V3.csv | {"where": {"method_id": "F02", "metric": "yaw_rmse_deg"}, "column": "algorithm_failure_count", "display_digits": 0} |
| N00135 | Main: 6.4 Core fault matrix, failures, and seed dispersion | -0.35 deg | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 90, "line_end": 90, "literal": "\u22120.346", "display_digits": 2} |
| N00136 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 98.8 % | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 90, "line_end": 90, "literal": "98.8", "display_digits": 1} |
| N00137 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 497 count | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 90, "line_end": 90, "literal": "497", "display_digits": 0} |
| N00138 | Main: 6.4 Core fault matrix, failures, and seed dispersion | -0.03 deg | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 90, "line_end": 90, "literal": "\u22120.029", "display_digits": 2} |
| N00139 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 98.8 % | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 90, "line_end": 90, "literal": "98.8", "display_digits": 1} |
| N00140 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 0.00 deg | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 90, "line_end": 90, "literal": "+0.0003", "display_digits": 2} |
| N00141 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 37.1 % | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 90, "line_end": 90, "literal": "37.1", "display_digits": 1} |
| N00142 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 2.447 deg | <V3>/07_AGGREGATE/CORE_541_SUMMARY_V3.csv | {"where": {"method_id": "F04", "metric": "yaw_rmse_deg"}, "column": "p95", "display_digits": 3} |
| N00143 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 2.00 deg | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 91, "line_end": 91, "literal": "2.00", "display_digits": 2} |
| N00144 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 4.18 deg | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 91, "line_end": 91, "literal": "4.18", "display_digits": 2} |
| N00145 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 0.002 deg | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 28, "line_end": 28, "literal": "0.0023", "display_digits": 3} |
| N00146 | Main: 6.4 Core fault matrix, failures, and seed dispersion | 541 count | configs/paper_rebuild/degradation_60types_9seeds.yaml | {"key_path": ["matrix", "total_case_count"], "display_digits": 0} |
| N00147 | Main: 6.5 Injected interruption families | -1.61 m | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 95, "line_end": 95, "literal": "\u22121.61", "display_digits": 2} |
| N00148 | Main: 6.5 Injected interruption families | 10 s | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 21, "line_end": 21, "literal": "10", "display_digits": 0} |
| N00149 | Main: 6.5 Injected interruption families | -10.50 m | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 95, "line_end": 95, "literal": "\u221210.5", "display_digits": 2} |
| N00150 | Main: 6.5 Injected interruption families | 20 s | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 21, "line_end": 21, "literal": "20", "display_digits": 0} |
| N00151 | Main: 6.5 Injected interruption families | 9 count | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 3, "line_end": 3, "literal": "9", "display_digits": 0} |
| N00152 | Main: 6.5 Injected interruption families | 9 count | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 3, "line_end": 3, "literal": "9", "display_digits": 0} |
| N00153 | Main: 6.5 Injected interruption families | 0.126 m | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 95, "line_end": 95, "literal": "0.126", "display_digits": 3} |
| N00154 | Main: 6.5 Injected interruption families | 0.241 m | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 95, "line_end": 95, "literal": "0.241", "display_digits": 3} |
| N00155 | Main: 6.5 Injected interruption families | 0.328 m | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 95, "line_end": 95, "literal": "0.328", "display_digits": 3} |
| N00156 | Main: 6.5 Injected interruption families | 1.025 m | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 95, "line_end": 95, "literal": "1.025", "display_digits": 3} |
| N00157 | Main: 6.5 Injected interruption families | 30.800 m | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 95, "line_end": 95, "literal": "30.8", "display_digits": 3} |
| N00158 | Main: 6.5 Injected interruption families | 30 s | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 43, "line_end": 43, "literal": "30", "display_digits": 0} |
| N00159 | Main: 6.6 External methods by output class | 0.112 fraction | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 23, "line_end": 23, "literal": "0.111679", "display_digits": 3} |
| N00160 | Main: 6.6 External methods by output class | 0.133 fraction | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 23, "line_end": 23, "literal": "0.132593", "display_digits": 3} |
| N00161 | Main: 6.6 External methods by output class | 0.059 fraction | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 23, "line_end": 23, "literal": "0.059416", "display_digits": 3} |
| N00162 | Main: 6.6 External methods by output class | 14.566 deg | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 23, "line_end": 23, "literal": "14.566166", "display_digits": 3} |
| N00163 | Main: 6.6 External methods by output class | 27.011 deg | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 23, "line_end": 23, "literal": "27.011169", "display_digits": 3} |
| N00164 | Main: 6.6 External methods by output class | 23.139 deg | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 23, "line_end": 23, "literal": "23.138950", "display_digits": 3} |
| N00165 | Main: 6.6 External methods by output class | 33.634 m per 100 m | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 25, "line_end": 25, "literal": "33.633600", "display_digits": 3} |
| N00166 | Main: 6.6 External methods by output class | 47.526 m per 100 m | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 25, "line_end": 25, "literal": "47.525517", "display_digits": 3} |
| N00167 | Main: 6.6 External methods by output class | 28.559 m per 100 m | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 25, "line_end": 25, "literal": "28.558852", "display_digits": 3} |
| N00168 | Main: 6.6 External methods by output class | 100 m | docs/paper_rebuild/hext/HX05_PREREG.md | {"line_start": 31, "line_end": 31, "literal": "100", "display_digits": 0} |
| N00169 | Main: 6.6 External methods by output class | 1.407 m | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 27, "line_end": 27, "literal": "1.407350", "display_digits": 3} |
| N00170 | Main: 6.6 External methods by output class | 7.769 m | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 27, "line_end": 27, "literal": "7.769345", "display_digits": 3} |
| N00171 | Main: 6.6 External methods by output class | 18 count | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 13, "line_end": 13, "literal": "18", "display_digits": 0} |
| N00172 | Main: 6.6 External methods by output class | 18 count | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 13, "line_end": 13, "literal": "18", "display_digits": 0} |
| N00173 | Main: 6.6 External methods by output class | 2 count | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 9, "line_end": 9, "literal": "2", "display_digits": 0} |
| N00174 | Main: 6.6 External methods by output class | 271 count | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 9, "line_end": 9, "literal": "271", "display_digits": 0} |
| N00175 | Main: 6.6 External methods by output class | 2.895 m | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 29, "line_end": 29, "literal": "2.894928", "display_digits": 3} |
| N00176 | Main: 6.6 External methods by output class | 6.209 m | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 25, "line_end": 25, "literal": "6.209111", "display_digits": 3} |
| N00177 | Main: 6.6 External methods by output class | 9.178 m | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 25, "line_end": 25, "literal": "9.178417", "display_digits": 3} |
| N00178 | Main: 6.6 External methods by output class | 6.322 m | docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md | {"line_start": 25, "line_end": 25, "literal": "6.322412", "display_digits": 3} |
| N00179 | Main: 6.6 External methods by output class | 100 m | docs/paper_rebuild/hext/HX05_PREREG.md | {"line_start": 31, "line_end": 31, "literal": "100", "display_digits": 0} |
| N00180 | Main: 6.7 External comparisons under controlled faults | 18 count | docs/paper_rebuild/v3/uncertainty/UNC02_DISTINGUISHABILITY.md | {"line_start": 44, "line_end": 44, "literal": "18", "display_digits": 0} |
| N00181 | Main: 6.7 External comparisons under controlled faults | 18 count | docs/paper_rebuild/v3/uncertainty/UNC02_DISTINGUISHABILITY.md | {"line_start": 44, "line_end": 44, "literal": "18", "display_digits": 0} |
| N00182 | Main: 6.7 External comparisons under controlled faults | 18 count | docs/paper_rebuild/v3/uncertainty/UNC02_DISTINGUISHABILITY.md | {"line_start": 44, "line_end": 44, "literal": "18", "display_digits": 0} |
| N00183 | Main: 6.7 External comparisons under controlled faults | 18 count | docs/paper_rebuild/v3/uncertainty/UNC02_DISTINGUISHABILITY.md | {"line_start": 44, "line_end": 44, "literal": "18", "display_digits": 0} |
| N00184 | Main: 6.7 External comparisons under controlled faults | 0.177 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "A2"}, "column": "F04", "display_digits": 3, "regex": "horizontal_rmse_m=([-+\\d.eE]+)/"} |
| N00185 | Main: 6.7 External comparisons under controlled faults | 1.407 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "A2"}, "column": "LC01", "display_digits": 3, "regex": "horizontal_rmse_m=([-+\\d.eE]+)/"} |
| N00186 | Main: 6.7 External comparisons under controlled faults | 2.913 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "A2"}, "column": "F02", "display_digits": 3, "regex": "horizontal_rmse_m=([-+\\d.eE]+)/"} |
| N00187 | Main: 6.7 External comparisons under controlled faults | 0.288 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "A2"}, "column": "F04", "display_digits": 3, "regex": "horizontal_rmse_m=[-+\\d.eE]+/([-+\\d.eE]+)"} |
| N00188 | Main: 6.7 External comparisons under controlled faults | 7.769 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "A2"}, "column": "LC01", "display_digits": 3, "regex": "horizontal_rmse_m=[-+\\d.eE]+/([-+\\d.eE]+)"} |
| N00189 | Main: 6.7 External comparisons under controlled faults | 17.077 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "A2"}, "column": "F02", "display_digits": 3, "regex": "horizontal_rmse_m=[-+\\d.eE]+/([-+\\d.eE]+)"} |
| N00190 | Main: 6.7 External comparisons under controlled faults | 2.786 m | docs/paper_rebuild/hext/HX05/EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv | {"where": {"method": "LC01-BR"}, "column": "BY2", "display_digits": 3, "regex": "horizontal_rmse_m=([-+\\d.eE]+)"} |
| N00191 | Main: 6.7 External comparisons under controlled faults | 1.611 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "\u4f4d\u7f6e\u504f\u5dee"}, "column": "LC01", "display_digits": 3, "regex": "horizontal_rmse_m=([-+\\d.eE]+)/"} |
| N00192 | Main: 6.7 External comparisons under controlled faults | 1.611 m | docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv | {"where": {"family": "\u4f4d\u7f6e\u504f\u5dee"}, "column": "F04", "display_digits": 3, "regex": "horizontal_rmse_m=([-+\\d.eE]+)/"} |
| N00193 | Main: 7 Discussion | 1.886 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00194 | Main: 7 Discussion | 0.233 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "F04", "segment_id": "occlusion_primary", "variant": "PROTOCOL_V3", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00195 | Main: 7 Discussion | 4.008 deg | <V3>/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | {"where": {"method_id": "LC01", "segment_id": "occlusion_primary", "variant": "", "evaluator_contract": "evaluator_contract_v3"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00196 | Main: 7 Discussion | 0.35 deg | docs/paper_rebuild/v3/uncertainty/UNC02_DISTINGUISHABILITY.md | {"line_start": 14, "line_end": 14, "literal": "0.35", "display_digits": 2} |
| N00197 | Main: 7 Discussion | 4.016 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "LC01-S", "start_convention": "FILE_START"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00198 | Main: 7 Discussion | -1.61 m | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 95, "line_end": 95, "literal": "\u22121.61", "display_digits": 2} |
| N00199 | Main: 7 Discussion | -10.50 m | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 95, "line_end": 95, "literal": "\u221210.5", "display_digits": 2} |
| N00200 | Main: 8 Limitations and future work | 10 Hz | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 11, "line_end": 11, "literal": "10", "display_digits": 0} |
| N00201 | Main: 8 Limitations and future work | 0.3 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.3", "display_digits": 1} |
| N00202 | Main: 8 Limitations and future work | 1.4 deg | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "1.4", "display_digits": 1} |
| N00203 | Main: 8 Limitations and future work | 0.02 m | docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md | {"line_start": 7, "line_end": 7, "literal": "0.02", "display_digits": 2} |
| N00204 | Main: 8 Limitations and future work | 40 ms | docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md | {"line_start": 44, "line_end": 44, "literal": "40", "display_digits": 0} |
| N00205 | Main: 9 Conclusions | 1.886 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00206 | Main: 9 Conclusions | 1.934 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2H", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
| N00207 | Main: 9 Conclusions | 2.434 deg | <V3>/07_AGGREGATE/MAIN_TABLE_V3.csv | {"where": {"sequence_id": "BY2O", "method_id": "F04", "start_convention": "FROZEN_V21_RUNTIME_CONFIG"}, "column": "yaw_rmse_deg", "display_digits": 3} |
