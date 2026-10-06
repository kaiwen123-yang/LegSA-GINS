# Dense selected-observation frontend readout

完整驱动 COMPLETE 后在 Ubuntu 22.04 WSL 只读汇总。新增 CILS、模型重验收、导航、参考/trace 读取均为 0；全部 case 保留。

| 项目 | 旧 120 窗 / Python | 新 1191 窗 / native |
|---|---:|---:|
| 机会 / 实际搜索 | 120 / 120 | 1191 / 1191 |
| 机会间隔 s | 2.0 | 0.2 |
| 预选不可用 / 超时 | 0 / 0 | 0 / 0 |
| 全局证书 | 120 | 1191 |
| 初始合格候选 | 15 (12.50%) | 116 (9.74%) |
| 普通跟踪有效 / 总历元 | 62 / 1200 | 157 / 1200 |
| 串行有效 / 总历元 | 62 / 1200 | 157 / 1200 |
| 普通与串行 owner / release | 14 / 14 ; 14 / 14 | 55 / 55 ; 55 / 55 |
| 串行启动 / 忙丢弃 / 末尾待处理 | 120 / 0 / 0 | 1172 / 19 / 0 |
| CILS 中位 / P95 / 最大 s | 0.135904 / 0.498868 / 1.870632 | 0.034646 / 0.154479 / 0.727142 |
| CILS >0.2 / >1 / >2 s 个数 | 37 / 1 / 0 | 29 / 0 / 0 |

本轮冻结 `371bf0ae41c76f604772350dbbb40744824d8104`；对照冻结 `fc125a9a41527d8ac81a7a57802b5820404c0896`。
整数维数指搜索未知整数的数量，不是正号整数值的个数。新/旧分布分别为 {'6': 1191} / {'6': 120}。证书证明登记的新预选观测似然下的全局候选搜索完成，不能证明物理整数正确。

## 保留的初始结果

| 状态 | 旧 120 | 新 1191 |
|---|---:|---:|
| EXPERIMENTAL_FIXED_CANDIDATE | 15 | 116 |
| REJECTED_LENGTH | 13 | 95 |
| REJECTED_PHASE_FAULT_DIAGNOSTIC | 16 | 215 |
| REJECTED_RESIDUAL | 12 | 118 |
| REJECTED_RESIDUAL_AND_LENGTH | 5 | 62 |
| UNRESOLVED_ACTIVE_ARC_CHANGED | 53 | 535 |
| UNRESOLVED_COMPETITION | 6 | 50 |

## 跟踪、串行与时间边界

新普通与串行测量 CSV 逐字节一致：True；旧轮一致：True。新串行被丢弃机会中原初始合格候选为 0 个。owner 竞争、释放与无效历元仍保留，不能把初始候选数量直接当作独立有效测量数量。

新普通跟踪事件：`{"INACTIVE": 988, "TRACK_RELEASED": 55, "TRACK_STARTED": 55, "TRACK_UPDATED": 102, "suppressed_valid_origins": 61}`。

新串行到达结果（包括无效候选）：`{"AVAILABLE_CURRENT_CANDIDATE": 55, "ORIGINAL_RESULT_UNAVAILABLE": 961, "SUPPRESSED_OWNER_AT_ENTRY": 156}`。

新释放原因（普通与串行分别保存在 JSON）：`{"RELEASED_REJECTED_LENGTH": 10, "RELEASED_REJECTED_PHASE_FAULT_DIAGNOSTIC": 28, "RELEASED_REJECTED_RESIDUAL": 2, "RELEASED_UNRESOLVED_ACTIVE_ARC_CHANGED": 14, "RELEASED_UNRESOLVED_COMPETITION": 1}`。

新登记服务成本来源：`{"CERTIFICATE_ELAPSED": 1191}`；实际被串行模拟服务的来源：`{"CERTIFICATE_ELAPSED": 1172}`。

正常搜索服务成本严格取 certificate.elapsed_s；无证书失败才取显式 whole-attempt timer，明确未搜索的预选失败计 0 CILS。后两类本轮均为 0。总 case 时间与 whole-attempt 时间另存在 JSON/逐例 CSV，未替换 CILS 成本。分位数使用排序样本的线性插值，保留超时与失败，不只统计合格结果。

串行结果仍是 idealized recorded CILS service cost 回放：单 worker、忙则丢弃、无队列；准备、模型读取、验证、诊断、catchup、跟踪、导出、I/O 与资源争用开销均未计。完成后且原五历元验收齐备才允许当前历元输出；不是实际 wall-clock 实时测量，也不是部署实时性证明。

## 比较允许的结论

相比旧轮，本轮同时把 Python 球面核改为 native，并把 2 s 获取机会改为每个 0.2 s RAWX 历元；两次执行负载与时段也不同。因此这些整轮差异不是孤立调度消融，不能把耗时变化或可用量变化全部归因于 cadence。共用 120 窗的独立等价复核由 DENSE_SELECTED_EQUIVALENCE 报告承担，本脚本不重做候选搜索或等价审计。

重叠选择/未来窗口与同一 owner 的持续输出存在依赖，116 个初始合格、157 个有效历元均不是独立成功试验。无真实整数标签，lifetime false-fix probability 未校准；没有以参考精度删窗或改门。这里只报告前端支持与记录成本，不作航向/位置精度判断。

## 复现

从仓库根目录在 Ubuntu 22.04 WSL 执行（只读已有产物）：

```bash
python3 scripts/paper_rebuild/carrier_phase/summarize_dense_selected_frontend.py --scratch-root <CARRIER_INTEGRATION_ROOT> --output-dir <REPORT_DIRECTORY>
```

脚本要求两轮 COMPLETE 和三阶段成功，核验 summary/case pins、CSV/event 数量、时间顺序与逐行有效状态；保存所有 1311 个 case 的状态/维度/耗时/串行动作及 SHA。运行目录以调用参数传入，报告不保存机器绝对路径。
