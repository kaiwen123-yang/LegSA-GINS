# V3-01 第 0 步只读前置检查

状态：`BLOCKED_PREREQUISITE_FACT_CONFLICT_PENDING_USER_RESOLUTION`。0b 已计算，0a 中的冻结有限数与“无新增失败”前提同原始封存表冲突。此记录不批准预注册或全量执行，五个身份门均为 `NOT_RUN`。

起点与代码基线：`6257a4fa46efd11a8b8888c5e466cf923a45336e`。用户授权的单项变更为原始 HPPOSECEF 5 Hz 标量航向；std 标记保持 `2.933193`。C++、参数、冻结二进制、评估器、IMU/位置/速度/RD/RP、全部工况 HV 文件均未改动。HV 保持 status 航向旋转的冻结文件，不用新航向重生成。既有草稿和冻结结果均保留。

## 0a：三序列与 61 例原始表回查

主评估器 v3 的 F04 三序列 yaw RMSE 之和及相对 R5 的下降量如下。0.3° 仅为用户指定的既有 T5bc-R 记录核对条件，不是后续 v3 结果筛选阈值。

| evaluator | variant | sequence_count | yaw_rmse_sum_deg | improvement_from_R5_deg | reaches_0p3_deg |
| --- | --- | --- | --- | --- | --- |
| v3 | T5A_R5 | 3 | 6.2538569227651107 | 0E-16 | False |
| v3 | R5SIGMA | 3 | 6.1442162463454558 | 0.1096406764196549 | False |
| v3 | R5W | 3 | 6.1050993524129546 | 0.1487575703521561 | False |

两版评估器均按相同 61 个 case ID 配对。有限要求原评价状态 `COMPLETED` 且对应指标有限；缺失不填零。

| evaluator | metric | total_cases | frozen_finite | R5_finite | paired_finite | frozen_nonfinite | R5_nonfinite | R5_failed_on_frozen_completed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v3 | yaw_rmse_deg | 61 | 60 | 58 | 57 | 1 | 3 | 3 |
| v3 | h_rmse_m | 61 | 60 | 58 | 57 | 1 | 3 | 3 |
| v2 | yaw_rmse_deg | 61 | 60 | 58 | 57 | 1 | 3 | 3 |
| v2 | h_rmse_m | 61 | 60 | 58 | 57 | 1 | 3 | 3 |

以下列出 v3 任一侧失败或非有限的全部四个 case，并排保留两侧原状态。**四个是两侧失败集合的并集，不是冻结 F04 的四个失败。** 冻结 F04 唯一非有限为 D37；R5 失败为 D27、D57、D60，这三例冻结均完成。R5 在 D37 有有限结果，所以 60 与 58 的交集是 57。不能确认“R5 未在冻结完成的工况上失败”。平行 v2 的逐例值见 CSV。

| case_id | frozen_terminal | frozen_yaw_rmse_deg | R5_failure_classification | R5_yaw_rmse_deg | R5_failed_on_frozen_completed |
| --- | --- | --- | --- | --- | --- |
| D27_seed_00 | COMPLETED | 32.472978585312966 | ALGORITHM_FAILURE_DIVERGED | UNAVAILABLE | True |
| D37_seed_00 | ALGORITHM_FAILURE_ALL_YAW_REJECTED | UNAVAILABLE | NONE | 1.8862718548526467 | False |
| D57_seed_00 | COMPLETED | 1.7870833845921381 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | UNAVAILABLE | True |
| D60_seed_00 | COMPLETED | 1.9413335363795345 | ALGORITHM_FAILURE_DIVERGED | UNAVAILABLE | True |

0a 的这项冲突改变失败比较的科学含义，保留事实并等待用户裁定；没有改写既有表、删除工况或替换来源。

## 0b：BY2O 主段与次段

读取 T5a-R 已封存的 BY2O F02/F04 × R5/R5F error_series；先验证 T5BC 源索引 pin，再验证 T5a-R 聚合清单 → OUTPUT_SEAL → error_series 哈希链。直接调用原 `hext.aggregate.segment_rows`，主段闭区间 `[3369.94, 3411.95]` s、次段 `[3495.94, 3508.94]` s、全窗 `[3186, 3563]` s。未启动 evaluator 或 native，没有读取 trace。

| evaluator_contract | configuration_id | variant | segment_id | count | yaw_rmse_deg |
| --- | --- | --- | --- | --- | --- |
| evaluator_contract_v3 | F02 | R5 | occlusion_primary | 7612 | 0.8630369665699419 |
| evaluator_contract_v3 | F02 | R5 | occlusion_secondary | 2754 | 1.57921171453566 |
| evaluator_contract_v3 | F02 | R5F | occlusion_primary | 7612 | 0.8862759689859719 |
| evaluator_contract_v3 | F02 | R5F | occlusion_secondary | 2754 | 1.7608525803877044 |
| evaluator_contract_v3 | F04 | R5 | occlusion_primary | 7612 | 0.2325140820805299 |
| evaluator_contract_v3 | F04 | R5 | occlusion_secondary | 2754 | 1.861542194198912 |
| evaluator_contract_v3 | F04 | R5F | occlusion_primary | 7612 | 1.0351701650068426 |
| evaluator_contract_v3 | F04 | R5F | occlusion_secondary | 2754 | 1.129737855158939 |
| evaluator_contract_v2 | F02 | R5 | occlusion_primary | 7612 | 0.8630369665699419 |
| evaluator_contract_v2 | F02 | R5 | occlusion_secondary | 2754 | 1.57921171453566 |
| evaluator_contract_v2 | F02 | R5F | occlusion_primary | 7612 | 0.8862759689859719 |
| evaluator_contract_v2 | F02 | R5F | occlusion_secondary | 2754 | 1.7608525803877044 |
| evaluator_contract_v2 | F04 | R5 | occlusion_primary | 7612 | 0.2325140820805299 |
| evaluator_contract_v2 | F04 | R5 | occlusion_secondary | 2754 | 1.861542194198912 |
| evaluator_contract_v2 | F04 | R5F | occlusion_primary | 7612 | 1.0351701650068426 |
| evaluator_contract_v2 | F04 | R5F | occlusion_secondary | 2754 | 1.129737855158939 |

用户规则：若 F04-R5F 主段 yaw RMSE ≤ F04-R5 主段，则两接收机均载波相位解（fixed 或 float）；否则两接收机均 fixed。主评估器 v3 实算 `1.0351701650068426` > `0.2325140820805299` deg，因此选定 **两台接收机均 fixed（R5）**。v2 平行值完整保留；这只是 0b 条件计算结果，不解除 0a 冲突。

## 身份与执行状态

| role | sha256 | status |
| --- | --- | --- |
| executable | 96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c | PASS |
| evaluator | aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da | PASS |

这两项是既有文件哈希的只读核验；不等同于 v3 的五个身份门通过。

| gate | status |
| --- | --- |
| 2a_NON_HEADING_BYTE_IDENTITY | NOT_RUN |
| 2b_BY2_T5A_TABLE_HASH | NOT_RUN |
| 2c_ALL_CONFIGS_LINE_AND_211_ECHO | NOT_RUN |
| 2d_THREE_SEQUENCE_F01_NAV | NOT_RUN |
| 2e_BY2_F04_C00_NAV | NOT_RUN |

本步骤 native / evaluator / provider 调用均为 **0**，raw payload / trace 读取均为 **0**。未生成 v3 provider、runtime config、NAV 或全量结果。F01 完整 NAV 的封存哈希和 T5a-R BY2 F04 R5 NAV 是后续门的目标；当前没有执行比较。

## 产物和复算

外部原件目录：`<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3/00_PREREQUISITES`。本目录保存同字节的小型交接副本：

- `V3_01_PREREQUISITES.json`：状态、完整来源 SHA256、代码基线和调用计数；
- `F04_THREE_SEQUENCE_SUMS.csv`：两版三序列求和；
- `SUBSET61_FINITE_COUNTS.csv`、`SUBSET61_F04_R5_COMPARISON.csv`、`SUBSET61_FAILURE_COMPARISON.csv`：有限计数及逐例比较；
- `BY2O_T5AR_SEGMENTS.csv`：两版、四个配置/变体组合、全窗/主段/次段共 24 行。

实现：`scripts/paper_rebuild/v3_prerequisites.py`。运行 `/usr/bin/python3 -B scripts/paper_rebuild/v3_prerequisites.py`，从 ignored local config 解析路径，输出采用独占新建；已存在时拒绝覆盖。脚本只允许在以上起点 HEAD 执行，保证本次前置检查身份明确。无新增科学运行；0a 引用的 61 例退化队列含半合成工况，与 0b 原始三序列证据分别报告。
