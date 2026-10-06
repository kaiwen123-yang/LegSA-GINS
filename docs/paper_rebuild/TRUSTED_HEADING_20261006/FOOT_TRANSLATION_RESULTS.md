# 有限区间足端位移内核：局部工程结果

已完成 foot_translation.py 和 24 项局部合成/域测试。Ubuntu 22.04 WSL 中仅执行一次 pytest，24 项全部通过，无失败重试。没有读取实际 raw、GNSS、参考或运行导航、整数搜索、评价器；没有生成真实 provider，也没有接入当前速度接口。

## 已核验的关系与接口

内核使用显式完整相对旋转 R（body1→body0，FRD）和同一连续支撑 episode 的足端位置，形成 p0=R p1+t_body。t_body 是区间机体原点位移，既不是绝对位置，也不是当前速度。输入 R 的区间与足端区间须完全匹配；所有来源需在决定时刻前可用。不从 rank-2 接触旋转代表值补齐 R。

杆臂 l 必填，方向为机体原点指向 IMU 点。IMU 点区间位移为 t_IMU=t_body+(R−I)l。非零杆臂纯转反例确认机体原点位移可以为零，而 IMU 点位移非零；未把两个物理点混用。

所有足端、旋转和杆臂误差由调用者提供同一个联合 Sigma。左 body0-FRD 旋转扰动对应 J_theta=[Rp1]×，杆臂增量对应 −[Rl]× 和 R−I。完整相关协方差、固定权 GLS、联合 body/IMU 协方差和端点/角度/杆臂有限差分检查均通过。跨足、跨时及旋转相关项没有被默认置零。

## 必须保留的反例

单足在给定完整 R 时可以给出三维条件位移，但残差自由度为零，不能检测滑移。多足差异滑移合成例产生非零残差；所有足共同滑移的合成例则给出偏移的 t 且残差仍近零。因此本内核没有“残差小即可信”的准入条件，不声明无滑移或测量已接受。

接触 episode 变化、整段连续性未知、R 不完整、旋转区间不匹配、未来可用数据、错误坐标/来源声明、无效联合协方差和奇异传播 Q 均有测试。FLU/FRD、足序变化及子集选择保留全部交叉项；没有补零或对协方差做 floor。

## 不确定度和证据边界

Sigma 与全部交叉项来自调用者，使用 first-order fixed working linearization；几何、雅可比和 GLS 权不针对残差迭代。这里不是已校准的不确定度，也不是完整非线性 errors-in-variables 似然。零相关块仅是调用者模型选择。GNSS-free 仅为显式来源声明，不证明与 EKF IMU 统计独立。

测试通过后仅补了一句杆臂方向 docstring；去掉 docstring 的 Python AST 逐项一致，没有额外算法执行。执行时源码 SHA、最终源码 SHA 和这一说明均保存在 receipt。

此阶段只交付位移内核及局部测试。后续若使用历史位姿克隆构造相对位移因子，仍需独立登记其统计处理、可用时刻与不退化检查；本阶段没有进行该集成。

## 复核入口

- FOOT_TRANSLATION_PLAN.md：执行前的工程范围、误差模型和测试预算；
- FOOT_TRANSLATION_TEST_01.log：唯一一次 pytest 的持久输出；
- FOOT_TRANSLATION_RECEIPT.json：24 个测试名称、命令、源码/测试/日志哈希及零真实调用计数；
- src/legsa_gins/paper_rebuild/carrier_phase/foot_translation.py 与 tests/paper_rebuild/test_foot_translation.py：完整可执行实现和测试。

parent 与 planner 已完成只读符号、完整 Sigma 及测试覆盖审查，未发现阻断问题；未为审查追加数值运行。

## 来源标记的后续修正

只读检查发现原输出将旋转输入的 GNSS-free 声明泛化成整个足端组合观测。已修正：仅旋转声明为 true，足端位置与组合来源均为未知（None），IMU 统计独立仍为 false；位移计算未变。增加1项针对性元数据回归通过，原24项未重跑，总独立测试数25。修正执行源码和最后仅文档字符串修订的SHA、持久日志见 FOOT_TRANSLATION_PROVENANCE_CORRECTION.json；原24项回执保留原执行身份。
