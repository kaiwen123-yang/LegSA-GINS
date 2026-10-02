# 正式 V3 对照与已有退化的输入层级

本项只转录原结果、核对小元数据与原注入函数的作用对象。新增 [CONTROL_REFERENCE_ROWS.csv](CONTROL_REFERENCE_ROWS.csv) 共 **1,051 个来源单元格/元数据条目**，保留 `source_path / row_key / column / value`、原数值字符串、读取副本和分类理由；不是 1,043 次实验。没有调用 solver/provider/evaluator，没有打开 RAWX、NPY、NAV、参考或任何保留 error_series，没有重新计算性能或复核 V3 全集。

## 三序列正式 F04：原完整精度对照

选取的是 **Protocol V3 正式 F04（A01、AB1111、scalar raw HPPOSECEF 5 Hz / R5 BOTH_FIXED）**。不是 B3、R5W、R5SIGMA，也不是本轮任何定义候选。主源为 `<V3_ROOT>/07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv`，读取此前已经无损转录的小表；三个 F04 数据行如下。

|序列 / 原物理 run_id|原 full-ablation 数据行|yaw RMSE (deg)|yaw absolute P95 (deg)|水平 RMSE (m)|Up RMSE (m)|matched / output 历元|
|---|---:|---:|---:|---:|---:|---:|
|BY2 / `RUN_00004`|26|1.8862718548526467|3.518066976630167|0.09790607774950152|0.04899590433188947|56642 / 56642|
|BY2H / `SEQUENCE_BY2H_F04`|11|1.93377013508875|3.6481369134119714|0.06836245149191253|0.04535210822197352|58580 / 58580|
|BY2O / `SEQUENCE_BY2O_F04`|22|2.433814932823714|3.709243297643519|0.054543210912875166|0.04585890723786377|76548 / 76548|

源文件入口：[完整消融小表](../../audit_xbpg_20261001/v3_results/source_tables/FULL_ABLATION_TABLE_V3.csv)、[原主表](../../audit_xbpg_20261001/v3_results/source_tables/MAIN_TABLE_V3.csv)。MAIN 的对应行分别为 3、8、12；本项仅逐字符串核对 7 列×3 序列，**21/21 一致**。MAIN 的 `h_rmse_m` 对应 FULL 的 `horizontal_rmse_m`，其他被核列为 up/yaw RMSE、yaw P95、output/matched count、coverage ratio。CSV 同时保存两处来源，没有用舍入手稿值替代。

|序列|登记评价窗 (s)|原 matched 首末时刻 (s)|reference_epoch_count|水平 P95 (m)|Up absolute P95 (m)|
|---|---|---|---:|---:|---:|
|BY2|66.0 至 340.0|66.005054 至 339.997056|5480|0.2651433111192599|0.09923790735213835|
|BY2H|413.0 至 683.0|413.047045 至 682.99505|5400|0.1446270289793796|0.08947386313355736|
|BY2O|3186.0 至 3563.0|3186.005234 至 3562.997055|7540|0.0742037488803522|0.08174271545455218|

三个原槽均为 `COMPLETED / failure_classification=NONE`，评价版本 `evaluator_contract_v3`。BY2 原 `case_id=C00_clean_normal` 且 `sequence_c00_alias=True`；另两序列实际 case_id 是 `CLEAN5_BY2H_NATURAL`、`CLEAN5_BY2O_NATURAL`，不能为统一名称改写原身份。这里称自然 C00 视图，不增加三次新运行。

这些数值是原全窗匹配输出历元上的统计，不是九种子均值，也不是置信区间。`matched_epoch_count` 是其原有效匹配支持，`reference_epoch_count` 是另一计数，不替换 RMSE 分母；插值后的相邻点也不代表独立样本。`coverage_ratio=1.0` 只说明已有输出点匹配率，不单独证明预期窗完整或采样连续。正式 F04 的密集 NAV 支持与文献 heading-only 的原生 RAWX 支持不同；新比较必须分别保留各自有效数和支持，不能把不同样本的 RMSE 差直接称为同支持算法效应。原 reference 也不是独立真值证明。

科学身份来源为 [METHOD_IDENTITY.csv](../../audit_xbpg_20261001/METHOD_IDENTITY.csv) 的正式 F04 行 4：native 科学源 `ca73cb1fb48a020fd2a450d79e520562c34eeb24`，正式 binary SHA256 `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`；runner 为 `7d43b9af26120ed5dde21f53e515386361072ba6`；冻结 evaluator SHA256 `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`。该身份表以 BY2 `RUN_00004` 为 F04 实物审计入口，三序列原行分别保留各自 run/config/NAV hash。

FULL/MAIN 原 `code_commit=7d43...` 字段按原样转录，与科学 native 源 ca73 分列；不把旧 manifest 的字面 commit 或本轮 HEAD 当成新的科学身份。本项只复用既有身份审查，不重新哈希 binary/provider/NAV，也不升级此前关于参考独立性、恢复评价和生成链的审查结论。

## 已登记九族：没有取得 EXT01–03 同层 RAWX 退化版本

九族以 [HX05/DEGRADATION_MANUSCRIPT.csv](../HX05/DEGRADATION_MANUSCRIPT.csv) 的原九行定义，映射来自 [DEGRADATION_SCOPE_CHECK.json](../HX05/DEGRADATION_SCOPE_CHECK.json)、`configs/paper_rebuild/hext/HX03/CASES.json` 及 [HX03_PREREG.md](../HX03_PREREG.md) 第 10、20、24–52 行。登记明确：**注入发生在 HPPOSECEF/provider cache 建成后，仅修改 p1/p2/valid/time；原始输入层不改**。LC01/EXT05C 的更新使用两接收机位置及 Go2 IMU，不使用 RAWX 码/载波 DD。

本项实际读了全部 181 个 CASES 小元数据身份（162 Classic、18 A2、1 C00），并按已收集索引精确入口读了 **20 个不同 LC01 seed_00 INPUT_HASHES.json**（18 Classic 类型及 A2 两个时长），取得原 `report`、数组角色和源 pin。未读它们指向的 GNSS18、RAWX、NPY 或参考载荷。源码只静态读取 [`hx03_injection.py::transform`](../../../../src/legsa_gins/paper_rebuild/hext/hx03_injection.py)；没有导入或执行。具体分支为位置 92–103 行、航向 104–129 行、中断 130–150 行、时间 151–167 行，忽略通道见第 15、89–90 行。

|原展示族|原类型 / 工况|已有作用对象和适用区别|与 EXT01–03 RAWX 码/载波输入的分类|
|---|---|---|---|
|位置噪声|D14、D21，各 9 seeds|把已实现 GNSS18 位置差投到固定 NED，同一位移加到 cache p1、p2；未改原始码/相位|`PROVIDER_LAYER_ONLY`；不是 raw 伪距/相位噪声版本|
|位置偏差|D16、D18，各 9 seeds|同样只平移 p1、p2，分别复用既有静偏/漂移|`PROVIDER_LAYER_ONLY`；不能用同名型证明码 DD 暴露相同|
|位置中断|D03、D04，各 9 seeds|半开窗内 LC01 两台 valid=False；EXT05C valid1=False。seed_00 窗分别 201.2–211.2、196.2–216.2 s|`PROVIDER_LAYER_ONLY`；不是删 RAWX 码/载波或改变其跟踪位|
|速度中断|D05、D42，各 9 seeds|D05 复用位置中断，与同 seed D03 的 native 哈希等价后复用；D42 属于不读取通道的 no-op/C00 身份确认|`PROVIDER_LAYER_ONLY`；不能把 D42 的不参与通道解释为 raw 文献法抗中断|
|航向噪声|D32、D33、D35，各 9 seeds|复用原 1 s yaw 增量，使 p2 绕 p1 做 NED 水平旋转；不是载波 cycle 注入。EXT05C 的 p2 只参与初始化|`PROVIDER_LAYER_ONLY`；未取得相位噪声/周跳同层输入|
|航向中断|D06、D31，各 9 seeds|D06 两台位置 valid=False；D31 valid2=False，LC01 跳过更新，EXT05C 持续位置更新不因此受影响|`PROVIDER_LAYER_ONLY`；不是停用某天线 RAWX 或整周模糊度弧|
|多普勒|D46、D47、D50，各 9 seeds|LC01/EXT05C 不读取这一通道；既有 seed_00 确认后复用 C00。metadata 的 operations 为空|`PROVIDER_LAYER_ONLY`，且目标位置输入无改动；没有 raw 码/载波退化|
|时间戳|D57，9 seeds|只移动 cache solution_times 并稳定排序，IMU 不移。seed_00 原 latency `0.10401432335291612` s、jitter 上限 `0.025616545567535644` s|`PROVIDER_LAYER_ONLY`；没有改 RAWX rcvTow/P/L，不能当作原始码载波时标故障|
|A2|D62 的 10/20 s，各 9 seeds|LC01 两台 valid=False、EXT05C valid1=False；另列 LC01-BR 窗内相对更新。不是同一未改动方法|`PROVIDER_LAYER_ONLY`；未取得原始双频码/载波层的 A2 版本|

因此，在这份**已登记九族及其输入映射范围内**，`RAW_LEVEL_COMPATIBLE=0`、`PROVIDER_LAYER_ONLY=9`、`UNDETERMINED=0`；该计数是元数据分类，不是性能实验。准确交付状态为 **“暂无同层退化对比”**。它不声称全磁盘永远不存在其他 raw 版本，也不阻止今后另行登记，但本轮不新建 raw 矩阵、不把现有 valid mask 或位置旋转自动改成 RAWX 注入。

D57 的原暴露尤其不能等同：HX03 只移位置事件，而 V3 F04 在该型全程没有有效标量航向，原表本已注明。`operations=[]` 也不能单独证明 no-op：中断与时间分支主要通过 interval/valid/time 修改，必须按具体 `type` 与分支读取。

原九行 Classic 范围是 153 cases，完整 Classic-18 为 162，差出的 D43 速度噪声 9 cases 保持独立补表；D43 在 LC01/EXT05C 同样为不读取通道的 C00 确认。A1 等价报告的 18 行复用 A2，不增加 native，也不能据名称额外推导一套 raw A1。源 CSV 保留各族原 case_id 全列表。

[HX03R2_PREREG_R2.md](../HX03R2_PREREG_R2.md) 第 4 节及 `USER_RULING_R2.json` 明确 R2 复用原 native，原始 summary/error 的字节身份为审计门；这是观察器审计重评，原生调用预算 0。R2 的通过不会把 provider 退化变成 RAWX 退化。本项只读该历史处置，不重新打开误差或独立重证这些哈希。

## 已有 RTKLIB 四变体保持自己的身份

原 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07R/SUMMARY.csv` **13 行全部读取并逐字段转录**到本 CSV。V0/V0E/V1/V2 各三序列为 12 个既有运行；V0-convbin 是额外一个 BY2 评价/输入历史敏感性对照，不是第五套三序列矩阵。

- V0：HX02 完整观测历史与原 binary/config/起点的复现身份。
- V0E：既有外部星历替换对照。
- V1：既有星座掩码变化对照。
- V2：既有 AR `fix-and-hold` 对照。具体依据是已登记 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07/CONFIGS/V2.conf` **第 13 行 `pos2-armode = fix-and-hold`**；该值已实际读取，不能仅凭 REPORT 第 1 节的“AR 模式”概括推断。

总体身份和变化顺序来自 [HX07R_REPORT.md](../HX07R/HX07R_REPORT.md) 第 1 节；V2 的具体 AR 值另外由原配置核实。三序列 `HX07R/RUNS/{BY2,BY2H,BY2O}_V2/COMMAND.json#/argv/2` 均以 `-k` 指向上述 V2.conf，`#/input_sha256` 均记该配置 hash `3f55e8ff20318a674a3acfa6d52c7b756072c5e6b057d90db2cfb384a864ed78`，与 [HX07R_INPUT_SHA256.json](../HX07R/HX07R_INPUT_SHA256.json) 的对应 pin 相同。这是原记录字符串核对，不是本轮重新计算配置哈希。8 条精确字段证据已追加本 CSV，三序列控制数值未改。本轮不选更好数值替换旧身份，也不因 EXT 新输入适配而重跑 RTKLIB。原 HX07 的 157/1370 对 153/1370 硬停、以及 HX07R 的 V0-convbin 行继续保留其原输入历史用途。

SUMMARY 的 `valid_rmse_deg`、`hold_rmse_deg`、`q2_rmse_deg` 分别有不同原支持；`valid_count/paired_denominator` 不是 F04 的 NAV matched/output 计数。它们作为本次 heading-only 对照引用，不提供可与完整导航解等价排名的位置误差。EXT01/02/03 与这种 heading-only 行没有 H/up 时写 **NOT_APPLICABLE/NA**，不能填 0；relative-pose 漂移也不能冒充绝对 IMU 点 RMSE。这里只提供原对照的精确来源，不以已有控制行宣称新文献实现已获得相同输入、相同支持或整数真值。

本项可复查入口为本页和 `CONTROL_REFERENCE_ROWS.csv`。三序列数值来自 33/52 行小表，九族证据来自登记/20 份小注入记录，RTKLIB 来源为原 13 行摘要；没有重扫旧大库存或性能载荷，所有记录 hash 均保持“既有记录”含义。
