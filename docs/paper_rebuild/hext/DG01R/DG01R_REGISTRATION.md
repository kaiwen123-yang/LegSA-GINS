# DG-01R 计算前登记

日期：2026-09-27。起点 `0386675653e2f284e5df8e1f9c34ed3973d770c8`。本文件提交后才计算 R1–R3；不写预期结论，不按结果改定义。

## 输入和边界

`<W>` 为工作树，`<CLEAN_ROOT>`、`<RAW_ROOT>`、`<RTKLIB_ROOT>` 从本地 DATA_PATHS 配置解析；`<DG01>` 和 `<DG01R>` 分别为 CLEAN10_GNSS_RAW_DIAGNOSTIC 下同名目录。原始 12 文件在内容解析前与 DG01 原始输入 pin 核对。DG01 的 121 项输出 SHA256 已验证，保留全部原文件。RTKLIB 源码提交为 `180043ee24b6d2b168f98b64be15f69d50046b1a`，使用已有官方 convbin，记录二进制 SHA256 和源码树逐文件 SHA256；不编译、不改源码。

仅运行诊断 Python、官方 convbin 以及 Git/磁盘/访问审计等管理工具；导航算法、rnx2rtkp、LegSA、评估器、provider 调用均禁止。拒绝读取参考轨迹或路径包含 trace/.bag/.fpl 的文件。G: 仅写 DG01R；仓库仅写本登记目录、dg01r_*.py 及 AGENTS 末尾。图缓存仅用本地配置 hx02_scratch 的同级 DG01R，结束删除任务创建文件。单线程；无随机抽样、无调参。所有明细/原始行例子留 G:，仓库汇总不超过 20 MB。

| 序列 | base_time UTC Unix s | 闭评估窗 s |
| --- | --- | --- |
| BY2 | 1772784000 | [66,340] |
| BY2H | 1772784000 | [413,683] |
| BY2O | 1772780400 | [3186,3563] |

## R1：只变卫星几何，保留既有配对和 pivot

直接以 DG01 FRACTIONAL_DD_DETAIL 每一行的 time/gnss/signal/frequency/sv/pivot/fix_group 为身份集，不重选 pivot，不增加卫星、不补入新星历。复用其 HP 时间关联及 RAWX 观测；先独立重现 DG01 raw_cycles，最大绝对差须小于 1e-6 周，否则停止并排查实现，不发布误配结果。旧值记 R0，不覆盖。

对每台接收机取对应 HPPOSECEF 的同整数 iTOW NAV-CLOCK clkB（单位 ns 转 s）。缺同标签时，仅在两侧 CLOCK 标签夹住目标、间隔不超过 1 s 时线性插值；不外推，不跨大间隔。逐接收机记录 exact/interpolated/missing 数，缺任一侧时保留身份和不可计算原因。R1/R2 使用相同可计算身份；R0 全量和与 R1 相同身份的 R0 另列分母。

接收时刻为各自 RAWX rcvTow−clkB_i。每台接收机、每颗卫星独立求发射时刻：以原始伪距/c 初始化传播时长，在该接收时刻下按广播轨道及地球旋转计算卫星位置，再以到固定 HPPOSECEF 的几何距离/c 更新，固定四轮迭代。这里不能把含接收机钟差的原始伪距直接再减一次当作已校正传播时间。广播轨道模型与 DG01 相同，唯使用各自的接收/发射时刻；不估计卫星或相位偏置，不改变接收机位置。

题述“0.2 s 内自身运动 ≤1.2 mm”暂作为任务给定、未独立验证的忽略运动假设，不能称为实测事实；单位若经作者澄清，在报告明确记录。本任务始终保持 HPPOSECEF 不变，不读参考验证该假设。

令 rho_i,s 为各自时刻几何距离，R1 未包裹残差为 ((rho_2,s−rho_1,s)−(rho_2,p−rho_1,p))/lambda−[(Phi_2,s−Phi_1,s)−(Phi_2,p−Phi_1,p)]。包裹 x−ceil(x−0.5)，范围 (−0.5,0.5]。统计列沿用 DG01：n、mean、median、P05/P95、SD(ddof=1)、min/max、P95(abs)、abs>0.25 比例、圆均值/圆离散；按序列/信号/波长/fix_group 分开。

Delta_clk=clkB_2−clkB_1 对完整成对 RAWX 历元和 D4 实际身份历元分别给中位/P05/P95/最小/最大/最大绝对值，单位 s 与 ms。估计钟差的一阶 DD 影响 abs((range_rate_s−range_rate_p)*Delta_clk)/lambda：在固定接收机位置上，以接收时刻 ±0.05 s 的几何距离中心差分计算 range_rate；逐行保留，报告最大值，不将此近似替代完整 R1。另保留双接收机 clkB 均设零的几何对照，以区分独立发射时刻实现与钟差项；它不成为择优版本。

## R2：半周标志，两方案平行

从 DG01 INTER_DETAIL 读取完整两机共同观测，逐 (历元,卫星,信号) 保留原 tracking 字节及 cpValid(bit1)、halfCyc(bit2)、subHalfCyc(bit3)。完整共同集、D4 非 pivot 行、D4 的独立 sv/pivot 端点集分别报告组合数量及两机 subHalfCyc 不同的比例，分母不能混用。

R2a 在 R1 上剔除 sv 或原 pivot 任一端的两机 subHalfCyc 不同的 DD 行；不更换 pivot，不重新匹配。R2b 对每一原始相位的 subHalfCyc=1 侧加回 0.5 周，再按同一 DD 符号求残差；因此相位 DD 增量为 0.5*((sub2_s−sub1_s)−(sub2_p−sub1_p))，几何不变。原 cpValid/halfCyc/cpStdev 资格不变，不恢复已无效观测。两套结果均发布，不选择更窄者当最终方法结果。

固定直方图范围 [-0.5,0.5]，步长 0.025 周。GPS L2C sigId=3 的边界峰占比定义为 abs(wrapped)>=0.45 周，分母为该版本有限 DD 行数；分别给正端、负端、两端总数。另给最大连续两个箱（0.05 周，首尾周期相接）的质量占比作为窄峰描述量，不设优劣阈值或触发重跑。

## R3：原样 UBX 与 convbin RINEX

按 DG01 消息清单使用的导出 raw CSV Time−base_time 闭窗提取全部以 UBX sync 字节开头的消息，保持原顺序、原字节；不修改 checksum/标志，不附加窗外热启动帧。NMEA 不进入 UBX 文件。长度/checksum 失败仍原样交给官方解码器，并另计数；记录每文件帧数、类型计数、字节数和 SHA256。RINEX 窗口统计再按观测 GPST 转 UTC 裁窗，因此与消息到达窗可能有端点差别，显式报告。

每序列每接收机仅一次数据转换，共六次。固定命令模板：`<convbin> -r ubx -v 3.04 -f 5 -od -os -o <DG01R>/CONVBIN/<SEQ>_R<r>.obs -n <DG01R>/CONVBIN/<SEQ>_R<r>.nav <DG01R>/UBX/<SEQ>_R<r>.ubx`。默认全系统和全信号 mask；-od/-os 显式包含 Doppler/SNR，-f 5 为源码默认频段数，不加 -halfc、-TADJ、-y、卫星排除或任何门限。确切 argv、返回码、stdout/stderr、二进制身份及 openat/execve 审计留存。若编译能力限制了系统/信号，报告限制而非修改源码或另选版本。

以 GPST 日历时间舍入到 1 us、卫星标识、RINEX 信号后缀（如 2L）精确 outer join；不最近邻补配、不换信号名称。只比较两侧都有值的字段，缺值单列；观测集按至少有一个 C/L/D/S 非空字段定义。分别输出全提取结果和评估闭窗，主汇总使用闭窗。

伪距差=convbin−bridge（m），输出零/非零、最大绝对差；相位差同方向，原始差与 x−ceil(x−0.5) 小数差均保留。按 RINEX 0.001 周印刷精度，zero=abs(frac)<=0.0005，half=abs(abs(frac)−0.5)<=0.0005，其余 other，三类互斥。比较 LLI bit0、bit1（空白按0，观测缺失不当0），S 字段数值差及 L 字段信号强度指示位另列。仅一侧存在的信号/各字段计数、历元集合差分别列出。差异不设硬停，不据“应为0”强制覆盖。

每个非零差异类别按序列、接收机、信号、时间、卫星稳定排序保存前20样本，给两侧文件/行号、原始历元行、原始卫星行及字段 token；缺失一侧明确 null。LLI两个位、SNR、SSI、单侧观测/字段、历元差均有独立类别。导航文件按 RINEX 每条星历块首行系统计数，保留系统与 Galileo 可用性；全文件数与 toe/toc 在窗口内的数量不混称。

## 展示与收尾

SFIG-DG2R：174 mm，PNG 宽至少4096，PDF/SVG；每信号一行，列为 R0/R1/R2a/R2b，R0/R1 相邻；三序列用固定色/线型，both-fixed 与 other 分页或独立面板说明，汇总不删 other。使用 style.py/qa.py 并实际看 PNG。缺失/不可计算计数明确列出。报告只陈述事实；HX-07 建议仅列用户指定条件，不执行后续导航或星座变体。两个提交后 push，29 条既有未跟踪路径及哈希前后相同，scratch 清空。
