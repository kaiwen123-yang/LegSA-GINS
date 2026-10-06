# 持续可信航向：局部内核与输入支持阶段

本阶段解决的是合法保留信息和可观性表达，不是完整导航版本。G5–G8 仍未完成；
原 V3 和 main 未改变，研究结果不得自动合并。全目标仍为可验证的持续可信航向版本，
而非局部 PASS、对照纠错或负结果报告。

## 已实现与检查范围

| 内核 | 行为 | 已有最终局部检查 |
|---|---|---|
| arc_relations | 已冻结 SD 弧整数势、合法换参考、局部失弧永久退休、投影合并保留来源 | 27 passed |
| arc_projection | 保留 code、重构幸存 phase、完整 UQUᵀ、未知新 pivot 相位消去 | 4 passed |
| contact_rotation | 平移消元、有限区间 Cayley 转动、完整端点 Q、显式可观/零空间 | 22 passed |
| support_arcs | 因果 force/dwell episode、缺样/错误/低阈值退休、禁止旧弧复活 | 31 新测试 passed；另复用 22 contact 检查 |
| directed_motion | 重力高度与有向面积的误差界必要条件；缺界/弱激励不伪造可信性 | 25 passed |
| candidate_envelope | 固定 raw cost 域内整数枚举及连续基线方向外包络；超限不发布完整集合 | 18 passed |

上述是各模块的最终局部测试结果，不是一次统一执行，也不是独立实测样本数。
contact 首次退化几何检查失败已保留并修正尺度判定；directed 测试有 23→25 扩充。
candidate 局部枚举共 18 次 API 调用，17 次返回、1 次入参拒绝，
累计 50 个节点、25 个叶；没有打开原生 LAMBDA 库。
部分初次终端输出未重定向文件；补记回执明确注明追记，不能冒称同时刻文件封存。
没有为补日志重新跑已完成试验。具体回执与命令见局部验证记录。

代码采用 Ubuntu 22.04 WSL。数学/控制流测试为合成，不读取评价参考、不产生导航。
先前 1191 窗口的输入支持审计为独立实测数据诊断，不混入以上局部测试数量。

## 实测输入支持带来的下一步依据

见 ARC_SUPPORT_AUDIT_REPORT.md 及全部逐窗结果。原 1191 窗口均保留：
535 个原 DD 标签支持失败中，509 首先失去 target 弧，25 失去 pivot，1 二者同时；
纯 pivot 坐标变化 0。516 个原失败窗口在原五个未来槽仍保有至少四条独立相位
差分和三维 phase 几何秩。这是条件几何支持上界，不能算新增准入或固定率。

局部隔离不自动保证好结果：这 516 窗口最差槽的条件 trace(Cb) 相对全部当前
整数已知的乐观参考，中位损失 2.8756、P95 12.2092，最大 91.4247。
下一步必须用固定原整数检查剩余支持的观测残差、长度、故障可检测性及
primary/competitor 是否投影合并；未知第三候选始终未由这项诊断覆盖。

## 进入完整系统仍需解决

1. 实测本体 proxy 的支撑覆盖、重复字段、源错误、秩与 gyro 内部一致性；
   SDK 足端位置不是独立编码器真值，rank-2 不可伪装为完整角速度。
2. 合法投影后的完整候选覆盖或明确工程验收；旧 top-two/global 证书不能继承。
3. 新弧的因果重获、全部载波丢失时相对传播及不确定性增长，错误先验撤销。
4. 原 V3 三完整窗的最终导航和必要消融，航向/H/V、尾部、覆盖、空窗、
   重获及完整时延；随后再评估跨日留出支持。
5. 每项贡献与最近前作的实际差异、联合收益与失败边界。任何单核通过均不闭合该要求。

## 复核入口

- GOAL_CONTRACT.md：G1–G9 完整目标及不变量。
- METHOD_AND_NOVELTY.md、DATA_AND_SCENARIOS.md、REQUIREMENTS_REVIEW.md。
- ARC_SUPPORT_AUDIT_PLAN.md、ARC_SUPPORT_AUDIT_REPORT.md、ARC_SUPPORT_AUDIT_RESULTS.csv。
- WSL scratch <TRUSTED_HEADING>/ARC_RELATIONS_UNIT_ATTEMPT01.{json,log}、
  ARC_PROJECTION_UNIT_ATTEMPT01.log、CONTACT_ROTATION/、SUPPORT_ARCS/。
- LOCAL_UNIT_TEST_RECEIPT.json 与 CANDIDATE_ENVELOPE_FIRST_RUN_CALLS.csv：directed/candidate 追记记录；源文件身份与证据性质明确。
