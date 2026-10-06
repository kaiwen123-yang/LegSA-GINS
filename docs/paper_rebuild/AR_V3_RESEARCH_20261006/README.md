# V3 数据上的受控模糊度研究

状态：进行中。V3/main 保持；用户明确审核同意前禁止合并。
GPS Solutions 为主要方向，IEEE TIM 为备选，本阶段不写论文。

- [目标与完成条件](GOAL_CONTRACT.md)：范围、条件式三序列验证和停止规则。
- [原 V3 身份](V3_BASELINE_LOCK.md)与[原三序列指标](V3_BASELINE_METRICS.md)：
  全窗、初始化、物理点、评价器和既存结果独立锁定。
- [原因审查](CAUSE_AUDIT.md)：已确认、已排除和未决问题。
- [输入核查](INPUT_AUDIT_RESULTS.md)：六份同历史重建一致，旧15个LLI值复现；
  原失败和28条元数据异常全部保留。
- [经典候选器资格](CLASSIC_QUALIFICATION_RESULTS.md)：12个有限合成检查通过；
  候选可用不改称固定率。
- [RTKLIB执行链](RTKLIB_DIAGNOSTIC_READOUT.md)：唯一诊断重放输出字节一致，
  SPP/AR分母拆开、35个Q1长度警告有逐历元证据。
- [文献资格](LITERATURE_QUALIFICATION.md)：附件八篇定向阅读、最多两种新对照边界。
- [两历元机制与界](MOTION_BOUND_DESIGN.md)：安全界和精确反射别名的零信息边界；
  [待执行登记](MOTION_PAIR_PREREGISTRATION.md)明确数据模式及去留证据。

本目录不以合成恢复率替代实测固定率，不以错误参考调参，不将新原型写成已超过V3。
