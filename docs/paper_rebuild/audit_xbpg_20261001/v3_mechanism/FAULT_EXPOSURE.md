# E01：已登记扰动区间与评价窗的交集

本项只核对已有小型元数据的时间包络，没有重读 provider、error_series、NAV、STD、参考轨迹或任何 gzip。新输出不覆盖旧报告或源 CSV；未调用 solver、evaluator、provider generator、aggregate/controller，也未计算新性能指标。

实际读到八族 **540 个案例、657 个注入组件**，以及对应 **11,880 个评价终态行**（540×11×2）。展开显式多区间并保留无区间组件后，新表 693 行；这些是组件/区间条目，不是运行、独立实验或接受的更新次数。注册分母仍为 **540 个退化案例 + 1 个 clean = Canonical-541**，每例 11 个唯一方法；没有因窗口落在窗外删除注册案例。

完整结果见 [FAULT_EXPOSURE_NOTES.csv](FAULT_EXPOSURE_NOTES.csv)，生成器见 [exposure/collect_fault_exposure.py](exposure/collect_fault_exposure.py)。表中 source_path/source_row_key/source_column/source_value 指向原 bundle 的组件 details；read_source_path/read_source_row_key 指向本轮实际读取的既有 CSV。原 details 字符串与原 hash pin 保留；newly_verified hash 留空，本项没有再次打开原 bundle。每个区间另给 interval_pointer。

## 交集口径

全部案例已有 evaluation_window 为 `[66.0,340.0]`。成功评价行的 sequence_window_start_s/end_s 逐条与之匹配；失败/未调用槽仍保留，不能伪造实际输出时间。观测首末匹配包络来自已有评价表，源行键及状态逐例保留在新表。

沿既有 provider 解释使用注入半开 `[start,end)`、评价闭窗 `[66,340]`；半开规则来源为 [既有窗口定义](../v3_interpretation/series_checks/SCHEMA_AND_TOLERANCE.md) 第 169–174 行。原数值 JSON 自身不编码开闭括号，因此表中把解释政策与来源单列，不伪装成源字段。交集时长只做端点减法，不等于采样历元数或性能统计。精确落在 340 的起点保留为 EVAL_END_POINT_ONLY，不能仅因时长零就说没有端点；本批实际条目没有因此推造样本。

| 分类 | 本批行数 | 含义 |
| --- | ---: | --- |
| INSIDE_EVALUATION | 210 | 显式区间完整位于评价时间包络内 |
| PARTIAL_OVERLAP | 0 | 显式区间跨评价边界，仅部分时间相交（含覆盖整个评价窗的情况） |
| OUTSIDE_BEFORE | 1 | 半开区间在评价开始前结束，end=66 也不含该端点 |
| OUTSIDE_AFTER | 5 | 显式区间的 start>340，全部晚于评价窗 |
| EVAL_END_POINT_ONLY | 0 | start=340，仅可能共享评价窗末端点，需样本才能判断实际暴露 |
| NO_EXPLICIT_INTERVAL | 477 | 组件未登记局部数字区间；不等于无扰动、未执行或未暴露 |
| UNPARSEABLE | 0 | 有区间字段但当前不能可靠解析，保留原字符串待核查 |

显式区间共 216 条，属于 135 个案例；其余 405 个案例未在组件 details 中登记数字局部区间。窗内 210 条中，192 条是故障组件区间、18 条是已有 recovery 元数据；恢复条目不算第二次故障。多个组件可能共用同一时间窗，均保留各自来源，不按相同端点消掉组件身份。

无显式区间条目中包含 full_sequence、随机逐点作用、audit-only/no_active_path 元数据和可能继承其他组件掩码的情况。本项不从 anchor/duration 猜出窗口，不把这些情况统称为无法解析，也不补成零交集。clean_recovery_interval 单列为 RECOVERY_METADATA，不能将恢复标记再次算成故障注入。

## D22 与 D39 的直接核对

| 案例 | 原组件子键 | 原区间 [start,end) s | 分类 | 与评价窗交集 s |
| --- | --- | --- | --- | --- |
| D22_seed_00 | /components/0/details/intervals/0 | [348.205852,352.205852) | OUTSIDE_AFTER | 空集 |
| D22_seed_06 | /components/0/details/intervals/0 | [346.21325,349.21325) | OUTSIDE_AFTER | 空集 |
| D39_seed_00 | /components/0/details/intervals/0 | [82.204517,84.204517) | INSIDE_EVALUATION | [82.204517,84.204517) |
| D39_seed_00 | /components/0/details/intervals/1 | [182.204872,184.204872) | INSIDE_EVALUATION | [182.204872,184.204872) |
| D39_seed_00 | /components/0/details/intervals/2 | [349.204539,352.204539) | OUTSIDE_AFTER | 空集 |

D22_seed_00 与 seed_06 的既有成功评价首末匹配时刻均为 66.005054/339.997056 s；两个 burst 均在评价请求末端之后。其组件 affected_epoch_count 是 provider 全范围内记录的受影响条目，不能据正计数声称本评价窗受到位置脉冲。这里只证明已登记时间包络不交叠，不证明完整 NAV 字节身份或任意其他机制正确。

D39_seed_00 的前两段各 2 s，在评价窗内；第三段 3 s 在窗外。原 details 还分别保存 frozen_affected_count=2/2/3、source_ids 和 count_to_duration_seconds；组件总 affected_epoch_count=7。保留字段里的计数不是本次 scalar R5 的真实接受数。既有扫描未提取 dict intervals 的缺口属于扫描窗口登记，不能据此判原数据错误或声称窗内两个区间没有发生。

## 全部窗外、跨界或解析异常条目

| 案例 | 组件/作用源 | role | 区间 s | 分类 | 原子键 |
| --- | --- | --- | --- | --- | --- |
| D22_seed_00 | position_burst_spike / gnss_position | FAULT_COMPONENT_METADATA | [348.205852,352.205852) | OUTSIDE_AFTER | /components/0/details/intervals/0 |
| D22_seed_06 | position_burst_spike / gnss_position | FAULT_COMPONENT_METADATA | [346.21325,349.21325) | OUTSIDE_AFTER | /components/0/details/intervals/0 |
| D39_seed_00 | baseline_quality_dropout / dual_yaw_quality | FAULT_COMPONENT_METADATA | [349.204539,352.204539) | OUTSIDE_AFTER | /components/0/details/intervals/2 |
| D39_seed_01 | baseline_quality_dropout / dual_yaw_quality | FAULT_COMPONENT_METADATA | [354.202136,357.202136) | OUTSIDE_AFTER | /components/0/details/intervals/2 |
| D39_seed_06 | baseline_quality_dropout / dual_yaw_quality | FAULT_COMPONENT_METADATA | [59.205119,63.205119) | OUTSIDE_BEFORE | /components/0/details/intervals/0 |
| D39_seed_06 | baseline_quality_dropout / dual_yaw_quality | FAULT_COMPONENT_METADATA | [347.204883,349.204883) | OUTSIDE_AFTER | /components/0/details/intervals/2 |

包络相交不证明输入恰有观测、观测通过有效性/时间匹配/门控，或求解器实际接受。窗外区间也不能解释为源文件没有被修改。失败槽有登记区间仍不意味着存在可评价输出；本表保留 completed_evaluation_records 和原状态，不替换原运行终态。

## D39 可选局部核对清单：PROPOSED_NOT_EXECUTED

若需补齐先前局部窗口缺口，可单独补充读取下表 22 个已保留文件，对固定 `[82.204517,84.204517)` 和 `[182.204872,184.204872)` 两窗只核对匹配历元数、首末时刻，以及沿既有定义的 H/yaw 误差摘要；每文件一次目标读取，44 个窗口条目。第三窗完全在评价窗外，只保留空交集，不伪造零 RMSE。本项尚未读任何 gzip，未执行这些统计；这仍不能恢复在线接受计数。

清单仅从既有 `../v3_interpretation/series_checks/CORE_dual_yaw/FILE_CHECKS.csv` 的 case_id=D39_seed_00 行取得，逐行 recorded/newly_verified hash、EOF 与主扫描次数仍在该原回执中；下面路径使用 `<V3_ROOT>` 别名。

| 方法 | run_id | v3 精确文件 | v2 精确文件 |
| --- | --- | --- | --- |
| F01 | RUN_03774 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03774/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03774/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| F02 | RUN_03775 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03775/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03775/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| F03 | RUN_03776 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03776/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03776/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| F04 | RUN_03777 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03777/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03777/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| A03 | RUN_03778 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03778/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03778/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| A04 | RUN_03779 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03779/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03779/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| A05 | RUN_03780 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03780/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03780/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| A06 | RUN_03781 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03781/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03781/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| A07 | RUN_03782 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03782/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03782/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| A08 | RUN_03783 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03783/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03783/v2/FROZEN_EVALUATOR/error_series.csv.gz` |
| A09 | RUN_03784 | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03784/v3/FROZEN_EVALUATOR/error_series.csv.gz` | `<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/RUN_03784/v2/FROZEN_EVALUATOR/error_series.csv.gz` |

## 本项实际读取的小型来源

| 来源 | 数据行数 |
| --- | ---: |
| [gnss_outage/INJECTION_CASES.csv](../v3_interpretation/core/gnss_outage/INJECTION_CASES.csv) | 63 |
| [gnss_outage/INJECTION_COMPONENTS.csv](../v3_interpretation/core/gnss_outage/INJECTION_COMPONENTS.csv) | 90 |
| [gnss_outage/ORIGINAL_RUN_VALUES.csv](../v3_interpretation/core/gnss_outage/ORIGINAL_RUN_VALUES.csv) | 1386 |
| [gnss_sampling/INJECTION_CASES.csv](../v3_interpretation/core/gnss_sampling/INJECTION_CASES.csv) | 45 |
| [gnss_sampling/INJECTION_COMPONENTS.csv](../v3_interpretation/core/gnss_sampling/INJECTION_COMPONENTS.csv) | 45 |
| [gnss_sampling/ORIGINAL_RUN_VALUES.csv](../v3_interpretation/core/gnss_sampling/ORIGINAL_RUN_VALUES.csv) | 990 |
| [position_value/INJECTION_CASES.csv](../v3_interpretation/core/position_value/INJECTION_CASES.csv) | 90 |
| [position_value/INJECTION_COMPONENTS.csv](../v3_interpretation/core/position_value/INJECTION_COMPONENTS.csv) | 90 |
| [position_value/ORIGINAL_RUN_VALUES.csv](../v3_interpretation/core/position_value/ORIGINAL_RUN_VALUES.csv) | 1980 |
| [position_std_status/INJECTION_CASES.csv](../v3_interpretation/core/position_std_status/INJECTION_CASES.csv) | 63 |
| [position_std_status/INJECTION_COMPONENTS.csv](../v3_interpretation/core/position_std_status/INJECTION_COMPONENTS.csv) | 63 |
| [position_std_status/ORIGINAL_RUN_VALUES.csv](../v3_interpretation/core/position_std_status/ORIGINAL_RUN_VALUES.csv) | 1386 |
| [dual_yaw/INJECTION_CASES.csv](../v3_interpretation/core/dual_yaw/INJECTION_CASES.csv) | 108 |
| [dual_yaw/INJECTION_COMPONENTS.csv](../v3_interpretation/core/dual_yaw/INJECTION_COMPONENTS.csv) | 108 |
| [dual_yaw/ORIGINAL_RUN_VALUES.csv](../v3_interpretation/core/dual_yaw/ORIGINAL_RUN_VALUES.csv) | 2376 |
| [velocity_raw_doppler/INJECTION_CASES.csv](../v3_interpretation/core/velocity_raw_doppler/INJECTION_CASES.csv) | 81 |
| [velocity_raw_doppler/INJECTION_COMPONENTS.csv](../v3_interpretation/core/velocity_raw_doppler/INJECTION_COMPONENTS.csv) | 81 |
| [velocity_raw_doppler/ORIGINAL_RUN_VALUES.csv](../v3_interpretation/core/velocity_raw_doppler/ORIGINAL_RUN_VALUES.csv) | 1782 |
| [go2_prior_metadata/INJECTION_CASES.csv](../v3_interpretation/core/go2_prior_metadata/INJECTION_CASES.csv) | 54 |
| [go2_prior_metadata/INJECTION_COMPONENTS.csv](../v3_interpretation/core/go2_prior_metadata/INJECTION_COMPONENTS.csv) | 54 |
| [go2_prior_metadata/ORIGINAL_RUN_VALUES.csv](../v3_interpretation/core/go2_prior_metadata/ORIGINAL_RUN_VALUES.csv) | 1188 |
| [multi_source_mixed/INJECTION_CASES.csv](../v3_interpretation/core/multi_source_mixed/INJECTION_CASES.csv) | 36 |
| [multi_source_mixed/INJECTION_COMPONENTS.csv](../v3_interpretation/core/multi_source_mixed/INJECTION_COMPONENTS.csv) | 126 |
| [multi_source_mixed/ORIGINAL_RUN_VALUES.csv](../v3_interpretation/core/multi_source_mixed/ORIGINAL_RUN_VALUES.csv) | 792 |
| [D39 候选文件来源](../v3_interpretation/series_checks/CORE_dual_yaw/FILE_CHECKS.csv) | 264（只选 22 行作提案） |

复核：两种 interval 结构（pair 和 start_s/end_s 字典）均支持；540 案例/657 组件全覆盖，11,880 评价槽完整保留；源 components_json 与分表 details/计数/组件身份逐组件一致；新旧数据模式分开，V3 正式角色为 semisynthetic。另读上述既有窗口定义核实半开解释。没有读取旧工程或重新库存，脚本生成仅为本项 CSV/说明；脚本本体为新增小工具。运行 `python3 exposure/collect_fault_exposure.py --self-test` 可检查 11 个解析/边界断言，默认调用只读取上述明确小来源并重建本项说明，不调用科学流程。
