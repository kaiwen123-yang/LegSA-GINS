# 图 5(b)：这次改图具体在说明什么

原来把“所有原始估计”和“筛选后保留的估计”同时叠在同一条时间轴上。C-LAMBDA 与 C-WLS 在很多历元的估计又非常接近，因此四层散点互相覆盖。读者不容易看出颜色、空心圈和叉号各代表什么，也难以把输出减少与误差变化联系起来。

新版把两个方法分开，每个方法各画两个竖向分布：

- **Original**：原方法所有有参考支持的有效方向输出。
- **Added ratio screen**：同一批原始输出经过此前已固定的 ratio ≥ 3 工程筛选后保留的部分。

纵轴是绝对航向误差，越低越好。每个小点对应一个真实历元；水平方向的小幅散开仅为了避免覆盖，没有时间或性能含义。箱体下、上边缘为第 25、75 百分位，黑横线为中位数；须线按 1.5 倍四分位距延伸到实际样本，全部须外样本仍以点显示，未删异常值。两侧不是独立实验，而是同批数据在筛选前后的结果。

大幅机身运动记录中：

|方法|原始输出／全窗|筛选后输出／全窗|绝对误差中位数：前 → 后|
|---|---:|---:|---:|
|C-LAMBDA|1059 / 1350|269 / 1350|24.981° → 4.085°|
|C-WLS|1029 / 1350|253 / 1350|27.004° → 4.044°|

因此，这个面板先让人看见“筛选后典型误差降低了”，再同时看见“留下的输出变少了，而且仍存在大误差”。下方三场景 ECDF 再给出全部误差分布；本文蓝线与外部方向路线的精度、输出支持比较保留不变。

本轮只是重画已经完成的结果，没有重新运行 ratio 筛选，没有改阈值、选择窗口、接受状态或误差值。图 5(a)、80–100 s 转弯放大和(c–e)原数据与坐标范围不变。

## 更新后的图注补充

中文：(b) 大幅机身运动记录中 C-LAMBDA 与 C-WLS 的绝对航向误差，按原始输出和此前固定 ratio ≥ 3 工程筛选后的输出分组。全部有参考支持的历元逐点显示，箱体为四分位区间，黑线为中位数，须线按 1.5 倍四分位距定义；数字为输出数／完整评价窗历元数。水平抖动仅用于显示，未改变误差值。

English: (b) Absolute heading errors of C-LAMBDA and C-WLS on the large-body-motion recording, shown separately before and after the previously fixed ratio ≥ 3 screen. Every finite reference-supported epoch is plotted. Boxes show the interquartile range, black lines the medians, and whiskers extend to observations within 1.5 interquartile ranges. Samples beyond whiskers remain visible. Counts are outputs over all recorded evaluation epochs. Horizontal jitter is for display only.
