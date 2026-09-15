# CLEAN3R2 人工批复与 Attempt 修正案

## 一、人工批复块（对 CLEAN3 终态报告所请四项）

依据 `CLEAN3_S3_AB0000_PARITY_REPORT.json`（immutable 34 角色前后一致、`trace_used_online=false`、`performance_metrics_read=false`、`retry_count=0`）与 `solver_stderr` 的 `FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH`，批复如下：

1. **新技术 attempt：批准。** 原 attempt 按规则保留为 sealed failed technical attempt，不删除、不覆盖。
2. **port_runtime.cpp 最小 allowlist 扩展：批准**，且**仅限**下文第三节定义的单点改动（`validateFormalRuntimeCounters` 的 AB 分支路由键），不得顺带重构该文件其他内容。
3. **新的不可覆盖 stage identity：批准**，定为 `CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME`。
4. **新的 freeze/authorization：批准。** 在路由修复提交后建立新 code freeze 与 runner freeze；authorization 记录本文件哈希。

附带批准条件：修复实现提交 `0d8cc2b` 所在链（分支 HEAD `9d51794`）的三处数学修复与 253 项测试**原样继承，不得重新实现**；本 attempt 从 S3 重入，S4–S9、全部验收门（G-C1…G-C4）、证据边界与不授权清单**继续沿用原 CLEAN3 提示词**，本文件只作修正案。

## 二、根因认定（写入 attempt 报告）

`validateFormalRuntimeCounters`（`port_runtime.cpp`）中 AB 型 `algorithm_id` 的计数器契约以 `options.stage_id == "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"` 为路由键。AB 契约的语义（AB 四位 → RD/SA/RP/HV 激活模式，叠加 position/receiver/yaw 必须激活、FGO/QA/QM/contact 必须为零）与阶段无关；`stage_id` 合取项无语义贡献。CLEAN3 S3 的 AB0000 因新 `stage_id` 落入终结 `else` 而被 fail-closed 拒绝，发生于滤波循环结束后、`writeAll()` 之前，未产生 NAV/STD，S3 byte parity 为 `NOT_EVALUATED`。

**连带风险认定**：Canonical-541 的 4869 条 AB 消融逻辑行使用同一校验路径与非 CLEAN2R2A 的 `stage_id`，若未修复将在首个正式求解处发生同类失败。本修复为 CLEAN3 与 Canonical-541 的共同前置。

## 三、最小修复契约（唯一授权改动）

**位置**：`cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp` 的 `validateFormalRuntimeCounters`。

**改动**：AB 分支去除 `stage_id` 合取项，路由键改为 `algorithm_id` 的 AB 形态本身：

```cpp
// 原：
} else if (options.stage_id == "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD" &&
           options.algorithm_id.size() == 6 && options.algorithm_id.rfind("AB", 0) == 0 &&
           std::all_of(...)) {
// 改：
} else if (options.algorithm_id.size() == 6 && options.algorithm_id.rfind("AB", 0) == 0 &&
           std::all_of(options.algorithm_id.begin() + 2, options.algorithm_id.end(),
                       [](char v) { return v == '0' || v == '1'; })) {
```

分支体内按位推导的期望（`receiver_active && yaw_active` 与四位逐一匹配）**一字不改**；四个 F 名分支、position 前置、FGO/QA/QM/contact 零值断言、终结 `else`、异常文本**一字不改**。`stage_id` 继续记录进 run manifest / parity report 作 provenance，不再参与路由。

**数值安全论证（写入报告）**：该函数在滤波循环结束后只读计数器并抛出或返回，不写任何滤波状态；改动不可能影响 NAV/STD 字节。真正的数值门仍是 S3 逐位 parity。

## 四、新增测试（并入 tests/paper_rebuild）

- T1 `test_clean3r2_counter_contract_ab_stage_independent`：AB0000 期望计数模式在任意 `stage_id`（含 CLEAN3R2 与 Canonical-541 的 stage 字符串各一例）下通过校验。
- T2 反向护栏：AB0000 但 raw_doppler 计数 >0 时必须抛 `FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH`；AB1111 但 source_aware 计数 =0 时同样必须抛。
- T3 回归护栏：四个 F 名分支与 CLEAN2R2A `stage_id` 下的 AB 行为与修复前逐项一致（防止顺带改语义）。
- T4 canary：以 Canonical-541 runner 传入的 stage/algorithm 组合构造一次干跑（不触数据），确认路由命中 AB 分支而非 `else`。

## 五、执行序（fail-closed）

```text
S0  worker 实施第三节单点改动 + 四项测试 → build → 全量 tests/paper_rebuild 通过
S1  新 code freeze / runner freeze 记录；authorization 哈希入 manifest
S3' 重跑 S3 parity 门：AB0000 于 CLEAN1_BY2_CLEAN_NORMAL，
    NAV/STD 与 CLEAN1R2R1 anchor（800f0dc1… / 04ebff45…）逐位比较
    → 一致：继续原 CLEAN3 提示词 S4–S9
    → 不一致：BLOCKED_PARITY_REGRESSION_AB0000_MISMATCH（此时才是真 parity 问题，
      按原提示词处置，禁止为凑 parity 回改数学修复）
```

3641/5951 manifests 的 rebind 决策维持原 CLEAN3 提示词第 10 节：待本 attempt PASS 后随 Canonical-541 重启一并执行，rebind 前逐文件哈希校验。

## 六、终态

- `PASS_CLEAN3R2_MATH_REPAIR_CLEAN_NOHARM_READY_FOR_HUMAN_REVIEW`（沿用原 PASS 语义）
- `BLOCKED_PARITY_REGRESSION_AB0000_MISMATCH` / `BLOCKED_SA_CLEAN_HARM_PERSISTS` / `FAILED_TECHNICAL_<原因>`

## 七、本 attempt 不授权

除第三节单点改动外的任何 `port_runtime.cpp` 修改；parity 骨架任何语义改动；Canonical-541 执行；merge/tag；论文主张。`ready_for_paper_claims=false`。
