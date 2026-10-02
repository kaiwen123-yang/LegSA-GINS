# 三序列独立复現：单序列离线航向评价

本入口只在三方法对应序列的 native `RUN.json` 均已 `COMPLETED` 后调用，每次仅处理明确指定的一条序列。方法输出为 `EXT01/EXT02/EXT03__RAW_REPRO_V1`，旧 HX 与本轮版本不合并。没有 controller、Context、solver、provider、位置评价或占位 roll/pitch 评价。原生处理中的失败历元保留在 HEADING 全配对表及评价分母内。

入口是 `src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_evaluation.py`：

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONPATH=src python3 -m legsa_gins.paper_rebuild.horizontal_literature.reproduction_evaluation \
  --roots configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json --sequence BY2
```

`--sequence` 可明确指定 BY2、BY2H 或 BY2O；程序没有“全部序列”、自动重试或自动选更晚 native attempt 的模式。运行根通过 ignored roots 解析，输出独占 `<EXT_REPRO_ROOT>/evaluation/<SEQ>/`，已存在则拒绝覆盖。

## 输入与一次参考读取

读取 `<EXT_REPRO_ROOT>/inputs/<SEQ>/INPUT.json`、三个原生 `RUN.json` 和各自 hash 固定的 `HEADING.csv`。三方法的 `epoch_index/gps_week/gps_tow_seconds/time_unix_s` 必须逐项一致，行数必须等于 INPUT 配对数；本机已有的完整配对数为 BY2 1509、BY2H 1483、BY2O 2231。若原生技术失败导致表不完整，入口前置门拒绝，不补造缺失时刻或分母。

参考路径、SHA256、base time、窗口来自已有 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07R/RUNS/<SEQ>_<V0|V0E|V1|V2>/eval/SPEC.json`。四份 SPEC 的参考与窗口身份必须一致，且与新 INPUT 一致。准备阶段仅读 SPEC 元数据，不读取真实参考正文。实际已核的原窗口为闭区间：

| 序列 | base time | 相对窗口 (s) |
|---|---:|---|
| BY2 | 1772784000.0 | [66, 340] |
| BY2H | 1772784000.0 | [413, 683] |
| BY2O | 1772780400.0 | [3186, 3563] |

父入口不读 reference；单独 Python child 在 `strace -xx` 下将 reference 只读打开一次，并对同一 handle 读得的原字节计算 SHA256。三方法共用该 payload 得到的一份同时间网格参考列，不按方法再开参考。参考不匹配即失败，保留目录和计数，不自动 retry。访问审计必须确认 1 次成功 Python `execve`、1 次只读参考 open、0 次其他 raw open。原生求解器和 evaluator child 的次数分别记载，不把三方法当成三次 child。

冻结实现为 `hext/hx02_heading_evaluation.py` 中 `read_heading_table`、`reference_yaw_ned`、`heading_metrics`；源 SHA256 为 `eedb3faf56ccffca222d915c401d3075dc64583ce68a10f08add9f8b705fa994`。其统计 helper 所在 `horizontal_literature/phase2_runner.py` 为 `85112d34e27f1fa8c3043bdcdeb2f418232cd2fffacb40cab3f387f179db6c9b`。只导入函数，不实例化或执行该旧 runner。新入口、协议及两个冻结文件须与调用时 HEAD 的已提交字节一致，child 再核传入 source pins；这里的 HEAD 用于入口版本绑定，不替代原 native 的 `code_commit`。

## 指标、状态与分母

参考语义保持 `wrap360(90-interp(unwrap(yaw_ENU)))`，只在参考时间支撑内插值，不外推；残差为 `wrap180(method_body_yaw_ned-reference_body_yaw_ned)`。

每方法完整保留三种视图：

- `native_valid`：原生 `valid=1` 且有参考支撑的航向误差，valid availability 的分母仍为原窗口全部配对历元。
- `ratio_fixed`：EXT03 原 paper-ratio 标志且 native valid 的子集；EXT01/EXT02 没有独立接受检验，显示 `NOT_APPLICABLE_NO_ACCEPTANCE_TEST`、空指标，不伪称“正确固定”或 0 固定率。HX07R 固定视图为自身原 `q1_fixed`，不把 q2 float 变成其 native valid。
- `causal_held`：从 native 文件起点开始，只保持本方法此前最后一次有效航向；第一有效值前的无航向保持空值。没有利用未来值、参考值或窗口末端回填。

RMSE、P95、最大绝对误差、MAE、circular bias 来自同一 frozen 统计函数；全部原嵌套字段保存到 `HEADING_METRICS.json`。`RESULT_ROWS.csv` 为每方法/视图一行，并列原始分母、available 数、实际评分数、状态和 source pointer。0 个评分值的指标为空，不填零。

新增描述字段单列为本轮派生：完整 native / 窗口内首个 valid 与 fixed 时刻；原 frozen `maximum_gap_seconds`；窗口边界与所有 valid 时刻之间的最大间隔（含两端截断间隔，明确不是另一个 RMSE）；causal-held 的 source epoch、source time、age，以及窗口内 age 的 count/P95/max。后者包含当前有效历元的 0 age，不将其冒充仅 outage 段 age。

`ERROR_SERIES.csv` 含窗口内每个新方法的全部配对行，原时刻与 epoch、valid/fixed/failure/state、误差、实际参考 yaw、native yaw、held yaw/source/age、原生相对基线 N/E/D/长度。原无效行不删除、旧失败状态不改写。参考是 Fixposition 派生结果，并非独立真值；这个限制留在说明中。

## 旧对照引用与共同支撑

HX07R **V0、V0E、V1、V2 全部保留**。既有 `HEADING_METRICS.json` 数值直接引用并保存 `REUSED_METRICS.json`；不再用新参考重评旧方法。另读 hash 固定的原 `HEADING_TABLE.csv` 和已存在的 `HEADING_ERROR_SERIES_RTKLIB.csv`，用于时轴/支撑检查、原生时刻诊断及共同支撑归约。评分行计数须与旧 JSON 相符。 另外逐行核验原 heading 的 valid、rtklib_q、同一 epoch/time、参考支撑掩码、causal hold 是否可用及 source epoch、误差有值掩码；核验旧 error_convention/reference_semantics 等于冻结定义。所有检查成功后才原子加入共同支撑，晚阶段异常也不能残留成员。若原指标本身身份/语义合格而时序载荷失败，仍引用其原数值和分母，并标注 COMMON_SUPPORT_REJECTED。某一旧对照缺项/不一致会留下三视图失败记录及 `MISSING_MEMBER` 共同支撑槽，不阻塞三新方法的已取得结果。

共同支撑只连接已保存误差，以原 Unix 时间字面值经 `Decimal` 转换后按 **nearest microsecond、ties-to-even** 得整数 key。每条源内 time 必须有限、严格递增、key 唯一；重复 key 拒绝，不择一。连接后再查所有原字面时间的最大差 `<=1e-6 s`，并记录实际最大差；不搜索时移、不 nearest-neighbor 追配、不插值、不按行号对齐。这是固定量化后的连接，不是原时间字符串 exact equality；原时刻与 epoch 保留，原字符串不同不意味着数值时间不同。

固定计算 18 个方法组合，每个均保留三种 support 槽：12 个“每个新方法 × 每个 RTKLIB 变体”、3 新方法共同集、4 个“3 新方法 + 某一 RTKLIB 变体”共同集、7 方法共同集。只有该 support 的各成员误差都有限才入共同集合。空交集记录 0 个共同评分、空指标；未定义 ratio 记录 N/A，不能和空交集混同。`COMMON_SUPPORT.csv` 每组合/视图/成员一行，列出原行数、共同评分数和同支撑指标；`COMMON_SUPPORT_KEYS.json` 提供全部实际 key，支持检查，未挑选最佳 RTKLIB 变体。

V3 只引用已收集 33 行 `NATURAL_C00_ALL_CONFIGS.csv` 中该序列原 F04/v3 的原值及运行键，保存 `V3_REFERENCE.csv`。其导航点、采样密度和支撑与方法原生航向不同，不混入 heading common support，不打开旧 error-series 集或重新评价 V3。

## 图与失败隔离

数字先保存，再默认从 `ERROR_SERIES.csv` 生成一幅四 panel 图：native heading + `Reference`、native yaw error、原生 invalid/valid/ratio-fixed 状态、相对基线 N/E/长度。基线图不是全局轨迹；硬长度约束方法的长度也不是独立准确率证据。

真实 invalid/缺值、epoch 不连续、相邻时间差大于固定 `0.300001 s`（原 5 Hz cadence 的 1.5 倍加 1 us）、wrap 跳变超过 180° 都断线。图没有倒推数值或跨 gap 连线。PNG 宽 4200 px，另存 PDF；实际视觉审阅由 root 后续完成，代码/文件生成不等于视觉 PASS。

图进入 `figures/attempt_001/`，有独立 `PLOT_RECEIPT.json`。绘图失败保留完成的评价状态与数据；恢复时明确执行同一命令加 `--plot-only`，仅读保存的 ERROR_SERIES、写下一独占绘图 attempt，reference open 与 evaluator 调用都是 0。不覆盖已有图片、数字、旧历史结果。

## 合成验证记录

实际 pytest 记录如下；每次调用的完整结果与源/测试 SHA256 均保留。合成测试涵盖微秒 key/碰撞/非有限/时间差，参考角度跨 360° 与禁止外推，失败分母与 N/A fixed，causal-held 源时刻与 age，旧原值保持，全部共同支撑槽，缺旧成员保留，single child/真实 strace 的合成参考一次读取，hash 失败不重试，PNG/PDF 导出及图失败不改变数字状态。所有测试参考均是 pytest 临时生成数据；没有读取本机真实 reference。

### pytest attempt 1

```json
{
  "attempt": 1,
  "timestamp_utc": "2026-10-02T13:45:55.903443+00:00",
  "argv": [
    "python3",
    "-m",
    "pytest",
    "-p",
    "no:cacheprovider",
    "--disable-warnings",
    "-rA",
    "tests/paper_rebuild/test_ext_reproduction_evaluation.py"
  ],
  "exit_code": 0,
  "elapsed_seconds": 2.666202621003322,
  "data_mode": "synthetic_unit_tests_only",
  "synthetic_data_used": true,
  "semisynthetic_data_used": false,
  "real_native_processes": 0,
  "real_evaluator_processes": 0,
  "real_reference_reads": 0,
  "source_sha256": "468a1cbf967703b9721dbd6015ac51a3de8a2f2720c21b9602e8faa293db5516",
  "test_sha256": "1ee8d495c356fb6b956ee04d8af3876271a45ccda5887578148260fbc5168519",
  "stdout": "============================= test session starts ==============================\nplatform linux -- Python 3.10.12, pytest-6.2.5, py-1.10.0, pluggy-0.13.0\nrootdir: <CODE_ROOT>, configfile: pyproject.toml\nplugins: ament-flake8-0.12.15, ament-pep257-0.12.15, launch-testing-ros-0.19.13, ament-xmllint-0.12.15, launch-testing-1.0.14, launch-pytest-1.0.14, ament-lint-0.12.15, ament-copyright-0.12.15, colcon-core-0.20.1, cov-3.0.0\ncollected 20 items\n\ntests/paper_rebuild/test_ext_reproduction_evaluation.py ................ [ 80%]\n....                                                                     [100%]\n\n==================================== PASSES ====================================\n__ test_plot_only_saved_series_no_reference_and_failure_keeps_numeric_receipt __\n----------------------------- Captured stderr call -----------------------------\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\n=========================== short test summary info ============================\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search[197-197.0-197000000]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search[1772784066.1979997-1772784066.198-1772784066198000]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search[1.0000005-1.00000049-1000000]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[NaN]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[Infinity]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[UNKNOWN]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_key_collisions_and_reordered_clocks_are_not_silently_deduplicated\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_frozen_reference_wrap_interpolation_and_no_extrapolation\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_synthetic_full_child_metrics_original_denominators_and_reused_values\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_reference_hash_mismatch_retains_failure_without_metrics_or_retry\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_heading_hash_failure_happens_before_reference_open\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_missing_old_variant_does_not_remove_its_common_comparison_slots\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_breaks_preserve_invalid_epochs_wrap_jumps_and_physical_time_gaps\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_plot_only_saved_series_no_reference_and_failure_keeps_numeric_receipt\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[none-True]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[duplicate-False]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[write-False]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[other_raw-False]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_one_synthetic_evaluator_subprocess_under_real_strace\n======================= 20 passed, 14 warnings in 2.28s ========================\n",
  "stderr": ""
}
```

### pytest attempt 2

```json
{
  "attempt": 2,
  "timestamp_utc": "2026-10-02T13:47:45.351611+00:00",
  "argv": [
    "python3",
    "-m",
    "pytest",
    "-p",
    "no:cacheprovider",
    "--disable-warnings",
    "-rA",
    "tests/paper_rebuild/test_ext_reproduction_evaluation.py"
  ],
  "exit_code": 0,
  "elapsed_seconds": 2.184319884996512,
  "reason": "Added exact heading-pointer gate and metadata-only/overwrite negative controls after first 20 cases passed.",
  "data_mode": "synthetic_unit_tests_only",
  "synthetic_data_used": true,
  "semisynthetic_data_used": false,
  "real_native_processes": 0,
  "real_evaluator_processes": 0,
  "real_reference_reads": 0,
  "source_sha256": "2f0e9b1aec28bcb1a6eef2504042866be798a3f9e8445d3ad320142a9b561330",
  "test_sha256": "cfe05a503c1b8d37877969a240af4be77add05f22ef1e7bfa9534eb916e8a5fa",
  "stdout": "============================= test session starts ==============================\nplatform linux -- Python 3.10.12, pytest-6.2.5, py-1.10.0, pluggy-0.13.0\nrootdir: <CODE_ROOT>, configfile: pyproject.toml\nplugins: ament-flake8-0.12.15, ament-pep257-0.12.15, launch-testing-ros-0.19.13, ament-xmllint-0.12.15, launch-testing-1.0.14, launch-pytest-1.0.14, ament-lint-0.12.15, ament-copyright-0.12.15, colcon-core-0.20.1, cov-3.0.0\ncollected 25 items\n\ntests/paper_rebuild/test_ext_reproduction_evaluation.py ................ [ 64%]\n.........                                                                [100%]\n\n==================================== PASSES ====================================\n__ test_plot_only_saved_series_no_reference_and_failure_keeps_numeric_receipt __\n----------------------------- Captured stderr call -----------------------------\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\n=========================== short test summary info ============================\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search[197-197.0-197000000]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search[1772784066.1979997-1772784066.198-1772784066198000]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search[1.0000005-1.00000049-1000000]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[NaN]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[Infinity]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[UNKNOWN]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_key_collisions_and_reordered_clocks_are_not_silently_deduplicated\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_frozen_reference_wrap_interpolation_and_no_extrapolation\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_synthetic_full_child_metrics_original_denominators_and_reused_values\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_reference_hash_mismatch_retains_failure_without_metrics_or_retry\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_heading_hash_failure_happens_before_reference_open\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_missing_old_variant_does_not_remove_its_common_comparison_slots\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_breaks_preserve_invalid_epochs_wrap_jumps_and_physical_time_gaps\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_plot_only_saved_series_no_reference_and_failure_keeps_numeric_receipt\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[none-True]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[duplicate-False]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[write-False]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[other_raw-False]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_one_synthetic_evaluator_subprocess_under_real_strace\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_prepare_metadata_only_native_gates[None]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_prepare_metadata_only_native_gates[incomplete]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_prepare_metadata_only_native_gates[wrong_heading]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_prepare_metadata_only_native_gates[wrong_pair_count]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_parent_refuses_existing_output_before_child\n======================= 25 passed, 14 warnings in 1.93s ========================\n",
  "stderr": ""
}
```

旧 error series 若已有 `EXISTING_HX_FILES.csv` 的 recorded_sha256，将在同次读取验证；当前 SPEC 本身未给 error pin 时不凭新读 hash 冒充历史 pin。无可用 recorded pin 的读取标记为 `NEW_READ_HASH_NOT_HISTORICAL_PIN`。库安装路径在测试日志中替换为 `<PYTHON_USER_SITE>`，不作为数据读取入口。

### pytest attempt 3

```json
{
  "attempt": 3,
  "timestamp_utc": "2026-10-02T13:53:23.470461+00:00",
  "argv": [
    "python3",
    "-m",
    "pytest",
    "-p",
    "no:cacheprovider",
    "--disable-warnings",
    "-rA",
    "tests/paper_rebuild/test_ext_reproduction_evaluation.py"
  ],
  "exit_code": 0,
  "elapsed_seconds": 2.1293579429984675,
  "reason": "Reviewer-requested atomic old-member admission, per-row support/semantics/history-pin gates, and synthetic counterexamples; Reference figure label.",
  "data_mode": "synthetic_unit_tests_only",
  "synthetic_data_used": true,
  "semisynthetic_data_used": false,
  "real_native_processes": 0,
  "real_evaluator_processes": 0,
  "real_reference_reads": 0,
  "synthetic_evaluator_subprocesses_in_this_pytest": 1,
  "source_sha256": "616cff8479c7a64a124af24bd01c2ab9a6a284964889a0879c20b00050ead075",
  "test_sha256": "4589e56f3a4c8398ffc94659027bfe29ccf8db6e20180c84729d3e2b2331ae5a",
  "stdout": "============================= test session starts ==============================\nplatform linux -- Python 3.10.12, pytest-6.2.5, py-1.10.0, pluggy-0.13.0\nrootdir: <CODE_ROOT>, configfile: pyproject.toml\nplugins: ament-flake8-0.12.15, ament-pep257-0.12.15, launch-testing-ros-0.19.13, ament-xmllint-0.12.15, launch-testing-1.0.14, launch-pytest-1.0.14, ament-lint-0.12.15, ament-copyright-0.12.15, colcon-core-0.20.1, cov-3.0.0\ncollected 34 items\n\ntests/paper_rebuild/test_ext_reproduction_evaluation.py ................ [ 47%]\n..................                                                       [100%]\n\n==================================== PASSES ====================================\n__ test_plot_only_saved_series_no_reference_and_failure_keeps_numeric_receipt __\n----------------------------- Captured stderr call -----------------------------\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\n=========================== short test summary info ============================\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search[197-197.0-197000000]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search[1772784066.1979997-1772784066.198-1772784066198000]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search[1.0000005-1.00000049-1000000]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[NaN]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[Infinity]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_nonfinite_or_unknown_time_rejected[UNKNOWN]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_key_collisions_and_reordered_clocks_are_not_silently_deduplicated\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_frozen_reference_wrap_interpolation_and_no_extrapolation\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_synthetic_full_child_metrics_original_denominators_and_reused_values\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_reference_hash_mismatch_retains_failure_without_metrics_or_retry\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_heading_hash_failure_happens_before_reference_open\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_missing_old_variant_does_not_remove_its_common_comparison_slots\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_breaks_preserve_invalid_epochs_wrap_jumps_and_physical_time_gaps\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_plot_only_saved_series_no_reference_and_failure_keeps_numeric_receipt\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[none-True]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[duplicate-False]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[write-False]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_strace_reference_audit_distinguishes_counts_and_forbidden_opens[other_raw-False]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_one_synthetic_evaluator_subprocess_under_real_strace\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_prepare_metadata_only_native_gates[None]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_prepare_metadata_only_native_gates[incomplete]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_prepare_metadata_only_native_gates[wrong_heading]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_prepare_metadata_only_native_gates[wrong_pair_count]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_parent_refuses_existing_output_before_child\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_old_error_mask_corruption_never_enters_common_support[swap_valid_same_count]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_old_error_mask_corruption_never_enters_common_support[swap_q_same_count]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_old_error_mask_corruption_never_enters_common_support[reference_mask]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_old_error_mask_corruption_never_enters_common_support[hold_source]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_old_metric_semantics_must_match_frozen_contract[error_convention]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_old_metric_semantics_must_match_frozen_contract[reference_semantics]\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_late_support_failure_is_atomic_and_cannot_leave_common_member\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_recorded_error_pin_is_verified_and_unknown_pin_is_explicit\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_causal_hold_never_backfills_before_first_native_valid\n======================= 34 passed, 14 warnings in 1.88s ========================\n",
  "stderr": ""
}
```

### 准备完成计数

```json
{
  "status": "PASS_SYNTHETIC_PREPARATION_ONLY",
  "pytest_processes": 3,
  "failed_pytest_processes": 0,
  "case_executions_by_attempt": [
    20,
    25,
    34
  ],
  "case_executions_total": 79,
  "distinct_final_cases": 34,
  "synthetic_evaluator_subprocesses_total": 3,
  "successful_reference_opens_per_synthetic_child": 1,
  "real_evaluator_processes": 0,
  "real_native_processes": 0,
  "real_reference_reads": 0,
  "source_sha256": "616cff8479c7a64a124af24bd01c2ab9a6a284964889a0879c20b00050ead075",
  "test_sha256": "4589e56f3a4c8398ffc94659027bfe29ccf8db6e20180c84729d3e2b2331ae5a",
  "note": "Attempts 2 and 3 add execution gates and reviewer-requested negative controls, not real result retries. Matplotlib dependency deprecation warnings retained; actual sequence raster review remains pending."
}
```

### pytest attempt 4：孤立有效点显示

合成 PNG 实际查看后只增加小点标记；NaN、wrap 和时间 gap 仍断线。真实序列图仍需另行视觉审阅。

```json
{
  "attempt": 4,
  "timestamp_utc": "2026-10-02T13:55:55.417164+00:00",
  "argv": [
    "python3",
    "-m",
    "pytest",
    "-p",
    "no:cacheprovider",
    "--disable-warnings",
    "-rA",
    "tests/paper_rebuild/test_ext_reproduction_evaluation.py",
    "-k",
    "plot_only_saved or breaks_preserve"
  ],
  "exit_code": 0,
  "elapsed_seconds": 1.3683149999997113,
  "reason": "Actual synthetic raster inspection found isolated valid points invisible without markers; added only small markers, preserving NaN/gap separation. Focused plot regression only.",
  "data_mode": "synthetic_unit_tests_only",
  "synthetic_data_used": true,
  "semisynthetic_data_used": false,
  "real_native_processes": 0,
  "real_evaluator_processes": 0,
  "real_reference_reads": 0,
  "synthetic_evaluator_subprocesses_in_this_pytest": 0,
  "source_sha256": "3576636cf0f3192af21d4fc8bbc6cba1c5a4a1c46e8fc741cfab960df5fbc360",
  "test_sha256": "4589e56f3a4c8398ffc94659027bfe29ccf8db6e20180c84729d3e2b2331ae5a",
  "stdout": "============================= test session starts ==============================\nplatform linux -- Python 3.10.12, pytest-6.2.5, py-1.10.0, pluggy-0.13.0\nrootdir: <CODE_ROOT>, configfile: pyproject.toml\nplugins: ament-flake8-0.12.15, ament-pep257-0.12.15, launch-testing-ros-0.19.13, ament-xmllint-0.12.15, launch-testing-1.0.14, launch-pytest-1.0.14, ament-lint-0.12.15, ament-copyright-0.12.15, colcon-core-0.20.1, cov-3.0.0\ncollected 34 items / 32 deselected / 2 selected\n\ntests/paper_rebuild/test_ext_reproduction_evaluation.py ..               [100%]\n\n==================================== PASSES ====================================\n__ test_plot_only_saved_series_no_reference_and_failure_keeps_numeric_receipt __\n----------------------------- Captured stderr call -----------------------------\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'parseString' deprecated - use 'parse_string'\nIn <PYTHON_USER_SITE>/matplotlib/mpl-data/stylelib/classic.mplstyle: 'resetCache' deprecated - use 'reset_cache'\n=========================== short test summary info ============================\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_breaks_preserve_invalid_epochs_wrap_jumps_and_physical_time_gaps\nPASSED tests/paper_rebuild/test_ext_reproduction_evaluation.py::test_plot_only_saved_series_no_reference_and_failure_keeps_numeric_receipt\n================ 2 passed, 32 deselected, 14 warnings in 1.12s =================\n",
  "stderr": ""
}
```

最终准备计数（承接上方三次记录）：

```json
{
  "final_status": "PASS_SYNTHETIC_PREPARATION_ONLY",
  "pytest_processes": 4,
  "failed_pytest_processes": 0,
  "case_executions_by_attempt": [
    20,
    25,
    34,
    2
  ],
  "total_case_executions": 81,
  "distinct_final_cases": 34,
  "synthetic_evaluator_subprocesses_total": 3,
  "real_native_processes": 0,
  "real_evaluator_processes": 0,
  "real_reference_reads": 0,
  "final_source_sha256": "3576636cf0f3192af21d4fc8bbc6cba1c5a4a1c46e8fc741cfab960df5fbc360",
  "final_test_sha256": "4589e56f3a4c8398ffc94659027bfe29ccf8db6e20180c84729d3e2b2331ae5a",
  "no_git_mutations": true
}
```
