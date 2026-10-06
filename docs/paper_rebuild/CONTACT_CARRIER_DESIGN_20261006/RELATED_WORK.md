# 针对性文献核查

访问日期 2026-10-06。以下来自原论文、出版商或作者研究机构。
区分全文/可见正文和摘要；不声称穷尽检索、作者代码复现或新颖性已经成立。

| 编号 | 原始来源 | 本次读取范围 | 对方案的约束 |
|---|---|---|---|
| R1 | [Giorgi et al., 2010, Enhancing the Time-To-Fix ...](https://www.ion.org/publications/abstract.cfm?articleID=8938) | 出版商摘要 | 已有将天线几何约束嵌入整数搜索的MC-LAMBDA；固定长度加AR本身不是新贡献 |
| R2 | [Zhu et al., 2014, The Inertial Attitude Augmentation ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC4168469/) | 公开正文与公式 | 已有惯性推导基线、先验协方差和失败率框架；“IMU辅助固定”不能单独声称首次 |
| R3 | [Multi-sensor Attitude Estimation using Quaternion Constrained GNSS Ambiguity Resolution and Dynamics-Based Observation Synchronization, 2024](https://link.springer.com/article/10.1007/s40328-024-00441-2) | 出版商可见正文/摘要 | 已有动态平台约束和观测同步；平台换成足式机器人不足以形成方法差异 |
| R4 | [Hartley et al., Contact-Aided Invariant Extended Kalman Filtering for Robot State Estimation](https://arxiv.org/abs/1904.09251) | 作者摘要；另核[RSS2018原论文](https://www.roboticsproceedings.org/rss14/p50.pdf) | 足端接触运动学与惯性融合已有理论；无绝对参考时位置及绕重力轴旋转不可观 |
| R5 | [Integer estimability in GNSS networks, 2019](https://link.springer.com/article/10.1007/s00190-019-01282-6) | 出版商可见正文 | 整数可估函数和合法基变换已有理论，不能将pivot重参数化本身包装为新方法 |
| R6 | [GNSS Odometry: Precise Trajectory Estimation Based on Carrier Phase Cycle Slip Estimation](https://arxiv.org/abs/2312.02424) | 作者摘要 | 载波周跳估计用于机器人里程计已有相关路线，需要与本课题的双天线/独立运动约束区分 |
| R7 | [Leg-KILO, 2024](https://ieeexplore.ieee.org/document/10631676/) | 出版商摘要 | 足式接触约束和高度波动处理已有工作；需以具体误差模型和验证区分 |

候选对应的相邻工作：C2/C8 对应 R4、R7，并由 R2/R3/R6 界定其与载波模块的区别；
C5 对应 R1、R2、R3、R5、R6；C6 对应 R1、R2、R3、R5、R6；
C7 对应 R2、R3、R4、R5、R7，相关性机制仍需单独定向追踪，当前引用不证明某种新融合公式已成立。

本次证据足以否定“独立速度+惯性辅助AR+EKF的组合必然新颖”；
不足以证明下面提案是首次。新增贡献必须落实到失效处理、信息复用边界及可证伪验证。
