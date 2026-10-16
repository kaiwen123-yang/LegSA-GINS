# 本轮文献图形阅读与采用方式

本地目录34份PDF，去重29种文件内容，建立逐页文本与图号索引。这里只记录实际参与图形设计的选读，不声称逐字审完全部29篇。

| 本地文献/素材 | 实际借鉴 | 用于本轮图 |
|---|---|---|
| 作者提供的PADP截图 | 原创机器人线稿、少量颜色分组、简明信息流；不复制算法内容或机械臂 | 1、2 |
| Hartley Contact-Aided Invariant EKF，1805.10410v1 | 实物图与坐标系标注、不同初始方向的结构验证 | 1、4 |
| Constrained MEMS-Based GNSS/INS…，第7–9页图8–11 | 同一时间轴、明确中断区间和局部放大 | 6、7 |
| A Robust Adaptive Extended Kalman Filter…，第16/18页图14–17 | 全时序与局部差异、代表过程和汇总的分工 | 6、8 |
| Factor graph optimization for GNSS/INS…，Fig.5/8 | 完整路线与局部定位误差联系 | 3、9 |
| On the Recursive Joint Position and Attitude…，Fig.7 | 姿态/位置分量和算法配置比较 | 3、9 |
| Constrained Wrapped Least Squares，Fig.9–10 | 方向误差分布与接受/输出含义 | 5 |
| GPS/BDS Dual-Antenna Attitude Determination…，Fig.8等 | 观测层、固定状态与精度分开呈现 | 5 |
| Teunissen compass/ILS理论文献 | 模糊度处理与方向候选的术语、测量层定义 | 5 |

实际采用的原则：每组图一个问题；路线与误差共用事件；标量汇总和时间过程互补；对照关系可直接读；完整失败/覆盖在旁表保留；使用当前硬件和输入结果，而不是复刻文献中的优势结论。

文献PDF和页面渲染只保留本地。Git中仅发布目录/图号索引、上述阅读说明及自行生成的图件。

GPS Solutions图形要求已核对：常规Arial/Helvetica字8–12pt；组合图600dpi；EPS/TIFF为首选格式。图1/2的image原生分辨率限制另见`schematics/IMAGEGEN_RECORD.md`。定量图实际检查最终尺寸、字号、对齐和碰撞。

官方来源：https://link.springer.com/journal/10291/submission-guidelines ，核对日期2026-10-11。
