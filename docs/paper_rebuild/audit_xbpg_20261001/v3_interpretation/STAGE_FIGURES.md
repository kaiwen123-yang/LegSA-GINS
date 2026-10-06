# 阶段十组图：实际图像与结果含义

本轮只读 planner 已逐张打开十个现存 PNG，并结合原渲染定义和来源表阅读；没有重新渲染。图位于 `<V3_ROOT>/08_FIGURES/<图号>/<图号>.png`。每组 PNG/PDF/SVG 是同一结果的三个格式，不是三次实验。精确直接来源和原关系行键保存在 `figures/STAGE_SOURCE_LINKS.csv`，沿用上一轮来源图，不重建库存。

## MFIG00：C00 的时序和唯一保留配对轨迹

横纵坐标随面板不同：a 为 East–North 位置（m），b 为时间与展开航向（°），c 为时间与有符号 yaw error（°），d 为时间与 Up（m）。a/b/d 只有商业 reference 和 F04，不是五方法完整轨迹对照；a/d 用 MATCHED_TRAJECTORY 的 LLH 转到首参考点 ENU。图中的 Truth 是旧标签，本轮继续称商业融合 reference。

c 的五方法为 F01 灰、F02 黄、F03 浅蓝、A04 蓝、F04 橙；来自 C00 RUN_00001/2/3/6/4 的 v3 error_series。轨迹来源是 RUN_00004 的唯一九字段 MATCHED_TRAJECTORY；本轮已全文读取该文件及误差，未用参考加误差重建算法轨迹。图只描述 BY2 C00 一次录制；完整 NAV 已释放，不能把保留的匹配位置当全采样 NAV。

## MFIG01：有限案例的分布与失败分母

来源 CORE_541_TABLE_V3，五方法顺序 F01/F02/F03/A04/F04。每法注册 541，有限分别 521/498/512/513/519，失败 20/43/29/28/22。H/yaw 分布面板区分空心圆 mean、菱形 median、三角 P95 和 worst 5% mean；后者为最大的 ceil(0.05n) 个有限 case RMSE 的均值，不是 P95。ECDF 的误差横轴采用对数，纵轴为有限 case 累积比例。

例如 F04 H mean=0.6185612890785892 m、median=0.09822807379435361 m，A04 H mean=0.577658775651872 m；F04 yaw worst5% mean=15.789495456125561°，A04=44.69996778401163°。yaw 尾部与水平尾部方向不同，且有限集合不同。图内失败标记不能自动并入 ECDF，也不能因 F01 失败更少就称其满足相同航向任务。

## MFIG02：A04−F03，并非 SA 单因素

横轴 D01–D60、纵轴 H/yaw 配对差。蓝点为该 type 的共同有限种子差值中位数，竖线是种子观察范围，**不是 CI**。灰叉 D27/D57/D60 表示无共同有限对，不赋予零误差。族级 win rate 分母是有限配对；图内 Outage 63/63、Mixed 17/36 是有限/注册配对数量，不是胜场。

来源 PAIRWISE_CASE_LEVEL_V3 的 comparison=A04_vs_F03，按 case/method 对应；A04 开 RD/RP/HV 而不开 SA，相对 F03 是多模块组合。图不能单独归因 SA 或 RP。

## MFIG03：F04−A04 的有限配对和散点

族级纵坐标为配对差中位数与旧 B=10000 配对 bootstrap CI；散点横轴 A04、纵轴 F04，只画共同完成的案例。来源 PAIRWISE_SUMMARY_V3 的 full_vs_no_SA 和对应 CASE_LEVEL。

Mixed n=18，H median=0.001477694094307885 m，CI=[−0.0027548687412595196,0.39982821036144633]；yaw median 约 −0.000020284°，CI=[−14.661054224781083,0.00026379881729]。散点对角线只比较已有有限值；F04 新增完成和新增失败须连读各族 2×2 表，不能消失在图外。

## MFIG04：展示梯与消融

上排有限分布只含五展示配置；下排为 F04−noRD/noSA/noRP/noHV/noGo2 的 overall 配对中位数及旧 CI。负号代表该误差降低，正号代表升高，不能把不同指标的方向统一成“模块有益”。直接来源 CORE_541_TABLE_V3、PAIRWISE_SUMMARY_V3 及原 manifest；ABLATION_TABLE_V3 可作延伸阅读，完整 11 配置另见 FULL_ABLATION_TABLE_V3 与本轮自然/CORE 报告。

## MFIG05：五个固定 seed00 案例，空白不是零

固定行 D27/D60/D04/D12/D58，列为时间 H（m）与 yaw error（°），F03/A04/F04，灰底为原固定事件区间。D27/D60 三方法都是 DIVERGED，没有可画误差，自动纵轴 0..1 不是误差落在 [0,1]；横轴仍固定 66–340 s。完整运行键如下。D04/D12/D58 仅是固定例，不代表九种子平均或最坏尾部。

|case seed00|F03|A04|F04|
|---|---|---|---|
|D27|RUN_02588|RUN_02591|RUN_02589|
|D60|RUN_05855|RUN_05858|RUN_05856|
|D04|RUN_00311|RUN_00314|RUN_00312|
|D12|RUN_01103|RUN_01106|RUN_01104|
|D58|RUN_05657|RUN_05660|RUN_05658|

窗口读法须与本轮 `WINDOW_SUMMARY.csv` 同看：旧 evaluator_event 与真实 provider centered interval 在部分类型不是同一窗口。已保存的图不改；这属于展示支持说明，不重选对 F04 有利的片段。原图的断线/无数据保留，未填补失败。

## MFIG06：运行计数，不是因果归因

图为水平条形图：纵轴 case_family（含 clean_normal），四面板横轴分别为 changed-weight fraction、RD mean count、Scheme-C rejected yaw mean count、HV mean count。直接数字源是 CORE_541_TABLE_V3 的 F04 行；publication/protocol_v2_figures.py::mfig06 271–288 行逐字段转数值后取有限均值。有限 counter 可来自失败 native，分母按字段而异，不必等于精度图的成功集合。

C00 touch=3946/7932=0.49747856782652544，RD=1108、yaw reject=21、HV=1369。这说明有计数记录，不能证明 N09/N12/N16 在特定时刻触发或造成误差，也不能从误差曲线倒造 update_count。字段和原行键沿 STAGE_SOURCE_LINKS 精确连接。

## SFIG01：热图的白色和对数色阶

横轴五展示配置、纵轴 D01–D60，六指标以有限 case **mean** 做对数热图。白色为不可用，不是零；D27 全白、D57 除 F01 外白。直接来源 CORE_541_TABLE_V3，由 protocol_v3/figures.py 335–353 行调用 type_heatmap 按 type/method/metric 求有限均值。此图不含 C00、不展示完整十一配置，颜色差不能直接当倍数，须先读色条和单位。

## FIG02S：三序列全窗外部参照

三序列六指标面板，LC01 绿色纹理、F02 黄、A04 蓝、F04 橙、LC01-S 黑空心菱形，来源 MAIN_TABLE_V3/SEQUENCE_TABLE_V3。柱为原全窗指标，无 CI。内部方法为正式 V3，LC01/LC01-S 是保留旧协议和 start 身份的引用层 B，不因 evaluator=v3 而成为本轮新 native。BY2H 的起点及几何审计状态必须连读外部解释。

## FIG02S-b：BY2O primary 与 secondary

横轴为两段，纵轴 yaw RMSE（°）与 H RMSE（m），显示 F02/A04/F04/LC01/LC01-S。来源 BY2O_SEGMENT_TABLE：F04 primary/secondary 分母 7,612/2,754，LC01 为 7,823/2,819，并非共同时间网格。图没有 outside，不表示 outside 不重要；必须连读 `natural/BY2O.md` 的 full/primary/secondary/inside_union/outside 五视图。既有 R5/R5F 选择已使用该录制，不能称新盲测。

本轮查看图像与来源，未以原 manifest PASS 替代目视阅读。10 组图直接关系 55 条；图像能展示保留内容，不证明所有上游全采样载荷仍存在，不完成算法数学审查。
