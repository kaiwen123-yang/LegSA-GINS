# FC-01：统一失败分类（只读）

终态：**`HARD_STOP_F01_CLASSIFICATION_INCONSISTENCY_DUE_TO_HASH_AND_EVIDENCE_CONFLICT`**。全量分类与统计未完成，不能报告统一失败总数或更新手稿失败结论。原始自动停止回执为 `HARD_STOP_F01_IDENTITY`；定点复核确认该哈希冲突使指定来源下的 F01 分类成为 v3 `COMPLETED`、v2.1 `UNCLASSIFIABLE`，不满足用户要求的 F01 一致性门。

起点：`fb39cb8b8bd0ed08ac20ea62f5e4f2ffc483bfef`。授权范围为重分类既有证据、重汇总已封存评估数值；本轮停在 F01 自检，尚未进入统计。未执行解算器、评估器或 provider，未修改已封存表。

路径别名：`<V3_ROOT> = <CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3`；`<V21_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21`；`<FC01_ROOT> = <V3_ROOT>/07E_UNIFIED_FAILURE`。全部新 CSV、复现脚本与审计回执保存在 `<FC01_ROOT>`，作为 `07_AGGREGATE` 的伴随产物。

## F01 硬停事实

冲突科学身份为 `BY2 / D62_10s_seed_00 / F01`，运行编号 `ADD_RUN_00298`，域为 A1/A2 附加实验。两链各自只有一个匹配身份；已核对 dataset、case、method，并非 run_id 或配置别名连接错误。

| 项目 | 协议 v3 | 协议 v2.1 |
| --- | --- | --- |
| 原始分类 | COMPLETED | COMPLETED |
| NAV SHA-256 | `bcfb4e5b04d10cd68b1e5b7205c047160d750a21bbe2fbe420a2e76d1d29fe98` | `395e34939f3e14881bfb214486661065d0c0cec200aa453669186aaf7413655e` |
| 当前合格界限证据 | 与该 NAV 哈希绑定的 `V3_NATIVE_SUMMARY` | 指定 `RETAINED_RUNS` 中无该正式复用运行，冻结评估行不含完整界限判定 |
| 统一分类 | COMPLETED | UNCLASSIFIABLE |

v3 封存界限通过：位移约 116.159 m、速度约 6.0575 m/s、高度位移约 3.8812 m，全部数值行有限；清单确认航向关闭、attempt=0、accepted=0。v2.1 两个评估器版本的冻结表都记录 `395e349…`，并标记正式 F01 复用；v3 运行注册表、归档摘要、摘要内界限的 source NAV 哈希都为 `bcfb4e5…`。原始 `COMPLETED` 标签不能补足 v2.1 缺失的界限证据，两个不同 NAV 哈希之间也不能转移判定。

来源为 `<V21_ROOT>/20_FINALIZE/13_AGGREGATE_ADDENDUM/{v3,v2}/UNIQUE_EVALUATION_RESULTS.csv` 及 `<V3_ROOT>/03_NATIVE/V3R_CONTINUATION/ADD_RUN_00298/` 的封存记录。归档清单校验的 v3 摘要 SHA-256 为 `2b429bb4c70f05bb7f53da291fbfaf0808aae27cd327fe2008eb35db708b351e`；v2.1 两张表 SHA-256 分别为 `9d8021712f62bb4107f52dedf3229c45b86a80a41797075abeb8cba42fda7f5a` 和 `69beeefa8c47ba0ab84ffe15ec26dbef26da888a5acb4d90ae9848e9c9d4a401`。

这不证明 v2.1 该轨迹发散，也不证明 F01 数值性能恶化；它证明“F01 两条链 NAV 哈希相同”的前提在全范围此条目不成立，现有授权来源不能完成统一分类自检。没有转读该行指向的附加实验原始 NAV 来扩大来源，也没有缩小到 CORE 后绕过硬停。继续分类前需要人工明确该复用证据的处理方式或重新界定范围。

## 交付状态

| 请求产物 | 状态 |
| --- | --- |
| 两链逐运行完整分类表 | NOT_PRODUCED：F01 硬停 |
| 故障族 × 配置 × 类别对照 | NOT_PRODUCED：F01 硬停 |
| 完成→失败、失败→完成、双失败、双完成转移表 | NOT_PRODUCED：F01 硬停 |
| 同分母 541 分布与 61 例摘要 | NOT_PRODUCED：F01 硬停 |
| F01 自检 | FAILED；保留首个冲突记录，不宣称 588 对全部检查通过 |
| dual_yaw 统一分类计数 | NOT_COMPUTED；不能以原分类计数替代 |
| dual_yaw 5 Hz 注入映射说明 | 已完成，仅源码/冻结协议读取 |
| 手稿失败段落替换文字 | NOT_PRODUCED；统一失败总数未建立，不能形成可用比较结论 |

以下统一定义和汇总方法保留为本次实现说明，不表示后续全量表已经生成。

## 只读执行与验证

F01 按注册编号排序先行检查：前 27 对通过，第 28 对为上述冲突；后续 560 对 F01 和 5,880 对非 F01 未继续分类。不得将这些待处理条目计为已确认的 `UNCLASSIFIABLE`，也不得据此前缀推断全量失败数。

12 项纯内存规则测试通过，覆盖严格界限、非有限行、F01 航向禁用、无有效输入、全拒绝和缺证。两份独立脚本不导入项目运行模块，并以 Python audit hook 禁止科学子进程、运行模块导入、trace 读取及目录外写入；解算器调用 0、评估器调用 0，未读取降采样 NAV 来补判。`READ_ONLY_AUDIT.json` 的进程计数限定于审计脚本内部，不把外层启动 Python 或 Git 的命令误记为科学运行。

`SEALED_TABLE_GUARD.json` 验证 181 张既有 CSV 的前后 SHA-256 一致，修改数为 0。原自动 `HARD_STOP.json` 保持原字节；定点收束通过新文件补充，没有恢复全量分类。独立只读复核确认冲突身份、两个 NAV 哈希、v3 摘要及清单归档 pin、v2.1 来源缺口与停止决定。

关键伴随文件：`HARD_STOP_PAIR.csv`、`HARD_STOP_EVIDENCE.json`、`HARD_STOP_SOURCE_PINS.csv`、`PENDING_OUTPUTS.json`、`READ_ONLY_AUDIT.json`、`SEALED_TABLE_GUARD.json`、`FOCUSED_TESTS.json`、`MANIFEST.json`。复现实现保留为 `fc01_audit.py` 和 `fc01_close_hard_stop.py`；后者只收束停止证据，不继续统计。

`MANIFEST.json` SHA-256：`cf5bb902828b46c7da4cf23607b91ce8ec1b25c6404a56757c6d3edd1f8f593a`。其中 15 个文件的大小与哈希已全部复核。提交范围仅为本报告；29 个已有无关未跟踪文件的内容哈希与 `GIT_BASELINE.json` 一致，外部证据不入 Git。

## 统一定义与证据粒度

两链应用相同的 FAIL 条件：

1. 启用航向的配置无有效航向输入；
2. 启用航向的配置航向尝试次数大于零、接受次数为零；
3. 完整 native NAV 中出现位移大于 10,000 m、速度大于 50 m/s、高度位移大于 1,000 m 或非有限数值行。

均使用严格大于号，等于界限本身不构成失败。位移采用 v3 冻结定义：WGS84 LLA 转 ECEF，以首个 native 输出位置建立固定 NED 坐标系，取三维位移范数；速度取 NAV 三维速度范数；高度位移取相对首个输出大地高的绝对差。F01 关闭航向，不适用条件 1、2。其余配置的航向计数来自 `RUN_MANIFEST`；在冻结标量路径、QA 关闭的前提下，有效航向进入更新函数便在拒绝门前累计 attempt，因此 attempt=0 表示没有进入更新的有效航向。

证据不足单列 `UNCLASSIFIABLE`，不并入 FAIL 或 COMPLETED。降采样 `NAV_10HZ.csv.gz` 不能证明完整 NAV 没有中间时刻越界或非有限行；旧 `COMPLETED` 标签和仅有 `finite=true` 的验证记录也不能证明三项界限通过。不得用这些材料补造完整 NAV 判定。

v3 的 NAV 已按保留政策释放时，直接使用 `V3_NATIVE_SUMMARY.json` 内与 NAV SHA-256 绑定的封存界限判定，不重建或重算已释放 NAV。v2.1 优先读取指定 `RETAINED_RUNS` 的完整 NAV 和清单；缺完整 NAV 且无合格封存界限的运行保留为不可分类。

F01 是显式冻结复用的特例：v2.1 的 5,880 条新运行记录不包含 588 个正式 F01。`03_F01_INVARIANCE/F01_INVARIANCE_GATE.json` 记录正式 F01 为字节一致复用；每个科学身份另外以冻结评估表的 `native_nav_sha256` 对接 v3 的 NAV 哈希。只有哈希相同且航向禁用时，才把同一 NAV 的封存界限判定绑定给两链。该步骤是已封存 NAV 判定的哈希复用，不是重新读取 v2.1 的完整 NAV；原 50 例抽样复用审计不能替代原计划的全部 588 对哈希自检。当前首个冲突已证明该绑定不能普遍成立。

两链以 `(dataset_id, case_id, method_id)` 为科学身份；实现按注册 run_id 索引后逐项断言这三个字段一致，避免把存储目录编号当科学身份。配置别名 F03/A02、F04/A01 不重复计数。核心 541 例对应 5,951 个唯一配置运行；另有 22 个额外自然序列运行与 495 个 A1/A2 运行，全范围共 6,468 对。自然序列和受控故障结果分域报告；故障注入保留半合成标签。

## 共同接纳集合与统计限制

对每个配置，先取两链均为统一 `COMPLETED` 的相同工况集合，再按指标取两链封存评估值均有限的交集。每个指标的两链统计共享同一成员清单与分母；报告 mean、median、p95、maximum 和最差 5% 均值。最差 5% 使用 `ceil(0.05*n)` 个最大值，分位数采用线性插值。61 例为原封存子集，不重新挑选。

评估器版本 `v3`（主）与 `v2`（并行）和实验协议 `v3`、`v2.1` 是不同维度，表中分别标注。这里只筛选、汇总已有评估结果，不调用评估器或读取 trace。分母为零时数值为空，状态说明不可计算；不可分类不赋零误差，不以旧标签填补。共同接纳后的分布是有条件描述，不能代表包括缺证和失败运行在内的全体鲁棒性。

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
