# V3 数据上的受控模糊度研究

状态：本轮受控研究已完成，当前两历元角度支线停止扩展。
V3/main 保持；用户明确审核同意前禁止合并。
GPS Solutions 为主要方向，IEEE TIM 为备选，本阶段未写论文。

先读[去留结论与限制](DECISION_AND_LIMITS.md)：预注册的整数区分收益门未满足，
因此未启动十二个新导航身份；未执行的新方法指标均为 NA。这不是三序列实测失败，
也不是对所有运动辅助 AR 的否定。

- [目标与完成条件](GOAL_CONTRACT.md)及[完成核查](COMPLETION_AUDIT.md)：范围与条件式终态。
- [原 V3 身份](V3_BASELINE_LOCK.md)与[原三序列指标](V3_BASELINE_METRICS.md)：
  全窗、初始化、物理点、评价器和既存结果独立锁定。
- [原因审查](CAUSE_AUDIT.md)：已确认、已排除和未决问题。
- [输入核查](INPUT_AUDIT_RESULTS.md)：六份同历史重建一致，旧15个LLI值复现；
  原失败和28条元数据异常全部保留。
- [经典候选器资格](CLASSIC_QUALIFICATION_RESULTS.md)：12个有限合成检查通过；
  候选可用不改称固定率。
- [RTKLIB执行链](RTKLIB_DIAGNOSTIC_READOUT.md)：唯一诊断重放输出字节一致，
  SPP/AR分母拆开、35个Q1长度警告有逐历元证据。
- [文献资格](LITERATURE_QUALIFICATION.md)与[两项对照纳入决策](COMPARISON_ADMISSION_DECISION.md)：
  PD-PAR和2013 gyro-integral仅完成资格审查，未强行新增实现或实测排名。
- [两历元机制与界](MOTION_BOUND_DESIGN.md)、[原登记](MOTION_PAIR_PREREGISTRATION.md)及
  [全部数值结果](MOTION_PAIR_RESULTS.md)：16槽，14返回、2错误先验超时，没有积极扩展证据。
- [R8指标覆盖与NA口径](R8_METRIC_COVERAGE.md)：315行台账，保留原V3与新条件未执行身份。

本目录不以合成恢复率替代实测固定率，不用评价参考调参，不将新原型写成已超过V3。
[草稿PR #65](https://github.com/kaiwen123-yang/LegSA-GINS/pull/65)只供审查，无自动合并。
