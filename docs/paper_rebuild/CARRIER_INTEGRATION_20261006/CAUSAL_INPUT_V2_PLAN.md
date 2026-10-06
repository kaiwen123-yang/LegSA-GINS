# 第二版因果输入维护

初版导航已完成，完整/部分载波有效输出1/7次，启用body-HV时航向仍逊现有PVT链。以下改动依据输入故障记录，在新输出目录执行；不改变整数目标、AR协方差、验收/诊断门限、后端权重或既有结果。

1. 广播星历在100、120、…、320秒推进。100秒复用已验证前缀；其余前缀由同一raw UBX与已验证Gal E1B八字转换器构建，不重新编译。无时间标签SFRBX用其后一个原RAWX作为到达上界，消费者只在当前epoch>=cutoff后打开对应NAV。
2. 当前GPS code-SPP成功时更新粗线性化位置；失败时仅使用最近过去成功点，最多20秒。假设工程位置半径为100+5*age米，不来自四颗星恰定SPP的近零残差，也不是精度保证。此位置只计算短基线观测几何，不作EKF位置/速度观测或参考。
3. 已固定参考星不可用时，在当前合格同组卫星中重新选择。显式生成新的DD标签，禁止把旧N直接当新N或跨周跳延续。原固定pivot策略保持可选。
4. 新准备仍覆盖BY2 100–340秒，所有失效/切换完整记录。先检查输入覆盖和可复用的10窗180–200秒小试验，再决定同参数完整前端及导航重放。
5. 不以新的导航RMSE选择frame、sigma、阈值、卫星或时间窗；本轮已查看整体导航结果，所有实验均属于开发数据，不能称独立验证。

## Full-span continuation

The new preparation produces all 1200 model epochs in every family, with 1200
current raw-code anchors, zero held anchors, 12 NAV snapshots and 13 distinct
physical group pivot switches (23 family-level events). The registered
180–200 s pilot completes all 20 searches, with zero qualified outputs; arc
support and measurement consistency remain limiting. No input implementation
defect was found. Extend to all 120 registered windows per method using exactly
the same code/inputs/gates, resuming the 20 pilot cases and issuing 220 new
search attempts. Do not reinterpret the newly recovered input epochs as
admitted carrier measurements. Complete the raw full-span outputs before
evaluating their navigation effect.
