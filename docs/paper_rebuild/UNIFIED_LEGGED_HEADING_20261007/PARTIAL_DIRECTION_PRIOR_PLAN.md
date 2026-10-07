# 部分方向域与真实共同先验：一次事件诊断计划

2026-10-07，起点 `57821fc`。上一轮向量信息类型修正已经完成，本阶段不改变观测、噪声、门限、源策略、共同状态或支撑重放。仅补旧保存数据缺失的载波更新前真实共同先验，以回答 41/117 个双分量物理域是否仍有第二段被先验支持。

## 运行与输入

只用原 BY2O VECTOR 完整窗 [3186,3563] s，同一 foot XY、ROLLING carrier、SDK、初始化与全部 provider。只执行 1 次新增日志 binary native；旧 VECTOR 作为现成状态对照，不再运行；evaluator=0，reference opens=0。不以这次日志采集再次宣称精度收益。

复用已有 runtime runner 与配置逐行克隆，仅修改 run_id/run_label/case_id/outputpath；读取新旧 YAML 的科学键必须相同。新输出独立保存，旧 binary/NAV/评价与原始输入均保留。对照五份既有输出 NAV×2、STD×2、IMU error 的完整字节，验证日志未改变状态历史。若不同，检查实际原因，不用误差阈值掩盖差异。

## 事件截面

在 external 三维载波模型构建成功后、当前 carrier hard-NIS/QA/SA/EKFUpdate 前，记录精确事件时刻与稳定序号/identity、nominal Cbn/BLH/body baseline、条件 dx_phi 和完整 P_phi_phi，并保存位置误差均值与 Ppp/Pp_phi 供固定位置近似审查。后被当前门拒绝的可用 carrier 也记录。此时先前 foot/SDK/PVT/载波已在共同先验中，不重复叠加；同一事件前序观测也可能已被处理，因此名称为 PRE_CURRENT_CARRIER_UPDATE。

## 冻结读出与下一动作

保留全部 117 partial 及其每个方向分量，另外单列 41 双分量，接受与拒绝均保留。原物理域为源 anchor 北东平面上的侧向基线 atan2(E,N)，不是机体 Euler yaw。先验投影必须按真实误差图表和源 anchor 转换，不用参考寻找符号或角度偏移。

在固定 nominal 位置、当前三维 Gaussian 姿态误差先验的工作模型下，求均值基线单位方向到每个角弧（允许所有高程）的球面最小角 d。该 d 是姿态旋转距离的下界。若 lambda_max 为完整姿态协方差最大特征值，则达到该弧需 Mahalanobis 距离平方至少 d²/lambda_max，对应质量上界为 chi-square(3) 的 survival function；保留 log 上界以表示极远分量。预定用 99.9% 先验置信椭球报告是否排除，并保存连续数值，不扫阈值。

这是有意放宽高程和协方差方向后的先验质量上界，不是各弧的后验模态概率。域使用过 RP/gyro 资格，不能作为独立概率再乘入相同来源的 prior；域外质量不删除，两弧不强制归一化。一个弧未被上界排除，不等于它是显著后验模态。

若第二分量已被实际共同先验明确排除，停止基于域数量增加多分支后端，转向航向对平移的实际作用条件；若仍未排除，再针对留下的实际槽推导同模型 nonlinear 更新，而不是直接增加并行导航器。不得用此单窗工作先验判断替代所有弱先验场景的可辨识性结论。

执行脚本：`scripts/paper_rebuild/unified_legged_heading_20261007/partial_direction_prior_pilot.py`；字段定义与生产差异随实际实现保存。本计划在新 native 前写入，下一层 PLAN.json 绑定具体新 binary、配置及旧 VECTOR 输入身份。
