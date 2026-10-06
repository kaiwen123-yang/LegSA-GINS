# 本轮完成核查与条件式停止

本轮交付为受控对照审查、有限机制验证和去留报告。不是新 AR 的实测集成或投稿就绪认证。
最终 Git 回执在 WSL scratch 的 FINAL_DELIVERY_RECEIPT.json 中记录实际远端身份；
本文件所属提交可由 Git 历史查询，避免在文件内伪造自身哈希。

| 要求 | 终态 | 主要证据 |
|---|---|---|
| R1 | 原 V3 科学身份与三序列结果锁定；无重跑 | V3_BASELINE_LOCK、V3_BASELINE_METRICS |
| R2 | 12 槽有限经典候选器资格完成；实测物理误差原因仍有未决项 | CLASSIC_QUALIFICATION_RESULTS、CAUSE_AUDIT |
| R3 | 六份同历史同选项转换一致；15 旧 LLI 复现 | INPUT_AUDIT_RESULTS |
| R4 | 一次 BY2/V0 诊断重放，position/stat 与旧结果逐字节相同 | RTKLIB_DIAGNOSTIC_READOUT |
| R5 | 两项额外方法完成资格及不强行实施的决策 | COMPARISON_ADMISSION_DECISION |
| R6 | 16 槽终态，积极扩展门未满足 | MOTION_PAIR_RESULTS、motion_pair_qualification/COMPLETE.json |
| R7 | NOT_EXECUTED_CONDITION_NOT_MET | 原登记与 COMPLETE.json；无新导航/evaluator 调用 |
| R8 | 315 行指标证据覆盖交付，条件未执行保留 NA | R8_METRIC_COVERAGE.csv/.md |
| R9 | 停止当前两历元无向角度支线，保持 V3 | DECISION_AND_LIMITS |
| R10 | 研究分支逐阶段推送，草稿 PR #65；不得合并 | Git 历史、PR、最终交付回执 |

## 独立复核

只读核查完成，没有为复核重跑算法或读取原始轨迹：
- 315 个唯一键为 5 方法 × 3 序列 × 21 指标。
- 252 个新臂字段全部 NA / NOT_EXECUTED_CONDITION_NOT_MET。
- 原 V3 39 个数值与锁定指标表精确一致；另外 24 项明确为缺证 NA。
- 16 个唯一搜索结果和 32 条 BEGIN/END 记录对应；两个超时保留。
- 256 个固定整数可行对下界检查全部通过。
- ordering_evidence_cases 为空、navigation_expansion_allowed 为 false，
  与原登记和 R7 不执行决策一致。
- 数学结论显式限定相同满列秩几何、共享有效整数弧、精确相位模型。
  不用此反例否定 2013 原法所含有向平面角信息。

## 实际数值调用与边界

六次 convbin 转换、一次 RTKLIB 原生诊断、12 个经典资格搜索槽；
新原型为 16 个搜索槽，14 返回候选、2 超时、无重试。
12 个局部测试、256 个固定 N 界检查和 81 点子模型 oracle 分开计数。
本目标新增完整 LegSA 导航/evaluator 调用为 0/0；旧 V3 结果只复用。

无真实整数标签、无新跨日留出、无新物理不确定度校准、无在线全链时延测量。
数值搜索最优证据不等于物理整数真值，保存几何合成案例不进入实测效果表。
此次没有建立第三项已验证 AR 创新，未改写论文。
