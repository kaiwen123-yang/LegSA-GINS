# 图 5：短基线方向观测的航向误差与输出支持

## 中文图注

**短基线方向处理路线在四足机器人记录中的航向误差。** (a) 大幅机身运动记录中的位置产品衍生方向输入、原生更新实际采用的方向以及 RTKLIB 默认动基线输出；右侧放大图对应与图 3、图 6 相同的 80–100 s 参考确认转弯，未按方法误差选择。(b) 同一记录的 C-LAMBDA 与 C-WLS 原始估计，以及本研究额外施加成本比筛选后的输出。细点表示原始结果，青色空心圆与紫色叉号分别标记两方法经过筛选保留的结果。(c–e) 三条完整评价记录上绝对航向误差的经验累积分布。主轴展开 0–15° 精度范围，内嵌图显示完整 0–180° 范围，纵轴均为 0–1。对 C-LAMBDA / C-WLS，虚线表示原始估计，实线表示项目新增 ratio ≥ 3 筛选；阈值在生成全部接受状态之前固定，未使用参考误差调节。下方给出新输出数和完整评价窗历元数，箭头表示筛选前后数量。曲线只使用有参考支持的有效输出，未跨缺测保持或插入估计。DD-KF 展示其原生 ratio 接受的结果，RTKLIB 其余三种配置见完整配表。比较对象是同批实测记录上的不同方向处理路线；蓝线是采用的方向观测而非融合后的姿态输出。

## English caption

**Heading errors of short-baseline direction-processing routes on the quadruped recordings.** (a) Position-derived direction before and after native update selection, together with default RTKLIB moving-baseline outputs, during the large-body-motion recording. The adjacent detail shows the reference-defined turn at 80–100 s, shared with Figs. 3 and 6 and selected independently of estimation errors. (b) Original C-LAMBDA and C-WLS estimates on the same recording and outputs retained by an additional project-defined cost-ratio screen. Small points denote original estimates; teal circles and purple crosses identify retained C-LAMBDA and C-WLS outputs, respectively. (c–e) Empirical cumulative distributions of absolute heading error over each full evaluation interval. Main axes show 0–15°; insets show the complete 0–180° range with the same 0–1 cumulative scale. For C-LAMBDA and C-WLS, dashed curves denote original estimates and solid curves the added ratio ≥ 3 screen. The threshold was fixed before all acceptance masks were generated. Counts below the panels give new outputs over all recorded evaluation epochs; arrows indicate counts before and after screening. Distributions use finite reference-supported outputs, without holding estimates across gaps. DD-KF uses its native ratio acceptance; the other three RTKLIB configurations are retained in the accompanying table. These are direction-processing routes with their original input and validity conditions. The proposed curve shows used observations, not the fused navigation attitude.

## 子图怎么读

### (a)：先看本文的实际方向观测

灰蓝细虚线是有效方向输入。约 205 s 的较大异常在完整图中保留，蓝色采用观测没有跟随该异常。橙色方点是 RTKLIB 默认动基线的固定输出；有些时段精度接近本文，有些输出偏差较大，很多时刻没有新输出。80–100 s 转弯放大图显示，两条路线在实际转弯中的小误差和输出稠密程度；它既不是最优差距窗口，也没有把未输出时刻填成零误差。

### (b)：新增接受层到底做了什么

原来的每个候选仍显示为细点。新增成本比筛选只保留最佳答案明显优于第二个不同整数答案的历元，对已经不收敛/搜索失败的历元不作补救。圈或叉是这一步保留的实际估计，没有重新改变方向。

读图可见筛选减少了候选数量，却仍保留了部分大误差。其含义是“这条固定工程规则在当前输入上能筛掉一部分历元，但不能保证剩余整数正确”。这不再是以没有接受步骤为理由解释原结果，也不是事后从参考中挑选正确样本。

### (c–e)：正文主张首先落在航向误差上

横坐标是绝对航向误差，纵坐标是该方法有参考支持输出中，误差不超过此值的比例。蓝线在这三个记录上更快接近 1，表示采用的方向观测更集中在小误差范围。橙线部分时段的精度也很好，但其全窗输出数少。青、紫曲线说明新增 ratio 筛选改善了部分记录上的误差分布，同时减少了支持；原始估计用虚线完整保留。

曲线均为历元分布，不是跨独立实地重复的置信区间。输出数与评分数不完全相等：本文采用观测数 1348 / 1334 / 1586，对应有限参考支持评分数 1348 / 1333 / 1582。

## 本图可写入正文的结论

在本次短侧向基线四足机器人记录中，位置产品衍生方向结合既有观测选择形成了误差较小、输出较连续的方向观测流。直接原始载波方向处理经过明确的成本比筛选后，在部分场景中获得精度改善，但仍有较大误差与支持减少。因此，图 5 支撑本平台上方向观测路线的选择，图 6 再检验这些观测是否实际改善融合航向。

所有方法的物理量仍沿用已保存定义：原始双天线路线输出是侧向基线的水平投影方位经固定安装转换，离线参考是商业融合 Euler yaw。处理输入、有效时刻和姿态表示不应被写成完全相同的模糊度求解器竞赛；确切同时间支持的原始方法配对指标见 `COMMON_SUPPORT_COMPARISON.csv`。
