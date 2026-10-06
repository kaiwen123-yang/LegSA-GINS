# A2 小项复核

只读reviewer检查README、完整输入/调度笔记、6身份30hash，并逐source/window/row_key回查3份SUMMARY；未读大载荷或重算。发布检查PASS，无阻塞项。

- 3886/7594/7632快照全VALIDATED，失败0、未修改实际R；30项hash的两列字符串相同。
- F04 N12最终影子R差98+356+418=872，RD cap遮蔽15，N16=1369；按provider时间during的yaw100无Hdx/NIS差，HV/RP的101及OIM差9/90被LSIM遮蔽，与源表相符。
- 调度during yaw/HV/RP各100接受、RD100资格门拒绝、position/RV入口0；A04全程38次SA-off残差门与F04分开。
- A04两条恢复事件明确关联trigger与provider时刻；F04仅援引独立汇总，不复用A04事件身份。101条源时间快照没有写成中断入口内额外接受。
- 保留半合成、保留heading、arrival UNKNOWN、多模块差异、无HV-off对照和影子未反馈限制。不是完全GNSS拒止或完整科学审查通过。
