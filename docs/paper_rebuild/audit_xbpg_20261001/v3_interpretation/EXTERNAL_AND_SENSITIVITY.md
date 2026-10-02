# 外部引用的身份、输出与限制

本节只解释最终展示实际引用的外部源；不以更新的 HX07R 替换旧 RTKLIB，不启动三篇文献复现。旧内部协议对照另见 [OLD_PROTOCOL_COMPARISONS](OLD_PROTOCOL_COMPARISONS.md)，候选 R5W/R5SIGMA/B3 另见 [CANDIDATE_SENSITIVITY](CANDIDATE_SENSITIVITY.md)。这些材料属于引用层 B，不加到 6,468 个 Protocol V3 自有 native 的分母。

## 阶段主表的 37 个外部行

`<V3_ROOT>/07_AGGREGATE/MAIN_TABLE_V3.csv` 共 52 行：15 个正式内部展示行（五配置×三序列），其余 37 行保持旧版本。

其中 21 行是七类×三序列的历史 UNAVAILABLE/NOT_EXECUTED 占位：LC02_GINAV、EXT01/02/03/04、Hartley、EXT05B。后来的 HX02/HX05 有结果不等于当时表格自动变成已有结果，也不覆盖历史记录。

另 16 行为 LC01/EXT05C/LC01-S/EXT05C-S，含 BY2H 两种起点：11 COMPLETED、4 AVAILABLE_GEOMETRIC_AUDIT_FAIL、1 NOT_RUN_ALGORITHM_FAILURE。BY2H 的 LC01 CONTRACT_START 是主展示身份但几何审计失败（原 data_row42），FILE_START（row41）不是主行；LC01-S 两起点均几何失败。EXT05C-S 的 BY2H FILE_START 失败（row47），CONTRACT_START 完成（row48）。完整 metric 仍可以读取，但这些状态不能抹掉。

这里的 v3 后缀是评价点/口径，不意味着这些外部 native 使用正式 Protocol V3 输入和算法协议。source/start/implementation 的原字段均保留在来源行。

## 论文 Fig07 的三种输出类别

来源 `<CODE_ROOT>/docs/paper_rebuild/hext/HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv` 和 SOURCE_CITATIONS 的 MAIN.01–14.sequence。每方法跨三个序列，十四个方法行并不表示十四种等价的导航解算器。

|类别|原方法/实现|源及起点|可以描述的量|必须保留的限制|
|---|---|---|---|---|
|heading-only|EXT01/02/03、EXT04 FAR/PAR 的 LIT 实现，RTKLIB_UNMODIFIED_MOVING_BASE|HX02_FIVE_CATEGORY/90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv；BY2 FILE_START、BY2H CONTRACT_START、BY2O FILE_START|有效 heading 比例、yaw 误差|没有完整导航位置；EXT04 有效数 0 时 yaw NA；RTKLIB 为旧 unmodified 身份|
|navigation|LC01 LIT、EXT05C LIT、GINav|同上，start_mode 保留；BY2H FILE_START 为单列敏感性|yaw/H/up、输出与匹配计数|GINav BY2/BY2O DIVERGED；BY2H 仅 2/271 期望点，不等于全窗结果|
|正式内部参考|F04/F02/F01|V3 FULL_ABLATION_TABLE_V3 的三序列行，MAIN.12/13/14|正式三序列原指标|属于 A 层已计数 native；不能重复算外部新实验|
|relative pose|Hartley official、ports、LEG-DR|见下节|位置漂移 m/100m、有符号 yaw 漂移 deg/min|不与绝对 yaw RMSE、全局位置 RMSE 排同一名次|

例如 MAIN.01.BY2 有效 980/1370，ratio=0.7153284671532847，yaw=120.36002862722869°。GINav BY2H 的 yaw=11.662263303395555°、H=2.894928083236164 m 只在两个匹配点，matched/output=2/2=1 与期望窗 2/271 是不同分母。没有按性能挑选更有利的起点或把两点当完整实验。

## Hartley 和 LEG-DR：实现资格不能由一张表替代

Hartley official 来源 HX02E_HARTLEY_OFFICIAL 的 HARTLEY_OFFICIAL_TABLE.csv，OFF-LIT 为主身份、OFF-DEF 为补充，start=C00，output_type=relative_pose。position drift 是带截距 OLS 的**有符号斜率**，不是末端绝对距离误差。

Port-S/S 与 Port-LIT/LIT 仍标 UNVALIDATED_PORT；BY2H ABNORMAL_EXIT 为初始化停止，其他两个序列有数字也不自动成为官方完整复现。原论文需要的接触/关节等输入在本数据条件下受限，不能由漂移表反推原算法本身错误。SFig01 只选这些 ports/official 和 LEG-DR 五行，其他补充身份并没有都画进去。

LEG-DR 为 C4 INPUT_REFERENCE，来源 HX05_CLOSEOUT/RUNS/<sequence>/RESULT.json，使用 onboard attitude 的无滤波参考实现；源文件没有统一 start_mode 字段，保持 unknown，不补造。BY2 有 43 个未观测 gap，总计 0.2044345769999545 s，对位移积分作零贡献，没有插值补速。其位置 OLS slope=0.06942580845419305 m/100m、BY2O yaw slope=−0.37939114728288426 deg/min 不能解释为负绝对误差，也不能由小斜率认定全过程轨迹准确或参考独立。

## Fig08 的外部退化子集

来源 HX03R2_AUDIT_REEVAL 的 DEGRADATION_EXTERNAL_TABLE_R2.csv，共 396 行，failure_class 为 NONE 360、DIVERGED 36；另一轴 audit_status_R2 为 PASS 368、NOT_EVALUATED 28。有 8 条失败行的审计状态为 PASS，表示审计过程通过，不能覆盖算法失败。PRE_FAILURE 片段不计作完整窗。

LC01、EXT05C、LC01-BR 是不同身份；Fig08 只选 LC01 与 F02/F04，BR 是仅 A2 的修改补充，不能替换主方法。源表没有统一 start 字段，保留目录/type/seed/config/input_identity，未知不猜。

position-noise 子集取 D14/D21，LC01 0/18 完成且 DIVERGED；D57 的 F02/F04 为 0/9。柱图有限统计与失败一起读，不能用 LC01 更小的成功子集赢得“整体更稳”。F04 position-noise H median/P95=1.2624288869293778/1.9402875087451732 m（18 有限），A2=0.17667112573862742/0.2877465570267067 m（18 有限）。Fig08 的 whisker 是 P95，不是 CI；选定九族也不等于 CORE 八族全集。

## 源文件与本轮结论

本轮完整读取的既有外部表、具体身份键和原字段值见 `secondary/EXTERNAL_INPUTS_READ.csv`、`EXTERNAL_SOURCE_CELLS.csv`。旧 MAIN 的缺项、几何失败，当前 HX05 的稀疏覆盖、ports 未验证，以及不同 output_type 都单列，未通过换版本补成 PASS。

这些资料能说明“最终展示比较了哪些具体实现，在本数据和支持上给出什么数字”。它们不能证明三篇目标论文完整复现，也不能证明商业融合 reference 为独立真值。若以后更新展示，应明确旧→新方法身份、起点、输入及验证状态的差异，再决定是否采用；本轮没有执行替换。
