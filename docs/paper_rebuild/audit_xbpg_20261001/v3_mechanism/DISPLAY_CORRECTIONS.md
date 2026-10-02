# D01：V3 维护中手稿的展示更正

本项只更新维护中的手稿、来源模板、数字账本和对应的展示生成规则。原 UA/UNC 文档、性能 CSV、已封存解释及 Figure 6 均保留。原数字来自现有完整精度 CSV；没有重新计算 RMSE、置信区间或 bootstrap，也没有启动算法、provider、评价器或全量装配入口。

起点提交为 `b0fdb81f103a5f0e7c7432e5247a9341524c7fa6`。历史文字和原账本快照在 [display/BASELINE.json](display/BASELINE.json)，逐项原值、完整精度源值、行键、列名、展示位数及更正位置在 [DISPLAY_CORRECTIONS.csv](DISPLAY_CORRECTIONS.csv)。旧发现来源 [CLAIM_EVIDENCE_MATRIX.csv](../v3_interpretation/CLAIM_EVIDENCE_MATRIX.csv) 保持原样；本更正对应其 CE06、CE10、CE12、CE14、CE15 及复现声明边界。

| 项目 | 旧展示 | 完整精度源及口径 | 当前展示 |
|---|---|---|---|
| A1，30 s，F04 水平误差 | 30.800 m，未清楚指出统计量 | `UA01_ADDENDUM_STATS.csv` 数据行 103：D61 / 30 / F04 / horizontal_rmse_m，mean=`30.80599245730669`，9 个有限案例 | 30.806 m；明确为九案例各自**全窗水平 RMSE 的均值**，不是故障终点误差 |
| A2，20 s，F04−F03 水平差 | −10.50 m，两处 | `UA01_ADDENDUM_PAIRED.csv` 数据行 70：D62 / 20 / F04-F03 / horizontal_rmse_m，mean=`-10.510165904595015`，9 对有限案例 | −10.51 m；两处都明确为全窗指标的配对均值差 |
| F04−F03 航向配对分母 | NEED 占位 | `UA01_PAIRED_OVERALL.csv` 数据行 2：n_pairs_finite=`511`，n_registered=`540` | 511 个共同有限对；540 个故障案例域，排除 C00 |
| BY2/BY2H 水平 F04−F02 分类 | 旧 UNC02 文字写 RESOLVED，现表为 RESOLVED_NEGLIGIBLE | `UNC_DISTINGUISHABILITY.csv` 数据行 2、20：verdict=`RESOLVED_NEGLIGIBLE`，wording=`comparable (difference below reporting resolution)` | 补充材料 S9 的当前说明与原表一致；旧 UNC02 不改写 |
| F04 航向中位数的 fault-type 区间 | 旧 UNC01 将舍入后相等描述为零宽 | `UA01_DISTRIBUTION_QUANTILES.csv` 数据行 4：cluster_q50_low=`1.8859878395987226`，high=`1.8862718548526467` | 主文保留两端完整精度，明确非零宽；端点仅在三位小数展示精度下重合，S9 同步说明舍入相等不代表零宽 |
| 三处 bit-for-bit 复现承诺 | 暗示同软件/配置可从原输入逐位重现 | 已完成的保留导出核对，见 [RETAINED_SERIES_REVIEW.md](../v3_interpretation/RETAINED_SERIES_REVIEW.md) | 限定为保留导出 hash 匹配、保留字段支持的统计在预先声明容差内一致 |

中位数区间行属于 541 注册案例、519 有限结果的单方法分布；511 配对数属于排除 C00 的 540 故障案例域。二者不互换。全部区间均为原有导出，本项没有产生新置信区间。

`N00149`、`N00199` 和 `N00157` 保留原 ID，来源从舍入后的 DOC 文字改为上述 UA CSV 的精确行键和列。新增 `N00208`、`N00209`、`N00210`、`N00211` 分别记录 511、540 和中位数区间两端；原 207 个 ID 不重编号。其他原有数字、单位和来源定位保持不变，只同步其引用段落文字。

`assemble_manuscript.py` 新增有限的 `UA|...` token，直接选择唯一 CSV 行，保留数值原字符串并用 Decimal 按指定位数展示。新增数字使用固定 ID，不挤占原自动编号。历史 `{{UNC:1}}`、`{{UNC:3}}` 仍从原 UNC03 读取，只在当前展示时覆盖两句复现承诺，防止后续装配恢复旧表述；历史源文不变。CLAIM_SPECS 只增加相对路径的新条目，既存绝对路径条目未扩大修改。

Figure 6 源码直接绘制既有逐案例 `horizontal_rmse_m` 散点，并没有这些均值或配对均值标签；因此不重画图，不改变其数据、导出或映射。

## 检查及边界

[check_display_corrections.py](display/check_display_corrections.py) 完成 **287 PASS / 0 FAIL**，详见 [CHECKS.csv](display/CHECKS.csv) 与 [CHECK_RECEIPT.json](display/CHECK_RECEIPT.json)。检查直接读取小型源表，核对唯一行键、精度、当前段落、所有旧 ID 及未修改数字来源，并通过 AST 只提取所需函数，对五个更正段落和两个 UNC 段落进行内存中的定点渲染。没有导入 `common.py`，没有执行 assembler 顶层读取循环或 `main()`。

原性能 CSV、三份 UA/UNC 文字、旧 claim matrix、`READ_FILES.json` 和 Fig06 源码共 11 个小文件在检查前后 hash 相同。调用计数：solver/provider/evaluator/bootstrap/原装配控制器/载荷读取/重画图/Git 修改均为 0。检查和更正回执仅写在本目录；主代理负责本项单独提交。

这是展示和来源更正，不代表数学或机制审查通过，也不补足原输入重现同一 NAV 的证据。保留字段不足的指标、已释放载荷，以及 D22/D39 局部窗口未提取等原有限制继续有效。
