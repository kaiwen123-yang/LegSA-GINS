# RTKLIB 单次执行链诊断结果

已完成登记 3d0dbcf65ff390e1fe34c12be5bd7236c130fe6c 下唯一一次 BY2/V0 重放。原官方二进制、配置、完整观测历史和两份星历均未改，只增加 -x4；新 solution.pos 和 solution.pos.stat 与 HX07R 原文件 **逐字节完全相同**。实际调用：RTKLIB 1、重试 0、编译 0、转换 0、LegSA 0、参考评估 0。strace 未发现 raw UBX/FPL/BAG、商业参考或 error_series 读取。仪器化耗时 96.613618498 s，含大量 trace/strace 开销，不是在线性能结果。

结论是：本配置低可用率中存在可直接数清的 **SPP 入口拒绝、AR ratio 拒绝**；同时，官方固定版本 **固定解 postfit 大残差只被记录，不阻止 Q1**。不能把所有异常归因于长度约束完全未执行，也不能据此确定整数是否正确或唯一物理误差来源。

## 执行分解与分母

| 事件 | 完整原生输入域 | 原始观测时间标签 [66,340] s |
|---|---:|---:|
| 输入历元 | 1509 | 1370 |
| 输出 Q1 | 177 | 153 |
| 输出 Q2 | 483 | 416 |
| 无输出 | 849 | 801 |
| 进入相对定位 | 661 | 570 |
| AR ratio 通过且固定条件计算成功 | 178 | 154 |
| AR ratio 失败 | 482 | 415 |
| 未调用 AR | 849 | 801 |
| Q1 带任意 fixed postfit 大残差日志 | 43 | 43 |
| Q1 带 fixed postfit 长度大残差日志 | 35 | 35 |

完整域的 848 个历元在相对定位前终止：680 个 rover SPP chi-square 失败、168 个 base SPP chi-square 失败，均有逐历元 trace；本 argv 的 rover/接收机1是物理 GNSS2，base/接收机2是物理 GNSS1。另有 1 个历元进入 relpos 后未调用 AR，作为独立未完全归因行保留，不能算入 SPP 失败。原本较差的总覆盖率不能全部叫作“整数搜索失败”。

AR ratio 通过 178 次却只有 177 个 Q1：116.198 s 历元只有 1 个 DD，ratio trace≈4.23，但源码要求 resamb_LAMBDA 返回值 >1 才进入 fixed postfit，所以该行仍为 Q2。此事件不是 ratio 门失灵，也未被删除。

1370/153/416 的窗口计数与 HX07R 旧表一致；这里按输入观测标签报告，没有读旧参考或按方向误差重新匹配。所有 1509 个历元都在 RTKLIB_EPOCH_DIAGNOSTICS.csv；849 个无输出行明确保留为空输出，不记成零误差。

## 长度约束：确定的执行机制

1. 35 个 Q1 的固定解长度残差触发了原 valpos 的 4σ 日志，长度项 σ=0.01 m，对应 |残差|>0.04 m。它们仍输出 Q1。
2. 这 35 个历元 **全部有至少一次成功滤波迭代加入长度项**；32 个也出现后续迭代因非线性门而跳过，3 个没有任何成功滤波迭代跳过。因此“根本没施加长度约束”不是统一解释。
3. 三个未跳过例子为输入时间 151.598/151.798/152.998 s；Q1 基线长度约 0.468462/0.491017/0.466823 m，ratio 输出约 10.8/7.0/4.3。这是区分执行机制的重要反例，完整 35 行仍全部保留。
4. 最大长度残差例：输入时间 81.998 s、输出时间 82.000 s；基线长度 0.7077479565 m，偏离名义 0.35 m 约 0.3577479565 m；ratio trace≈4.87（.pos 输出四舍五入为 4.9）。该历元两个成功浮解迭代加入长度项、一个跳过；固定 postfit 又计算长度残差，但没有再次更新滤波。
5. 35 个长度警告 Q1 的 .pos ratio 范围 3.0–52.6。ratio 通过不能替代物理基线一致性检查；这里的“长度警告”也不能直接当成整数真值错误标签。

源码与实际记录一致：rtkpos.c:980–988 的 constbl 非线性门可以跳过；1512–1542 的第一轮 Pp 为零初始化，后续轮次才有更新后的协方差；1575–1580 的 fixed postfit 传 P=NULL，仅形成残差；1437–1458 的 valpos() 从头到尾保持 stat=1，对大残差只打印。固定解经过整数条件更新后，没有强制投回硬长度球面。以上定位的是 **此固定版本/此配置的实际执行行为**，不宣称已经证明应如何修复或修复后的性能收益。

## 派生关联修正与时间证据

首次冻结 summarize 因“输入 trace 时间键必须等于输出 .pos 时间键”的错误假设而停止，未生成正式汇总。该失败保存为 DERIVATION_ATTEMPT01_FAILURE.json，并写入公开 summary；原 runner 未修改，未重放 native。

新只读 ar_v3_rtklib_readout.py 按实际源码作关联：

- RTKLIB pntpos.c:408–409：sol.time = obs.time − receiver_clock；sol.dtr[0] 保存该钟差秒值。
- rtkpos.c:251–253：$CLK 写 receiver=1、sol.dtr[0]×1e9，单位 ns。当前第一个观测文件是 gnss2.obs，所以这是物理 GNSS2 的 rover 钟差，不能误取 base 钟差。
- 由 output_time + CLK_ns×1e−9 还原输入时间。输入、输出分别只打印到毫秒，匹配区间上限取两端舍入误差和 1 ms，加极小浮点容差；不估计时间平移，不读 yaw/reference。
- 660 个输出、660 个 CLK 全部唯一且严格单调匹配；未匹配输出 0。重建时间与 trace 打印值最大绝对差约 0.298074 ms；849 个没有输出的输入历元全部列出。

这也直接说明原程序处理了接收机钟差。ephemeris.c:774–792 另按各观测 T−P/c−卫星钟差求发射时刻。DG01R 的旧 HPPOSECEF 几何诊断需要钟差处理，不能推导出在这条 RTKLIB 链再补扣一次接收机钟差。

## 排除与仍未知

排除：本次诊断改变科学输出、输入历史截断、额外参考读入、未开启长度参数、35 个长度警告全部因“从未施加长度项”而发生、ratio 通过必然保障短基线一致性。重复减接收机钟差或无条件补回 0.5 周，没有由本记录获得支持。

仍未知：这些真实相位/码残差的唯一物理原因，具体整数真值，已校准的固定错误率，以及只加入 postfit 拒绝或硬约束是否能在完整性能/可用率上改善。部分 Q1 长度近似合理也不证明方向或整数正确。另两序列、其他 RTKLIB 变体没有新重放；原历史结果保持原身份。

## 复核入口

- RTKLIB_DIAGNOSTIC_SUMMARY.json：原生字节门、计数、时间关联和首次派生失败；
- RTKLIB_EPOCH_DIAGNOSTICS.csv：1509 个输入历元全表；
- RTKLIB_Q1_LARGE_LENGTH_DIAGNOSTICS.csv：35 个原内部长度警告 Q1 全表；
- RTKLIB_DERIVATION_RECEIPT.json：只读命令、脚本 hash、派生产物 hash、原生记录链；
- scratch BY2_V0_TRACE4_PREP02/RUN：原始 solution.pos/.stat/.trace、调用记录和文件访问审计；
- scratch TRACE_DETAIL_CLOCK_JOINED.json：带原 trace 行号的全部 DD/AR/残差分支。

只读派生命令：

python3 scripts/paper_rebuild/carrier_phase/ar_v3_rtklib_readout.py --code-root <CODE_ROOT> --stage <RTKLIB_DIAGNOSTIC_STAGE>

派生脚本 SHA256：06027f0a8d7768dcc1e811e67bb38d73062db00fcd9e57a6449d7b6d2bd196e4。
冻结执行脚本仍为 045ef075c57b0c418ebfd1908c633903d3d41b0e624f918dc4a546881a1ef918。
