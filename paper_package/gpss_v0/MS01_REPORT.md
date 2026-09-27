# MS-01 执行报告

状态：PART_1_READY，正文第 3–6 节、主表、图与账本已完成，继续写前后章节及补充材料。

起点 HEAD：5007bf1149b028f323573cc178cd925060f2c35f；起点例外核验通过。既有未跟踪 29/29 不变，逐文件 SHA256 与 MS01_BASELINE.json 一致。

第 3–6 节英文词数（不计表格和图注）：7207。数字账本 171 PASS / 0 FAIL。

图：DRAWN_SCHEMATIC 2、REDRAWN 4、COPIED 4、PLACEHOLDER_NEED_PHOTO 1；合计 10 张图、11 条面板记录。新图机器 QA：Fig01 7/7、Fig02 6/6、Fig03–Fig06 各 7/7；已逐张查看实际 PNG。

数据边界：未调用求解器、评估器、provider、外部方法二进制或 MATLAB；未读取参考原始轨迹；G: 无写入。图只消费允许的保留误差序列及聚合表。未运行任何既有执行脚本。

包大小：6514879 字节。figures/_build 已删除。无交接包。

读文件清单与 SHA256：READ_FILES.json；图输入逐项见 FIGURE_MAP.csv；表的选行逻辑见 TABLE_MAP.csv。

已处理的问题：qa.py 的 numpy.bool_ 转为 Python bool 后保存检查结果；首次并行绘图的输入日志写入竞争已改为顺序重绘和汇总。无科学计算重跑。分段表显式限定 evaluator_contract_v3，避免同文件中两种评估口径重复入表。

待后半稿说明：时标 0.205 s 未在指定文件找到同值字段（现有时标表为约 0.2067 s）；按 [NEED] 保留。F03 无 roll/pitch 先验；F03−F02 的现有配对差为约 −0.32/−0.34°，不能写为单独 RP 收益。共同参考项在 RMSE 差中不保证严格抵消；保留指定不确定度原文后补充数学限定。A1 各配置表现相近而非逐值相同。F04−F03 故障胜率摘要缺配对分母，保留 [NEED]。

Git：第一次提交前 status 仅为 29 条基线、paper_package/gpss_v0/ 和 ms01_ledger_check.py；AGENTS.md 尚未修改。提交哈希将在第二阶段记录；本文件所属最终提交可由 git log -1 -- paper_package/gpss_v0/MS01_REPORT.md 获取，避免内容自引用。
