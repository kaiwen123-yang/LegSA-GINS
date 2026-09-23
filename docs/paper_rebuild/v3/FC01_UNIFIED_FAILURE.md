# FC-01：统一失败分类（只读续作）

当前终态：**`HARD_STOP_CORE_F01_NAV_HASH_DIFFERENCE`**。按用户续作裁决完成 F01 哈希盘点后，核心 541 例中发现 54 对哈希不同，触发明确硬停；尚未执行分类自检、全量分类或指标汇总。**54 是 NAV 哈希差异数，不是算法失败数。**

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
