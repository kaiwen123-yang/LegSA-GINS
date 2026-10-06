# 建议段落结构：观测机制、作用量级与失效条件

本结构面向 GPS Solutions 的完整正文。TIM 不宜仅通过增加通用不确定度传播公式另立同一套方法新颖性；若作者保留 TIM 目标，应补实际测量特征辨识与验证后再改其主线。所有数值来自原 V3；方法读者标签使用 Proposed/完整配置、基础 GNSS/INS、gated+RV 骨架、no RP/no HV/no RD/no SA，内部代码映射放 SI。

| 段 | 所在部分 | 本段必须回答的问题 | 具体证据/公式 | 结束时引向下一段 |
|---:|---|---|---|---|
| 1 | Introduction | 为什么低速/停步机器人需要独立于速度方向的航向？ | 约0.35m安装、低速时速度方向不等于body方向 | 小基线方向进入导航器有何难点 |
| 2 | Introduction | 本文处理的是哪一层输入和哪两种信息失效？ | 接收机position/status→direction；HV需direction转换 | 与原始载波算法的实际区别 |
| 3 | Related work | 最近的两接收机滤波与AR方法怎样处理信息？ | Pavlasek absolute+relative joint covariance；Teunissen integer search；Farkas同步约束 | 明确本文未解决什么，并指出具体研究问题 |
| 4 | Contributions | 两个可检验问题是什么？ | RP是否改善tilt；HV是否只在heading-retained loss有效 | 直接列方法接口及三个量化结果，不堆矩阵规模 |
| 5 | Setup | 哪些设备、点和时间流被观测？ | 原安装照片/frame/约0.35m；GNSS1/2、bodyIMU、SDK、共享reference角色 | 15-active-state估计器 |
| 6 | Estimator | 状态、传播、位置/速度leverarm如何定义？ | conventional error state，P、RV两个模型及同物理点说明 | 第二接收机方向观测 |
| 7 | Heading observation | 两位置何时成为标量航向？ | exactiTOW、fixed状态、投影atan2+90°、wrapped residual | 资格和工作噪声 |
| 8 | Heading admission | normal/soft/reject怎样改变更新？ | σfloor.5；strict3/6与hard6/15；softR×2.5 | 该观测如何支持SDK辅助 |
| 9 | Robot tilt | RP到底是哪个量、什么噪声和资格？ | SDKroll/pitch二轴先验，实际工作noise/tmatch写SI | HV除了SDKvelocity还依赖什么 |
| 10 | Robot velocity | 如何旋转SDK弱估计、何时失效？ | 原Ĉ/kHV/M/Hprojection；preparedA1support；不等同腿FK | 原调度与完全失去GNSS条件 |
| 11 | Dependency graph | 准备资格和运行时GNSS入口分别是什么？ | enabled-validP/RV/yaw→dispatch；D61/D62 surviving channels | 解释为何需要信息损失对照 |
| 12 | Source policy | 正式工作R倍率如何计算和限幅？ | score/α/cap小表、boundedmax、只放大R | 实验与模型参数迁移 |
| 13 | Dataset/design | 哪些记录用于拟合，哪些用于转移检验？ | BY2拟合、H/O相同hyperparameter；作者开发声明；回顾选择单列 | 同一参考和输出点合同 |
| 14 | Evaluation | 实际评价量是什么？ | matchedsupport RMSE、midpoint/refshared、失败NA、不独立epochs | 内部比较配置 |
| 15 | Controlled design | 如何避免把多开关变化说成单模块？ | F02→F03jointbranch；F04/A03/A04/A05/A06单flag；CORE+ADD完整形状 | 自然结果的作用范围 |
| 16 | Natural results | 航向输入在自然记录上改变了多少？ | 全F01/F03/full三序列H/yaw/support；F03接近full、O不处处占优 | 单变量姿态结果 |
| 17 | RP results | 最稳定的模块作用是什么？ | 519roll/pitch全降低，中位−1.072°/−.664° | SDKvelocity常规影响与故障影响 |
| 18 | HV CORE | 普通受控条件效应大还是小？ | H中位−1.119mm/均值−10.651mm；Up+0.004mm微小 | 更关键的条件式故障收益 |
| 19 | ADD results | 丢平移但保留heading时发生什么？ | D62 10/20s各9；20s全窗7.961→.241m、pairedmedian−7.750m | 反例是否吻合资格链 |
| 20 | ADD negative | 同时失去heading为何不具有独立outage odometry？ | D61全部10/20/30s各9；20s10.301→10.292m；原调度资格 | 不把模块累加当普遍提升 |
| 21 | SA/RD results | R政策改变完成还是精度？ | SA519vs513、common513Hmean/mediantradeoff；RD中位.145mm | 外部输入路线比较 |
| 22 | External comparison | 最接近方法与较远路线如何合理解释？ | IEKFsame-outputroute；RTKfreshsupport；FGOstrict/segmentedpoint/input | 归纳适用机制而非跨输入排行榜 |
| 23 | Discussion | 这些效果如何由信息链解释？ | RP直接限制tilt、heading-supportedHV约束translation、allloss不可dispatch | 独立测量与泛化边界 |
| 24 | Limitations | 哪些影响物理准确性/泛化仍未知？ | sharedreference、SDKframe/POI、clock/installation、singleinstallation；R不是U | 为后续试验列少量明确动作 |
| 25 | Conclusion | 读者应带走哪三项已证实发现？ | 自然yaw范围、RP量级、D62/D61对照及条件 | 一段完成，无软件历史或新AR承诺 |

## 主文、SI 与可复现资料分工

- 主文保留能理解观测的式子、实际参数、基线角色、三条主要量化发现以及一组负对照。
- SI 提供11配置的代码映射、全部33自然结果、28配对指标、45ADD case、全矩阵失败与完整外部输入/支持表。
- 可复现资料提供原科学源/二进制/evaluator身份、路径索引、原tokens与只读汇总脚本；主文不以提交次数、收据数或全仓扫描数当科学贡献。
- 若已有图需要 map、时间序列或姿态图，使用原冻结输出；不重新挑最好片段、最佳偏移或调参以改善RMSE。

## 原V3指标的正文用语约束

1. 使用“相对融合参考的 agreement/discrepancy”；没有独立truth不能把全部RMSE称为独立准确度。
2. D62称“translation-observation loss with heading retained”；D61才同时失去heading。
3. ADD三种duration是原固定274s窗口的whole-windowH-RMSE；不要替换成in-fault、endpoint、recovery或后来135指标。
4. RP/HV/RD/SA配对以各自common-completed519/519/518/513为分母；失败会员另外保留，不能忽略它们后声称全部541改善。
5. “median paired difference”与“difference of medians”分开，mean/median与majority方向分开。
6. 原CORE541包含1clean+60×9controlledplacements；588cases、6468runs是矩阵规模，不是588独立采集或6468独立配置设计。
7. F02→F03是RV、heading处理与algorithmbranch的联合结构差；只有明确单flag对照可用于相应组件归因。
8. 未识别的SDK速度融合机制/POI/时钟项是讨论和后续验证问题，不借通用公式直接宣称完成measurementuncertaintycalibration。
