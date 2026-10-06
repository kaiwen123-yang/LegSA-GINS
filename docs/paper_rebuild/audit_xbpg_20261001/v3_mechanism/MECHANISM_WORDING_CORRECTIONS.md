# M01：维护稿的机制实现限定

本小项接续已发布 C00/A1/A2 的固定对象证据，仅修改维护中的正文、对应模板及数字账本中的两个引用段落；D15 不用于本项论据。原性能数字、参数、数学显示方程、表图、原审查与 D01 历史更正保持不变。没有运行 assembler 或任何科学程序。

逐句核对入口：[MECHANISM_WORDING_CORRECTIONS.csv](MECHANISM_WORDING_CORRECTIONS.csv)。其中 8 行分别记录两份正文各 3 个完整旧/新段落，以及 NUMBER_LEDGER 中 N00198、N00199 的 quoted_text 同步；每行保留修改前后行号、原文全文、新文全文、源表数据行、身份键和原证据字段。

|范围|正文 / 模板行号|更正内容与证据边界|
|---|---|---|
|N09 辅助入口、N16 HV 元数据|MANUSCRIPT_GPSS_v0.md:175 / manuscript_source.md:171|本源合格不保证辅助入口；还要求至少一个使能后的 position/receiver-velocity/heading 有效。HV 的 D 观测仍禁用，但启用 SA metadata scaling 时，禁用 D 维 std sentinel 仍进入冻结 maxStd。|
|N12 权重统计|主稿179 / 模板175|原概括和显示数学方程保留，补充实际统计使用 dz 与 H P_before H^T + base_R，没有扣顺序累计 H dx_before；同快照影子倍率变化不证明闭环收益，也未改变原轨迹。|
|A2 因果范围|主稿516 / 模板399|将“main explanatory burden”收窄为与 HV/RP 参与一致。F04-F03 不隔离 HV；已有 A06 HV-off 身份，只是本轮机制重放没有包含它。A1 原句中的“that path”明确指 HV，避免误写成 RP 输入也不存在。|
|数字账本引用同步|NUMBER_LEDGER.csv:199/200；数据行198/199|仅 N00198、N00199 的 quoted_text 改为新正文；211 个 ID、数值、单位、source_path/source_locator、derivation/check_mode 全部原样保留。|

证据范围是 [C00](groups/C00/README.md)、[A1](groups/A1/README.md) 和 [A2](groups/A2/README.md) 的既有小表：C00/A1/A2 的 INNOVATION_COMPACT 中 F04 同状态影子；A1/A2 SCHEDULING_COMPACT 的 during/RP/HV/RD 身份行。A1 的合格 RP 入口受阻与 HV/RD 无合格候选分开，A2 的 HV/RP 实际接受与 RD 资格拒绝分开。调度时刻与 provider 测量时刻的分窗不互换。A06 身份来自 METHOD_CONFIGS 数据行8、AB1110、HV config/echo=false，不声称本轮已经重放这个对照。

正文未增加新的性能数字或把本轮局部证据推广到全部种子；没有修正后 RMSE 或闭环修复效果。此处保留完整实现限定，不据此撤销原观察结果，也不把旧源码问题裁为全部无影响。

检查回执：[MECHANISM_WORDING_CHECK_RECEIPT.json](MECHANISM_WORDING_CHECK_RECEIPT.json)。逐个反向替换可恢复三个维护文件的原始字节；原显示方程、数值字面量和模板 token 顺序保持。其余四个 D01 许可文件及两个旧 DISPLAY_CORRECTIONS 文件 hash 前后一致。新增 native/evaluator/provider/bootstrap/assembler/大日志读取/Git 操作均为 0。

只读reviewer另行逐格核查了211个身份及1688个非quoted_text单元格，确认仅N00198/N00199引用段落变化；按8条旧/新记录逆替换可恢复本项修改前三文件字节。原公式、模板token及数字范围不变，新增限定与C00/A1/A2吻合，发布审阅PASS。本审阅未运行assembler或科学程序。
