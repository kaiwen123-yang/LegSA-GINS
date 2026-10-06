# RTKLIB 因果诊断：单次原配置 trace 重放登记

状态：PREPARED_NATIVE_ZERO。当前仅执行旧文件读取、源代码核对及解析器自测；未调用 RTKLIB、转换器、LegSA 或参考评估器。必须由 root 提交本登记与脚本后，传入该注册 commit 才允许一次真实重放。

## 1. 问题与现有证据缺口

固定官方源为 RTKLIB 180043ee24b6d2b168f98b64be15f69d50046b1a；原二进制 SHA256 为 3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda。

HX07R/BY2/V0 的完整 .pos 有 660 行（Q1 177、Q2 483）；.stat 中 POS/VELACC/CLK 各 660 行、SAT 25738 行。原 run 没有 .trace，stderr 也没有 constbl / AR 分支记录。完整原生输出口径不等于旧 [66,340] 配对窗口的 Q1 153/1370，不能混用分母。

已有源码明确显示：

- src/rtkpos.c:980–988：长度软约束在平均位置方差大于 (0.1 × 当前基线长度)² 时跳过。
- src/rtkpos.c:1512–1542：每历元的第一次 DD 调用收到零初始化 Pp；后续迭代才使用更新后的 Pp。不能用输出的最终协方差反推每次约束是否执行。
- src/rtkpos.c:1575–1580：固定解 postfit DD 调用传 P=NULL，constbl 的 var 保持 0；这里只生成残差，没有再做一次滤波更新。
- src/rtkpos.c:1437–1458：valpos() 初始化 stat=1；超 4σ 只写 large residual，未将 stat 改为 0，最终返回 1。因此长度或其他 postfit 大残差本身不会在此函数阻止 Q1。它不同于前面的创新剔除和 LAMBDA 比值门。
- src/ephemeris.c:774–792：各观测已按自身 T−P/c−卫星钟差计算发射时刻；不能据 DG01R 的旧 HPPOSECEF 几何诊断再对这里重复减接收机钟。
- src/rcv/ublox.c:343–398：RAWX cpMes、half-valid、sub-half 状态各有不同语义；本登记不添加通用 0.5 周校正。

这些是代码语义事实。实际多少历元执行/跳过软约束、多少 Q1 带有已记录的过大 postfit 残差，仍需逐历元执行记录。不能据源码 alone 断言主要物理误差来源。

## 2. 唯一重放配置与输入

选择 BY2 的原 V0 主对照，因为它对应现有 BY2 研发输入；不选择误差最大的序列/变体。仅运行一个序列、一个配置、一次调用。

| 角色 | 固定身份 |
|---|---|
| 原结果目录 | <CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07R/RUNS/BY2_V0 |
| 配置 | <CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07/CONFIGS/V0.conf |
| 观测与星历目录 | <CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/RUNS/BY2__RTKLIB__NONE__C00__NA/native/SOURCE_BACKEND |
| 输入顺序 | gnss2.obs、gnss1.obs、gnss1.nav、gnss2.nav |
| 算法参数 | movingbase、L1+L2、GPS+BDS mask33、continuous AR、ratio3、0.350m/0.010m 长度约束；完整原 conf 不变 |
| 时间 | 原完整观测历史，无 -ts/-te；约 1509 个输入历元，不截断为分析窗口 |
| 原输出选项 | -y 2 保留 |
| 唯一新增 RTKLIB 选项 | -x 4，CLI 源码只设置 solopt.trace |
| 新输出 | <RTKLIB_DIAGNOSTIC_STAGE>/RUN/solution.pos(.stat/.trace) |
| 准入门 | 新 .pos 与 .stat 分别逐字节等于原文件，包括头部；任一不等即失败，保留且不重试 |
| 新评价 | 0；不读取 reference、error_series、商业融合轨迹 |

原二进制本身已有所需 trace 功能，因此本阶段 **不复制/修改/重编译 RTKLIB 源码**，不引入仪器化数值扰动。不更改任何现存外部目录文件。CLI、原输入、原输出和关键源码均核 SHA256；原配置与全部四个输入 hash 必须匹配原 COMMAND.json。

## 3. 成本与执行边界

原 BY2 V0 记录耗时 4.380123 s。本次 -x4 与 strace 有额外输出成本，预计秒至几十秒；240 s 进程组硬超时、trace 1,000,000,000 bytes 上限。该耗时不能用作在线性能结果。

预算：RTKLIB 1、重试 0、构建 0、convbin 0、CILS 0、LegSA 0、参考评估 0。所有计算在 Ubuntu-22.04 WSL。一次性 EXECUTION_STARTED.json 防重复；超时/输出不等/退出非零/禁读输入均保存 FAILED.json，不替换原结果。strace 仅观测 openat/execve，禁止 raw UBX/FPL/BAG/商业参考与 error_series 读取。

本登记前保留一个 PREPARATION_01（目录名 BY2_V0_TRACE4_ATTEMPT01）的未执行准备记录；补充解析器对成功滤波迭代、浮解 postfit、固定解 postfit 的分辨后生成 PREP02。两份准备的 native 均为 0，唯一执行目录是 BY2_V0_TRACE4_PREP02。当前最终 PLAN SHA256：
b58e709bab44bf930a8e7d00ee53efd3bd9086fcb3e2c09993a148f130064644。

## 4. 预定输出与解释

全历元保留，不按参考方向误差删选。逐历元区分：无输出、Q2、Q1；AR 未尝试、无 DD、数值失败、ratio 失败、ratio 通过；长度项加入/非线性跳过，并用 x(iteration) trace 标识成功滤波更新，valpos 标识浮解 postfit，AR 后 DD 标识固定解 postfit。固定 postfit 的 ADDED 不会被误称又做了一次约束滤波。

保留原始 trace 的行号和完整明细。trace 数字具有官方格式舍入，只用于执行分支/已打印残差诊断；不是高精度协方差输出。长度来自原 .pos 三维 ENU 向量模长，方向参考不参与。报告全原生域及原生时间标签 [66,340] 子域；后者明确不等于历史 selected_pairs 支持。

预定文件：
- RTKLIB_EXISTING_LOG_AUDIT.json：旧日志充分性与源码事实；
- RTKLIB_PREREGISTRATION.json：机器可读配置、输入/源/脚本 pins、预算；
- RTKLIB_EPOCH_DIAGNOSTICS.csv：全历元执行和 Q/长度记录；
- RTKLIB_DIAGNOSTIC_SUMMARY.json、RTKLIB_DIAGNOSTIC_READOUT.md：确定、排除、未知三类结论；
- 原始 .trace、strace、完整分支明细、调用账本只存独立 scratch。

即使全部输出一致，本阶段只说明 **该固定版本、该数据、该配置** 的执行链。不能证明整数正确性、校准后的 false-fix 风险、唯一多径原因或另两序列等价；不会以此更换原比较结果或启动参数搜索。
