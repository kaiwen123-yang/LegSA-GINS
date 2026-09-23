# FC-01：统一失败分类与只读输入差分

续作 2 已完成 72 例实际 F01 输入差分：非航向字节及实际 IMU 输入全部相同，差异只在 yaw/yaw_valid；未发现非航向重派生或整行删除。详见文末“续作 2”。下文原有哈希盘点及硬停记录属于续作 1，完整保留；本次输入审计不解除分类硬停。

分类任务终态仍为 **`HARD_STOP_CORE_F01_NAV_HASH_DIFFERENCE`**。按用户续作裁决完成 F01 哈希盘点后，核心 541 例中发现 54 对哈希不同，触发明确硬停；尚未执行分类自检、全量分类或指标汇总。**54 是 NAV 哈希差异数，不是算法失败数。**

原任务起点为 `fb39cb8b8bd0ed08ac20ea62f5e4f2ffc483bfef`，本次续作起点为 `4b9d7345edc6f745eff4852bd99ab84218c1c307`。解算器、评估器和 provider 调用均为 0。

路径别名：`<V3_ROOT> = <CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3`；`<V21_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21`；`<FC01_ROOT> = <V3_ROOT>/07E_UNIFIED_FAILURE`；`<FC01_CONT> = <FC01_ROOT>/CONTINUATION_01`。本次产物仅新增于 `<FC01_CONT>`，原硬停与原清单原字节保留。

## 最新裁决与范围

用户明确将 F01 分类自检限制为同 NAV 哈希且两链有合格证据的运行；哈希不同或缺证据者排除自检。额外规定：**核心 541 例出现任何 F01 哈希不同即硬停**；A1/A2 哈希不同属于预期，只记录。跨链分类与指标配对限定核心 541 例；A1/A2 只报告 v3 自身分类。v2.1 缺合格判定证据者应标记 `UNCLASSIFIABLE`，单列并排除配对。

裁决原文与 SHA-256 保存在 `<FC01_CONT>/USER_RESOLUTION.json`。本轮先完成全部 F01 哈希盘点，再执行核心哈希门；不得用“排除不同哈希后继续”绕过核心硬停条款。

## F01 哈希盘点

| 范围 | F01 运行数 | 两链哈希相同 | 两链哈希不同 | v2.1 缺可核对哈希证据 |
| --- | ---: | ---: | ---: | ---: |
| 核心 541 例 | 541 | 487 | 54 | 0 |
| A1/A2 族 | 45 | 27 | 18 | 0 |
| 额外自然序列，仅作盘点 | 2 | 2 | 0 | 0 |
| 全部 F01 哈希盘点 | 588 | 516 | 72 | 0 |

这里的“缺证据”列专指缺可核对的 NAV 哈希；哈希存在不等于完整 NAV 或分类证据可用。表中另列封存界限、航向禁用清单、正式复用来源、自检资格和范围排除原因。哈希已知但不同的条目保留为 `DIFFERENT`，不会被“缺分类证据”掩盖。

`F01_HASH_COMPARISON.csv` 含 588 个逐运行身份，`F01_HASH_SUMMARY.csv` 给出上表三个范围。字段 `core_selfcheck_included_count=487` 仅表示门前识别出的候选资格；实际分类自检执行数为 **0**，不能称为 487 对自检通过。A1/A2 45 对全部不进入跨链分类，额外序列也不进入核心配对。

核心差异按类型分布如下，均为 F01：

| 类型 | NAV 哈希不同的种子数 |
| --- | ---: |
| D05 | 9 |
| D09 | 9 |
| D10 | 9 |
| D11 | 9 |
| D12 | 9 |
| D57 | 9 |
| 合计 | 54 |

## 核心硬停的可复核例证

首个不同项是 `RUN_00408 / BY2 / D05_seed_00 / F01`。两链以 `(dataset_id, case_id, method_id)` 精确连接，每个身份唯一，排除了编号或配置别名误配。

| 来源 | NAV SHA-256 |
| --- | --- |
| v2.1 两个评估器版本的冻结核心表 | `395e34939f3e14881bfb214486661065d0c0cec200aa453669186aaf7413655e` |
| v3 运行注册表与封存 native 摘要 | `bcfb4e5b04d10cd68b1e5b7205c047160d750a21bbe2fbe420a2e76d1d29fe98` |

v2.1 来源为 `<V21_ROOT>/20_FINALIZE/13_AGGREGATE/{v3,v2}/UNIQUE_EVALUATION_RESULTS.csv`，v3 来源为 `FINAL_RUN_RECORDS.json` 与 `<V3_ROOT>/03_NATIVE/RUN_00408/V3_NATIVE_SUMMARY.json`。v3 摘要字节与归档清单 SHA-256 一致，其运行身份和 NAV 哈希与注册记录一致。

独立复核另外确认：v2.1 两个评估器版本的全部 588 个 F01 身份与 NAV 哈希一致；D05、D09、D10、D11、D12、D57 各取 seed_00，对应 v3 实际归档摘要的清单 pin、科学身份及注册 NAV 哈希均通过，且与 v2.1 对应哈希不同。该抽查支持六类代表项的归档绑定；本次盘点脚本则读取了全部 588 个 F01 的封存摘要和关联清单。

没有通过读取未授权来源的旧 NAV、修改 provider、重跑或放宽核心范围来消除差异；本记录不推断核心差异原因，也不把哈希差异解释为发散或性能恶化。

## 交付状态与待完成项

| 请求产物 | 本次状态 |
| --- | --- |
| F01 两链哈希逐运行表、核心与 A1/A2 分项计数 | 完成 |
| 核心 F01 哈希门 | FAIL：54 对不同 |
| 同哈希且合格运行的分类自检 | NOT_RUN：先行核心哈希门硬停 |
| 两链逐运行完整统一分类表 | NOT_PRODUCED：核心哈希硬停 |
| 故障族 × 配置 × 类别对照 | NOT_PRODUCED：核心哈希硬停 |
| 完成→失败、失败→完成、双失败、双完成转移表 | NOT_PRODUCED：核心哈希硬停 |
| 同分母 541 分布与 61 例摘要 | NOT_PRODUCED：核心哈希硬停 |
| A1/A2 的 v3 单链分类 | NOT_PRODUCED：在全量分类前硬停 |
| 统一失败总数、构成和 dual_yaw 计数 | NOT_COMPUTED；不能拿原分类计数代替 |
| dual_yaw 5 Hz 注入映射说明 | 已有说明与源 pin 保留，见下节 |
| 手稿失败段落替换文字 | NOT_PRODUCED；统一失败结论尚未建立 |

所有 6,468 条 v3 与原计划 5,951 条 v2.1 核心统一分类均未执行；未处理条目不得直接计为已确认的 `UNCLASSIFIABLE`。停在哈希门也不意味着失败率为零。

## 统一规则及尚未执行的统计方法

两链原定使用完全相同的 FAIL 条件：启用航向的配置无有效航向输入；或航向尝试大于零且接受为零；或完整 NAV 出现位移大于 10,000 m、速度大于 50 m/s、高度位移大于 1,000 m 或非有限行。F01 关闭航向，不适用前两条。均为严格大于，等于界限不构成失败。

位移沿用 v3 的 WGS84 LLA→ECEF→首个输出位置固定 NED 三维范数；速度取三维速度范数，高度取相对首个输出大地高的绝对差。航向条件使用 RUN_MANIFEST 计数；冻结标量路径在拒绝门前递增 attempt，QA 关闭时 attempt=0 对应没有进入更新的有效航向。脚本保留该前提检查。

NAV 已释放的 v3 运行仅能使用与 NAV 哈希绑定的封存 `V3_NATIVE_SUMMARY` 界限。v2.1 缺完整 NAV 且无合格封存判定时标记 `UNCLASSIFIABLE`；降采样 `NAV_10HZ`、旧完成标签和仅有有限性检查不能补出三个界限。仅同哈希且合格的 F01 可绑定同一 NAV 的封存判定，不能跨不同哈希借用。

核心共同接纳集合原定为两链均统一 `COMPLETED` 的相同工况/配置，再逐指标取两链封存评估值均有限的交集。541 与原封存 61 例子集均使用同一分母与成员清单；分别报告评估器 v3、v2 的七项指标之 mean、median、p95、maximum、最差 5% 均值，空集合数值留空。该方法目前只完成实现，未运行汇总、未形成性能结论。

## 历史硬停的保留

首轮 `4b9d734` 因 A2 的 `ADD_RUN_00298 / D62_10s_seed_00 / F01` 停止，其原 `HARD_STOP.json`、证据及 `MANIFEST.json` 仍位于 `<FC01_ROOT>`。续作裁决解除了 A1/A2 哈希不同所造成的阻断；本次停止来自另行明示的核心 F01 哈希门。两次停止记录均保留，没有覆盖原表、改写历史状态或将原停机记录变成 PASS。

## 本轮审计与产物索引

16 项纯内存规则测试通过，其中使用虚拟计数/界限的 12 次分类函数调用只属于测试；真实注册运行的分类及 F01 分类自检均为 0。两份独立脚本安装进程、运行模块导入、写入范围及 trace 守卫；解算器、评估器与 provider 调用均为 0，native NAV、降采样 NAV 和 trace 读取均为 0。停机收束只校验哈希，没有恢复分类。

17 个既有 `<FC01_ROOT>` 文件和 181 张封存 CSV 的前后 SHA-256 一致。`SOURCE_PINS.csv` 记录 1,974 项来源哈希；原 `HARD_STOP.json`、本轮完整哈希表与脚本也有不可改写检查。独立复核确认核心差异计数和六类分布，并确认应按裁决硬停。

本轮主要文件：

- `F01_HASH_COMPARISON.csv`、`F01_HASH_SUMMARY.csv`：全部 588 个 F01 的哈希对照及分域计数。
- `CORE_F01_HASH_MISMATCHES.csv`、`CORE_F01_HASH_MISMATCH_TYPE_COUNTS.csv`：核心 54 对差异及类型计数。
- `FIRST_CORE_MISMATCH_PROOF.json`：首个核心冲突的唯一科学身份及两链完整哈希。
- `HARD_STOP.json`、`PENDING_OUTPUTS.json`：终态和未产出清单。
- `READ_ONLY_AUDIT.json`、`CLASSIFICATION_SCOPE_CLARIFICATION.json`：零科学调用、零真实运行分类，以及候选资格字段的含义。
- `PRIOR_07E_GUARD.json`、`SEALED_TABLE_GUARD.json`、`SOURCE_PINS.csv`：来源与保留回执。
- `MANIFEST.json`、`FINAL_OUTPUT_SEAL.json`：本轮终态与 21 个已封存产物的哈希。

`MANIFEST.json` SHA-256：`e48369a1c8a11856a0f64aaee7d44d0afde01aae881ecba5acf36eac4acffa6b`。
`FINAL_OUTPUT_SEAL.json` SHA-256：`55d81140cd2f27aca80f67c9b794e6a7e76c3c6f8174bb527f8f940d095fdcc6`。

## dual_yaw 族的 5 Hz 注入映射

映射依据冻结的 [PROTOCOL_V3_PREREG.md](PROTOCOL_V3_PREREG.md)、`configs/paper_rebuild/v3/PROTOCOL_V3_CONTRACT.yaml` 和 `src/legsa_gins/paper_rebuild/protocol_v3/providers.py`，逐类型清单见 `<FC01_ROOT>/DUAL_YAW_INJECTION_MAPPING.csv`。

| 类型 | 5 Hz 表上的实际映射 | 是否只落在原 1 s 行 |
| --- | --- | --- |
| D30、D31 | 原 5 s / 20 s 半开停测窗覆盖窗内可用 5 Hz 行 | 否 |
| D32、D33 | 原已实现的 1° / 5° 角度扰动按 `[t_i,t_i+1)` 单元延拓 | 否 |
| D34、D35 | 保留已选尖峰事件与符号，按原 1 s 单元延拓 | 否 |
| D36、D37 | std×1.5 / ×3 的原逐行 token 保持不变，中间行不补乘 | 是，仅指 std 故障 |
| D38 | 10° 角度扰动按单元延拓；std×0.25 只保留原行 | 角度否，std 是 |
| D39 | 三个冻结秒制停测区间覆盖窗内可用 5 Hz 行 | 否 |
| D40 | baseline 长度/相对精度元数据故障无活动标量量测通路 | 不适用 |
| D41 | 只转移已实现的标量圆周角差，按原单元延拓 | 否 |

角度扰动的原时间单元覆盖 `[56,357)` s，末单元为 `[356,357)`；不重新抽取独立 5 Hz 噪声。所有非 yaw/valid 字节保持冻结，包括标准差和 HV；HV 仍使用原 status 航向旋转。统一分类只统一失败定义，没有消除两协议故障暴露方式的差异，dual_yaw 的计数差不能单独解释为算法鲁棒性提高。

## 续作 2：72 例实际输入只读差分

本次起点 `8443c57c562f2386a2fe3e28a70aae10e829271f`，终态 `PASS_READ_ONLY_ACTUAL_INPUT_DIFF_COMPLETE`。范围严格为核心 D05、D09、D10、D11、D12、D57 各 9 种子，以及 A2 的 10 s / 20 s 各 9 种子，共 72 个 F01；这 72 个身份与续作 1 的 NAV 哈希差异集合完全一致。A2 在此只比较输入来源，不进入跨链失败分类或性能配对。

新增别名 `<FC01_CONT02> = <FC01_ROOT>/CONTINUATION_02`。本轮新表均写入该目录；没有修改原 GNSS 表、provider、RUN_MANIFEST、NAV 或已封存汇总表，也没有恢复任何分类或指标计算。

### 实际输入来源与比较口径

按 `(dataset_id, case_id, F01)` 连接正式复用记录、冻结 RUN_MANIFEST、v3 注册表和归档摘要，逐一验证来源文件及 provider SHA-256。v2.1 的核心 F01 正式复用原 `CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2` 运行，A2 F01 正式复用原 `CLEAN6_ADDENDUM_FAMILIES_A1_A2` 运行。因此，实际输入是这些运行的 GNSS pin；`CLEAN6_SENSOR_MODEL_V21` 下重新生成的 case bundle 不能代替 F01 已实际读取的文件。本次读取这两个原来源只用于用户指定的输入溯源，不提取其性能结果。

72/72 个 v3 `frozen_template` 与 v2.1 正式 F01 实际 GNSS 文件哈希相同；实际 v3 GNSS 则与其自身 RUN_MANIFEST 的 provider 哈希一致。三方比较分别留在 `FORMAL_INPUT_PROVENANCE.csv` 和 `GNSS_THREE_WAY_COMPARISON.csv`。`INPUT_DIFF.csv` 每例一行，保留两侧路径、完整 SHA-256、来源层数据标签、列组状态、差异 token/行数和行号。

标签按原来源层保留，不统一改写：两链实际 native RUN_MANIFEST 各 72 份均为 `real_base_controlled_degradation / synthetic=false / semisynthetic=false`；v2.1 外层正式 source record 的核心 54 份同此标签，A2 的 18 份为 `semisynthetic / false / true`；v3 外层 V3_NATIVE_SUMMARY 的 72 份均为 `semisynthetic / false / true`。`INPUT_DIFF.csv` 的 source 标签字段对应外层 source record / summary，不是 native RUN_MANIFEST。逐例四层原值及分项计数见 `DATA_LABEL_PROVENANCE.json`；原生清单与外层标签口径差异完整保留，不将受控注入输入混称为未注入自然数据。

GNSS18 使用零基列号：时间 0；位置 1–3；位置 std 4–6；速度 7–9；速度 std 10–12；yaw 13；yaw std 14；位置/速度/yaw valid 15/16/17。按原行顺序比较完整 token，同时独立按唯一的原文时间 token 精确连接，不舍入时间、不以浮点近似相等替代文本相等。再仅遮蔽列 13 和 17，比较余下完整文件字节，包括空白及换行。72 对均无重复时间 token、无跨链未配对行。

两链全部 72 个 F01 的 `actual_solver_input_paths` 只有 GNSS18 与传播 IMU。IMU SHA-256 均为 `74e31747c5b10d46846472a5adb41bd8e75ad3e27a612f45946c4895b976f647`，实际文件复验通过。每份 IMU 为 63,277 行、7 列，时间 token 从 `44.889051` 到 `350.091049`；行数、时间序列和其余 6 列均为 72 对相同 / 0 对不同。GNSS 的位置/速度/std/valid 列不适用于该 IMU 格式，明确记为 `NOT_APPLICABLE_IMU_PROVIDER`，见 `OTHER_PROVIDER_STRUCTURE.csv`。

RD、Go2 RP、HV 仅配置了路径，F01 开关关闭，标记 `CONFIGURED_BUT_NOT_READ_BY_F01`，不混入“实际读取 provider”的分母。F01 关闭的是在线航向更新；`common_initialization_dual_yaw_used=true` 表示冻结共同初始化来源，不能解读为在线启用了 yaw 更新。另核对每例 20 项初始化回显（含 initpos/initvel/initatt 及共同初始化字段），72 对全部相同，见 `INITIALIZATION_IDENTITY.csv` 与原值 JSON。

### 相同 / 不同计数

每格为“相同 / 不同”，单位是运行，非 epoch。无缺失输入或不可判定项。

| 项目 | 核心 54 例 | A2 18 例 | 合计 72 例 |
| --- | ---: | ---: | ---: |
| GNSS 行数 | 54 / 0 | 18 / 0 | 72 / 0 |
| 时间 token 序列 | 54 / 0 | 18 / 0 | 72 / 0 |
| 位置列 | 54 / 0 | 18 / 0 | 72 / 0 |
| 速度列 | 54 / 0 | 18 / 0 | 72 / 0 |
| 位置 std | 54 / 0 | 18 / 0 | 72 / 0 |
| 速度 std | 54 / 0 | 18 / 0 | 72 / 0 |
| yaw std | 54 / 0 | 18 / 0 | 72 / 0 |
| position_valid | 54 / 0 | 18 / 0 | 72 / 0 |
| velocity_valid | 54 / 0 | 18 / 0 | 72 / 0 |
| yaw_valid | 0 / 54 | 0 / 18 | 0 / 72 |
| yaw 值 | 9 / 45 | 0 / 18 | 9 / 63 |
| GNSS 全文件 | 0 / 54 | 0 / 18 | 0 / 72 |
| 实际其他 provider（IMU）全文件 | 54 / 0 | 18 / 0 | 72 / 0 |

所以，valid 三列整体是 0 相同 / 72 不同，但变化完全来自 yaw_valid；位置/速度 valid 为 72 相同 / 0 不同。遮蔽 yaw/yaw_valid 后的完整字节也为 72 相同 / 0 不同。共发现 yaw token 差异 95,130 个、yaw_valid token 差异 60,939 个，其余列差异均为 0。D57 的 9 例 yaw 值本身未变，只将原 301 个有效 yaw 标记置为无效。

`BASELINE_ROW_SUPPORT.csv` 另将旧 F01 实际表与其冻结 C00 基准比较：除 D57 外的 63 例均保留基准的全部 1,510 行和相同时间 token 顺序，没有删行；D57 按已登记的独立时移源事件并集形成 3,321 行，两链原文时间序列及行数完全相同，不能拿未时移 C00 的 1,510 行作为 D57 删行标准。

### 工况定义、5 Hz 映射与差异来源

核心定义取自冻结 `CANONICAL541_CASE_MANIFEST.csv`，SHA-256 `ac58b992a56f3ab05c585973fa6ceef1493d0d5cd6a9f0a9e18dae8edd998cb2`；A2 取原 addendum 的 `00_PREREGISTRATION/CASE_REGISTRY.csv`。全部 72 条定义和源 pin 保存在 `CASE_DEFINITION_COMPARISON.csv`。映射取 v3 科学冻结 `7d43b9af26120ed5dde21f53e515386361072ba6` 的 [PROTOCOL_V3_PREREG.md](PROTOCOL_V3_PREREG.md)、合约及 `protocol_v3/providers.py`；当前预注册文档仅在原文之后增加存储/恢复条款，原映射不变。

| 类型 | 登记的原注入 | v3 预注册的航向映射与本次证据 |
| --- | --- | --- |
| D05 | 位置及接收机速度停测 10 s，航向不在停测源内 | 保持位置/速度停测，替换原始 5 Hz 航向及有效性；旧 1 Hz yaw 之外的有效航向增加，非航向字节不变。 |
| D09 / D10 | 位置、速度、航向分别按源降到 2 / 1 Hz，原 anchor 决定相位 | 新航向沿用 `anchor mod (1/rate)` 分箱、每箱首个有效行。旧航向原本约 1 Hz，不高于目标率时原注入不再降采样；其时刻与位置/速度保留时刻未必相同。两链均保留全部物理行，只改变有效性。 |
| D11 / D12 | 三源分别选择 30% / 60% 掉线事件 | 原已选 1 Hz 航向掉线按 `[t,t+1)` 单元延拓，不重抽事件；位置/速度已选 valid 模式逐字节保留。 |
| D57 | 各源独立 0.1–0.3 s latency、0.02–0.05 s jitter，并稳定排序 | 保留已扰动时间 token，只精确连接原始 iTOW，不插值、不修正时间；原 301 个 yaw 有效事件因无精确匹配置 0，原行与 yaw 数值保留。 |
| D62 / A2 | 位置、接收机速度及 RD 停测 10 / 20 s；旧航向保留 | 新原始 5 Hz 航向按自身有效性保留，停测窗内其他输入原样；RD 仍不由 F01 读取。 |

旧注入源码 `canonical541/provider_generator.py::_invalidate` 只修改源有效性及状态字段；普通 GNSS 组表从完整基准行列表复制，D57 才组成各源时移事件的并集。A2 的 `apply_outage` 另明确禁止改变行数、时间和前 15 列，并要求保留原 yaw_valid。v3 从正式 F01 旧表逐行替换列 13/17，非这两列的字节门及本次独立复验均通过。

**判定：没有证据支持“v3 重派生非航向输入、偏离仅替换 yaw/valid”，也没有发现“v2.1 把这些 GNSS 行整行删除”。** 实际差异符合预注册的 yaw/yaw_valid 替换。原注入采用各源独立有效性，v3 的航向时间映射又改变了有效事件并集；这与物理删行、位置/速度重派生是不同问题。

### F01 仍可能受 yaw_valid 影响的静态路径

`SOURCE_SEMANTICS.json` 保存二进制冻结清单 `CLEAN6_SENSOR_MODEL_V21/01_BINARY_BRIDGE/BINARY_FREEZE.json`、构建源 `ca73cb1fb48a020fd2a450d79e520562c34eeb24` 的源文件 SHA-256 与带行号片段。其 GNSS loader、GIEngine、runtime 三文件与桥接前 `a01ceb931049f84af8c900b39e4cf01c52f627c6` 字节相同；二进制桥只改 F02 std guard。这里使用实际构建源，未将清单中的上游算法参考 `source_commit` 误当成本地构建版本。

冻结 GNSS loader 保留解析后的每一行，并独立设置三个 valid。`GIEngine::addGnssData` 无条件使用 `has_position || has_velocity || has_yaw` 判定 GNSS 事件有效，未在该处用 F01 航向开关屏蔽 `has_yaw`。真正的 yaw 量测更新随后才受 `enable_dual_yaw_update` 限制。`newImuProcess` 又按有效事件时间选择传播/更新顺序；事件处于两个 IMU 时刻之间时会拆分 IMU 增量。因此，关闭 yaw 量测更新并不保证更换 yaw_valid 对事件调度完全无影响。

以下只对输入 valid 做布尔运算：`any_valid = position_valid | velocity_valid | yaw_valid`，`nonheading_valid = position_valid | velocity_valid`。它不是实际更新次数、接受次数或求解器回放，也包含整张输入表的起止边界行。

| 类型（各 9 例） | 两链每例行数 | yaw-only 行总数 v2.1 → v3 | any_valid 变化行总数 | nonheading_valid 变化行 |
| --- | ---: | ---: | ---: | ---: |
| D05 | 1510 | 90 → 450 | 360 | 0 |
| D09 | 1510 | 2709 → 0 | 2709 | 0 |
| D10 | 1510 | 2709 → 0 | 2709 | 0 |
| D11 | 1510 | 156 → 800 | 644 | 0 |
| D12 | 1510 | 386 → 1963 | 1577 | 0 |
| D57 | 3321 | 2709 → 0 | 2709 | 0 |
| D62_10s | 1510 | 90 → 450 | 360 | 0 |
| D62_20s | 1510 | 180 → 900 | 720 | 0 |

全部 72 例的事件并集都改变，共 11,788 个逐例输入行；位置或速度有效的事件并集全部不变。首个事件并集差异见下表，原文双行另在 `FIRST_RAW_LINE_DIFFERENCES.json/csv` 的 `FIRST_ANY_VALID_EVENT_DIFFERENCE` 项，全部变化行在 `ANY_VALID_EVENT_DIFF.csv`。

| 类型 | 示例工况 | 数据行号（从 1 起） | 原文时间 token |
| --- | --- | ---: | --- |
| D05 | D05_seed_00 | 728 | `201.200000048` |
| D09 | D09_seed_00 | 2 | `56.000000000` |
| D10 | D10_seed_00 | 2 | `56.000000000` |
| D11 | D11_seed_00 | 16 | `58.799999952` |
| D12 | D12_seed_00 | 13 | `58.200000048` |
| D57 | D57_seed_00 | 6 | `56.319448150820` |
| D62_10s | D62_10s_seed_00 | 728 | `201.200000048` |
| D62_20s | D62_20s_seed_00 | 703 | `196.200000048` |

这条路径是输入字节与冻结源码共同支持的**可能机制**，足以说明不能从“F01 关闭在线航向更新”直接推出全矩阵 NAV 必须字节相同。本次没有启动解算器、评估器或状态回放，故不宣称已经证明它是 NAV 哈希差异的唯一原因，不量化 NAV 变化大小，也不据此解除既有核心哈希硬停。

### 每族第一处差异的原文两行

按每类型最小工况/种子选择，然后取文件内最早差异行；A2 的 10 s / 20 s 分列。每个代码块第一行为 v2.1 正式 F01 输入，第二行为 v3 实际输入，保留原始 token、空格和行序，不重排或重新格式化数值。JSON/CSV 还保存两侧文件哈希、行号、原始行 SHA-256 和换行的 bytes 表示。所有类型的“首个非 yaw/yaw_valid 差异”均记为无此差异，不造出示例。

**D05：`D05_seed_00`，文件行 1，变化零基列 [13, 17]。**

```text
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 0.000000 1.500000 1 1 0
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 1.336460 1.500000 1 1 1
```

**D09：`D09_seed_00`，文件行 1，变化零基列 [13, 17]。**

```text
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 0.000000 1.500000 1 1 0
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 1.336460 1.500000 1 1 1
```

**D10：`D10_seed_00`，文件行 1，变化零基列 [13, 17]。**

```text
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 0.000000 1.500000 1 1 0
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 1.336460 1.500000 1 1 1
```

**D11：`D11_seed_00`，文件行 1，变化零基列 [13, 17]。**

```text
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 0.000000 1.500000 0 1 0
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 1.336460 1.500000 0 1 1
```

**D12：`D12_seed_00`，文件行 1，变化零基列 [13, 17]。**

```text
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 0.000000 1.500000 0 1 0
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 1.336460 1.500000 0 1 1
```

**D57：`D57_seed_00`，文件行 6，变化零基列 [17]。**

```text
56.319448150820 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 1.485569 1.500000 0 0 1
56.319448150820 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 1.485569 1.500000 0 0 0
```

**D62_10s：`D62_10s_seed_00`，文件行 1，变化零基列 [13, 17]。**

```text
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 0.000000 1.500000 1 1 0
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 1.336460 1.500000 1 1 1
```

**D62_20s：`D62_20s_seed_00`，文件行 1，变化零基列 [13, 17]。**

```text
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 0.000000 1.500000 1 1 0
55.799999952 39.984829852538 116.343128120990 41.779992153 0.014000 0.014000 0.010000 -0.001000 -0.008000 -0.008000 0.050000 0.050000 0.050000 1.336460 1.500000 1 1 1
```

### 本次交付与保留检查

`INPUT_DIFF.csv` 是请求的 72 例主表；`INPUT_DIFF_SUMMARY.csv` 为 8 类型分项；`GNSS_TOKEN_DIFFS.csv` 为精确 token 差异明细；`OTHER_PROVIDER_HASHES.csv` 区分实际读取与仅配置的 provider，`OTHER_PROVIDER_STRUCTURE.csv` 给出实际 IMU 行/列及 token 相同性；`BASELINE_ROW_SUPPORT.csv` 保留旧表相对冻结 C00 的行支持证据。来源定义、三方溯源、原始双行及事件并集文件均在同一 `<FC01_CONT02>` 目录。初始化与 IMU 结构补充由 `INPUT_SUPPLEMENT_RECEIPT.json` 单独绑定，没有改写主审计的已封清单。

主审计通过 6 个纯内存比较测试；451 项来源 pin 留档，146 个实际 provider 路径在结束时复验。此前 40 个 FC01 文件和 181 张封存 CSV 前后哈希不变。解算器、评估器、provider 生成、NAV payload、降采样 NAV 及 raw trace 读取均为 0；科学模块导入为 0。读取冻结源码使用的 `git show` 只输出源文本，不属于科学执行。

独立只读复核重新核验了 72 对输入、144 份清单、所有实际 IMU pin、16 组原文双行和 9 项冻结源文件，确认上述 token/字节计数与事件并集计数。分类、转移表和 541/61 指标汇总维持续作 1 的未执行状态；本次仅完成新增授权的输入差分。

最终独立复核为 PASS，回执为 `FINAL_REVIEW_RECEIPT.json`；`FINAL_OUTPUT_SEAL.json` 封存本轮 33 个审计文件（自身及后写 Git 提交回执除外）。`INPUT_DIFF.csv` SHA-256 为 `05f3096182bfd539e85072ac934fcb0d77fdfba3c49ea751208953ac6d3cbd4e`；最终 seal SHA-256 为 `57cf7fbe0125d0bb0935b38055d3a7ada9a9ce01e40447f16c20bd5676adba0f`。Git 仅提交本报告；大表、清单及审计附件按仓库规则留在 `<FC01_CONT02>`。

## 附录：F01 位置更新次数与 yaw_valid 的只读核对

本次从 `cce42f792cd6241508f7ee8d89f7e1f3ad68a592` 追加，仅核对 F01 的 `C00_clean_normal`、`D57_seed_00`、`D05_seed_00`、`D09_seed_00` 至 `D12_seed_00`，两链共 14 个保留运行。结论是：**这 7 个工况的两链位置更新总次数全部相同，但六个故障工况的 GNSS 处理事件数不同。yaw_valid 参与历元调度，不是 F01 位置更新的直接筛选条件。**

### 保留计数与 GNSS 全表行数

位置次数取 native `RUN_MANIFEST.json.position_update_count`，并独立对原始 `PORT_GNSS_UPDATE_TRACE.csv`（若存为 gzip，则只在内存解压）的 `position_update` 列求和。14 项均完全一致。表中“GNSS 事件”是 trace 数据行数，也全部等于 manifest 的 `measurement_update_count`，不能代替位置次数。全部 trace 的 `update_index` 连续为 `1..N`、`gnss_time` 严格递增，存储及解压 SHA-256/字节数与封存 pin 一致。

GNSS 总行数与 yaw_valid=1 行数来自该 F01 实际读取并通过 provider 哈希核验的 GNSS18 全文件，yaw_valid 是零基列 17。所有运行配置窗口均为 66–340 s；输入全表还包含窗口外行，不能直接用全表行数减更新次数推算运行内的丢弃数。下表的 D 编号均指 `seed_00`。

| 工况 | 链 | manifest 位置更新 | trace 位置更新之和 | GNSS 全表 yaw_valid=1 | GNSS 全表总行数 | GNSS 事件 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| C00 | v2.1 | 1369 | 1369 | 301 | 1510 | 1369 |
| C00 | v3 | 1369 | 1369 | 1510 | 1510 | 1369 |
| D57 | v2.1 | 1365 | 1365 | 301 | 3321 | 3005 |
| D57 | v3 | 1365 | 1365 | 0 | 3321 | 2736 |
| D05 | v2.1 | 1319 | 1319 | 301 | 1510 | 1329 |
| D05 | v3 | 1319 | 1319 | 1510 | 1510 | 1369 |
| D09 | v2.1 | 548 | 548 | 301 | 1510 | 821 |
| D09 | v3 | 548 | 548 | 604 | 1510 | 548 |
| D10 | v2.1 | 274 | 274 | 301 | 1510 | 547 |
| D10 | v3 | 274 | 274 | 303 | 1510 | 274 |
| D11 | v2.1 | 960 | 960 | 211 | 1510 | 1268 |
| D11 | v3 | 960 | 960 | 1060 | 1510 | 1333 |
| D12 | v2.1 | 553 | 553 | 120 | 1510 | 933 |
| D12 | v3 | 553 | 553 | 605 | 1510 | 1085 |

14 个运行的 `enable_dual_yaw_update`、`enable_basic_dual_yaw_baseline`、`enable_qa_fallback` 均为 false；trace 的 `yaw_update` 之和全部为 0。C00 两链 trace 的解压内容哈希也完全相同。D57 的 v3 即使全表 yaw_valid=1 行数为 0，仍有 1,365 次位置更新，直接排除了“只有 yaw_valid=1 才允许 F01 位置更新”的解释。

另对 trace 中 `position_update=velocity_update=yaw_update=0` 的事件计数：

| 工况 | v2.1 三列均 0 的事件 | v3 三列均 0 的事件 | GNSS 事件差（v3−v2.1） |
| --- | ---: | ---: | ---: |
| C00 | 0 | 0 | 0 |
| D57 | 269 | 0 | −269 |
| D05 | 10 | 50 | +40 |
| D09 | 273 | 0 | −273 |
| D10 | 273 | 0 | −273 |
| D11 | 18 | 83 | +65 |
| D12 | 42 | 194 | +152 |

各工况 GNSS 事件数的差恰好等于上述三列均为 0 的事件数之差。这是保留诊断 trace 的实测计数，与前文“仅航向有效的行仍可参与历元处理”的静态路径一致；这里没有重放解算器。位置总次数相同不证明位置更新时间序列、传播路径或 NAV 字节相同，也不证明 NAV 差异的唯一原因。

### 冻结源码的具体行

以下行号均针对二进制桥构建源 `ca73cb1fb48a020fd2a450d79e520562c34eeb24`，不是当前工作区可能已位移的行号。可用 `git show ca73cb1fb48a020fd2a450d79e520562c34eeb24:<文件路径>` 取原文。下述 loader、GIEngine、runtime 三文件与旧求解器冻结 `64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00` 及桥接前 `a01ceb931049f84af8c900b39e4cf01c52f627c6` 字节完全相同，两链均适用。

文件路径以下表的 `cpp/legsa_v23_port_core/src/` 为共同前缀。

| 文件与冻结行号 | 具体处理及含义 |
| --- | --- |
| `fileio/gnss_file_loader.cpp:53–73` | 53–54 行读取三个 valid；69–71 行分别设置 `has_position`、`has_velocity`、`has_yaw`；第 73 行无条件保留成功解析的行。不会因为 yaw_valid=0 删除位置有效行。 |
| `kf_gins/gi_engine.cpp:247–256` | `addGnssData` 第 256 行设置 `isvalid = has_position || has_velocity || has_yaw`；这里没有检查 F01 的 `enable_dual_yaw_update`。这是 yaw_valid 在单天线配置中仍进入历元处理的入口。 |
| `kf_gins/gi_engine.cpp:259–275` | 第 260 行由 `isvalid` 决定事件时间是否有效；266–273 行据其与前后 IMU 时刻的关系返回处理分支 1/2/3，否则为 0。 |
| `kf_gins/gi_engine.cpp:361–379` | 364–365 行仅在 `has_position` 且未被 QA 拒绝时调用位置更新；377–379 行才用 `has_yaw && enable_dual_yaw_update && yaw_scheme_C_enabled` 门控实际 yaw 更新。 |
| `kf_gins/gi_engine.cpp:413–414` | `gnssUpdate` 末尾清除本事件有效标志并递增 `update_count_`，不要求本事件的位置/速度/yaw counter 曾增长；所以 trace 可以出现三类更新标志均为 0 的事件。 |
| `kf_gins/gi_engine.cpp:828–859` | `applyPositionUpdate` 在 858 行执行 `EKFUpdate` 后，859 行递增 `position_update_count_`；844 行是 Basic 分支的计数，本次 F01 不走该分支。 |
| `kf_gins/gi_engine.cpp:486–510` | 491–492 行用有效事件时间选分支；493–510 行控制传播、`gnssUpdate`、`stateFeedback` 的顺序。505–510 行在 IMU 间的有效事件处拆分 IMU 增量并分两段传播。 |
| `runtime/port_runtime.cpp:1471–1495` | 1471–1475 行在 GNSS 已陈旧时只推进一行；1485–1488 行保存各 counter，1492 行处理 IMU；1495 行判断 GNSS 事件计数是否增长。 |
| `runtime/port_runtime.cpp:1503–1525` | 1514 行把位置 counter 是否增长写成 trace 的 `position_update`；1515–1516 行同理记录速度/yaw。1523–1525 行分别复制事件、位置、速度总次数。 |
| `fileio/file_saver.cpp:927–930` | 927–930 行分别写出 `measurement_update_count`、`position_update_count`、`velocity_update_count`、`yaw_update_count`，因此不能混用事件计数与位置计数。 |

最关键的原文是：

```cpp
// kf_gins/gi_engine.cpp:256
  gnssdata_.isvalid = gnssdata_.has_position || gnssdata_.has_velocity || gnssdata_.has_yaw;
// kf_gins/gi_engine.cpp:364-365
  if (policy_gnss.has_position && !qa_reject_position) {
    applyPositionUpdate(policy_gnss);
// kf_gins/gi_engine.cpp:377-379
    if (!qa_reject_yaw && policy_gnss.has_yaw && options_.enable_dual_yaw_update &&
        options_.yaw_scheme_C_enabled) {
      applyYawUpdate(policy_gnss);
```

这表示：当位置或速度有效时，yaw_valid 不决定该行能否成为有效 GNSS 历元；当位置、速度都无效而 yaw_valid=1 时，该行仍可触发 GNSS 历元分支，即使 F01 的 yaw 量测更新关闭。不能把后者的事件处理次数解释成位置更新次数。

上述三个行为源文件的 SHA-256 分别为：

| 文件 | SHA-256（上述三个冻结提交均相同） |
| --- | --- |
| `fileio/gnss_file_loader.cpp` | `a95e2bc2f3b9ebae935a049148f77a6f0b77684d148d7c0713429cde14522b2f` |
| `kf_gins/gi_engine.cpp` | `4d2e329a1f6a11ed232941c3150a5569791f7ac5fceb0362e91e5dd856dc6a50` |
| `runtime/port_runtime.cpp` | `9a00eabdbbd7d629da4e476461a69872c9eb26550a9c286fcc59931e1d04bc99` |

正式 native 记录的 solver executable SHA-256 为：v2.1 七项均 `9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`，v3 七项均 `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`，与二进制冻结桥对应。RUN_MANIFEST 中的 `helper_executable_hash` 不是 solver binary 哈希，本核对没有混用两者。

### 保留来源及诊断 trace 哈希

新增别名 `<V2_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2`；`<PROTOCOL_V3_SCRATCH>` 为既有注册的 v3 scratch 路径。七个工况的运行编号及目录如下，每个目录内读取原 RUN_MANIFEST 与诊断 trace。

| 工况 | run_id | v2.1 正式复用的 solver 目录 | v3 native 目录 |
| --- | --- | --- | --- |
| C00 | RUN_00001 | `<V2_ROOT>/RETAINED_RUNS/RUN_00001/solver` | `<V3_ROOT>/03_NATIVE/RUN_00001` |
| D57 | RUN_05556 | `<V2_ROOT>/RETAINED_RUNS/RUN_05556/IO_RECOVERY_20260912_cycle220_attempt01/solver` | `<V3_ROOT>/03_NATIVE/V3R_CONTINUATION/RUN_05556` |
| D05 | RUN_00408 | `<V2_ROOT>/RETAINED_RUNS/RUN_00408/solver` | `<V3_ROOT>/03_NATIVE/RUN_00408` |
| D09 | RUN_00804 | `<V2_ROOT>/RETAINED_RUNS/RUN_00804/solver` | `<V3_ROOT>/03_NATIVE/V3R_CONTINUATION/RUN_00804` |
| D10 | RUN_00903 | `<V2_ROOT>/RETAINED_RUNS/RUN_00903/solver` | `<V3_ROOT>/03_NATIVE/V3R_CONTINUATION/RUN_00903` |
| D11 | RUN_01002 | `<V2_ROOT>/RETAINED_RUNS/RUN_01002/solver` | `<V3_ROOT>/03_NATIVE/V3R_CONTINUATION/RUN_01002` |
| D12 | RUN_01101 | `<V2_ROOT>/RETAINED_RUNS/RUN_01101/solver` | `<V3_ROOT>/03_NATIVE/V3R_CONTINUATION/RUN_01101` |

六个退化工况的 manifest/GNSS 路径及完整哈希与已封 `<FC01_CONT02>/FORMAL_INPUT_PROVENANCE.csv`、`INPUT_DIFF.csv` 相同。新增 C00 的两份 RUN_MANIFEST SHA-256 为 v2.1 `15b728a514e3ef661935806860ff417766772819f8302712c2d8bef1a1366ff9`、v3 `dd55532bf0fb4ff702939335e118e3572690de9e8ce30ea77f661cc717c08c6e`。

C00 的实际 v2.1 GNSS 是 `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS/BY2/CALIBRATED_GNSS.gnss`，SHA-256 `68ed8de7f91b267072bab09e968a9cab4b5220bc5eb116140adacdfde0382e7a`；实际 v3 GNSS 是 `<PROTOCOL_V3_SCRATCH>/02_PROVIDERS/CASES/BY2__C00_clean_normal__68ed8de7f91b267072bab09e968a9cab4b5220bc5eb116140adacdfde0382e7a/GNSS18.gnss`，SHA-256 `3485b93459fa4c6c695d51e3f9714c133de6b4627a443515aeb1ada191b04b97`。均通过冻结注册表、实际 manifest provider pin 与文件字节的绑定，不用其他配置的 C00 表代替。

v2.1 trace 均存为 `PORT_GNSS_UPDATE_TRACE.csv.gz`，存储/解压 pin 来自实际 solver 目录上一级 `ARCHIVE_RECEIPT.json.retained_files`，并以正式 source record 的 `output_seal` 再核解压内容。v3 的 C00/D05 为 `.csv.gz`，其余五项为 `.csv`；pin 来自该 native 目录的 `ARCHIVE_RECEIPT.json.files`，并与 `V3_NATIVE_SUMMARY.file_hashes` 交叉核验。以下均是实际保留诊断 trace，不是真值 trace。

| 工况 | 链 | 存储文件 SHA-256 | 解压 CSV 内容 SHA-256 |
| --- | --- | --- | --- |
| C00 | v2.1 | `1745fe68dbfc28a73ea376646d8f2fd3cfb39f5c08e5eaad1754f862b9d5889a` | `70a4a336a7e92a4f7b68e18e6c7da3a6930191adf2239dc4a378ed3bd5146f10` |
| C00 | v3 | `1745fe68dbfc28a73ea376646d8f2fd3cfb39f5c08e5eaad1754f862b9d5889a` | `70a4a336a7e92a4f7b68e18e6c7da3a6930191adf2239dc4a378ed3bd5146f10` |
| D57 | v2.1 | `980aa3baa7372313e9775df92a10985e75c9dacdfc26f3f0f8cf3c66b1cee62a` | `08c86a20f327c2570c811deebe8586cb6cc512e4c66812f02838986f5ece939c` |
| D57 | v3 | `e2cbf1936ff636c4d6f675b8a35e1e506b2c24f60800b5c04fc49cff4d49794f` | `e2cbf1936ff636c4d6f675b8a35e1e506b2c24f60800b5c04fc49cff4d49794f` |
| D05 | v2.1 | `55be555ed8f93df23643d3a050af55efff3f2575929d19391ac8f6e598c6fab6` | `acee0a45f514ed0f43ab239a066e6f038ba03870f7c54cba575d8d4e6fe531c8` |
| D05 | v3 | `82cf3a74a883cd25d9c37ae7fd2dfc899ebc356b929b9a332c817f4ed5321778` | `586c6fedba26ad09ca8bdde3e90924bc4f1ef17d4932815b732fecdc3649d672` |
| D09 | v2.1 | `7a6c692a956784972793dec72e81d9a11fb7cf46ab5fdc7e762a5e19f99e3edd` | `6ec89e11f21b5de41a9a4932a8728220e5193cf5d02c0bbd7e82f8085fdf58c9` |
| D09 | v3 | `4ee687be30453a1a758556cdb028dfc1888005311fd9f41a5a44b43320546704` | `4ee687be30453a1a758556cdb028dfc1888005311fd9f41a5a44b43320546704` |
| D10 | v2.1 | `07ba8117335025acf1825c553349b213a3476e72eae704b4291d7b44be158c11` | `cd7d037d214ec098d14b00aca4d5b11aa5cf770ef898b0e0e0e6bb6bebd34fdd` |
| D10 | v3 | `8cbf2dacaade228b14b0eb51b73b9f0c227eadf63d037d17f0bb95d4e74ecbd3` | `8cbf2dacaade228b14b0eb51b73b9f0c227eadf63d037d17f0bb95d4e74ecbd3` |
| D11 | v2.1 | `bc3f7ca80c760a15fc1a3f5f513997d6903ae8f0e1bc7fc24e483fff12c9bbe2` | `3ab042bd6ff99ace873ab4cf3ada078b987399910fa6cfb27440bc9de73af43c` |
| D11 | v3 | `8a792864bf6906b14d904d0a1e04a4c2d9522c03e7dcb7b5629fc23a963ff1b5` | `8a792864bf6906b14d904d0a1e04a4c2d9522c03e7dcb7b5629fc23a963ff1b5` |
| D12 | v2.1 | `9d94c06a9f9fd539b835f93514d417286a6ba018aaea18aebafbcaedc1e7d8af` | `d28841a5a64e7de3a9a6c0c52fbc02e80b0e074d8d04f32f10bd4cba5d46f665` |
| D12 | v3 | `2fa44c1938e6e6470a70a7e2161541b160a8a06f8bbd4e045b19dd00bf0a0172` | `2fa44c1938e6e6470a70a7e2161541b160a8a06f8bbd4e045b19dd00bf0a0172` |

本次只追加本报告附录，原报告保持精确字节前缀；没有新增或改写外部表、清单、回执、provider、源码或保留运行。统计读取的 71 个文件前后 SHA-256 不变；解算器、评估器、provider 生成调用及 NAV/真值 trace 读取均为 0。原统一分类硬停继续保留，本附录不恢复分类或指标汇总。

独立只读复核重新统计全部 14 项、交叉核验 trace 封存哈希及冻结源码行号，结果 PASS；附录之外的报告原字节和 29 个无关未跟踪文件均保留。
