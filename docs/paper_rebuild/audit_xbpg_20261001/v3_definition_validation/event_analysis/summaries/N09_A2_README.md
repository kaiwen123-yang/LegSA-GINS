# N09 A2 20 s seed_00：保留航向时的事件负对照

原对象为 D62_20s_seed_00，A04/ADD_RUN_00402 与 F04/ADD_RUN_00400。四条事件流各一次完整主扫描，原/候选每组8014个测量键配对、56642个共同IMU末状态全部精确相同。接受、实际R、dx/actual_delta、名义状态均无首差异；没有新增/缺失/歧义键，也没有RP-only尝试。此前五输出各字节一致与同冻结离线评价相同继续成立，此项无新增native/evaluator/reference读取。

原A2保留yaw有效性，因此原GNSS总入口已经可用。它与A1三位全失效不是同一路径；窄N09候选在这里保持原调用，不将此负对照说成修复了完整异步调度。

|原固定[196.2,216.2)内实际接受|A04 原→候选|F04 原→候选|
|---|---:|---:|
|GNSS position|0→0|0→0|
|RV|0→0|0→0|
|yaw|100→100|100→100|
|RD|0→0|0→0|
|HV|100→100|100→100|
|RP|100→100|100→100|

计数取完整事件流的实际接受记录，window原半开边界不变，位置/RV该窗无接受事件的零是完整解析后的计数，不是把未知指标填零。HV确实参与，但这里没有HV-off干预，不能单独量化它对位置的因果收益。RD中断内没有更新；全窗RD A04/F04分别970/1008不得偷换为中断内参与。

全流position/RV各1269、实际yaw1348、HV/RP各1369；N09候选完全相同。完整P在候选每个56642 IMU末检查、基线只检查现存EKF前后快照，仍为NONPOSITIVE_DIAGONAL；归一化对称/Cholesky未执行，不能称全P通过，参见[共同P边界](../../P_MODEL_BOUNDARY.md)。

此项4条新全文流的计数、hash和来源见[N09_A2_READ_RECEIPT.json](N09_A2_READ_RECEIPT.json)。小摘要在[A04](N09_RP_ONLY__ADD_RUN_00402/SUMMARY.json)与[F04](N09_RP_ONLY__ADD_RUN_00400/SUMMARY.json)，完整比较原位为`<VALIDATION_ROOT>/analysis/comparisons/N09_RP_ONLY__{ADD_RUN_00402,ADD_RUN_00400}/`。时间是context测量/GNSS事件时刻及单列IMU时刻，真实arrival未知，不据此证明实时调度。没有全失效合格RP机会行，A1的整数/浮点文本键漏联问题不作用于这里的空关系；不用A1原错误80摘要作本项依据。
