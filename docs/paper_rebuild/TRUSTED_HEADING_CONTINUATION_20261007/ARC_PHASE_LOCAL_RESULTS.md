# 未固定载波跨时差分：首次局部资格结果

2026-10-07，26/26 pytest cases 首次通过，0 失败、0 修复重试。pytest 报告 0.40 s，
整个 Python 测试进程 0.537 s；只执行新 test_arc_phase_difference.py。
既有 412 行 arc_phase_difference.py 草稿未改写，本轮新增独立检查与实际执行回执；
不把旧草稿存在误称此前已测，也不把本次测试当成完整导航实现。
事前范围见 ARC_PHASE_LOCAL_PLAN.md/json，原始日志/JUnit/身份在 ARC_PHASE_LOCAL_ATTEMPT_01.*。

## 本次明确验证了什么

| 检查 | 实際结果及其意义 |
|---|---|
| 未固定任意常整数、两个不同几何与姿态 | 独立 SD 物理生成器先构造相位，再形成 DD。任意更换两个时刻共同 N 不改变跨时观测；精确模型最大残差 1.9984e-15 m。错误把 H1 写成 H0 在此例导致 0.0228414 m 差异。 |
| ECEF 左乘两姿态 Jacobian | 六轴独立有限差分最大误差 3.8969e-10；预测与 z-h 残差符号分别核对。转动态二姿态秩为 4，仍保留两端基线轴 gauge。 |
| 静止同几何 | 秩 2、nullspace 维数 4，共同全局旋转不改变观测；不能由此产生绝对航向。不同几何/不同姿态未强加这个特殊 gauge。 |
| 全 Q 与共享 pivot/跨时相关 | 独立潜变量 oracle 与 D Qstack D^T 最大差 5.4210e-20 m²。错误忽略该例跨时相关造成矩阵差范数 2.3821e-4 m²。 |
| 相邻差分复用端点 | 显式负互协方差保留；两差分求和后中间端点噪声按代数抵消。擦除共享端点块或同名端点内容冲突会拒绝。 |
| pivot/物理弧/信号组 | 合法换 pivot 不变，epoch-only 新 pivot 自身 N 消去，原 pivot 退休后幸存关系可用；中途断弧、全断、同 SV 新 token 不继承旧端点。不同波长组分开，跨组 DD 拒绝。 |
| 隐藏相位阶跃 | 整周 pivot 与非整周 target 的注入符合物理模板且残差增大；内核不会声称已检测这种未声明故障。 |
| 输入合同 | 单调/身份/时标/receiver/phase、实际可用时刻、完整 Q 边际、PSD、姿态frame均检查；奇异PSD允许，未floor或加载噪声。 |

26 是参数化测试实例数，不是 26 个独立实测样本。测试从 SD 潜变量构造物理数据，
不使用生产 physical_integer_design/F0/F1 生成观测或 covariance oracle。没有 Monte Carlo
风险估计、真实模型、raw UBX、reference、native、evaluator、CILS 或新整数搜索调用。

## 对后续集成的约束

- 当前是观测代数内核，whole-interval continuity 是明确调用者前置条件。
  matching endpoint token 不等于中途无断弧，也不证明无未检测物理周跳。
- 内核不含消费ledger；未来首版应使用互不重叠五epoch块与原始端点ID消费，
  不能换ID重用相位。共享端点函数保留已声明互协方差，不能代替原始来源账本。
- 隐藏周跳/非整周异常的模板已经可测，但尚无本因子的正式统计检测、撤销与准入。
  旧 fixed-N 单历元 GLRT 的自由度不能直接继承。
- FULL_STACK 必须有真实来源的完整联合噪声模型。WORKING_ZERO_CROSS 是显式假设，
  不是从“整数消去”推出的独立性。state-measurement cross 仍由上层给定或按有效工作界处理。
- 模型使用每端实际 ECEF 几何和刚性 body 基线；安装、码anchor、星历/时钟、
  接收机物理同步、大气/多路径偏差尚未因此消失。秩是局部代数秩，不是精度资格。
- 未接 native，不证明真实方向误差/置信覆盖/正确固定率/导航收益或硬实时。

后续只读 saved-model 字段核查与建议预算另见 ARC_PHASE_SAVED_MODEL_QUALIFICATION.md。

## 后续有限扩展资格（首次 26 项记录保持原身份）

随后按授权扩展 geometry-only 接口，未知真实可用时间可显式为 None；旧完整 factor
仍拒绝 None、原默认行为不变。未知 cross 的条件二阶矩界作为独立类型输出，
不冒充 full covariance。扩展后单次回归：**原 26 + 新增 5 = 31/31 通过**，
pytest 0.54 s、进程 0.713 s；没有失败或修复重试。新增用真实 PSD 潜变量 cross
验证上界，并覆盖极端正/负相关（实际差分噪声从 0 到 4Q，零 cross 不是恒真）。
ARC_PHASE_LOCAL_ATTEMPT_02.* 保存本次源/test 身份、日志和 JUnit；
首轮 412 行草稿的 SHA 与 26 项报告不被本次源修改覆盖。
