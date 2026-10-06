# 航向来源计数修正记录

这是已封存六条导航的独立 metadata 修正；原 RUN_MANIFEST、RESULT、ALL_NATIVE_SEALED 和科学输出全部保持未改。

## 原因

正常收尾已写出最终 RUN_MANIFEST，但 port_runtime.cpp 原 1600–1624 行漏把 engine.headingSourceCounts() 复制到 PortOptions。此前唯一拷贝位于 covariance-failure helper 第 178 行。因此 manifest 的六个 heading_*_count 是默认零，不能作为真实次数。GIEngine 617–676 行的实时计数与 1331–1346 行事件表直接由 engine 保存；本记录依据封存事件表重新统计。

## 六组实际计数

| 运行 | PVT 尝试 | PVT 接纳 | PVT 拒绝 | PVT 抑制 | Carrier 尝试 | Carrier 接纳 | Carrier 拒绝 | Carrier 绕过 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BY2__PVT_CONTROL | 1369 | 1348 | 21 | 0 | 0 | 0 | 0 | 1369 |
| BY2__CARRIER_FALLBACK | 1369 | 1348 | 21 | 0 | 0 | 0 | 0 | 1369 |
| BY2H__PVT_CONTROL | 1349 | 1334 | 15 | 0 | 0 | 0 | 0 | 1349 |
| BY2H__CARRIER_FALLBACK | 1349 | 1334 | 15 | 0 | 0 | 0 | 0 | 1349 |
| BY2O__PVT_CONTROL | 1593 | 1588 | 5 | 0 | 0 | 0 | 0 | 1884 |
| BY2O__CARRIER_FALLBACK | 1593 | 1588 | 5 | 0 | 12 | 8 | 4 | 1872 |

“接纳”仅表示原 EKF 实际 normal/downweighted 更新，不表示整数已知正确或独立真实方向。绕过包含 invalid carrier 行及 PVT 优先排除，不能等同统计检验拒绝。

## 封存交叉核对

- 共读取 18,408 条 HEADING_SOURCE_EVENTS；六表、六份 baseline3d 表和 manifest 的 SHA 均符合原 ALL_NATIVE_SEALED。
- 每事件的 PVT/carrier 尝试互斥；每个 accepted 必须有相应 attempt。
- 六组事件的 carrier 尝试/接纳均与 BASELINE3D_DIAGNOSTICS 完全相等。BY2O fallback 为 12/8，其余五组为 0/0。
- 事件 PVT+carrier 总尝试数等于原 manifest.yaw_update_count，总接纳数等于原 dual_yaw_update_count；BY2O fallback 为 1605 次尝试、1596 次接纳。
- 原 controller 对 control manifest 中 carrier_attempt=0 的断言因默认零而不具证据力；现由封存事件直接补核三个 control 均为 0。

## 后续源码修复与边界

仅在正常收尾 1608 行新增 options.heading_source_counts = engine.headingSourceCounts();。修复只面向未来运行，本次未重新编译、测试、导航或评价。当前 binary 和原登记 pins 不改；旧 attempt 因当前源码 pin 变化不能重新进入是预期行为，不允许据此重跑。

修复前源码 SHA: d80cf80e76740cd90fc832f288ff31fc3e97e93d11d8edba2ff304e2bd854c37  
修复后源码 SHA: f7741fd5ece7875b67cad2b2960524b49619426c62a93c94d5cae6bd553c2874  
逐组来源 SHA、原零字段、具体计数口径和交叉核对在 [HEADING_COUNTER_CORRECTION.json](HEADING_COUNTER_CORRECTION.json)。

此次读取限小型输出及源码；0 raw、reference、NAV/error-series/SOURCE_AWARE trace 读取，0 新 solver/evaluator/search/test/build。未修改阈值、参数、观测或已有输出。
