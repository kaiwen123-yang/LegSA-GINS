# 三个描述性暂名及统一术语

**推荐先使用候选A的描述性全名，不急于发布新缩写。** 归档正式名称LegSA-GINS、所有方法/结果代码ID继续保留。本目录的候选不是已获作者确认的新正式名；PPT可用中文描述性题目，下角标注明“归档名LegSA-GINS；正式名称待讨论”。不存在为名称拟合数据或更换算法的步骤。

| 候选 | 英文方法描述 / 可选缩写 | 中文 | 数学与输入依据 | 表达风险 |
|---|---|---|---|---|
| A，推荐 | Status-qualified dual-antenna GNSS/INS / SQ-GINS | 状态筛选的双天线GNSS/INS | exact iTOW、BOTH_FIXED、wrap残差及有限R膨胀，使航向更新具备明确准入 | qualified是规则准入，不能解释成已校准正确率；dual-antenna实际是两个位置接收机解 |
| B | Heading-conditioned, robot-velocity-aided GNSS/INS / HRV-GINS | 航向条件下的机器人速度辅助GNSS/INS | SDK HV=Π_H Ĉ k v；Ĉ含A1航向与SDK倾斜，失去heading或GNSS入口时不独立续桥 | 重点突出条件速度；不能把A1投影角称所有倾斜姿态下的Euler yaw，也不能暗示独立腿式里程计 |
| C | Covariance-weighted dual-antenna GNSS/INS with robot-reported velocity / CW-GINS | 机器人报告速度辅助的协方差加权双天线GNSS/INS | R′=aR，1≤a≤cap；receiver/RD/RP/HV进入一个标准ESKF | 权重自身不是新鲁棒估计理论；长名不利图例，简称可用Proposed而不强造缩写 |

候选A最贴近核心操作对象与当前GPS路线，B最能提醒辅助的实际条件，C用于作者想强调融合结构时。没有做全球缩写/商标唯一性检索，故缩写只是内部讨论建议。避免Leg-…/Kinematic-…暗示本文处理真实关节/接触FK；避免Ambiguity-resolved…暗示主方法内部做整数解；避免Robust/Integrity/Uncertainty-calibrated…超出现有验证。

## 图表统一名称规则

主图完整配置一律先标**Proposed**，图注首次写“Proposed denotes the archived LegSA-GINS configuration; the descriptive name is provisional.” 若作者决定保留LegSA-GINS，可一次性替换这层display label，代码映射不变。内部11方法及30外部身份见两份CSV。无合法性能比较资格的注册行只放SI注册索引，不在主图造一个论文方法名。

定义 Receiver velocity = PVT-derived GNSS1 RV；Doppler velocity = raw-Doppler-derived RD；Robot horizontal velocity = SDK高层HV；Robot tilt prior = SDK roll/pitch RP。RP不是绝对roll/pitch truth，HV不是独立contact odometry。SA统一写**Covariance inflation**或**Source-aware covariance inflation**，不写“七种鲁棒算法集成”。七个QA11E形状是模块analogue，未作为正式默认分支。

角量统一区分 **baseline-projection heading**（固定天线差的水平投影加90°）、**estimated Euler yaw**（原V3姿态输出）、**reference yaw**（商业融合输出）。低倾斜安装近似使前两者接近，但不自动全姿态等同；near-vertical projected heading无定义。诊断新投影模型和后结果guard不得回贴到原V3或旧EXT执行身份。

“Single receiver”只在在线更新层说明；所有原内部基线共同用了双接收机初始化。EXT05C必须带“dual-receiver initialization”注释，不能在读者名中隐去。IEKF配置分开作者算法核心与项目参数。OiSAM strict continuous与segmented diagnostic必须分别标；分段初始化增加信息，不能改称严格同一长序列无重启。

## 可直接使用的题目（均待作者确认）

A，GPS优先：**Status-qualified short-baseline dual-antenna GNSS/INS for quadruped navigation**。

B，突出信息依赖：**Conditional heading and robot-velocity aiding for short-baseline GNSS/INS navigation**。

C，TIM讨论稿：**Measurement admission and conditional velocity aiding in a compact dual-antenna GNSS/INS system**。此题目不能替代TIM所需测量创新、不确定度与安装验证；若没有补强，不能仅换题目就宣称TIM-ready。
