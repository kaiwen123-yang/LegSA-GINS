# 原 V3 / F04 三序列基线指标

此表只复用 V3_BASELINE_LOCK.json 锁定的三个原 F04 运行。没有新 solver、evaluator、reference 读取或 error_series 派生。
原科学冻结为 7d43b9af26120ed5dde21f53e515386361072ba6，评价合同为 evaluator_contract_v3；不是研究分支的 PVT/body-HV 对照，也不是新载波原型结果。

| 序列 | 注册全窗 (s) | 实际匹配首末时刻 (s) | 匹配/输出历元 | 评价覆盖率 | yaw RMSE (°) | H RMSE (m) | V RMSE (m) |
|---|---|---|---:|---:|---:|---:|---:|
| BY2 | 66–340 | 66.005054–339.997056 | 56642/56642 | 100% | 1.886271855 | 0.097906078 | 0.048995904 |
| BY2H | 413–683 | 413.047045–682.995050 | 58580/58580 | 100% | 1.933770135 | 0.068362451 | 0.045352108 |
| BY2O | 3186–3563 | 3186.005234–3562.997055 | 76548/76548 | 100% | 2.433814933 | 0.054543211 | 0.045858907 |

H 为 EN 平面误差范数；V 对应源字段 up。航向误差按冻结 evaluator 包裹至 [-180°,180°)。
覆盖率是 matched_epoch_count/output_epoch_count，三组 unmatched 均为 0；不表示原始传感器全可用、固定率 100% 或独立真值覆盖。
末时刻是最后匹配的导航样本，不能替代注册窗口的精确终点。

| 序列 | yaw P95 / P99 / max (°) | H P95 / P99 / max (m) | V P95 / P99 / max (m) |
|---|---:|---:|---:|
| BY2 | 3.518067 / 5.221693 / 8.770339 | 0.265143 / 0.376479 / 0.541378 | 0.099238 / 0.137761 / 0.341506 |
| BY2H | 3.648137 / 5.166552 / 7.924041 | 0.144627 / 0.259696 / 0.341517 | 0.089474 / 0.169841 / 0.294654 |
| BY2O | 3.709243 / 12.501914 / 13.626088 | 0.074204 / 0.200229 / 0.529985 | 0.081743 / 0.138608 / 0.745673 |

yaw 与 V 的分位数/最大值取绝对误差，H 本身非负。BY2O 的航向 P99=12.501914° 与最大值13.626088°必须保留，不能只用全窗 RMSE 掩盖尾部。
CSV 另保留现成 MAE、P50、P90、末匹配时刻绝对误差及完整数值精度；没有重新从误差序列计算。

| 序列 | H ≤ 2 m 比例 | V ≤ 3 m 比例 | 航向绝对误差 ≤ 2° 比例 | 冻结收敛时间 (s) |
|---|---:|---:|---:|---:|
| BY2 | 1.000000000 | 1.000000000 | 0.712651389 | 31.114075 |
| BY2H | 1.000000000 | 1.000000000 | 0.690867190 | NA |
| BY2O | 1.000000000 | 1.000000000 | 0.770510007 | 2.533848 |

这些比例直接来自已保存 summary.json，是历史 evaluator 的误差阈值诊断，不是准入门、错误固定概率或新的工程达标判决。
收敛定义：首次 H≤2m 且 |yaw|≤2° 连续保持至少3s，返回该段起点相对首评价样本的时间。
BY2H 原值为 null，写为 NA，并保留 NULL_NO_REGISTERED_HOLD_OBSERVED；不是缺失运行，也不是零秒。
超阈值事件个数、最长超阈值持续时间和故障恢复时间未在这些小型汇总中记录，均为 NA，未另行解析 error_series。
速度误差为 NA：冻结评价明确 reference_velocity_supported=false。原始载波整数固定率为 NA：此原 V3 基线没有新增原始载波 AR 实绩。

## 数值来源与身份

主表与 CSV 的原字段直接读取 EVALUATION_RESULT.json 的 /row/<字段名>；CSV 中 source_result_path/source_result_sha256 和 /row 前缀逐行指明来源。
额外 summary 字段的 JSON pointer：

- horizontal_pass_ratio_at_2m ← /position/horizontal_pass_ratio
- vertical_pass_ratio_at_3m ← /position/vertical_pass_ratio
- yaw_pass_ratio_at_2deg ← /attitude/yaw_pass_ratio
- frozen_convergence_time_sec ← /convergence/convergence_time_sec
- matched_duration_sec ← /meta/duration_sec
- yaw_truth_mode ← /meta/yaw_truth_mode

各源文件均为 V3 保留小文件，主结果数值优先于 summary 的浮点末位差异；二者九个核心指标各序列逐项检查，容差1e-12，最大绝对差 1.7763568394002505e-15。
本次只针对读入的三份 result 和三份 summary 校验既有哈希，没有重复全输入、raw、binary 或 reference 哈希。

- BY2：<V3_ROOT>/04_EVALUATION/RUN_00004/v3/EVALUATION_RESULT.json；SHA256 d00efef45c3f210425c0aa26dc8bdbaf8757e9fe16904120e2f9fbf3ed9fc8e1
  - 次级诊断：<V3_ROOT>/04_EVALUATION/RUN_00004/v3/FROZEN_EVALUATOR/summary.json；SHA256 327e524df5ea4d94102099f4f9c2177bcf56d4e6b8fd354b3af3748548c3b8de
- BY2H：<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/SEQUENCE_BY2H_F04/v3/EVALUATION_RESULT.json；SHA256 4597ab15b20e0b21ed60c525238625459455be09dee3870eeb75bf119d54c6ba
  - 次级诊断：<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/SEQUENCE_BY2H_F04/v3/FROZEN_EVALUATOR/summary.json；SHA256 7f0c5ff9ebed6f1ea48ad83a2359c50af5bda2b84fede4a97404d6538e2e9a32
- BY2O：<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/SEQUENCE_BY2O_F04/v3/EVALUATION_RESULT.json；SHA256 d6dcd2785426fe59698557105efa69eff3bcf24ccd3b7331cf2a07a7e59a72b3
  - 次级诊断：<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/SEQUENCE_BY2O_F04/v3/FROZEN_EVALUATOR/summary.json；SHA256 79dd37c0fb537a51c3b2a18de73df1d60b7a5ecdf7818b2b2696a82a629a3b95

CSV 保留 native_nav_sha256、evaluator_nav_sha256、std_sha256、trace_sha256、runtime_configuration_sha256、binary_sha256 和 evaluator_sha256。
这些 NAV/STD 身份是历史回执，原完整 NAV/STD 已释放，本次没有重新验证相应 payload。trace SHA 仅复用历史身份，不打开 reference。

位置指标严格使用 V3 原物理点变换：只变换位置列，采用锁定 baseline_median 和 lever；未拟合平移或旋转。
STD 没有随物理点变换运输，其一致性统计不作为本表精度或风险结论。
评价参考是共享 GNSS 来源的商业融合参考，不是独立真值。三序列分别列示，不合并成新精度排名。

新载波前端及其 LegSA 融合尚无同一 V3 全窗的已审核实绩，本交付不填入占位改善值，也不将 BY2 100–340s 研究子窗当作 V3 66–340s。

核查结果：78 项来源/身份/窗口/覆盖率与数值交叉检查通过。solver/evaluator/reference/error_series 读取或重算均为 0。
本文件与 V3_BASELINE_METRICS.csv 只新增到研究分支，不替换既有结果。
