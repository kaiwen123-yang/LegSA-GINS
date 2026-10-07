# 未固定载波跨时相位差：局部资格计划

状态：REGISTERED_BEFORE_FIRST_TEST，2026-10-07；本线程新 goal 授权的有限合成资格。
范围仅为 arc_phase_difference.py、新 test_arc_phase_difference.py 与本目录 ARC_PHASE_* 记录。
不提交、不推送、不改 V3、native、既有 provider、directed_domain 或其他代理文件。

## 被测模型与独立检查

PhaseEpoch 使用 GNSS2-GNSS1 的 SD、target-pivot 的 DD、相位米值以及各自实际历元 ECEF 几何。
同一完整物理 SD 弧上的未知整数常量由 D=[-F0,F1] 消去。
不输入、搜索、固定或接受整数；弧连续性由外部全区间证据提供，端点同标签不足以证明连续。

独立物理生成器先生成逐 SD 的几何相位、任意整数及潜变量噪声，再构造两端 DD。
检查不复用生产 physical_integer_design 生成合成观测或真值。

首批目标不超过 35 个 pytest cases，只运行该新文件一次并保存退出码、完整stdout/stderr及JUnit。
如失败先保留原记录，再仅针对可定位的实现或测试问题修复；不得换数据/容差掩盖科学失败。

1. 任意常 N 消去；两端几何不同、刚性基线发生转动，避免把 H0=H1 当恒等。
2. 六维 ECEF 左扰动预测/残差 Jacobian 独立有限差分；静止同几何共同旋转 gauge、
   单基线自身轴不可观、弱几何/空支持不伪造姿态信息。
3. 同弧换 pivot、原 pivot 退休而幸存关系可消元、部分/全失弧、同 SV 新 token。
   区间内曾失效但端点 token 相同也不能继承（continuity 清单移除该节点）。
4. 精确信号组和不同波长：不跨频构造 DD；同组合法变化及全协方差维持。
5. 完整跨时 Q 和 shared-pivot 协方差用独立潜变量线性变换对比；
   相邻差分共享端点的负互协方差保留，擦除共享块明确拒绝。
6. 隐藏目标/pivot 整周和非整周脉冲的物理模板，证明不满足连续整数模型时残差会改变；
   此模块不把这类模板冒称检测/验收器。
7. 时间单调、时标/接收机/相位约定、实际可用时刻、完整 covariance 来源和边际一致；
   非PSD/不同同名端点/错误姿态frame拒绝。无状态消费ledger的接口边界明确保留。

## 执行与停止边界

运行环境为已有 Ubuntu22.04 /usr/bin/python3（numpy 1.26.4、pytest 6.2.5），数值线程为1。
只调用局部 Python 测试；RAW UBX、saved real model、reference、native、evaluator、CILS均不调用。
日志中区分真实调用与预期拒绝。测试通过只证明声明线性/局部模型的观测代数、来源规则及
协方差/Jacobian一致，不证明真实观测误差界、绝对航向、整数正确率、故障率、导航收益或硬实时。
下一步真实 saved-model 资格须另登记固定非重叠五epoch块、完整全分母与真实连续性/噪声来源；
尚不在本计划执行。

## 首次26通过后的受控扩展

根代理授权真实saved-model资格前，加入geometry-only接口：历史真实availability缺失保留None；
原可用factor构造仍必须拒绝None，默认数值时间行为不变。加入5个cases检查这种拆分、空支持，
以及2*(Q0′+Q1′)在已知PSD潜变量正相关/负相关/一般cross下的条件界。
只再运行本文件31例一次，区分原26回归与新增5例。首轮源码/日志/JUnit保留。
