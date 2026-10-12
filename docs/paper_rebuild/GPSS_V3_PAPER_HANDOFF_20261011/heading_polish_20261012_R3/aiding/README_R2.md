# 航向主线正文精修 R2

图 6 保留已认可布局，只统一颜色；图 7 内容和样式完全保留，只提高预览分辨率；图 8 展示三个已完成质量条件的航向误差过程和全部九个变体；图 10 增加真实受扰方向输入与融合航向输出的直接对照。

所有投稿图宽 174 mm、最小字号 8 pt。图 6/7/8/10 高度分别为 174/204/205/210 mm。PNG 600 dpi；图 6/8/10 预览宽 3082 px，图 7 预览宽 3200 px。主方法蓝 `#2563EB`，基础加航向珊瑚 `#E76F51`，基础 GNSS/INS 蓝灰 `#5F6B7A`，关闭加权／倾角及原始方向观测紫 `#8B5CF6`，再配合线型。图 7 按作者要求保留原配色。

## 图 6：自然场景航向与倾角作用

![图6](preview/F06_heading_and_tilt.png)

(a–c) 完整航向误差；基础与基础加航向共享初始方向，两者用于说明持续方向更新。(d–f) 保留上一轮的局部：两条运动记录为 80–100 s 转弯；遮挡记录为 173.94–235.95 s 上下文，其中底色标实际 183.94–225.95 s 遮挡。它们均在新版图 3 更长的 60–120 s、163.94–245.95 s 上下文内。事件身份没变。(g–i) 关闭倾角与完整方法的 roll/pitch 整窗 RMSE，小收益按原值保留。

**英文图注**：Effect of sustained short-baseline heading updates in three recorded scenarios. (a–c) Full-window heading errors for basic GNSS/INS, the basic configuration with heading updates, and LegSA-GINS; all share the initial direction. (d–f) Original samples in reference-defined turning windows and the registered obstruction interval with context. These detail windows lie within the longer route intervals shown in Fig. 3. (g–i) Whole-window roll and pitch RMSE for the full configuration and its tilt-aiding ablation. No time-series smoothing is applied.

## 图 7：只提高预览清晰度

![图7](preview/F07_heading_retained_translation.png)

四种原投稿文件均保持原字节。上方三条状态线描述完整方法的位置观测、方向观测和机身辅助更新；左列全 GNSS 中断时辅助也暂停，右列方向与辅助更新继续。(a–b) 航向误差，(c–d) 同次 20 s 中断的位置误差和恢复校正，(e–f) 每个时长全部九个布置的整窗水平 RMSE。右列 20 s 整窗中位数 7.961→0.241 m；代表布置中断末端瞬时误差 88.007→1.377 m，二者统计范围不同。

## 图 8：三个真实质量条件与完整变体

![图8](preview/F08_heading_quality_scaling.png)

三列分别是：纯位置加噪（H σ3 m，V σ5 m）；方向噪声与乐观 std（原 σ10°、原行 std×0.25）；位置异常叠加 Doppler／接收机速度约 1 m/s 冲突。第三列与第一列包含共同坏位置成分，因此是三个已执行处理条件，不是三次独立外场验证。

(a–c) 每类首个保留配对时序的登记变体完整航向误差，RMSE 标注放在数据区域之外。(d–f) 三列统一放大 20–60 s 起始阶段，没有逐列按最大收益选窗。(g–i) 三类各自全部九个变体，空紫点关闭来源加权、蓝点完整，细线配对相同变体。

| 条件 | 代表例 RMSE：关闭→完整 | 各自完成集的中位数：关闭→完整 | 完成数：关闭／完整 |
|---|---:|---:|---:|
| 位置加噪 | 29.799→2.699° | 56.904→2.699° | 8/9；9/9 |
| 方向噪声与乐观 std | 1.731→1.631° | 3.042→2.643° | 9/9；9/9 |
| 位置与速度源冲突 | 28.277→2.703° | 56.250→2.703° | 8/9；9/9 |

各面板明确显示自己的纵轴范围，不用两列图的视觉高度代替改善数值。中位数属于各自完成集，不是同支持配对改善。缺失的一个关闭加权点是真实发散，未填 0 或任意 RMSE。两个完整方法大误差 55.8°、69.3° 在跨源冲突列突出保留，它们与上一轮图 10 是同一证据；其他原值也完整展示。

全部 513 个共同完成案例的航向与位置变化分布、同次位置加噪的实际来源倍率移至补图 `S_quality_complete_statistics`。541 个登记结果、六个额外完成及全部失败继续留在表中。代表位置加噪的位置 RMSE 仍为 3.166→3.557 m，不能将航向收益写成所有指标均改善。

**英文图注**：Heading response to three executed observation-quality conditions: position noise, degraded heading with optimistic uncertainty, and degraded position with a velocity-source conflict. (a–c) Full-window heading errors for the first registered variant with retained paired histories. (d–f) Original samples in the same fixed 20–60 s interval. Ordinates retain their labelled scales; the heading-uncertainty example has a modest benefit. (g–i) Whole-window RMSE for all nine registered variants. Open purple markers denote weighting off and filled blue markers denote full; lines join the same variant. The full configuration completes nine in every condition; weighting off completes eight, nine and eight. Missing numerical points denote actual divergence. Two large full-method errors are retained. The controlled variants share one recorded route and are not independent field trials.

## 图 10：由受扰方向输入到融合航向输出

![图10](preview/F10_heading_sensitivity.png)

上排 (a–c) 保留全部九个变体的原始整窗结果：方向中断 5/20 s、噪声 σ1/5°、±10° 尖峰概率 5/10%。零强度只有一条实际 clean 运行。点是各运行 RMSE，线连接中位数，不是置信区间。

中排 (d–f) **不再重复灰色基础配置漂移**，而是将原始受扰方向观测（紫色）与完整方法融合航向（蓝色）直接对照。原 `GNSS18.gnss` 仍实际保存在冻结运行配置指向的路径，读取后与 `V3_NATIVE_SUMMARY` 中三个原输入 hash 完全一致，没有重新生成任何 provider。

受扰输入直接连接到上一轮已经保存的 reference-heading 匹配时刻。第 0 列为接收机时间（s），第 13 列为 NED 机身 heading（deg），第 14 列为 std（deg），第 17 列为方向有效标记。参考继续采用此前保存的 `90°−ENU yaw` 展开角，误差为 wrap(input−reference) 至 [−180°,180°)。按原接收机时刻、六位小数键一对一左连接，不新增插值、不外推、不优化时移或旋转。

| 条件 | 评价窗全部输入行 | 有效输入 | 有效但原参考不支持 | 可评分 | 实际 GNSS 调度但未更新方向 |
|---|---:|---:|---:|---:|---:|
| 20 s 方向中断 | 1370 | 1270 | 1 | 1269 | 100 |
| σ5° 噪声 | 1370 | 1370 | 1 | 1369 | 0 |
| 10% 尖峰 | 1370 | 1370 | 1 | 1369 | 0 |

三个文件均为 1510 原始行、1370 窗内行，所有原始行和未评分状态保留。三个参考时间键匹配失败数均为 0。每类窗首 66.0 s 的一个有效输入沿用原来 `reference_supported=false`，没有强行补值。新派生的输入误差 RMSE 分别为 4.031°、6.689°、5.009°，属于本轮图层观测统计，不回写冻结导航评价结果，也不直接当作与高频输出共同支持的 RMSE 比值。

下排 (g) 为实际方向中断前 5 s、中断 20 s、恢复后 10 s；横轴相对于中断起点。100 条停更输入保持 NaN 和空白，没有跨缺口连接成有效观测。(h) 在预先确定的 80–100 s 参考转弯段展示噪声输入与融合输出。(i) 采用“评价开始 40 s 之后第一个已执行 ±10° 输入事件，起点前后各 5 s”的固定规则。逐时间点比较原 clean 与受扰 GNSS18，确认首个事件在 **42 s**，持续至约 43 s，显示 **37–47 s**。clean 输入 hash 与原 native 记录一致；1510 个时间点全部匹配，实际 150 个扰动行的角差为 ±10°，其余为零。事件选择没有读取参考或估计误差，也没有重建随机注入。完整输入差与选择规则保存在 `F10_D35_ALL_INPUT_DIFFERENCES.csv` 和 `F10_SPIKE_EVENT_SELECTION.json`。

原先已完成的 D30/D31 实际故障／前后阶段统计保存在 `F10_EXISTING_LOSS_AND_RECOVERY_STATISTICS.csv`；本轮没有新运行 evaluator。原始输入、运行记录路径、hash、角度约定、匹配计数和派生步骤在 `F10_OBSERVATION_MATCH_PROTOCOL.json`、`F10_OBSERVATION_MATCH_COUNTS.csv`、`prepare_retained_heading_observations.py`。源码中的三类受扰方向都是原 1 s 单元向 V3 输入延拓，不是新独立 5 Hz 随机试验。

**英文图注**：Heading accuracy and the relation between perturbed direction observations and fused heading. (a–c) Original whole-window heading RMSE versus interruption duration, angular-noise level and the registered probability of ±10° spikes; all nine variants are shown at each nonzero level and lines join medians. (d–f) Frozen direction-input errors and full-method heading errors for the first retained variant at the strongest executed level. Observation errors use an exact time-key join to previously saved reference matches without new interpolation, extrapolation or fitted alignment. (g) The registered 20-s heading interruption with 5 s before and 10 s after; the 100 unavailable observations remain blank. (h) The preselected 80–100 s reference-turn interval under noise. (i) The first executed ±10° input-change episode beginning after elapsed 40 s, found at 42 s by direct comparison of the original perturbed and clean inputs; the window spans 37–47 s. Event selection uses input values only. Input and fused output retain their native supports. No time-series smoothing is applied.

## 保留范围与检查

全部 5951 核心结果、2164 单开关配对及 283 个未完成记录继续保留。D29/D40/D55/D56 的无活动输入对照、D25/D28 的相同物理条件标记，以及 D51–54 的实际 RP/HV 分组保持已核实语义。

R2 没有新跑导航实验。但本轮图 10 新计算了输入相对既有参考的图层观测误差、支持计数及描述统计，不能写成“完全没有新增统计”。`build_heading_first.py` 只用保留数据重绘。新生成图在导出前经过 1.5 pt 容差的 panel-alignment gate，再检查 PDF 8 pt 字体下限和最终碰撞。原图 7 投稿文件校验保持不变，预览从其原 600 dpi PNG 生成。
