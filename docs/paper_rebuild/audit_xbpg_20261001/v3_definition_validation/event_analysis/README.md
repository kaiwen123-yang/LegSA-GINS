# 单例事件分析

当前只完成实现和合成验证，真实事件、NAV、旧 error_series、reference 读取均为 0；native/evaluator/provider 调用均为 0。实际扫描由根代理审查、提交后单独执行。

输入限于 [CANDIDATE_QUEUE.csv](../CANDIDATE_QUEUE.csv) 的 10 个候选和 7 个去重旧观察基线，路径来自 ignored `V3_DEFINITION_ROOTS.local.json`。先核候选完成/访问回执和旧观察版字节身份/访问回执，再打开事件；不读同输入 provider。

```bash
python3 docs/paper_rebuild/audit_xbpg_20261001/v3_definition_validation/event_analysis/analyze_events.py scan --roots configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json --candidate-id N12_ONLY --run-id RUN_00004
python3 docs/paper_rebuild/audit_xbpg_20261001/v3_definition_validation/event_analysis/analyze_events.py compare --roots configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json --candidate-id N12_ONLY --run-id RUN_00004
```

每次只选一组。每流一次完整读取，同时计算 SHA256、检查 BEGIN/END、event_seq、run_id、END.prior_event_count、EOF 和前后 stat。外部缓存位于 `<VALIDATION_ROOT>/analysis/event_cache/`；C00/F04 基线可供三个候选复用，复用时载荷打开为 0。原文件 stat、分析器 hash、身份变化或残缺缓存都拒绝自动重扫；输出不覆盖。`compare` 只读缓存，在 `<VALIDATION_ROOT>/analysis/comparisons/<slot_id>/` 写完整结果，本目录 `summaries/<slot_id>/` 只放小摘要和首分叉索引。

SA_BEGIN 只核同一 dz/H/dx/P/base_R，不重复计 evaluate。每个实际 SA 保存 raw dz、Hdx、conditional nu、两种同快照 NIS、原倍率和策略 accepted/rejected；N12 实际统计采用 nu，其余采用 raw dz。fallback 单列，不冒充协方差 NIS。SA-off 辅助源没有调用时保留 NO_SA_CALL。**实际 R 只取 EKF_BEFORE.R**，SA.effective_R 不等于已经接受；实际接受核 MEASUREMENT_DECISION、EKF_AFTER 和原 position/RV/RD/RP/HV 计数。post-R NIS 与 pre-SA NIS 分开。

跨流键是 gnss_input_seq/source/原 measurement_time，不能用因新增事件变化的 event_seq 拼接。重复稳定键明确未决，新增事件没有的基线 R/dx/状态不补零。分别给首个实际 R、接受、dx/delta 差异；状态按字段和原单位输出向量差，不求混合单位范数。首次状态差异按 double 精确值识别，R 另列固定容差判定。

共同 IMU 末状态按相同 imu_seq/imu_current_time 对齐，取当轮最后 PROPAGATION_AFTER 或 FEEDBACK_AFTER，并核 state.time。候选 COVARIANCE_HEALTH 标明末边界；基线在下一输入/机会或正常 EOF 闭合。N09 新增 RP 没有基线中间状态时不插值；记录新增尝试/接受后首共同 IMU、split/propagation/feedback 数。RP 被拒绝仍可能伴随 res3 拆传播，不归因为接受了 RP。旧全失效 GNSS 输入的合格 RP 与候选真实尝试/接受完整连接，不预设全部接受。原 isActive 只有 active 与 std>0，保留其对正 Inf 的行为，没有另加有限性门。

更新计数同时给 FULL_STREAM、[66,340] 闭窗和 [196.2,216.2) 半开窗。时间轴为 measurement_time；RP_ONLY 字段为 gnss_event_time；arrival time 仍 UNKNOWN。固定局部窗只有在 A1/A2 才具有中断含义。

候选汇总所有已初始化 IMU 末的 COVARIANCE_HEALTH。基线只检查现存 EKF_BEFORE/AFTER 完整 P，不能称逐 IMU 连续覆盖。按 [决策](../V3_DEFINITION_DECISIONS.md) 和 [公共头](../common/covariance_diagnostics.hpp) 检查有限性、正对角、归一化对称门 1e-10 和诊断副本 Cholesky pivot ±1e-12；无 jitter，不写回 P。NIS 容差 abs 1e-9 + rel 1e-8，倍率/R 传播 abs 1e-10 + rel 1e-10；零 base_R 项要求仍为零。NumPy 算术固定单线程。

stream_status 和 analysis_status 分开，完整流但公式校验失败/不可用仍非零退出。VALIDATED 只表示本分析器的流/关联/公式验证通过，不宣称科学正确或 P 总是正定；合法读出的 P 风险按原诊断状态单列。

先读 SCAN_RECEIPT.json，再读 MEASUREMENTS.csv、UPDATE_COUNTS.csv、RP_ONLY_EVENTS.csv。比较目录含全量 MEASUREMENT_COMPARISON.csv、ORIGINAL_RP_OPPORTUNITIES.csv、IMU_STATE_COMPARISON.csv。SUMMARY.json 和 FIRST_DIVERGENCE_SNAPSHOT_INDEX.csv 给首分叉；来源有 event_seq、行号和字节 offset/length。每源首 SA、首 EKF_AFTER、首异常完整快照写外部 KEY_SNAPSHOTS.jsonl；其他首分叉完整矩阵仍在原 events，按索引可读，不为复制而再次打开。EVENT_INDEX.csv 和 cache.sqlite 保留全部关联。

本项不增加 NAV 首叉扫描入口。NAV/STD 有限性及评价共同支持由根代理评价小项处理，不能从共同 IMU 状态假称已读 NAV。所有大表、SQLite、快照留外部。

[VALIDATION_RECEIPT.json](VALIDATION_RECEIPT.json)：最终 41 项纯合成检查通过；6 份本轮已生成 native fixture 日志共 247 行、8 次 SA 全部核对通过，两组缓存比较通过；本分析器没有新增 native。初始 schema 检查另读两份新 N16 合成日志各一次，共 100 行；首次跨流比较误把 nested Cbn 当矩阵对象而失败，已修正并纳入测试。原失败目录/缓存、首轮 28 项通过回执保留，未重扫那两份源。这些合成检查不计入 10 个真实候选运行分母。

审查补充已实现：native 次数只接受精确整数 1 或字符串 "1"，拒 bool/浮点/UNKNOWN；回执分别记录打开尝试、物理 EOF、完整有效流、前缀或完整哈希。比较前核缓存 schema、当前分析器 SHA 和队列中的两侧 run/candidate/source 身份，错版/错对象拒绝，不自动重扫。N09 按可选新增调度能力报告；历史独立 RP 设计要求尚未核实，不默认称原设计缺陷。

六份 native fixture 流的算术核对绑定审查补门前的分析器 hash；补门后只重跑纯合成单元流，未重扫这六份日志。各版本 hash 与回执均保留，不能把旧缓存改签为新版本。
