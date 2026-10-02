# 既有 HX 结果读取入口

本批已实际读取 HX02、HX02E、HX03、HX03R2、HX05、HX07、HX07R 的结果表和运行/评价元数据；未调用 solver、provider、evaluator、历史 controller 或 Context。这里保留既有数值和历史状态，没有重新计算性能，也没有据这些文件宣布文献算法已忠实复现。

先打开 [EXISTING_HX_INDEX.csv](EXISTING_HX_INDEX.csv)：674 条 RUN 身份、1,040 条评价或资格门 JSON 摘要、83 条完整读取的源表入口。RUN 不是原生调用次数；评价摘要含失败资格门，不能当 evaluator 次数。公开 JSON 单元格只摘录原有核心指标、支持和状态；**完整字段仍在原 JSON/CSV及本机完整工作索引**，公开摘要不声称覆盖所有指标列。

[EXISTING_HX_RUNS.csv](EXISTING_HX_RUNS.csv) 是674行运行浏览视图；[EXISTING_HX_TABLES.csv](EXISTING_HX_TABLES.csv) 给出83份已完整读取的物理CSV、原表头、行数与同次读取哈希；[EXISTING_HX_FILES.csv](EXISTING_HX_FILES.csv) 仅公开主结果和关键载荷的读取入口。完整工作库存17,013行结果记录、12,903个文件条目留在 `<EXT_REPRO_ROOT>/existing_hx_full/`；带真实本机路径的30,016行镜像为 `<EXT_REPRO_ROOT>/existing_hx.local.csv`。完整回执见 [COLLECTION_RECEIPT.json](COLLECTION_RECEIPT.json)。未重复上传原本已经 tracked 的小结果表，也没有上传大 NAV、pos、heading、误差或参考数据。

83份物理表共有55,841条已读记录，包括同一结果在仓库和归档的副本；按本次表字节哈希有61份不同内容。28份原生 failure/runtime 表共42,612条逐历元结果已经读完，但不重复复制成库存行：准确入口、行数和哈希仍在 TABLES 中。此处没有将“文件清单”冒充“结果表已读”。

## 保存位置与版本

所有七阶段的当前运行/评价载荷位于 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/`，对应子目录如下。它们是可直接打开的归档目录，不是待解压ZIP；原记录中的 `<HX02_SCRATCH>` 路径仍保留历史含义。

|阶段|实际子目录|RUN目录数|主要原表及用途|
|---|---|---:|---|
|HX02|HX02_FIVE_CATEGORY|24|[480行五类别长表](../../HX02/EXTERNAL_FIVE_CATEGORY_TABLE.csv)，同时含已有对照引用和未实现占位|
|HX02E|HX02E_HARTLEY_OFFICIAL|6|[96行官方Hartley长表](../../HX02E/HARTLEY_OFFICIAL_TABLE.csv)，OFF-LIT/OFF-DEF×三序列|
|HX03|HX03_DEGRADATION|381|[v3 396行](../../HX03/DEGRADATION_EXTERNAL_TABLE.csv)与[v2 396行](../../HX03/DEGRADATION_EXTERNAL_TABLE_V2.csv)，保留旧审计处置|
|HX03R2|HX03R2_AUDIT_REEVAL|246|[R2 v3 396行](../../HX03R2/DEGRADATION_EXTERNAL_TABLE_R2.csv)与[R2 v2 396行](../../HX03R2/DEGRADATION_EXTERNAL_TABLE_V2_R2.csv)，492个已有评价槽|
|HX05|HX05_CLOSEOUT|3|[三序列主表14行](../../HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv)、[补表12行](../../HX05/EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv)、[九族表9行](../../HX05/DEGRADATION_MANUSCRIPT.csv)、[BY2O分段65行](../../HX05/BY2O_SEGMENT_TABLE_EXT.csv)、[D43补充18行](../../HX05/D43_VELOCITY_NOISE_SUPPLEMENT.csv)|
|HX07|HX07|1|[原九槽表](../../HX07/HX07_TABLE.csv)，原V0硬停及后续未启动槽不改写|
|HX07R|HX07R|13|根目录SUMMARY.csv的13行；[四变体补表](../../HX07R/HX07R_SUPPLEMENT_ROWS.csv)、残差/卫星/分段表另列|

根映射来自 ignored `configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json`；共享索引用别名。SOURCE_CITATIONS 中原 `$HX02`、`$HX02E`、`$HX03`、`$HX03R2`、`$HX05` 分别指上述阶段根，`$V3` 指 `<V3_ROOT>`，`$W` 指 `<AUDIT_SOURCE_WORKTREE>`。源码/配置版本取原记录，不拿本轮HEAD替代旧实现身份。

HX05收尾明确采用最终HX02五类别表（记录pin `7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba`）、HX02E官方库表（`30fda253e5fa4f56b829ae9e5184cefc0258c74d57c0e3fadbae98e407cbd888`）及HX03R2表（`17cfce3191231c1631b0b3b1c2d8196a838690e1e9eae83bbcef0621f23d4989`）。旧自写Hartley和HX03 R1仍单列。HX07R是后续RTKLIB四变体材料，不能反向改写HX07原硬停。此选择依据既有收尾来源链，未以文件名FINAL、修改时间或较好指标选版本。

## 阅读原有结果

HX02/HX07R的完整首批数值和13条RTKLIB结果在 [HX02_HX07R_FIRST_READ.md](HX02_HX07R_FIRST_READ.md)。HX02的63个展示组合不等于24次原生运行。原调用回执为24 native、21次参考评价、3次无参考覆盖评价；EXT04_FAR/PAR零有效支持时误差为UNAVAILABLE，不能读成零误差。GINAV原失败门与Hartley异常保留；EXT01的COMPLETED与原 `runner_terminal_status=UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION` 同时保留。

HX02E的OFF-LIT位置漂移（m/100m）为BY2 `33.63359978621048`、BY2H `47.525516541439565`、BY2O `28.55885167565558`；OFF-DEF分别为 `21.88907591581972`、`34.015027152331754`、`11.652023031652952`。来源为官方长表 `method_id=HARTLEY_OFFICIAL, config=OFF-LIT/OFF-DEF, sequence=<序列>, metric=position_drift_m_per_100m`。这些是各分支初始10秒yaw+平移对齐后的相对位姿口径，不和绝对IMU点RMSE混成排名。

HX03的381个目录包括282个普通NATIVE、3个IDENTITY_NATIVE、80个C00身份复用、16个D03/D05身份门后复用。原生总数285，实际已有v3/v2评价JSON各246份；复用目录保留 `source_run_dir` 和原评价状态，不把没有独立子进程当结果丢失。两版本各396条逻辑结果中，R1为214个有限、146个 `UNAVAILABLE_EVALUATION_FAILED`、36个 `ALGORITHM_FAILURE_DIVERGED`。R2为360个有限、36个原生发散、0个审计不可用。36失败来自D14/D21的LC01与EXT05C，每方法每型9个种子；[完整失败表](../../HX03R2/ALGORITHM_FAILURES_R2.csv)保留空指标及PRE_FAILURE字段。

R2是已有观察器审计更正版本，原native NAV和R1仍存在。[SCIENTIFIC_IDENTITY_R2.csv](../../HX03R2/SCIENTIFIC_IDENTITY_R2.csv)的492条原回执记录冻结summary/error哈希一致；本轮读取了该证明表，**没有再次解压/哈希这些大载荷来独立重证**。原历史调用为492次评价、0新native；该历史数量不能写成本轮调用。

R2的A2已有全窗水平RMSE中位数：LC01 `1.4073499260959883 m`、EXT05C `1.4222228466328284 m`、LC01-BR `2.7857817729516205 m`，各有限18/18。来源 [DEGRADATION_EXTERNAL_SUMMARY_R2.csv](../../HX03R2/DEGRADATION_EXTERNAL_SUMMARY_R2.csv) 数据行176/179/182，原字段 `median`；这里仅转录，不新算中位数。LC01-BR是“改动过的LC01”。A1等价报告的18行是A2的别名，不能再加18次运行。分布、配对、分位数请用各表原 `registered_n/finite_n/failure_n`，失败不因RMSE空白而消失。

HX05的LEG-DR是三次已有积分与三次相对评价，外部solver调用为0。它是使用机载姿态的输入参照，不是新增论文算法复现。原位置漂移为BY2 `0.06942580845419305`、BY2H `0.10752596591374582`、BY2O `-0.37939114728288426 m/100m`；相应对齐水平RMSE为 `6.2091109165498315`、`9.178417411465594`、`6.322411571899827 m`。来源 `RUNS/<序列>/RESULT.json#/metrics` 与 `SOURCE_CITATIONS.json#/MAIN.08.<序列>`。位置漂移是误差范数对参考路程的带截距OLS斜率，负斜率不表示负误差。

HX07原V0的157/1370相对HX02 153/1370超出原±2门，原进程退出0但阶段硬停。后续八槽保持未启动；不把该硬停说成求解崩溃。HX07R独立保留V0/V0E/V1/V2×三序列的12次原生记录，另BY2 V0-convbin仅为第13个评价对照；其13行SUMMARY全部已读，见首批表。图的三种格式不增加实验次数。

## 表图来源与读取限度

[HX05_SOURCE_CITATIONS.json](HX05_SOURCE_CITATIONS.json) 完整保留213个已有source_id的完整精度指标、原表行/列键、记录哈希与显示运算；[HX05_FIGURE_MANIFEST.json](HX05_FIGURE_MANIFEST.json) 完整保留FIG02S/FIG02D/SFIG-HX三个图组的bindings。它们是原JSON的路径别名化转录，JSON数字词元保存为字符串；未重绘、未做新的PNG视觉QA。已有仓库中的PNG/PDF/SVG及HX07R的SFIG-HX7在FILES登记；源manifest中的scratch路径是原渲染位置，不自动充当当前文件位置。

主收集回执登记83份完整CSV、10,356份完整元数据/说明文件，2,464个仅核元数据的载荷；其中986个gzip包括HX03R2的492份error_series、492份AUDIT_RESIDUALS及HX02的2份error_series。gzip只确认具体文件存在，未读正文或CRC，也未批量解压。各run NAV/pos/heading/error读取入口可从索引直接解析。记录hash与本轮同次元数据读取hash分别标记，未冒充新payload hash。

在已登记的主结果读取范围内未遇到实物缺失或无法读取的文件。这个结论不覆盖全盘、旧scratch、未被此任务选中的历史诊断目录，也不意味着所有曾声明的论文实现已经可用。HX02D仅保留直接引用的三份来源说明，未把诊断执行全部重收；先前 `UNAVAILABLE`、失败后未生成和未启动槽继续按原词呈现。V3借用表保持原V3身份，不加入HX新运行分母。

## 后续输入的明确入口

[INPUT_LOCATIONS.csv](INPUT_LOCATIONS.csv)的100条记录来自37份小元数据，给出原raw CSV、18份完整重建UBX/OBS/NAV、9组compact元数据与27个数组、HX07R各变体输入pin及lambda库位置；[回执](INPUT_LOCATION_RECEIPT.json)说明读取深度。所有输入载荷仅stat，未重新读取或计算哈希。

完整RTKLIB输入为 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/RUNS/<SEQ>__RTKLIB__NONE__<CASE>__NA/native/SOURCE_BACKEND/gnss{1,2}.{ubx,obs,nav}`。CASE分别为C00、CONTRACT_START、FILE_START；原raw配对1509/1483/2231，实际文件保留完整历史，BY2H原native另施加起点选择。

EXT02 compact根为同一RUNS下 `<SEQ>__EXT02__LIT__<CASE>__NA/native/ARTIFACT/03_EXT02_CWLS/C00/COMPACT_CACHE/`。EXT02/03/04元数据一致记录1509/1423/2231；所查HX02明确指针内没有找到BY2H完整1483配对compact，**不得用1423冒充1483**。这是有界定位结论，没有扫描其他磁盘，也未生成替代cache。

lambda库精确别名为 `<HX02_EXTERNAL_ROOT>/rtklib_bridge/lib/librtklib_legsa.so`，已有pin `28c25b1cc7fade9b956bfdf77005de8fcb0a382c8411ae6e608c83b82bff53f2` 来自 `HX02_FIVE_CATEGORY/01_INPUT_PINS/INPUT_PINS.json#/external_binaries/lambda_library`；路径来自ignored local配置。当前文件stat为729,792 B，库未加载，pin未新哈希验证。

本批结束在已有结果收集与描述。已有审查和后续方法实现边界不由本索引自动放行。脚本均为本轮只读收集/索引整理工具；复查来源只需打开已列文件，不需要重新运行整套收集。
