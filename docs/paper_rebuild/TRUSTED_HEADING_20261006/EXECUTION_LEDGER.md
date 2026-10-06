# 分层执行台账索引

本文件统计范围是本轮完整输入/前端/导航链，并索引此前机制记录；不是仓库全部历史调用总数。具体身份、预算、actual与复用来源见EXECUTION_LEDGER.json及各原receipt。枚举内节点、GLS、GLRT、球面核、SPP和native导航不能合计成“若干次AR实验”。

|阶段|实际执行/复用|范围与失败|
|---|---|---|
|完整原始输入R2|73新转换、1原结果复用；3prepare；4605 SPP机会；12686模型|305无anchor；首轮空NAV技术失败保留；0整数搜索/native/eval|
|clean前端|921固定机会、387完整枚举；5631 GLS/GLRT/geometry，2408球面|653研究点；0真实整数正确率；0native/eval|
|RAWX故障准备|3prepare、6源payload读；4605 anchor复用|0新SPP/转换/整数搜索/native/eval；卫星状态backend仍参与|
|RAWX故障前端|921固定机会、389完整枚举；5707 GLS/GLRT/geometry，2440球面|685导出/171内部有效回执；0native/eval|
|本体足对provider|3原V3完整窗口，4605机会|4309START/2512END/1797RETIRE；0融合|
|原生clone局部资格|1configure、1core/demo构建、1harness编译；1pytest/16唯一case|28 harness子进程含6预期非法域拒绝；不是28条实测导航|
|clone准备首轮及R2|2checker编译、1失败loader+6成功loader|首轮说明文字解析失败保留，0真实导航消耗；R2仅修元数据文字|
|完整导航比较|先前6native/6eval＋新6native/6eval|本范围总12/12，等于登记上限；原V3重用，不新跑；native/eval重试0|
|派生比较|两组六臂各1次比较|只读已封存误差，0原始reference/solver|

此前固定N、支撑、方向域、图投影及低维合成枚举各有独立receipt。其独立case与重复实例不压成一个大PASS总数，失败、fixture修正、技术续行仍在原记录。本表没有把“达到预算上限”作为停止理由；停止依据是原采用门A失败、足对净收益为0和用户允许的负结果关闭规则。
