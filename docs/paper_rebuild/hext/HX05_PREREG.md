# HX-05 收尾定义登记

起点 586a429796ba5e4429a7c9d25683f97ed761a94c；git pull --rebase 已完成。本次只新增 LEG-DR 输入积分与三次相对位姿评估；LegSA 解算/评估、外部方法解算均为 0。旧稿的定义冲突已由用户裁定，历史准备记录保留。

## A：LEG-DR 定义与一致性门

按用户裁定，采用 hx02d_reference_free.py:232–240 的完整定义：

`v_b = −mean_contact(ω × p_foot + foot_speed_body)`。

ω 与 p_foot 取该实现的同一来源：Go2 原始角速度经绕 x 轴 −1° 修正，与 H5 缓存角速度逐元素核对；foot_position_body 与 foot_speed_body 来自钉住的高层日志，腿序按 [1,0,3,2] 映射，不施加 −1° 修正。足端位置与足力分别核对缓存字段，沿用缓存接触位掩码，不重检测。

用高层消息 rpy 构成 `Rotation.from_euler('xyz', rpy)`，将 v_b 旋转到世界系。时间先作整数纳秒差再转秒；直接复用 hx02d_reference_free.integrate（:76–84）作三维梯形积分。只有区间两端均有有限速度观测才累加；任一端零接触则该区间三维位移增量为零，不插补。保留全部三维坐标，不能改为只积水平分量。位置起点为零。

BY2 一致性门为 1e-6：逐历元比对 HX-02D EXECUTION_V2/B_REFERENCE_FREE/BY2/OUTPUT/B_ARRAYS.npz 的时间、姿态、机体速度、积分位置、接触位及源行；NaN 掩码须相同。首次 BY2 评估后，再核 C_REFERENCE/BY2/OUTPUT/C_TABLES.json 的 C4.foot_speed_body：水平/yaw RMSE、位置与航向漂移各绝对差 ≤1e-6；未过即硬停，保留产物，不重跑或改定义。

NAV 使用 HX-02E 同字段与 17 位有效数字；输出点是 Go2 body IMU，roll/pitch/yaw 为机载姿态。无速度观测行的 NAV 速度列填零占位，但积分保留 NaN 与缺测记录；零偏及 state_dimension=0 表示未估计，不代表滤波器状态。评估器只消费姿态与位置。

## 已固定的输入与评估边界

H5_CACHE 为三份既有二进制文件；缓存格式仅包含时间、22 个数值、接触位掩码及事件标志，不含 rpy 和 foot_speed_body。后二者读取 HX-02 INPUT_PINS.json 已钉住的 Go2 高层日志，按整数纳秒时间戳与缓存一一匹配，做法沿用 HX-02E。没有接触重检测，不调用任何方法运行器。

三序列评估窗 BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]；复用 HX-02E 的缓存、base_time、b_med 与参考哈希。输出 NAV 采用 HX-02E 的旋转矩阵、位置、速度及 rpy 字段；由原 Hartley 相对位姿适配器施加 FRD 杠杆 [0.03, 0.03 − 0.5·b_med, −0.30] m 到天线中点。b_med：BY2 0.356191491865984 m、BY2H 0.35418777593777223 m、BY2O 0.35013463864843675 m；每支在评估窗起始 10 s 独立作 yaw + 平移对齐，来源 HX02E/CONTRACT.json:sequences。每序列只调用原 HX-02 相对位姿评估子进程一次，经原启动器与 strace 审计；合计严格 3 次，参考各只读打开一次并核验哈希。F04/F02 不新增相对位姿评估。

LEG-DR 的 role=INPUT_REFERENCE；说明为“同一份运动学输入不经滤波能达到的漂移水平”，非文献方法。机载姿态是输入，不能当作独立精度上限。

## BY2O 分段

主段闭区间 [3369.94,3411.95]，次段 [3495.94,3508.94]，并集、全窗减并集、全窗 [3186,3563]。只读 HX-02 六种航向输出的既有 HEADING_ERROR_SERIES。分母为切片内全部配对行；可用率为 valid 数/分母；有效和保持 RMSE 分别对有限的 error_valid_deg、error_hold_deg 算 RMS，各报评分行数。沿用归档的因果保持序列，不在切片起点重置；无有效值不填零。

LC01、EXT05C、F01–F04 只选 BY2O_SEGMENT_TABLE.csv 中 evaluator_contract_v3 的五段行，完整原行保存在 original_fields_json。该封存表未报告的航向法可用率/保持值字段写明 NOT_REPORTED，不推断成 100%。GINav 为发散状态行。

## 三张手稿表

EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv：14 行；列 category, method, config, role, output_type, BY2, BY2H, BY2O, source_ids, notes。航向六行包含可用率及有效数/分母、有效与保持 RMSE；官方 OFF-LIT 与 LEG-DR 包含位置/航向漂移、对齐水平 RMSE、参考路程；LC01、EXT05C、GINav 及 F04/F02/F01 保留各自导航指标和支持分母。BY2H GINav 的 matched/output=2/2 与窗口覆盖 2/271 分列披露。

EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv：LC01-S、EXT05C-S、官方 OFF-DEF、自写 Hartley 移植两支、EXT03 ratio-fixed 子集、RTKLIB Q=2 子集、LC01/LC01-S/EXT05C/EXT05C-S 的 BY2H FILE_START 行，另 LC01-BR 的 BY2 A2 家族摘要。移植标注“自写移植，未通过精度验证，见 HX-02D”；BR 标注“改动过的 LC01”。不适用的序列写明状态。

DEGRADATION_MANUSCRIPT.csv：位置噪声、位置偏差、位置中断、速度中断、航向噪声、航向中断、多普勒、时间戳、A2 共 9 行。方法列 LC01、EXT05C、F02、F03、A04、F04，各指标 median/P95、有限数/登记分母、失败或不可用数；两列 LC01−F04、LC01−F02 包含三指标配对差中位数和配对数。外部统计与配对直接读 HX-03R2；LegSA 从指定两个 V3 表按相同 case_id 汇总，P95 为线性经验分位数。PRE_FAILURE 不并入分布。D14/D21 外部两法写“18/18 原生发散”；D57 注明输入暴露不同。

SOURCE_CITATIONS.json 为每个表格单元 source_id 给出文件、行/字段、SHA256、汇总运算和未舍入数值；SOURCE_SHA256.json 汇列全部实际来源。显示值保留六位小数，原始精度保存在伴随数据。失败、未报告与不适用保留文字原因。

## 图的面板与 QA

FIG02S：5×3 面板，列为三序列；行为航向可用率、有效航向 RMSE、导航 yaw RMSE、导航水平 RMSE、相对位置漂移。F04/F02 只在具有同名已归档指标的 RMSE 面板画参照线，不给相对漂移面板虚构参照。不同输出类型与分母不混用。

FIG02D：yaw、水平、高程三面板；九族内画 LC01/F02/F04 的中位数和经验 P95 上端，明确不是置信区间；无有限结果用标记与 n/N，不留白。

SFIG-HX：三序列列、位置与航向漂移两行；自写移植 S/LIT、官方 OFF-LIT/OFF-DEF、LEG-DR 五种身份分别标记。BY2H 移植初始化失败保留文字状态。

沿用 canonical541_figures.py 实际导入的 publication/style.py，不修改样式源文件。PNG 至少 4096 px，并导出 PDF、SVG。机器 QA 核单位、面板标签、非空、图例、禁止文字与重复栅格；另外逐张查看实际 PNG，检查截断、重叠、状态标记及标题数据一致。英文图注使用 reference。

## 当前检查状态

开始门：65/65 pin（含 59 CSV）、423/423 方法本体、29/29 既有未跟踪文件通过。保护目录既存文件数量：HX02 12678、HX02D 82、HX02E 311、HX03 14525（含 HX03R1）、HX03R2 7477。记录路径、大小、mtime_ns，另对实际消费来源核 SHA256。登记前再次核 65/65 pin、423/423 方法本体、29/29 未跟踪文件与既存目录元数据；结果见 VERIFY_REGISTRATION.json。收尾前再核第三次。

F04 三序列 yaw 舍入为 1.886272 / 1.933770 / 2.433815；LC01 BY2 为 2.994827460，均已核对指定封存行。三项分段单元检查与三项积分接线检查均通过（TABLE_UNIT_CHECKS.xml、LEG_UNIT_CHECKS.xml），真实输入积分一致性门在登记后运行。首次直接调用 pytest 命令因 PATH 中无该入口退出 127，随后 python3 -m pytest 正常运行；无解算或评估调用。

登记时真实积分 0、LegSA 解算/评估 0/0、外部解算/参考评估 0/0；未创建交接包。既有 29 个未跟踪文件未动。登记提交后才积分，BY2、BY2H、BY2O 顺序各一次，子进程上限 600 s，无自动重试。

## 保护、存储与停止规则

旧 HX-02/02D/02E/03/03R1/03R2 与 V3 只读；冻结评估器、适配器和 423 项方法本体不改。除 A 的积分及三次评估外，只读取既存文件并汇总或绘图。控制进程以 Python 文件打开守卫禁止 trace/bag/fpl，参考仅由原登记启动器下的 strace 子进程打开、只读一次并核哈希。BY2O 切片只读归档误差序列。

中间文件仅在 $SCRATCH/HX05（此处 $SCRATCH 为用户指定 CLEAN9_EXTERNAL_COMPARISON scratch 根）；结果归档 $HX05，逐文件 SHA256 相等后删除对应 scratch。每次积分前 E 可用 ≥40 GB、G ≥30 GB，scratch 总量 ≤20 GB；E 不写，不做交接包。既存阶段检查使用路径/大小/mtime_ns，实际消费源另核内容哈希；不把元数据检查声称为全目录内容哈希检查。

硬停：任何解算调用；参考打开超过三次或在控制进程打开；任一 65 pin 不一致；BY2 C4 一致性门不过；方法本体变化。硬停保留记录、写报告提交并等待，不更换公式、不放宽容差。无数值门槛筛选结果，失败与不可用均带原因保留。首提交 prereg(hx05): closeout definitions；收尾 closeout(hx05): external comparison tables and figures，AGENTS.md 追加一行。

## 冻结代码 SHA256

合约 `$W/configs/paper_rebuild/hext/HX05_CONTRACT.json` SHA256：`ed19e05415350bda270d34cf390990fc17104eecca95d635214fb97cea1da518`。下表路径相对 $W。

| 文件 | SHA256 |
| --- | --- |
| src/legsa_gins/paper_rebuild/hext/hx05_leg_dr.py | 75c9fb48d236316078550fc70f849a80640049e7f33a5b3bae69614a6be91c0c |
| scripts/paper_rebuild/hx05_execute.py | 2a998a5e5adbe7a80aeb951dfd791963d40536d3bd027c9cafc7cc3c029956d7 |
| src/legsa_gins/paper_rebuild/hext/hx05_common.py | 922e677b8d7d0727ba4b64760f2a7a5fafdb24057ce07ac66ee9d36003287abc |
| src/legsa_gins/paper_rebuild/hext/hx05_tables.py | 0a6870e54089a119b45092942862b4a9d31b4bcf6c6471603e0f8c035e9201d9 |
| src/legsa_gins/paper_rebuild/hext/hx05_figures.py | 80f678f4be97fdff65ade35711df09467e3f847269ce48d807b2173c970e4a2f |
| src/legsa_gins/paper_rebuild/hext/hx02d_reference_free.py | 1bcfa0476ee3e340f2b9818bd78d2441d28ea509ef0ad70a2773e23221d3545a |
| src/legsa_gins/paper_rebuild/hext/hx02_evaluation_process.py | c94093d1fbf94c9f4db9f6f59334666ea8897c59bcd67654afd4a9914c7764fb |
| src/legsa_gins/paper_rebuild/hext/hx02_relative_pose_evaluation.py | d5a024d2218aeae3c1c24c211b170cabad7b4c730fd02b43c270fe2d6f1fa4d1 |
| src/legsa_gins/paper_rebuild/publication/style.py | bb6a4571ce81638ad44fa4f5cb39ad35ad121640fc54d03e92cf47b8a9a6bfb7 |
| src/legsa_gins/paper_rebuild/publication/qa.py | caf00d949c2a2f573e3aa0de7a17b7d4046cd7870fbb8beaccfa575e60bb9fdd |
| src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h5.py | 3b9e57d5470cf33360564b0736a81a31ee67c1274c9a87b7e335921f58a399c2 |
| scripts/paper_rebuild/hx05_prepare.py | 73c131c9fed61bcadafe889894fff37f711136b03e9a13837d4c8752c1097a43 |
| tests/paper_rebuild/test_hx05_leg_dr.py | 94b759650a69138ad5c8ad136a2310d27bfb396833099554ff7a9a5a17d36f30 |
| tests/paper_rebuild/test_hx05_tables.py | 1ac8093a58789d42b0dc3eddc244de5435651493d2c49f5793c9682311a64c75 |

## 已核验来源 SHA256

| 文件 | SHA256 |
| --- | --- |
| $HX02/90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv | 7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba |
| $HX02E/90_AGGREGATE/HARTLEY_OFFICIAL_TABLE.csv | 30fda253e5fa4f56b829ae9e5184cefc0258c74d57c0e3fadbae98e407cbd888 |
| $HX03R2/90_AGGREGATE/DEGRADATION_EXTERNAL_TABLE_R2.csv | 17cfce3191231c1631b0b3b1c2d8196a838690e1e9eae83bbcef0621f23d4989 |
| $HX03R2/90_AGGREGATE/DEGRADATION_EXTERNAL_SUMMARY_R2.csv | 2be556867bfb134605d62d29a08c393712573303910c7b810c60e8d588d03b69 |
| $HX03R2/90_AGGREGATE/DEGRADATION_PAIRED_R2.csv | 74ff5a8a15e598a5e589c0b50c7cdcce29e96e289d3c00d8c9130dc5a432d840 |
| $HX03R2/90_AGGREGATE/STATE_TRANSITIONS_R2.csv | 817926887c54c0c6abcbdb4b75cbe356a54e1c5b27789155e0641e2c7c1d3a43 |
| $V3/07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv | 44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1 |
| $V3/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv | 13a2c4e8de7638fa8672bb49d6556f531061a3924fe7dbf6911adfcf53779876 |
| $V3/07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv | 301cec24cb454781138aa39dd3b86a4b37b7855773e6d28e891b7231047d4c39 |
| $V3/07_AGGREGATE/ADDENDUM_TABLE_V3.csv | 82aaef841c4e62d13ce4c4a2625b063ec3ac02ffc379db835cf1452486c978bb |
| $HX02/01_INPUT_PINS/INPUT_PINS.json | 723ae92bbe4a2622ad5a1f254c504439ac015e9705495eb9c8310b3e1c8a670f |
| $W/configs/paper_rebuild/hext/HX02E/CONTRACT.json | d8511bd8bbbe84a77a257ba04b6794c22a9aa4517580899cdbfcf71d18ca0f9f |
| $HX02D/EXECUTION_V2/B_REFERENCE_FREE/BY2/OUTPUT/B_ARRAYS.npz | 70f85a3687d3d44b2795ad878ecdf3acbba461f513d44154bf19575eb97ba468 |
| $HX02D/EXECUTION_V2/C_REFERENCE/BY2/OUTPUT/C_TABLES.json | 15e947c9f0fa3c9bcf6a39a5bb9d281fe34e2442fd275728f4cdd497926983bd |
| $HX02D/HX02D_HARTLEY_DIAGNOSTIC.md | 7d0643cf396198372c4c50f91d6f0d9709bfa14bebf4f3621cb655ac8787e7aa |
| $HX02/RUNS/BY2O__EXT01__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT01.csv | e50514036850efe5460f3770c5ba242d963c9cd1b992b166047907944c8d3f15 |
| $HX02/RUNS/BY2O__EXT02__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT02.csv | abfa93ef5127e108a3937d7d80494b51695d425d387216a2ed390afe8a262a29 |
| $HX02/RUNS/BY2O__EXT03__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT03.csv | 182dbffc9a91fec5a8b6f6bde83919f6c0d4c32fdaf72eb18f5f1b8e3472fe68 |
| $HX02/RUNS/BY2O__EXT04__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT04_FAR.csv | 7cc6b7d24f97cb162e370d482121fdbeb44f569f0296391553edad2791ecd612 |
| $HX02/RUNS/BY2O__EXT04__LIT__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_EXT04_PAR.csv | 7cc6b7d24f97cb162e370d482121fdbeb44f569f0296391553edad2791ecd612 |
| $HX02/RUNS/BY2O__RTKLIB__NONE__FILE_START__NA/eval/HEADING/OUTPUT/HEADING_ERROR_SERIES_RTKLIB.csv | 86a716ed4142295420747ac2f2216abaff8e67ce7c526e9c44ae2fabdc6fa059 |
| $HX02/RUNS/BY2__GINAV__NONE__C00__NA/eval/D8_BOUNDED_GATE.json | 7ea5aa68e042d58034fb0ee1076a78733ddd9e5bbeeb8a7594aa06245839250b |
| $HX02/01_INPUT_PINS/HARTLEY/BY2/H5_INPUT_CACHE.bin | c169e26d66f35fe200bb17a695353cd2d751482df1cd97996a7a8afff8662065 |
| $HX02/01_INPUT_PINS/HARTLEY/BY2/H5_INPUT_CACHE_MANIFEST.json | 159c822a26a7b604946e20c9dd70d56f39eff9369b26a8ec17b3567c00a0a7ef |
| $RAW_ROOT/BY2_BY3/2026-03-06/高层数据/by2.txt | 95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278 |
| $HX02/RUNS/BY2H__GINAV__NONE__CONTRACT_START__NA/eval/D8_BOUNDED_GATE.json | 5ec81992f1606915a20f5b4f7b5b11477f4fa53e2da5b6e41c02e1db9cd376c0 |
| $HX02/01_INPUT_PINS/HARTLEY/BY2H/H5_INPUT_CACHE.bin | 732d45c70815ba65c7832ecbfb41edf5c571fd4e80fb13df497a99fe9863436e |
| $HX02/01_INPUT_PINS/HARTLEY/BY2H/H5_INPUT_CACHE_MANIFEST.json | 54b17d2f18d261d6f14533db22d5faeaf8a022ff29f1f403354db83bf1e350b2 |
| $RAW_ROOT/BY2_BY3/2026-03-06/高层数据/by3.txt | b2e80763c613a5a0d6739aea90ea3ed4f8c9170cf5f2f6b73e5a000a666f0c49 |
| $HX02/RUNS/BY2O__GINAV__NONE__FILE_START__NA/eval/D8_BOUNDED_GATE.json | 7bc7d4a0c9d42960373e5ee803ad8afaffc0a647d39691dd903c04efd301b83c |
| $HX02/01_INPUT_PINS/HARTLEY/BY2O/H5_INPUT_CACHE.bin | 8786456127571475e88a89a47ab30f118b09a789e521690b82170985e4aaec35 |
| $HX02/01_INPUT_PINS/HARTLEY/BY2O/H5_INPUT_CACHE_MANIFEST.json | d65501f39a0130cd8173d7bb0f0f629b5524e036d3f2427413cc8ddd24c2e3ae |
| $RAW_ROOT/BY2_BY3/2026-03-06/高层数据/by1.txt | 0e5c62e0a5af0b6c32c51b535cc90701677276fc73c5623b72abda66cc148f2e |
