# 部分方向域与更新前共同姿态先验

本次读取全部 117 条 partial，包含 41 条双分量域；更新前 prior 覆盖 117/117。native 已接受 106 条，但接受结果不参与样本筛选。本读出新增 native 0 / evaluator 0，未读取 reference 或进行 Monte Carlo。根任务此前只执行了唯一一次诊断 native（1 native / 0 evaluator），并确认新旧五份状态、偏置和 STD 输出全文件字节相同；新增日志没有改变这次实际导航轨迹。

## 双分量结果

**41/41 双分量事件均只有一个分量未被当前共同先验排除；没有双分量事件的两个分量都被排除。** 在这批输入与现有 Gaussian 先验工作模型下，不支持继续实现多分支后端。本批多分支工程到此停止；这一结论不永久撤销原候选，也不推广为其他数据中的分量概率保证。

| 量 | 最小 | 中位 | 最大 |
| --- | ---: | ---: | ---: |
| 41 个远弧的必要姿态旋转 (deg) | 85.331308 | 88.794031 | 89.999240 |
| 全 117 条的 99.9% 椭球外包半径 (deg) | 0.815657 | 0.932272 | 1.930753 |
| 41 个远弧先验质量上界的自然对数 | −94682.443882 | −38276.638646 | −16763.788533 |

全体 117 条中，115 条至少有一个域未被排除；另外 2 条都是单分量域与先验不相容，未删除。它们也被原生 NIS 门拒绝：

| source index | time (s) | 必要旋转 (deg) | 椭球半径 (deg) | 原生 NIS | 原生结果 |
| --- | ---: | ---: | ---: | ---: | --- |
| 649 | 3315.99799990654 | 3.840047 | 0.878041 | 16.401559 | NIS_3DOF_REJECT |
| 651 | 3316.3980000019073 | 1.203839 | 0.880263 | 12.817530 | NIS_3DOF_REJECT |

完整输出含 117 行事件与 158 行分量。一次集中数学核对（非零误差均值、各向异性 P、超过 90° 的远弧及 log-tail 稳定性）已通过；结果在 PARTIAL_DIRECTION_PRIOR_MATH_CHECK_01/CHECK.json。该核对是 synthetic-only，不是导航性能证据。

prior_state_time−event_time 的 min/median/max 为 {'min': 0.0, 'median': 0.0, 'max': 0.0} 秒，精确 bits 相同 117/117。实际 exact-event 代码先传播到事件，再设 timestamp_=event_time 后 gnssUpdate（gi_engine.cpp:797–823）；这里汇总实际差，不从标签预设为零。

固定 99.9% 置信判据；连续上界保存在每弧表中。弧序号保留原顺序，near/far 只按必要旋转距离排序。若两个弧都远，标为 prior/domain 不相容；不能自动认定近弧正确。没有排除也不证明两个后验模态，不能据此永久撤销候选或新增算法门。

## 计算合同

原误差图表 phi~N(mu,P)；使用 Exp(mu) C_nom r 构造图表中心。未假装把非零 mu reset 后仍沿用原 P。每条源 anchor 来自冻结模型 PLAN 的 anchor_ecef_m（原始 GNSS code anchor，非参考）；先由当前 nominal BLH 的 NED 转 ECEF，再投到源 anchor 北/东/下轴。角是侧向基线 atan2(E,N)，不是机体 Euler yaw。nominal p 固定，未积分位置随机性或 p/phi 相关项，因此不是完整联合状态概率。

每弧允许全部高程，故所得球面最短角 d 是触及原域的必要旋转下界。令 delta 为中心方位至弧的最小环形距离，中心单位基线=(rho*cos(theta),rho*sin(theta),z)。delta<=pi/2 时 d=asin(rho*sin(delta))；否则 d=atan2(rho,abs(z))，最优点在极点闭包。对所有 phi，SO3 的 Exp 映射满足 d_SO3(Exp(phi),Exp(mu))<=||phi-mu||。置信椭球又满足 ||phi-mu||<=sqrt(lambda_max(P))*sqrt(q2)，故弧内先验质量至多 SF_chi2_3(d*d/lambda_max(P))。该界有意忽略椭球方向和 RP 高程限制，保守但无大规模数值积分。log SF 用闭式 logaddexp 稳算；数值列若低于最小 normal double 则向上截断，真实量级仍由 log 列报告，未输出伪精确零概率。

这里对给定域计算原高斯 prior 质量的上界，没有把 RP/重力/gyro 域作为独立 likelihood 相乘。域是使用相关来源获得的几何外覆盖，输出既不校准 prior，也不是 posterior mode probability。足端、SDK 和此前载波对共同状态的作用已包含在实际 P 中，不另叠 foot prior。保留域外质量，不把两个弧归一化为总概率 1。

## 产物

- 事件表：/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/PARTIAL_DIRECTION_PRIOR_READOUT_01/PARTIAL_PRIOR_EVENTS.csv
- 每弧表：/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/PARTIAL_DIRECTION_PRIOR_READOUT_01/PARTIAL_PRIOR_COMPONENTS.csv
- 身份、全分母与汇总：/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/PARTIAL_DIRECTION_PRIOR_READOUT_01/SUMMARY.json

本次仅为是否值得研究多分量后端的诊断；不能作为新的测量、质量门、整数正确性或候选撤销依据。
