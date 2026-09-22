# V3-01-R 收尾报告（第二次续作）

第二次续作状态：`DONE_MATRIX_AGGREGATE_FIGURES_MACHINE_QA`，实际目视 QA 同时通过。
交接包按用户决定省略；证据以 G: 阶段目录 + 记录哈希为准。
最终只读验收：`PASS_V3R_FINAL_DELIVERY_PACKAGE_SKIPPED_BY_USER`。
DONE 时间：`2026-09-22T08:22:35.752561+00:00`，即北京时间 `2026-09-22 16:22:35.752561`。
十组图、69 项机器检查、30 个导出哈希以及 10/10 实际目视复核均通过。
起点提交 `76153ae374a100ee70f5b8b6bb2a9d03f7f7bc72` 已 push。
绘图/验证器修复提交为 `6b8d7aa5ed145fe9f2eb68811dcbc5f4ee1fa92c`，
标题 `fix(v3-r): failure-panel annotation and validator bool coercion`；
六个代码/测试路径通过只读复核，50 项针对性及相关合成回归通过。

本轮只调用出图入口，不调用 reports、聚合、解算或评估。59 个 CSV、62 个
清单绑定文件及三个原清单的出图前后哈希完全相同。原 MFIG05 视觉硬停、上一轮报告、
43 个旧图件文件、旧视觉回执及操作状态均已保留在
`00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/PREVIOUS/` 或
`PREVIOUS_REVIEW_DOCS/`；原 `AGGREGATE_RECOVERY/*HARD_STOP.json` 不改写。

上一轮于 2026-09-21 停在 MFIG05 四个空白面板及缺失方法图例，且验证器另有
NumPy 布尔类型误拒。新的失败注释包含原类别、方法和 run_id，保留坐标轴；
整图图例由固定方法句柄生成。相同注释规则覆盖单工况和序列图，群体图保留
原有限样本分母、失败计数和缺失标记，不把失败赋值为零。

路径别名：`<V3_ROOT> = <CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3`。
本报告的全部新运行证据来自该目录的既有封存产物；冻结比较表仅通过登记的
`V3_REPORT_SOURCE_INDEX.json` 精确路径与 SHA256 引用。

## 1. 冻结身份与恢复范围

| 身份 | 完整提交 SHA |
| --- | --- |
| 科学冻结 | `7d43b9af26120ed5dde21f53e515386361072ba6` |
| 原 V3-01-R 存储续接冻结 | `1643b9047777ffb8c474321cf8f22e1f66284810` |
| 汇总层修复 | `76153ae374a100ee70f5b8b6bb2a9d03f7f7bc72` |
| 第二次续作绘图/验证器修复 | `6b8d7aa5ed145fe9f2eb68811dcbc5f4ee1fa92c` |
| 明确省略交接包的规则与只读验收器 | `65beb49e2db5e2a6cfb4e44117f25968a22e43ac` |

修复提交标题：`fix(v3-r): aggregation reads retained artifacts only`。
本次恢复没有重新执行任何 native 或 evaluator，没有重做 provider，没有改变
C++、评估器、参数、案例、种子或科学冻结。恢复 admission 与最终执行账本均记录
新增 native 调用 0、新增 evaluator 调用 0；自动 native 重试为 0。

原硬停、原 STATE、原进度与日志保持独立留存；恢复目录中的
`ORIGINAL_STATE.json` 保存原 `phase=MATRIX`、`status=HARD_STOP` 字节。
上一轮操作用 `00_CONTROL/STATE.json` 先进入 `AGGREGATE / ACTIVE`，随后记录新的
`HARD_STOP` 和 `visual_review_status=FAIL_MFIG05`；原矩阵控制器的历史状态没有改写。

## 2. 硬停诊断：源码文件名误触守卫

原控制器在 `2026-09-20T15:38:53Z` 报错：
`V3 trace/bag/fpl only in registered evaluator child`。
最后一批归档完成时间为 `2026-09-20T15:30:14+00:00`，硬停晚于它 519 秒；
279/279 批归档均已完成，`all_started_workers_drained=true`。
这次异常发生于矩阵末尾的源码 pin 校验循环，汇总调用尚未真正开始。

被拒绝的调用来自 `tmux v3` Python 控制器父进程。启动会话快照给出的 PID 为
14277；原硬停 JSON 本身没有记录 PID。调用栈与源码 pin 清单共同定位到：

```text
<CODE_ROOT>/src/legsa_gins/datasets/by2/trace_reference_adapter.py

scripts/paper_rebuild/v3_resume_storage.py:11 main
  → protocol_v3/resume_storage.py:1612 ctx.matrix
  → protocol_v3/resume_storage.py:1448 runtime.verify_pin source loop
  → protocol_v3/runtime.py:35 frozen._pinned
  → hext/t5a_runtime.py:68 sha256_file
  → manifest.py:92 source.open rb
  → pathlib.py:1119 open
  → protocol_v3/controller.py:158 guard PermissionError
```

该对象是源码模块，SHA256 为
`2c4356af0e9948580c84fc3da7ce7353e1c3f6a838dc8ad72839625e721fb935`，
位于 576 个冻结源码 pin 的第 151 项。576 个 pin 均一致。
守卫把文件名中的 `trace_` 当成原始参考轨迹标志，在 Python audit `open`
事件中、实际文件打开之前抛出异常；该被拒调用没有打开 raw trace、bag 或 fpl。

证据边界：原守卫日志没有直接记录被拒绝的路径；路径由 traceback 指向的
源码循环及其中唯一命中禁用 basename 的 pin 确定，属于有明确依据的调用路径重建。
不能将它表述为原日志已经逐字记录该路径。

## 3. 全量访问审计与保留限制

`00_CONTROL/AGGREGATE_RECOVERY/OPENAT_AUDIT_SUMMARY.json` 的结论为 `PASS`。

| 审计对象 | 终端/进程数量 | 原始 strace 本次重新解析 | 原始 strace 已释放、以封存记录与释放回执绑定 | trace 打开 |
| --- | ---: | ---: | ---: | --- |
| Native | 6,468 | 512 | 5,956 | 总数 0 |
| 实际 evaluator 子进程 | 12,370 | 1,024 | 11,346 | 每个恰为 1，总数 12,370 |
| 未启动的 evaluator 终端槽 | 566 | 不适用 | 不适用 | 未调用，不能称为已审计子进程 |

计数守恒：`12,370 + 566 = 12,936`。566 个未调用槽对应 283 个 native
算法失败各自的 v3/v2 评估槽。6,468 个 native 中，6,185 个为 `COMPLETED`，
193 个为 `ALGORITHM_FAILURE_DIVERGED`，90 个为
`ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT`。评估器自身失败计数为 0。

已释放的 5,956 份 native 与 11,346 份 evaluator 原始 strace 不能再次逐行解析。
这些条目依赖原封存访问审计、原 strace 哈希和精确归档释放回执的绑定；
本次没有重建缺失日志，也没有把“哈希绑定审计”表述成“原始 strace 重新解析”。
完整逐项证据见 `OPENAT_AUDIT_ROWS.csv` 与 `OPENAT_SOURCE_PINS.json`。

恢复 admission 的访问守卫记录 raw source reads 0、trace data reads 0、
process launches 0；唯一允许的源码模块打开受精确源码 pin 约束。
参考轨迹和 BY2O 分段所需数据只从已保留的 `error_series`、
`MATCHED_TRAJECTORY`、`EVALUATION_RESULT` 读取，不增加评估调用。

## 4. F04 三序列与 T5a-R 一致性

Admission 的 `f04_t5ar_identity.status=PASS`，同时检查完整 CSV 数值和
六位小数展示值，`t5ar_full_precision_identical=true`。

| 序列 | F04 yaw RMSE，完整数值（deg） | 六位小数锚点（deg） |
| --- | ---: | ---: |
| BY2 | 1.8862718548526467 | 1.886272 |
| BY2H | 1.93377013508875 | 1.933770 |
| BY2O | 2.433814932823714 | 2.433815 |

比较源为 `<CLEAN_ROOT>/stages/CLEAN7_T5A_HEADING_SENSITIVITY/T5A_R/05_AGGREGATE/SENSITIVITY_TABLE_V3.csv`，
SHA256：`fd8ed33b803845a3a3b1c72ac5cf57c59e2a90654509da069f81aa5961328ee6`。
Pin 授权来自 `configs/paper_rebuild/hext/T5BC_FROZEN_SOURCE_INDEX.yaml` 的
`t5a_r.tables.SENSITIVITY_TABLE_V3.csv`。
最终 52 行主表已再次通过同一 F04 门禁：三行均为 COMPLETED，完整数值与 T5a-R 精确相同。

## 5. 失败计数：故障族 × 配置

以下数字按 541 个核心案例 × 11 个唯一配置，即 5,951 个 case/configuration
身份比较。当前 native 终端来自 `<V3_ROOT>/FINAL_RUN_RECORDS.json` 的 CORE
条目；v2.1 对照来自报告源索引中 `frozen_core.v3` 的精确 SHA256 固定表。
F03/A02 与 F04/A01 是配置别名，不重复计数。额外序列与 A1/A2 没有新增失败。

每个单元格为 **v3 / v2.1 的失败数量**；这里的 v3 指协议版本，主评估器同名 v3
另由源索引标明。v2.1 原始分类以 `solver_terminal_status` 为准；冻结导出器的
缺省 `failure_classification=NONE` 不覆盖其已记录的失败终端。

| family | F01 | F02 | F03 | F04 | A03 | A04 | A05 | A06 | A07 | A08 | A09 | 合计 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| dual_yaw | 0/0 | 0/0 | 0/9 | 0/9 | 0/9 | 0/9 | 0/9 | 0/9 | 0/9 | 0/9 | 0/9 | 0/81 |
| gnss_outage | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| gnss_sampling | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| go2_prior_metadata | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| multi_source_mixed | 10/0 | 26/0 | 19/4 | 13/2 | 14/3 | 18/3 | 13/4 | 13/3 | 13/4 | 19/2 | 14/2 | 172/27 |
| position_std_status | 9/0 | 9/0 | 9/0 | 9/0 | 9/1 | 9/1 | 9/0 | 9/3 | 9/0 | 9/0 | 9/0 | 99/5 |
| position_value | 1/0 | 8/0 | 1/9 | 0/5 | 0/6 | 1/6 | 0/6 | 0/6 | 0/10 | 1/7 | 0/9 | 12/64 |
| velocity_raw_doppler | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| 合计 | 20/0 | 43/0 | 29/22 | 22/16 | 23/19 | 28/19 | 22/19 | 22/21 | 22/23 | 29/18 | 23/20 | 283/177 |

| 故障族 | v3 divergence | v3 no-valid-heading | v2.1 all-yaw-rejected |
| --- | ---: | ---: | ---: |
| dual_yaw | 0 | 0 | 81 |
| multi_source_mixed | 82 | 90 | 27 |
| position_std_status | 99 | 0 | 5 |
| position_value | 12 | 0 | 64 |
| 合计 | 193 | 90 | 177 |

F02 单列：v3 为 43/541 失败，其中 divergence 34、no-valid-heading 9，
完成 498；v2.1 为 0/541 失败。两条链的失败分类规则不同——v2.1 仅有“航向全被拒”一类，v3 为发散与无有效航向两类——283 与 177 不可直接比较，统一规则下的对照另行给出。

下表只记录原始标签的转移，不构成统一规则下的性能对照。dual_yaw 族只作为 v3 结果报告：原航向故障按原 1 s 时间单元映射到 5 Hz 表，std 故障只落在原行；保留的 v2.1 数字用于原始分类溯源，不写成改进。

| v2.1 → v3 的核心身份转移 | 数量 |
| --- | ---: |
| 完成 → 失败 | 278 |
| 失败 → 完成 | 172 |
| 失败 → 失败 | 5 |
| 完成 → 完成 | 5,496 |
| 合计 | 5,951 |

### F01：20 个同 NAV、不同分类身份

`07D_CLASSIFICATION_PROVENANCE/MANIFEST.json` 为
`PASS_RETAINED_METADATA_CLASSIFICATION_PROVENANCE`，伴随 CSV 有 20 行。
这 20 个当前 F01 失败均与对应的 v2.1 完成记录具有完全相同的 NAV SHA256。
保留元数据同时显示 exit code 0、全部数值行有限、dual-yaw attempts 0，
首个界限违反项为 `speed_mps`，登记速度界限为 50 m/s。

因此，这 20 个计数差异属于相同 NAV 输出上的分类/准入差异，不能称为新增的
F01 轨迹恶化。审计没有读取 NAV payload，没有改变任何原终端标签；本报告也不
把其改写为完成。源 CSV 为 `07D_CLASSIFICATION_PROVENANCE/F01_IDENTICAL_NAV_CLASSIFICATION.csv`，
SHA256：`c309991a31a07afbcdd54a2934f06513e9d557b2de42384bededd66d2219026c`。

## 6. 汇总与交接项目的最终边界

主表目标为 52 行：替换 15 个内部方法行，LC01、EXT05C 等 37 个外部方法行保持
原始 CSV 字段 token 和 availability 分类。消融需同时保留五配置对照梯和三序列
全部 11 配置的 33 行表。541 汇总/分布、61 例比较、BY2O 主段/次段/并集/全窗/
段外、A1/A2、T5bc-R 的 R5σ/R5W/B3 独立敏感性块均属于本次已授权汇总范围。
实际 aggregate manifest 绑定 53 个文件，appendix manifest 绑定 8 个文件。核心表 5,951 行、核心标量汇总 77 行、有限样本分布 39,676 行；61 例表及其对照各 671 行。BY2O 表共 150 行，full、primary、secondary、inside_union、outside 各 30 行。A1/A2 共 495 行（297/198）。每版敏感性三序列表 15 行（B3 9、R5W 3、R5SIGMA 3），61 例表 183 行（各 61）；尾部汇总跨两版共 6 行。

主汇总清单 SHA256：`11b6779460ef4ade860b034cba88abe5f89fa6bb7eb125ee4b7d7bccb9f0464a`。分类/全消融附表清单 SHA256：`a2b83104c14b497eda6af3ef93bf092606bc12e95b4bb0803136f16621fc63c6`。

独立实际表格复核通过，回执为 `09_HANDOFF/TABLE_REVIEW.json`，SHA256
`f25d6f830e7743856c60d71d3c6293342b5e84d218b4e41c0005ad650143fc0d`。
检查覆盖全部 61 个汇总/附表文件的哈希、37 个外部行的字段同一性、全部失败
单元格与来源的一致性、BY2O 样本数守恒以及敏感性原字段同一性。
上一轮代码验证包括恢复 21 项、包装 17 项、既有汇总回归 19 项，共 57 项通过；本轮六路径的相关回归为 50 项通过。
测试样本不是科学运行；该通过结论不替代实际图件和归档完整性门禁。

| 后续门禁 | 第二次续作当前状态 |
| --- | --- |
| 最终主表、消融、541/61、BY2O、A1/A2、敏感性与比较附表闭合 | `PASS_AGGREGATE_AND_APPENDIX_MANIFESTS` |
| 十组图与机器 QA | 10 组、69 项机器检查、30 个导出哈希全部 PASS；NumPy 布尔回归通过 |
| 全十组实际视觉复核 | `PASS`：10/10；MFIG05 由 supervisor 与只读 reviewer 双重复核 |
| `DONE` 与 `SUMMARY.txt` | 已写 DONE 与 SUMMARY；UTC 2026-09-22 08:22:35.752561 |
| 交接包 | `SKIPPED_BY_USER`；明确省略，不作为本轮完成条件 |
| 结果提交与 push | 最终提交号、分支及远端核验记录于 `09_HANDOFF/FINAL_DELIVERY.json` |

手稿替换底稿见 [V3_01R_MANUSCRIPT_REPLACEMENT.md](V3_01R_MANUSCRIPT_REPLACEMENT.md)。
方法文本和数值表已准备；本轮十组图及实际视觉门禁已经通过。
交接包按用户决定省略；证据以 G: 阶段目录 + 记录哈希为准。
本轮缺少 ZIP 不触发硬停；最终只读验收绑定明确省略决定及既有证据哈希。

## 7. 来源身份与科学解释边界

| 已核验文件（相对 `<V3_ROOT>`，另注者除外） | SHA256 |
| --- | --- |
| `00_CONTROL/AGGREGATE_RECOVERY/ORIGINAL_HARD_STOP.json` | `da38632164b5da069a279a99e4e8f1c2601385d6146b2f6cee25f5c558ded157` |
| `00_CONTROL/AGGREGATE_RECOVERY/HARD_STOP_DIAGNOSIS.json` | `c46ecac0550b48effc6126a67839abd3f289ea588e3861a7c92d115008c8d90e` |
| `00_CONTROL/AGGREGATE_RECOVERY/OPENAT_AUDIT_SUMMARY.json` | `a4b78ec5bf8d1564e51d74eda7841fb73a5535aea09f1acf8e5a3fdfc2244560` |
| `00_CONTROL/AGGREGATE_RECOVERY/OPENAT_AUDIT_ROWS.csv` | `95c0e3c2b34f8d364eb720d509954520701ad1043df1838f5452fbe541f67199` |
| `00_CONTROL/AGGREGATE_RECOVERY/OPENAT_SOURCE_PINS.json` | `27114282f8b3fa1306936b9401657c867229e4735741a5edd94c27096796b3d2` |
| `00_CONTROL/AGGREGATE_RECOVERY/ADMISSION.json` | `4cff485e9df34710cd8adacac5f38c579758628d28ebd4cb1cd3592c35d5976a` |
| `FINAL_RUN_RECORDS.json` | `c8fd55b3895643a48a06c084b1b3d438ba7a12f5802703510f4b9887fd48ab92` |
| `FINAL_EVALUATION_RECORDS.json` | `4c0bbaec5b4aa14f22ca45ff966cc1e9d03824a2afef08133b0e42bfec81e319` |
| `07D_CLASSIFICATION_PROVENANCE/MANIFEST.json` | `000a6797920e9b7e1faec876a1badeba24242d9a762bf5e13baa08d5bf38e7ff` |
| `<CODE_ROOT>/configs/paper_rebuild/v3/V3_REPORT_SOURCE_INDEX.json` | `43dbdade50172e191b394dfc5b64815ddc0c6c5b7f73cbda41762d32acbc4704` |
| 报告源索引 `frozen_core.v3` | `45054701213cedb2057523c6f4706dfebd170ccea824bc882e8d281653f892d5` |

参考定义为 the fused navigation output of the commercial receiver, which the estimator under test does not read。接收机为 Fixposition Vision-RTK 2；该输出不能建立独立 ground truth，图中的 `Truth` 只标识评估参考角色。Trace 始终是 evaluation-only。
本次汇总不允许用参考选择符号、时移、provider、参数或删去不利 epoch。

自然三序列与控制故障结果分开呈现：`synthetic_data_used=false`；包含登记控制故障
的集合为 `semisynthetic_data_used=true`，不能冒充独立采集的真实序列。
R5 的双接收机精确历元 RTK-fixed 规则、物理天线次序/坐标变换及 wrap-safe
残差保持冻结。Go2 数据只作弱先验或诊断，接收机 IMU 不能替代 Go2 body IMU。
Source-Aware 与 Go2 机制仍限于有界、保护性或辅助性解释；没有完整九因子 FGO 主张。

本次是明确授权的 protocol-v3 航向输入比较。v2.1 的冻结结果与图保持不变。
T5bc-R 的 R5σ/R5W/B3 是原封存敏感性引用，不是本次重跑实验；B3 无航向 epoch
的结果维持 `NOT_APPLICABLE`，不作为失败率或误差分布中的零值。
汇总、图 QA 或交接包完整性均不能消除失败分类可比性、商用接收机评估参考与先验来源限制。

## 7A. 第二次续作验收证据

本轮 aggregate/reports/native/evaluator 调用均为 0；绘图与收尾访问守卫的
process_launches、raw_source_reads、trace_data_reads 均为 0。
全部 59 CSV、62 清单绑定文件未重算、未改写；原分类标签和科学冻结未变。
仅本轮绘图重新生成：10 PNG + 10 PDF + 10 SVG。MFIG05 的 D27/D60 失败
面板保留原发散类别与六个 run_id；没有将失败输出代入曲线或记为零误差。

| 证据（相对 `<V3_ROOT>`） | SHA256 |
| --- | --- |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/BASELINE.json` | `7830a1a596077558d0f2289c066dbd81b1f53e6c25adc8ec0c8833ee055a503b` |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/MACHINE_QA_AND_TABLE_IDENTITY.json` | `6a0d2914df1ac20ef48b1fcfe2a35e7a10bcae53f56b73e18ba5f5e53918114f` |
| `09_HANDOFF/VISUAL_REVIEW.json` | `a9504881ba0984d4e8c6a2298da5e90e951f5bf9d4a7863ec0af2b08fc64dbca` |
| `08_FIGURES/RENDER_MANIFEST.json` | `2df79f21f9094f6e49955c1ffd3d18f950963588fb4d09a140b2c6aa82e3faf1` |
| `00_CONTROL/DONE.json` | `2020dce5fba21e26ad7fd52fe3de15f5066995dbc3a96370937ae87b472507b8` |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/BEFORE_PACKAGE_OMISSION/00_CONTROL/SUMMARY.txt`（图 QA 收尾时版本） | `ec9735a69076ca0069618e1709a93465eafa73891dadeaf7cf75ca6c940be0c2` |
| `09_HANDOFF/MANUSCRIPT_REVIEW.json` | `bc67cb34b6391cc4f5509f89db8c5a0f0d1d5113ecc83195a2a68cb80689ad0b` |
| `09_HANDOFF/FIGURE_REPAIR_SOURCE/SOURCE_MANIFEST.json` | `036977615de6ef1664ee960b4aabc8fb1dfa6aab558264c1786197af0dd7dd6b` |

表不变回执逐项列出所有表及清单的前后同一 SHA256；主表 v3 摘要仍为
`cd734338cf89518679d78179f410a79ecad3060535d3b80e43a62545cee9b21c`，
完整三序列消融 v3 仍为 `44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1`。

## 7B. 用户省略交接包与精确清理

交接包按用户决定省略；证据以 G: 阶段目录 + 记录哈希为准。
包状态为 `SKIPPED_BY_USER`，`zip_required=false`。没有完整包验收结论，
也不以缺少 ZIP 触发硬停。原 DONE 与 COMPLETION 字节及 DONE 时间不变；
STATE、SUMMARY 与 PROGRESS 已更新省略决定，更新前版本保存在
`00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/BEFORE_PACKAGE_OMISSION/`。

打包进程 PID `6166` 于 `2026-09-22T13:24:30.161161+00:00` 收到 SIGTERM，
于 `2026-09-22T13:24:30.261484+00:00` 确认退出（北京时间 21:24:30）。
退出码 143 对应这次明确授权的终止，不是科学或图 QA 失败。
精确清理清单仅包含 `<HANDOFF_ROOT>/protocol_v3r_complete_handoff.zip`
与同 stem 的空 `BUILD.log`，共 2 文件、17,645,950,746 字节。
清单记录删除前文件身份与哈希，逐项删除后留存检查点；
`2026-09-22T13:28:11.011205+00:00` 确认全部目标不存在且其余交接目录条目未变。
同名 sidecar 与包装回执未生成。G: 的已检查 scratch 候选位置不存在；
注册 WSL scratch 无本包匹配文件，绘图缓存的 tmp 目录为空，历史测试目录不删。

`df /mnt/g` 的 1 KiB 块记录如下（文件系统总量 976,743,424）：

| 时点 | Used | Available | Use% |
| --- | ---: | ---: | ---: |
| 删除前 | 904,367,616 | 72,375,808 | 93% |
| 删除后 | 887,136,000 | 89,607,424 | 91% |

| 回执（相对 `<V3_ROOT>`） | SHA256 |
| --- | --- |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/PACKAGE_CANCELLATION.json` | `9f83f3913b4f19c0714fea36c8fcd2003cc7681432fd14c513b94126c82960b4` |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/PACKAGE_CLEANUP_MANIFEST.json` | `8394b5f330b6077f4dd134e0b0e81a7d9d70b816346151a792ccc9fed30eb69d` |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/PACKAGE_CLEANUP_RECEIPT.json` | `ba0d068f725f4ef6510d0dc79843cedb9f8cbf057853bc1254881f715aef6674` |
| `09_HANDOFF/PACKAGE_DISPOSITION.json` | `1e698d6423d6f993ede805ed32930363442861bdab9a7be5dc708edcea27e3d5` |
| `00_CONTROL/SUMMARY.txt`（当前版本） | `a42259d72f790fa0cd959fa60e18e024c61c08a88497a294713453205d576bbe` |
| `09_HANDOFF/FINAL_ACCEPTANCE.json` | `50b1f09dcaf0f86e3c3148871f7cbce66d4ad416fbd71ed7bae78019df6a5bdd` |

新增只读验收器 `scripts/paper_rebuild/v3r_delivery_verify.py` 只接受明确用户省略回执，
核验 8 项回执绑定、65 项文件身份（59 CSV）、10 图、69 条既有机器检查和 30 个导出，
不读取 ZIP、不调用打包器、不重跑图 QA 或科学计算。9 项针对性回归通过。
AGENTS.md 已追加：只在明确要求时制作交接包；仅含记录、哈希、回执、聚合表、图、文档；
逐例产物一律不装；目标不超过 2 GB（2,000,000,000 字节）。
规则与验收器提交为 `65beb49e2db5e2a6cfb4e44117f25968a22e43ac`。
实际只读验收于 `2026-09-22T13:31:40.021901+00:00` 通过：
`PASS_V3R_FINAL_DELIVERY_PACKAGE_SKIPPED_BY_USER`；全部 65 项身份、59 CSV、
10 图、69 条既有检查及 30 导出一致，ZIP 读取、图 QA 重跑及科学调用均为 0。

## 8. 主表：全部 52 行

以下为主评估器 v3 的展示列，数值展示至六位小数；CSV 保留完整精度、所有字段与原外部行 token。几何审计失败的外部结果继续显式标记，不升级为无条件可用。

来源：`<V3_ROOT>/07_AGGREGATE/MAIN_TABLE_V3.csv`，SHA256 `cd734338cf89518679d78179f410a79ecad3060535d3b80e43a62545cee9b21c`。

| 序列 | 方法 | 配置 | 起点 | 水平 RMSE (m) | Up RMSE (m) | yaw RMSE (deg) | 评估状态 | 几何审计 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | F02 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.101922 | 0.048068 | 2.231952 | COMPLETED | NOT_APPLICABLE |
| BY2 | F03 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.099920 | 0.047874 | 1.915591 | COMPLETED | NOT_APPLICABLE |
| BY2 | F04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.097906 | 0.048996 | 1.886272 | COMPLETED | NOT_APPLICABLE |
| BY2 | A04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.096920 | 0.050019 | 1.886001 | COMPLETED | NOT_APPLICABLE |
| BY2H | A04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.070046 | 0.045895 | 1.933907 | COMPLETED | NOT_APPLICABLE |
| BY2H | F02 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.071501 | 0.045410 | 2.283241 | COMPLETED | NOT_APPLICABLE |
| BY2H | F03 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.068667 | 0.044901 | 1.940801 | COMPLETED | NOT_APPLICABLE |
| BY2H | F04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.068362 | 0.045352 | 1.933770 | COMPLETED | NOT_APPLICABLE |
| BY2O | A04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.053942 | 0.044177 | 2.429173 | COMPLETED | NOT_APPLICABLE |
| BY2O | F02 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.054725 | 0.046174 | 2.309491 | COMPLETED | NOT_APPLICABLE |
| BY2O | F03 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.054709 | 0.043712 | 2.432184 | COMPLETED | NOT_APPLICABLE |
| BY2O | F04 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.054543 | 0.045859 | 2.433815 | COMPLETED | NOT_APPLICABLE |
| BY2 | F01 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.091771 | 0.047881 | 8.089647 | COMPLETED | NOT_APPLICABLE |
| BY2H | F01 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.062926 | 0.044904 | 7.137488 | COMPLETED | NOT_APPLICABLE |
| BY2O | F01 | PROTOCOL_V3 | FROZEN_V21_RUNTIME_CONFIG | 0.062842 | 0.043746 | 5.739038 | COMPLETED | NOT_APPLICABLE |
| BY2 | LC01 | LIT | FILE_START | 0.097548 | 0.050664 | 2.994827 | COMPLETED | FROZEN_PRIOR_AUDIT |
| BY2 | EXT05C | LIT | FILE_START | 0.087751 | 0.056470 | 12.048642 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2 | LC02_GINAV | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT01 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT02 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT03 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT04 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | Hartley | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | EXT05B | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | LC02_GINAV | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT01 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT02 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT03 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT04 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | Hartley | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2H | EXT05B | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | LC02_GINAV | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT01 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT02 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT03 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT04 | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | Hartley | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2O | EXT05B | NOT_APPLICABLE | NOT_EXECUTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_APPLICABLE |
| BY2 | LC01-S | S | FILE_START | 0.103525 | 0.045250 | 1.539239 | COMPLETED | PASS |
| BY2 | EXT05C-S | S | FILE_START | 0.114228 | 0.046998 | 9.722098 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2H | LC01 | LIT | FILE_START | 0.097453 | 0.055628 | 2.173936 | AVAILABLE_GEOMETRIC_AUDIT_FAIL | FAIL |
| BY2H | LC01 | LIT | CONTRACT_START | 0.074606 | 0.044804 | 2.208612 | AVAILABLE_GEOMETRIC_AUDIT_FAIL | FAIL |
| BY2H | EXT05C | LIT | FILE_START | 0.197284 | 0.078735 | 55.609934 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2H | EXT05C | LIT | CONTRACT_START | 0.069190 | 0.050646 | 20.108223 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2H | LC01-S | S | FILE_START | 0.106709 | 0.040726 | 1.794054 | AVAILABLE_GEOMETRIC_AUDIT_FAIL | FAIL |
| BY2H | LC01-S | S | CONTRACT_START | 0.083733 | 0.040364 | 1.943003 | AVAILABLE_GEOMETRIC_AUDIT_FAIL | FAIL |
| BY2H | EXT05C-S | S | FILE_START | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_RUN_ALGORITHM_FAILURE | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2H | EXT05C-S | S | CONTRACT_START | 0.085419 | 0.043321 | 8.114756 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2O | LC01 | LIT | FILE_START | 0.054304 | 0.044752 | 2.453697 | COMPLETED | PASS |
| BY2O | EXT05C | LIT | FILE_START | 0.051954 | 0.048903 | 5.845502 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2O | LC01-S | S | FILE_START | 0.060462 | 0.039930 | 4.015602 | COMPLETED | PASS |
| BY2O | EXT05C-S | S | FILE_START | 0.075080 | 0.039767 | 8.266805 | COMPLETED | NOT_APPLICABLE_SINGLE_RECEIVER |

## 9. 消融表：三序列全部 33 行

F03/A02、F04/A01 为配置别名，未增加独立解算。五配置对照梯另保留在 `07_AGGREGATE/ABLATION_TABLE_V3.csv`。

来源：`<V3_ROOT>/07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv`，SHA256 `44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1`。

| 序列 | 配置 | 水平 RMSE (m) | Up RMSE (m) | yaw RMSE (deg) | 评估状态 |
| --- | --- | --- | --- | --- | --- |
| BY2 | F01 | 0.091771 | 0.047881 | 8.089647 | COMPLETED |
| BY2 | F02 | 0.101922 | 0.048068 | 2.231952 | COMPLETED |
| BY2 | F03 | 0.099920 | 0.047874 | 1.915591 | COMPLETED |
| BY2 | A04 | 0.096920 | 0.050019 | 1.886001 | COMPLETED |
| BY2 | F04 | 0.097906 | 0.048996 | 1.886272 | COMPLETED |
| BY2 | A03 | 0.098050 | 0.048416 | 1.885676 | COMPLETED |
| BY2 | A05 | 0.098639 | 0.048478 | 1.913840 | COMPLETED |
| BY2 | A06 | 0.098997 | 0.048992 | 1.886870 | COMPLETED |
| BY2 | A07 | 0.099859 | 0.048474 | 1.914423 | COMPLETED |
| BY2 | A08 | 0.099760 | 0.049460 | 1.914867 | COMPLETED |
| BY2 | A09 | 0.099984 | 0.047858 | 1.913875 | COMPLETED |
| BY2H | F01 | 0.062926 | 0.044904 | 7.137488 | COMPLETED |
| BY2H | F02 | 0.071501 | 0.045410 | 2.283241 | COMPLETED |
| BY2H | F03 | 0.068667 | 0.044901 | 1.940801 | COMPLETED |
| BY2H | A04 | 0.070046 | 0.045895 | 1.933907 | COMPLETED |
| BY2H | F04 | 0.068362 | 0.045352 | 1.933770 | COMPLETED |
| BY2H | A03 | 0.068700 | 0.045364 | 1.932567 | COMPLETED |
| BY2H | A05 | 0.067847 | 0.044925 | 1.940927 | COMPLETED |
| BY2H | A06 | 0.068892 | 0.045355 | 1.934036 | COMPLETED |
| BY2H | A07 | 0.068334 | 0.044928 | 1.941106 | COMPLETED |
| BY2H | A08 | 0.068390 | 0.045419 | 1.941317 | COMPLETED |
| BY2H | A09 | 0.068666 | 0.044948 | 1.940210 | COMPLETED |
| BY2O | F01 | 0.062842 | 0.043746 | 5.739038 | COMPLETED |
| BY2O | F02 | 0.054725 | 0.046174 | 2.309491 | COMPLETED |
| BY2O | F03 | 0.054709 | 0.043712 | 2.432184 | COMPLETED |
| BY2O | A04 | 0.053942 | 0.044177 | 2.429173 | COMPLETED |
| BY2O | F04 | 0.054543 | 0.045859 | 2.433815 | COMPLETED |
| BY2O | A03 | 0.054465 | 0.045936 | 2.435462 | COMPLETED |
| BY2O | A05 | 0.054011 | 0.045365 | 2.434144 | COMPLETED |
| BY2O | A06 | 0.055421 | 0.045860 | 2.432539 | COMPLETED |
| BY2O | A07 | 0.054850 | 0.045369 | 2.433866 | COMPLETED |
| BY2O | A08 | 0.054777 | 0.043654 | 2.428660 | COMPLETED |
| BY2O | A09 | 0.054752 | 0.045437 | 2.435553 | COMPLETED |

## 10. 2026-09-21 历史记录：类型误拒与视觉硬停

以下仅记录上一轮终端；第二次续作结果见本报告开头与第 7A 节。

当时汇总进程退出码为 1。`00_CONTROL/AGGREGATE_RECOVERY/REPORT_HARD_STOP.json`
记录 `HARD_STOP_V3R_FIGURE_QA`，操作状态更新时刻为
`2026-09-21T04:48:08.036760+00:00`。其 SHA256 为
`18e50ed45b2ef5ea6127b9255e96c5dd4ca088c52eb98b2f1b703e48230898dc`。

只读诊断确认，冻结 PNG 检查的 `gray.std() > BLANK_STD_THRESHOLD` 返回
`numpy.bool_(True)`，而恢复层 `verify_render` 用 `is True` 进行身份判断。
原有 JSON writer 经 `.item()` 正确保存为 JSON `true`。全部 60 项落盘 QA、
十份单图清单与总清单的一致性、30 个 PNG/PDF/SVG 哈希以及十张 PNG 的
只读检查值均通过。因此，该异常本身是恢复验证器的类型接口错误，不是
这 60 项图质量条件实际失败。当时保留此错误，未修改恢复层代码；本轮已另行提交修复，原停记录仍保留。

当时随后完成全部十组实际栅格视觉检查：MFIG00–04、MFIG06、SFIG01、FIG02S、
FIG02S-b 共九组未发现实质问题；**MFIG05 失败**，并由主管再次实际查看确认：

- D27、D60 的 (a)–(d) 四个面板没有曲线，仅灰窗和默认 0–1 纵轴，图内未说明
  算法失败或不可用，不能将这些空白理解为零误差。
- (e)–(j) 含 F03/A04/F04 的曲线，但整张图没有方法图例，读者不能从图内确定颜色身份。
- 冻结 drawer 只把六个 `ALGORITHM_FAILURE_DIVERGED` 写入 manifest notes；
  图例仅取首个 D27 面板，该面板三条曲线均不存在，因此 legend handles 为空。
  caption 指向 manifest 的说明不能替代图内可识别的失败标记和方法图例。

这是独立于 NumPy 类型误拒的真实视觉 QA 失败。根据用户的明确硬停要求，
当时没有修复或重画 MFIG05，没有替换其数据，没有重跑解算、评估或汇总。
拟议的落盘 JSON 收尾入口已在创建文件或运行测试前取消，未留下新 finalizer。
当时没有写 DONE、制作最终包、创建结果提交或 push。

| 保留证据 | SHA256 |
| --- | --- |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/PREVIOUS/08_FIGURES/RENDER_MANIFEST.json` | `c57b7b7111e94e5958b1076cd9b8beca605baba9410a25aa6b0306dc4e9c395a` |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/PREVIOUS/08_FIGURES/MFIG05/FIGURE_MANIFEST.json` | `43cdc39376742d1d6216131e52b37406cf73f66d16e6a12494bb605e3962fe46` |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/PREVIOUS/09_HANDOFF/VISUAL_REVIEW.json` | `a89dae4bde5a7ba71925ae313af0eadb8bb72515bbba1691c78887986942ed38` |
| `00_CONTROL/AGGREGATE_RECOVERY/VISUAL_HARD_STOP.json` | `14a6510e186afd3578a5f0d0ac9e341c803b2ac44278f3dcdb127df52328ca17` |
| `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/PREVIOUS/00_CONTROL/SUMMARY.txt` | `9e90c181ed7ff9f8fbe28c0fad98a9e6675cd812b2eca1f34ea9032fe3565662` |

## 11. 2026-09-21 历史记录：源码补充已准备、当时未打包

拟议交接包的两个 Git 源码快照限于六个目录中的白名单文本文件，不是完整 Git
仓库备份。其范围外的 147 个 ADMISSION 登记维护模块已另存为
`09_HANDOFF/REGISTERED_SHARED_SOURCE.json`，附带原 alias 路径、源 SHA256、
字节数和 base64 字节；所有条目均与科学冻结和修复提交的 Git blob 及 ADMISSION
pin 一致，写后还原校验通过。此步骤没有读取 raw/provider/NAV 载荷。

补充 JSON SHA256：`66f8c2bb4761d75a6369d0e9284981acda22b7a049e16e689bd949b85a759218`；
伴随 manifest SHA256：`a186c96e43ef121e756514eef2b1576b340234eba82b8540688010b7caa86c82`。
上一轮只读全树打包范围扫描因真实视觉硬停终止，状态为 PARTIAL；不能将其描述为完整
排除清单或全树零泄漏检查通过。当时没有任何新 ZIP，这些补充文件本身不构成交接包完成。本轮打包按用户后续决定取消，处置记录见第 7B 节。
