# 期刊研究重构：GPS Solutions 与 TIM

日期：2026-10-04。本目录给出基于已证项目输入的研究判断、测量模型、primary 来源和 PPT 解释图。**原 V3 科学结果不变；不把已有位置差 heading 改名为内部模糊度算法；不宣称完成实体校准或已投稿就绪。** 正式算法名称仍由作者重新讨论。

|入口|用途|当前边界|
|---|---|---|
|[官方要求与实际输入](OFFICIAL_VENUE_AND_ORIGINAL_INPUT_BOUNDARY.md)|区分刊物要求、审稿判断、原方法实际数据层次|GPS 不强制 AR；TIM 要有 I&M 主贡献；preprint 官方措辞冲突待真实投稿前核实|
|[GPS 方向决定](GPS_SHORT_BASELINE_MOVING_BASE_DECISION.md)|当前条件融合问题与未来新载波研究的一页判断/方案|当前 G1+G2；未来 A1+A2+T1 独立版本，尚未科学执行|
|[TIM 测量模型](TIM_MEASUREMENT_MODEL_AND_VALIDATION_PLAN.md)|10 个方程、相关性/可辨识性、最小物理闭环|缺实体预算与 held-out coverage，RMSE 不等于 measurement uncertainty|
|[假设敏感性图](assumed_sensitivity/README.md)|可直接进入 PPT 的 U01–U03 PNG/SVG/CSV|常数假设解析图，不是实际仪器标定/新性能实验|
|[primary 文献与主张映射](PRIMARY_LITERATURE_AND_CLAIM_MAP.csv)|16 项来源、访问日期和实际阅读范围|明确摘要/选读/全文范围；不声称完整全文复现|
|[所需记录与验收](REQUIRED_RECORDS_AND_ACCEPTANCE.csv)|13 项可计算/作者事实/新增测量分界|未知 covariance、装置/clock 不能零填或由照片推测|
|[研究问题与主图](RESEARCH_QUESTIONS_AND_MAIN_FIGURE_PLAN.csv)|英文问题及 8 个主图/汇报建议|假设图与实际结果分开；未来 AR 图不当已做方法图|

建议次序：先完成当前 GPS 条件融合科学稿，保留原全矩阵和真实负结果；并行收集实体点位、安装、时钟与参考配置事实。TIM 先围绕量与联合测量模型整理可计算部分，再在有证据的输入分布和独立/可识别验证链上做覆盖检验。如果作者决定转向载波/moving-base，先核输入与实体记录是否满足，另立前注册研究，不能混装旧表来宣称新 AR 成立。这里不要求为了工程小差异重跑旧 6,468 全矩阵。

## 阅读与交付范围

[Block01](BLOCK01_READY_RECEIPT.json)、[Block02](BLOCK02_ASSUMED_FIGURES_READY_RECEIPT.json)、[Block03](BLOCK03_READY_RECEIPT.json) 分别冻结各自文件身份；[Block01 阅读账本](BLOCK01_READ_COVERAGE.csv) 与 [Block03 阅读账本](BLOCK03_READ_COVERAGE.csv) 记录真正读到的范围。没有全仓每一字完成的声明。所有科学 raw/reference、生成器、native、evaluator 在本研究线均未启动/读取；仅常数假设脚本生成三张解析图。

本目录是研究支撑包，正式稿和 PPT 由对应写作任务组织。作者、资金、设备模式、安装尺寸和独立性不由文稿代替事实。GPS/TIM 不以同一贡献仅改词拆成同时投稿的两稿。

## RV 归因更正

当前 GPS/TIM 说明已将“单模块诊断”限定到真正闭合的 RD/HV 条件对照。原 F02→F03 的 RV 与 heading-gate 共变是结构对照，不能识别 RV 单独效应；不据成绩差重命名为 pure-RV。此次仅修改解释文字，原数据、图表、科学运行和先前阶段收据保留。[此次版本与更正记录](RV_ATTRIBUTION_CORRECTION_READY_RECEIPT.json) 绑定修改后文件；Block03 原收据描述更正前文稿身份。
