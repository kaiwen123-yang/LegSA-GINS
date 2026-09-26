# HX-05 外部对比收尾

登记提交 `0ebb341dcf968aca71ce7fe057204794935ac1d9`，已推送。

Outcome：已按登记定义完成三次 LEG-DR 输入积分与三次相对位姿评估，其余结果全部来自既存归档。官方 Hartley OFF-LIT 保留四足状态估计主行；LEG-DR 单列 INPUT_REFERENCE；自写移植与 OFF-DEF 位于补充材料。没有新解算，没有重评既有方法。

## 表的读法与口径

三序列主表按输出类型分别呈现：航向法为可用率（有效数/配对分母）、有效 RMSE、全窗因果保持 RMSE；导航法为 yaw/水平/高程 RMSE 和支持分母；相对位姿为每 100 m 位置漂移、每分钟航向漂移、对齐后水平 RMSE、参考路程。三者不合并排名。GINav BY2H 的 matched/output=2/2 不等于窗口覆盖，其覆盖只有 2/271。

补充表保留两种 S 配置、官方 OFF-DEF、自写移植两支、BY2H FILE_START、EXT03 ratio-fixed 与 RTKLIB Q=2 子集，以及 LC01-BR。BR 是改动过的 LC01，仅 A2 补充；子集不替代主行。移植 BY2H 的异常退出保留；HX-02D 已记录其初始化静止门问题，不能解释为有限精度结果。

退化表每格为 yaw/水平/高程的 median/P95、有限数/登记数、失败或不可用数；配对差只在双方有限的工况/种子上计算。P95 表示工况间分布，不是置信区间。D14/D21 外部两法各 18/18 原生发散；截断运行不进入有限样本分布。D57 的 LC01 只移位置历元，F04 在 V3 下全程无有效航向，暴露不同。

按用户明确列出的八族加 A2，主表九行覆盖 Classic-18 的 153/162 个工况；D43 的九个种子在归档中属于另一“速度噪声”族。为保持登记行定义，D43 单列 D43_VELOCITY_NOISE_SUPPLEMENT.csv，不混入速度中断。A1 等价行不重复计入 A2 分母，原始 R2 表保持不变。具体工况身份见 DEGRADATION_SCOPE_CHECK.json。

BY2O 扩展表包含六个航向输出 × 五段、六个导航方法 × 五段、GINav 五条状态行。分段为闭区间；保持值沿用全窗因果序列。封存导航分段表未报告可用率/保持值，保留 NOT_REPORTED，不推断。

数值显示至六位小数，未舍入值保存在 MANUSCRIPT_DATA.json。每个 source_id 在 SOURCE_CITATIONS.json 中给出原文件、行或字段、SHA256、运算与精确值；D43 对应 D43_SOURCE_CITATIONS.json。下文方括号是该可复核索引，全部来源哈希汇列于末尾。

## 每类结论

双天线航向：RTKLIB 三序列主行可用率为 0.111679、0.132593、0.059416，有效 RMSE 为 14.566166°、27.011169°、23.138950°；EXT04 两策略均无有效输出。有效 RMSE 必须与可用率同时阅读。[MAIN.06.BY2/BY2H/BY2O；MAIN.04/05.*]

四足状态估计：官方 OFF-LIT 三序列位置漂移为 33.633600、47.525517、28.558852 m/100 m；LEG-DR 对齐水平 RMSE 为 6.209111、9.178417、6.322412 m。LEG-DR 使用机载姿态，是条件输入参照，不能由此单独断定官方库内算法有误。[MAIN.07/08.*]

松耦合：LC01 文献配置三序列 yaw RMSE 为 2.994827°、2.208612°、2.453697°；A2 水平中位数/P95 为 1.407350/7.769345 m，有限 18/18。[MAIN.09.*；DEGRADATION.A2.LC01]

单天线：EXT05C 三序列 yaw RMSE 为 12.048642°、20.108223°、5.845502°；GINav BY2 与 BY2O 分别在 244.999 s、3561.999 s 因速度 50.638686、68.772481 m/s 越界，BY2H 仅 2/271 行、水平 RMSE 2.894928 m。[MAIN.10/11.*]

LegSA 参照：F04 三序列 yaw 为 1.886272°、1.933770°、2.433815°；BY2O 的 F02 为 2.309491°，因此没有三序列统一最优的结论。[MAIN.12.*；MAIN.13.BY2O]

## LEG-DR 定义、结果与一致性

采用 v_b = −mean_contact(ω × p_foot + foot_speed_body)，三维梯形积分；零接触相邻区间不累加。ω 使用 C4 的 −1° 修正，足端位置/速度未施加该修正，机载 rpy 与 C4 相同。NAV 输出点及天线杠杆与 HX-02E 相同。

位置漂移是水平误差范数对累计参考路程的带截距 OLS 斜率，不是终点误差/路程。负斜率不表示负误差，较小斜率也不等于较小全窗 RMSE。

|序列|位置漂移 m/100 m|航向漂移 °/min|水平 RMSE m|高程 RMSE m|yaw RMSE °|参考路程 m|评分历元|来源|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|BY2|0.069426|0.17358|6.209111|5.158908|2.306305|328.471311|2741|$HX05/RUNS/BY2/RESULT.json:metrics；SHA256 462ddd3b50e38f29a283336b8c48dd8a2aa62c8fbd4f0609d4ac76bfdb9a6483|
|BY2H|0.107526|-0.156156|9.178417|5.068659|2.14753|325.513916|2700|$HX05/RUNS/BY2H/RESULT.json:metrics；SHA256 6681648373a1bed627c49ce29356f736cc8143cfb11fdfddd60fb187054bc819|
|BY2O|-0.379391|1.426454|6.322412|5.345451|6.005779|337.422047|3771|$HX05/RUNS/BY2O/RESULT.json:metrics；SHA256 105566ee09b8784609f3538e03a8fd5ca832fe76df960056c3deebdd524dd2d1|

BY2 全部逐历元数组差为 0，NaN 掩码相同；四项指标最大差 1.7080299674621102e-09，小于 1e-6。[RUNS/BY2/RESULT.json:integration.C4_array_gate 与 C4_metric_gate]

## 每族结论

位置噪声：LC01 与 EXT05C 各 18/18 原生发散，有限样本为 0。[DEGRADATION.位置噪声.LC01 / EXT05C / F04 / F02]

位置偏差：水平 RMSE 中位数/P95：LC01 1.610601/1.752856 m，F04 1.610689/1.750921 m；两者有限数分别 18/18、18/18。[DEGRADATION.位置偏差.LC01 / EXT05C / F04 / F02]

位置中断：水平 RMSE 中位数/P95：LC01 1.40735/7.769345 m，F04 0.106991/0.128009 m；两者有限数分别 18/18、18/18。[DEGRADATION.位置中断.LC01 / EXT05C / F04 / F02]

速度中断：水平 RMSE 中位数/P95：LC01 0.259805/1.234106 m，F04 0.104648/0.144169 m；两者有限数分别 18/18、18/18。[DEGRADATION.速度中断.LC01 / EXT05C / F04 / F02]

航向噪声：水平 RMSE 中位数/P95：LC01 0.098283/0.099761 m，F04 0.097807/0.098041 m；两者有限数分别 27/27、27/27。[DEGRADATION.航向噪声.LC01 / EXT05C / F04 / F02]

航向中断：水平 RMSE 中位数/P95：LC01 3.136051/8.326274 m，F04 2.50673/15.217129 m；两者有限数分别 18/18、18/18。[DEGRADATION.航向中断.LC01 / EXT05C / F04 / F02]

多普勒：水平 RMSE 中位数/P95：LC01 0.097548/0.097548 m，F04 0.097957/0.098704 m；两者有限数分别 27/27、27/27。[DEGRADATION.多普勒.LC01 / EXT05C / F04 / F02]

时间戳：LC01 有限 9/9，F02/F04 有限 0/9；输入暴露不同，不能按同一退化程度排名。[DEGRADATION.时间戳.LC01 / EXT05C / F04 / F02]

A2：水平 RMSE 中位数/P95：LC01 1.40735/7.769345 m，F04 0.176671/0.287747 m；两者有限数分别 18/18、18/18。[DEGRADATION.A2.LC01 / EXT05C / F04 / F02]

## 图、QA 与登记后的版式调整

FIG02S 三序列分输出类型，FIG02D 九族分布，SFIG-HX 三类 Hartley 身份与输入参照。最终图的数据文件 SHA256 与首版一致；冻结积分、适配器、评估器及表格代码不变。新增 hx05_figure_layout.py 仅换行轴标签、为状态文字加白底、让零可用率点完整可见。移动图例的中间版出现导出裁切，已恢复原图例位置；中间版只作过程记录，不交付为手稿图。最终调用原 publication.qa，不覆盖其判定。

Matplotlib 报告 Axes3D 不可导入，所有图均为二维，不受此警告影响。实际 PNG 复查与各导出哈希见 VISUAL_QA.json / FIGURE_MANIFEST.json；机器结果见 MACHINE_QA.json。图注 CAPTIONS_HX05.md 使用 reference。

## 修正与事故记录

HX-02 修正 88594ef：Hartley 两支各自在初始窗口独立对齐，并登记等待上限；本次读取最终长表 7475d7ef…，不覆盖旧结果。HX-02E 以未改动官方库替换主行，长表 30fda253…；自写移植与诊断退补充。HX-03R2 更正观察器投影为 WGS84，原评估器科学输出未变，146 行由审计不可用转有限；本次使用 R2 表 17cfce31…。来源为对应登记/结果提交及 STATE_TRANSITIONS_R2.csv:family.unavailable_to_finite_n，不重新评估。

HX-05 首次 pytest 命令未找到入口，改用 python3 -m pytest 后合成与分段检查通过。LEG-DR 真实积分/评估各三次，无重试。定义冲突的原准备稿保留；用户裁定后的完整公式由登记提交固定。所有历史事故记录保持原状。

## 保存、核验与补充材料

主产出为四份 CSV、三张图的 PNG/PDF/SVG 与本报告。三张表全文另存 MANUSCRIPT_TABLES_FULL.md；来源链、原精度数据、三次评估审计及一致性门另存伴随 JSON。补充清单：三序列补充表、D43 速度噪声表、BY2O 分段表、SFIG-HX、自写移植 HX-02D 诊断引用。没有交接包。

65 pin 开始/登记前/收尾前各一份 VERIFY 记录，方法本体 423 项、既有 29 个未跟踪文件及前阶段目录检查结果见对应记录。逐文件归档与仓库副本哈希核验后清理本任务 scratch；不清理其他目录。

调用计数：{"legsa_native": 0, "legsa_evaluation": 0, "external_native": 0, "leg_dr_integrations": 3, "relative_pose_evaluation": 3, "reference_opens": 3}。每个相对位姿子进程 trace 只读打开一次并核哈希；控制进程禁止打开参考。

## 全部来源 SHA256

|文件|SHA256|
|---|---|
|$HX02/01_INPUT_PINS/HARTLEY/BY2/H5_INPUT_CACHE.bin|c169e26d66f35fe200bb17a695353cd2d751482df1cd97996a7a8afff8662065|
|$HX02/01_INPUT_PINS/HARTLEY/BY2/H5_INPUT_CACHE_MANIFEST.json|159c822a26a7b604946e20c9dd70d56f39eff9369b26a8ec17b3567c00a0a7ef|
|$HX02/01_INPUT_PINS/HARTLEY/BY2H/H5_INPUT_CACHE.bin|732d45c70815ba65c7832ecbfb41edf5c571fd4e80fb13df497a99fe9863436e|
|$HX02/01_INPUT_PINS/HARTLEY/BY2H/H5_INPUT_CACHE_MANIFEST.json|54b17d2f18d261d6f14533db22d5faeaf8a022ff29f1f403354db83bf1e350b2|
|$HX02/01_INPUT_PINS/HARTLEY/BY2O/H5_INPUT_CACHE.bin|8786456127571475e88a89a47ab30f118b09a789e521690b82170985e4aaec35|
|$HX02/01_INPUT_PINS/HARTLEY/BY2O/H5_INPUT_CACHE_MANIFEST.json|d65501f39a0130cd8173d7bb0f0f629b5524e036d3f2427413cc8ddd24c2e3ae|
|$HX02/01_INPUT_PINS/INPUT_PINS.json|723ae92bbe4a2622ad5a1f254c504439ac015e9705495eb9c8310b3e1c8a670f|
|$HX02/90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv|7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba|
|$HX02/RUNS/BY2H__GINAV__NONE__CONTRACT_START__NA/eval/D8_BOUNDED_GATE.json|5ec81992f1606915a20f5b4f7b5b11477f4fa53e2da5b6e41c02e1db9cd376c0|
|$HX02/RUNS/BY2O__EXT01__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT01.csv|e50514036850efe5460f3770c5ba242d963c9cd1b992b166047907944c8d3f15|
|$HX02/RUNS/BY2O__EXT02__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT02.csv|abfa93ef5127e108a3937d7d80494b51695d425d387216a2ed390afe8a262a29|
|$HX02/RUNS/BY2O__EXT03__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT03.csv|182dbffc9a91fec5a8b6f6bde83919f6c0d4c32fdaf72eb18f5f1b8e3472fe68|
|$HX02/RUNS/BY2O__EXT04__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT04_FAR.csv|7cc6b7d24f97cb162e370d482121fdbeb44f569f0296391553edad2791ecd612|
|$HX02/RUNS/BY2O__EXT04__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT04_PAR.csv|7cc6b7d24f97cb162e370d482121fdbeb44f569f0296391553edad2791ecd612|
|$HX02/RUNS/BY2O__GINAV__NONE__FILE_START__NA/eval/D8_BOUNDED_GATE.json|7bc7d4a0c9d42960373e5ee803ad8afaffc0a647d39691dd903c04efd301b83c|
|$HX02/RUNS/BY2O__RTKLIB__NONE__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_RTKLIB.csv|86a716ed4142295420747ac2f2216abaff8e67ce7c526e9c44ae2fabdc6fa059|
|$HX02/RUNS/BY2__GINAV__NONE__C00__NA/eval/D8_BOUNDED_GATE.json|7ea5aa68e042d58034fb0ee1076a78733ddd9e5bbeeb8a7594aa06245839250b|
|$HX02D/EXECUTION_V2/B_REFERENCE_FREE/BY2/OUTPUT/B_ARRAYS.npz|70f85a3687d3d44b2795ad878ecdf3acbba461f513d44154bf19575eb97ba468|
|$HX02D/EXECUTION_V2/C_REFERENCE/BY2/OUTPUT/C_TABLES.json|15e947c9f0fa3c9bcf6a39a5bb9d281fe34e2442fd275728f4cdd497926983bd|
|$HX02D/HX02D_HARTLEY_DIAGNOSTIC.md|7d0643cf396198372c4c50f91d6f0d9709bfa14bebf4f3621cb655ac8787e7aa|
|$HX02E/90_AGGREGATE/HARTLEY_OFFICIAL_TABLE.csv|30fda253e5fa4f56b829ae9e5184cefc0258c74d57c0e3fadbae98e407cbd888|
|$HX03R2/90_AGGREGATE/DEGRADATION_EXTERNAL_SUMMARY_R2.csv|2be556867bfb134605d62d29a08c393712573303910c7b810c60e8d588d03b69|
|$HX03R2/90_AGGREGATE/DEGRADATION_EXTERNAL_TABLE_R2.csv|17cfce3191231c1631b0b3b1c2d8196a838690e1e9eae83bbcef0621f23d4989|
|$HX03R2/90_AGGREGATE/DEGRADATION_PAIRED_R2.csv|74ff5a8a15e598a5e589c0b50c7cdcce29e96e289d3c00d8c9130dc5a432d840|
|$HX03R2/90_AGGREGATE/STATE_TRANSITIONS_R2.csv|817926887c54c0c6abcbdb4b75cbe356a54e1c5b27789155e0641e2c7c1d3a43|
|$HX05/RUNS/BY2/RESULT.json|462ddd3b50e38f29a283336b8c48dd8a2aa62c8fbd4f0609d4ac76bfdb9a6483|
|$HX05/RUNS/BY2H/RESULT.json|6681648373a1bed627c49ce29356f736cc8143cfb11fdfddd60fb187054bc819|
|$HX05/RUNS/BY2O/RESULT.json|105566ee09b8784609f3538e03a8fd5ca832fe76df960056c3deebdd524dd2d1|
|$RAW_ROOT/BY2_BY3/2026-03-06/高层数据/by1.txt|0e5c62e0a5af0b6c32c51b535cc90701677276fc73c5623b72abda66cc148f2e|
|$RAW_ROOT/BY2_BY3/2026-03-06/高层数据/by2.txt|95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278|
|$RAW_ROOT/BY2_BY3/2026-03-06/高层数据/by3.txt|b2e80763c613a5a0d6739aea90ea3ed4f8c9170cf5f2f6b73e5a000a666f0c49|
|$V3/07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv|44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1|
|$V3/07_AGGREGATE/ADDENDUM_TABLE_V3.csv|82aaef841c4e62d13ce4c4a2625b063ec3ac02ffc379db835cf1452486c978bb|
|$V3/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv|13a2c4e8de7638fa8672bb49d6556f531061a3924fe7dbf6911adfcf53779876|
|$V3/07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv|301cec24cb454781138aa39dd3b86a4b37b7855773e6d28e891b7231047d4c39|
|$W/configs/paper_rebuild/hext/HX02E/CONTRACT.json|d8511bd8bbbe84a77a257ba04b6794c22a9aa4517580899cdbfcf71d18ca0f9f|

最终实际 PNG 复查 3/3 通过，原机器 QA 25/25 通过；24 个面板的数据绑定与首版相等，PNG 均至少 4096 px 宽。来源 VISUAL_QA.json 与 MACHINE_QA.json，导出哈希见 FIGURE_MANIFEST.json。
