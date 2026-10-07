# BY2O 部分方向供给与实际位置约束的源内交集

本次只回答一个输入条件问题：`VECTOR_DIRECTION_SA_BY2O_01` 中的真实 partial 方向，是否恰好出现在位置失效或位置观测明显稀疏时段。结果是 **117/117 partial 都被约 5 Hz、厘米级工作标准差的有效且实际接受的位置更新夹住**。这支持“本窗有持续强位置约束”的条件描述；不能单凭该交集认定它就是水平位置收益很小的原因，也不能据此关闭可靠位置观测来制造收益。

## 冻结范围与字段语义

- 固定 BY2O 原窗 `[3186, 3563]`，保留全部 285 条有效 carrier：168 FULL、117 PARTIAL。分类由同版本 `FULL.csv` 与 `MOTION.csv` 的实际有效行作差，不由接受、误差或参考轨迹选样。
- 只读取原 `GNSS18.gnss`、上述两个 carrier provider，以及既有 LEGACY / VECTOR 的 `SOURCE_AWARE_WEIGHT_TRACE.csv` 中 `receiver_position` 行。未打开 NAV、参考或原始包，未运行 native / evaluator。
- GNSS18 的第 5–7 列为 NED 位置标准差，第 16 列为独立的 position validity；第 18 列 yaw validity 不代表 position validity。此文件没有独立的原接收机 `pAcc` 字段，以下数值只能称输入工作标准差，不能称实际定位误差或经过独立校准的精度。
- `gnss_file_loader.cpp:189–221` 独立解析 `pos_valid` 并赋给 `has_position`；`gi_engine.cpp:493–494` 按位置资格进入位置更新，`:1194–1228` 使用 `diag(std_NED²)` 及实际 SA scale。
- 当前 exact-event 路径在 `port_runtime.cpp:1569–1576` 按真实 GNSS 事件排入 IMU 区间，`gi_engine.cpp:817` 明确不按 `TIME_ALIGN_ERR` 对齐。`heading_source_policy.hpp:23` 的 `0.21 s` 是 **heading freshness**，不是位置容限。本文只报告位置事件前后间隔；不会把前一个位置观测保持成 carrier 时刻的另一次位置测量。

## 全分母结果

| 量 | 原 GNSS18 窗 | LEGACY 实际位置 | VECTOR 实际位置 |
|---|---:|---:|---:|
| 行 / 更新数 | 1886 | 1884 | 1884 |
| position valid / accepted | 1886 | 1884 | 1884 |
| 首时刻 | 3186.000000000 | 3186.200000048 | 3186.200000048 |
| 末时刻 | 3563.000000000 | 3562.799999952 | 3562.799999952 |
| 最大相邻间隔 / s | 0.20000004800022 | 0.20000004800022 | 0.20000004800022 |

源窗边界两行不在实际位置事件列表内；不能将 1886 与 1884 的差称为源失效或更新拒绝。两臂 1884 个实际接受的位置时刻完全一致。原窗 yaw valid 只有 1595 行，但 position valid 为 1886/1886，说明将航向失效当位置失效会得到错误的暴露定义。

| 固定供给 | 条数 | 前后位置都 valid 且两臂实际 accepted | 与位置事件精确同刻 | 邻接原 PVT yaw 无效 |
|---|---:|---:|---:|---:|
| 全部 | 285 | 285 | 0 | 12 |
| FULL | 168 | 168 | 0 | 12 |
| PARTIAL | 117 | 117 | 0 | 0 |

全部 285 条、包括 117 条 partial 的前一位置更新距 carrier 约 **198.000 ms**，后一位置更新在约 **2.000 ms** 后：partial 的前龄范围 `[197.999954, 198.000192] ms`，后延范围 `[1.999855, 2.000094] ms`。这不是时间匹配后额外消费 PVT；它描述已有真实事件顺序。

位置标准差如下，N 与 E 的分布相同，单位 mm。前后观测均已保存在逐条表中，不仅保留摘要。

| 供给与邻接位置 | σN=σE 中位 / p95 / 范围 | σD 中位 / p95 / 范围 |
|---|---|---|
| FULL 前一位置，n=168 | 14 / 15 / 14–15 | 12.5 / 18 / 10–20 |
| FULL 后一位置，n=168 | 14 / 15 / 14–15 | 12.5 / 18 / 10–20 |
| PARTIAL 前一位置，n=117 | 14 / 15.2 / 14–17 | 11 / 16 / 10–17 |
| PARTIAL 后一位置，n=117 | 14 / 16 / 14–17 | 11 / 16 / 10–17 |

实际 SA 没有明显放松这些位置观测：全窗两臂 `R_scale` 中位均为 1，最大约 1.00373142；partial 邻接位置的最大值分别为 1.00312693 / 1.00312710。按实际 `sqrt(R_scale) × std` 计算后，partial 邻接位置水平标准差的中位仍为 14 mm、最大仍为 17 mm。此处不是以 log accepted 代替有效噪声审查。

## 自然最长位置间隔

本窗没有 position-invalid 行，也没有漏掉一个正常位置周期的输入或实际接受间隔。1885 个源有效位置间隔都在 `[0.19999981000001, 0.20000004800022] s`，是正常 5 Hz 及时间浮点量化。

严格按保存 double 的最大值，有 754 个并列“最长”间隔；其中包含 117 条 valid carrier、**54 条 partial**。其余 partial 同样处在正常约 200 ms 间隔内。因此不能声称“最长位置间隔中没有 partial”，也不能把这 54 条描述为 position-outage 下的 partial。当前数据没有自然长位置缺口与 partial 的交集可供这一机制比较。

## 对下一科学动作的约束

本读数说明当前 BY2O pilot 发生在持续、厘米级工作位置约束下，不具备“位置自然变弱 / 中断且仍有真实 partial”的输入对照。它与小水平位置差相容，但未隔离位置约束的因果作用；同源 GNSS 相关性、导航交叉协方差与事件后的约束竞争也未由本读数识别。已有方向向量 LSIM 修正的坐标等变意义不因此改变，航向改善能否形成稳定位置净收益仍需独立证据。

本次不据此追加故障试验、不关闭 PVT、不调位置噪声，也不把 NMB 无 carrier 的长缺口改称 partial 恢复机会。本交集不单独证明弱位置期的方向导航作用。若下一研究问题是自然位置中断，需要另有真实供给与自然位置条件；若明确设计受控的定位产品中断，则应独立冻结故障模型和同输入对照，并只作受控机制结论，不能称自然退化证据。本次没有设计或执行该实验，也未扩大到其他窗口。

## 可复现产物

- 脚本：`scripts/paper_rebuild/unified_legged_heading_20261007/carrier_position_source_intersection.py`，SHA256 `8d6d5e334226bf5b0d9db4ab0db1a5cf7d3b6ae66e881aae078cff8bb510fab3`。
- 完整结果：`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/BY2O_CARRIER_POSITION_INTERSECTION_02/`。
- `CARRIER_POSITION_INTERSECTION.csv`：全部 285 条的分类、源前后位置 validity / σ、实际前后接受事件 / R scale / 有效 σ，保留全部分母。
- `SOURCE_POSITION_INTERVALS.csv`：全部 1885 个源间隔及每段 carrier / partial 计数。
- `SUMMARY.json`：摘要、精确输入路径与 SHA256；`OUTPUT_SEAL.json`：上述 3 个文件的内容锁。
- `_01` 保留首次 JSON 序列化 `numpy.int64` 失败说明及未封存 CSV；仅将计数转成 Python int 后完整保存到 `_02`，无输入、筛选、模型或科学计算变化。旧已封存 LSIM / 方向 / native 结果未改。

```bash
python3 scripts/paper_rebuild/unified_legged_heading_20261007/carrier_position_source_intersection.py --out /path/to/new-output-directory
```
