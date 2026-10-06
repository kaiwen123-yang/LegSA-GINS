# 新 EXT02 / EXT03 已有失败的只读说明

本项读取当前 `RAW_REPRO_V1` 已有输出；没有重新运行或调整算法。范围是三个序列的完整 native 输入历元历史，**不是评估窗内样本数，也不是成功参考匹配点数**。全部 EXT02 `NUMERICAL_FAILURE` 共 103 条逐一保留；没有按参考精度筛选。

## 读取范围与状态分母

每个序列的 EXT02、EXT03 `RUN.json` 与 `HEADING.csv` 均全文读取。EXT02 三份 `EPOCH_EVIDENCE.jsonl.gz` 各顺序读取一次至 EOF，按 epoch、时间字段、原状态与 HEADING 全行关联；EXT03 gzip 本项读取 0 次，仅报告已有终态计数。

| 序列 | 全历史历元 | EXT02 WRAPPED_CANDIDATE | EXT02 INVALID | 其中 NUMERICAL_FAILURE | EXT03 float | EXT03 paper_ratio_fixed | EXT03 invalid |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BY2 | 1509 | 1057 | 452 | 20 | 531 | 78 | 900 |
| BY2H | 1483 | 1128 | 355 | 44 | 453 | 73 | 957 |
| BY2O | 2231 | 1527 | 704 | 39 | 486 | 7 | 1738 |

以上 `RUN.status=COMPLETED` 表示程序完成全部登记历元，不表示每历元可用。`WRAPPED_CANDIDATE` 不等于已验证整数正确；EXT03 的 `float` 与 `paper_ratio_fixed` 是不同输出类别，不能将未固定的可用 float 行当作失败或将固定标签当作独立真值验证。

## EXT02：103 条外层 NUMERICAL_FAILURE 的内层证据

| 序列 | 失败历元 | 所含候选总数 | 已收敛候选 | 未完成候选原状态与次数 | 每失败历元未完成候选数分布 |
| --- | ---: | ---: | ---: | --- | --- |
| BY2 | 20 | 2650 | 2614 | {"MAX_ITERATIONS_INTEGER_UNSTABLE_AND_DIRECTION_NOT_CONVERGED":36} | {"1":12,"2":5,"4":2,"6":1} |
| BY2H | 44 | 4809 | 4726 | {"MAX_ITERATIONS_INTEGER_UNSTABLE_AND_DIRECTION_NOT_CONVERGED":83} | {"1":21,"2":13,"3":7,"4":2,"7":1} |
| BY2O | 39 | 6602 | 6490 | {"MAX_ITERATIONS_INTEGER_UNSTABLE_AND_DIRECTION_NOT_CONVERGED":112} | {"1":15,"2":7,"3":6,"4":7,"6":1,"7":1,"12":2} |

候选级原状态总计：`{"MAX_ITERATIONS_INTEGER_UNSTABLE_AND_DIRECTION_NOT_CONVERGED":231}`。候选次数与历元次数分母不同；一个历元可有多个未完成候选。

**实际核实结论：103/103 个失败历元都仍有收敛候选。** 这些历元共含 14,061 个候选，其中 13,830 个已收敛、231 个未完成；231 个未完成候选全部达到 20 次，末次整数修正未稳定且方向变化仍大于 `1e-10`。其原 `failure_code` 全为 `null`、保存目标值均有限；本集合观察到的是候选细化未收敛导致整个候选池被拒，不是保存了 `SPHERE_SOLVER_FAILURE`、`NONFINITE_OBJECTIVE` 或 `ALL_REFINEMENTS_FAILED` 这几类异常。这里只判定已有记录所显示的直接终止原因，不推出未收敛的物理根因。

实施判据来源：`src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_ext02.py:120` 的 `solve_cwls`，尤其 143–168 行；固定 `K=all unique candidates`。只要候选池中有任一未收敛、带 failure_code 或目标值缺失/非有限的候选，就拒绝整个历元；其余已收敛候选不能单独使该历元变为有效。原外层 `NUMERICAL_FAILURE` 和完整 `failure_detail` 在 CSV 原样保留，不改标为其他状态。

迭代语义来源：`ext02_cwls.py:859` 的 `_refine_candidate`；常量 45–46 行规定最多 20 次，方向变化阈值 `1e-10`。必须同时满足整数修正向量稳定和方向变化不超过该阈值。各 `MAX_ITERATIONS_*` 原词来自 923–929 行。该说明仅解释保存的终态，不判定更上层物理成因、phase-bias、正确模糊度或若放宽准则能否改善。没有新增求解、重算目标函数或事后挑选最佳候选。

`FAILURE_DETAIL.csv` 的 `candidate_statuses_json` 将这些失败历元内**全部候选**的原终态按完全相同字段组合分组，保留每个 coarse_index 与源数组索引，可无损展开状态；`incomplete_candidate_iterations_json` 保留全部 231 个未完成候选的目标值等终态，以及全部原迭代号、整数修正、方向变化、整数稳定标记。已收敛候选的目标值及原 evidence 矩阵/几何仍在原文件，本 CSV 未复制。`null` 是原缺失值，不是零。

## 其余 EXT02 输入/模型门失败与 EXT03 状态

| 序列 | 方法 | 原失败 token | 历元数 |
| --- | --- | --- | ---: |
| BY2 | EXT02 | `INSUFFICIENT_CP_VALID` | 11 |
| BY2 | EXT02 | `INSUFFICIENT_DD_DIMENSION` | 1 |
| BY2 | EXT02 | `INSUFFICIENT_HALF_CYCLE_VALID` | 374 |
| BY2 | EXT02 | `INSUFFICIENT_SATELLITE_STATES` | 46 |
| BY2 | EXT02 | `NUMERICAL_FAILURE` | 20 |
| BY2 | EXT03 | `GNSS1_PNTPOS_REJECTED` | 699 |
| BY2 | EXT03 | `GNSS2_PNTPOS_REJECTED` | 149 |
| BY2 | EXT03 | `INSUFFICIENT_GPS_DUAL_FREQUENCY_SATELLITE_STATES` | 52 |
| BY2H | EXT02 | `INSUFFICIENT_CP_VALID` | 14 |
| BY2H | EXT02 | `INSUFFICIENT_HALF_CYCLE_VALID` | 297 |
| BY2H | EXT02 | `NUMERICAL_FAILURE` | 44 |
| BY2H | EXT03 | `GNSS1_PNTPOS_REJECTED` | 752 |
| BY2H | EXT03 | `GNSS2_PNTPOS_REJECTED` | 186 |
| BY2H | EXT03 | `INSUFFICIENT_GPS_DUAL_FREQUENCY_SATELLITE_STATES` | 19 |
| BY2O | EXT02 | `INSUFFICIENT_CP_VALID` | 93 |
| BY2O | EXT02 | `INSUFFICIENT_HALF_CYCLE_VALID` | 572 |
| BY2O | EXT02 | `NUMERICAL_FAILURE` | 39 |
| BY2O | EXT03 | `GNSS1_PNTPOS_REJECTED` | 1049 |
| BY2O | EXT03 | `GNSS2_PNTPOS_REJECTED` | 675 |
| BY2O | EXT03 | `INSUFFICIENT_BDS_DUAL_FREQUENCY_SATELLITE_STATES` | 6 |
| BY2O | EXT03 | `INSUFFICIENT_GPS_DUAL_FREQUENCY_SATELLITE_STATES` | 8 |

EXT03 `GNSS1_PNTPOS_REJECTED` / `GNSS2_PNTPOS_REJECTED` 保留原接收机身份，表示相应 SPP 准入被拒；后者是在先前阶段已通过后遇到的拒绝，不是两个接收机同时不可用率。`INSUFFICIENT_GPS_DUAL_FREQUENCY_SATELLITE_STATES` / `INSUFFICIENT_BDS_DUAL_FREQUENCY_SATELLITE_STATES` 表示对应双频 DD 几何构造的卫星状态数量门未满足（`reproduction_backend.py:207`）。本项只读 RUN/HEADING，不进一步拆分其输入原因，也不把这些 token 解释为已发生 KF/MLAMBDA 数值崩溃。

EXT02 的有效位、半周有效位、DD 维数、卫星状态门失败另列，不并入 103 条候选细化失败。所有失败总数在 RUN 和 HEADING 核对一致，未因没有 yaw 数值而删除。

## 定位与逐行复查

- 明细：[FAILURE_DETAIL.csv](FAILURE_DETAIL.csv)，共 139 行：`EXT02_NUMERICAL_FAILURE_EPOCH` 恰为 103 行，每行一历元；EXT02 原状态汇总 17 行、EXT03 原状态汇总 19 行。`*_STATUS_SUMMARY` 为原汇总单元格，和历元行重叠，不能相加成运行数。
- 原文件：`<EXT_REPRO_ROOT>/runs/<sequence>__<method>__RAW_REPRO_V1/{RUN.json,HEADING.csv,EPOCH_EVIDENCE.jsonl.gz}`。真实根只在 ignored `configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json` 解析。
- `epoch_index` 沿用原 0 基身份；`data_row` / `jsonl_line` 为 1 基数据行/文本行。每条失败 CSV 同时保存原 `gps_week` / `gps_tow_seconds` / `time_unix_s`。
- recorded SHA 来自各 RUN 输出清单。本项只核读取前后大小和 mtime 未变，未将记录哈希冒充本项重新计算的哈希。

## 本次读取回执

采集 UTC：`2026-10-02T14:00:36.572646+00:00`。下表的顺序读取均到 EOF（gzip 自身 CRC 校验成功），没有第二次打开、预览后重开或失败重试。

| 序列 | gzip 打开数 | 完整 JSONL 行 | NUMERICAL_FAILURE 行 | HEADING 关联不一致 | 读取前后元数据不变 |
| --- | ---: | ---: | ---: | ---: | --- |
| BY2 | 1 | 1509 | 20 | 0 | True |
| BY2H | 1 | 1483 | 44 | 0 | True |
| BY2O | 1 | 2231 | 39 | 0 | True |

提取表回读时首次遇到 Python CSV 默认单字段 131,072 字节限制；该检查未打开任何 gzip。随后只读取已提取 CSV，将全部候选终态改为可无损展开的字段分组，保留全部未完成候选的迭代记录；最终默认 CSV 限额下可读取。此为说明文件读取/编码处理，不是科学运行失败或原流重读。最终检查通过：103 个运行/历元键唯一、每个候选池源数组索引完整、231 个未完成候选的 20 次迭代记录齐全、目标值及未包裹目标值均有限、无机内绝对路径；检查期间额外 gzip 打开 0 次。

读取回执原值（路径别名，哈希仅 recorded）：

```json
[
  {
    "sequence": "BY2",
    "run_id": "BY2__EXT02__RAW_REPRO_V1",
    "source": "<EXT_REPRO_ROOT>/runs/BY2__EXT02__RAW_REPRO_V1/EPOCH_EVIDENCE.jsonl.gz",
    "gzip_open_count": 1,
    "read_mode": "one sequential read to physical EOF and gzip CRC",
    "stream_record_count": 1509,
    "numerical_failure_rows": 20,
    "heading_join_mismatches": 0,
    "recorded_sha256": "084d516391f08074e427a692a3332e20581cdcdf821ff86f0c1b3092139ef391",
    "hash_status": "RECORDED_ONLY_NOT_REHASHED",
    "complete_stream": true,
    "metadata_unchanged": true,
    "incomplete_candidate_states": {
      "MAX_ITERATIONS_INTEGER_UNSTABLE_AND_DIRECTION_NOT_CONVERGED": 36
    },
    "incomplete_candidate_failure_codes": {
      "null": 36
    },
    "incomplete_candidates_per_failed_epoch": {
      "1": 12,
      "2": 5,
      "4": 2,
      "6": 1
    },
    "candidate_total_in_failed_epochs": 2650,
    "converged_candidates_in_failed_epochs": 2614,
    "byte_size": 10417807
  },
  {
    "sequence": "BY2H",
    "run_id": "BY2H__EXT02__RAW_REPRO_V1",
    "source": "<EXT_REPRO_ROOT>/runs/BY2H__EXT02__RAW_REPRO_V1/EPOCH_EVIDENCE.jsonl.gz",
    "gzip_open_count": 1,
    "read_mode": "one sequential read to physical EOF and gzip CRC",
    "stream_record_count": 1483,
    "numerical_failure_rows": 44,
    "heading_join_mismatches": 0,
    "recorded_sha256": "84d37e17f887f0fe38fcd9b5dac63ab839416ca0ddf1134647dea7b66298e0c0",
    "hash_status": "RECORDED_ONLY_NOT_REHASHED",
    "complete_stream": true,
    "metadata_unchanged": true,
    "incomplete_candidate_states": {
      "MAX_ITERATIONS_INTEGER_UNSTABLE_AND_DIRECTION_NOT_CONVERGED": 83
    },
    "incomplete_candidate_failure_codes": {
      "null": 83
    },
    "incomplete_candidates_per_failed_epoch": {
      "1": 21,
      "2": 13,
      "3": 7,
      "4": 2,
      "7": 1
    },
    "candidate_total_in_failed_epochs": 4809,
    "converged_candidates_in_failed_epochs": 4726,
    "byte_size": 10376024
  },
  {
    "sequence": "BY2O",
    "run_id": "BY2O__EXT02__RAW_REPRO_V1",
    "source": "<EXT_REPRO_ROOT>/runs/BY2O__EXT02__RAW_REPRO_V1/EPOCH_EVIDENCE.jsonl.gz",
    "gzip_open_count": 1,
    "read_mode": "one sequential read to physical EOF and gzip CRC",
    "stream_record_count": 2231,
    "numerical_failure_rows": 39,
    "heading_join_mismatches": 0,
    "recorded_sha256": "fa16bcb1e184fa38cadefe1d72a3eaa4650fe8b117bcb6f4259c6e968fd69d97",
    "hash_status": "RECORDED_ONLY_NOT_REHASHED",
    "complete_stream": true,
    "metadata_unchanged": true,
    "incomplete_candidate_states": {
      "MAX_ITERATIONS_INTEGER_UNSTABLE_AND_DIRECTION_NOT_CONVERGED": 112
    },
    "incomplete_candidate_failure_codes": {
      "null": 112
    },
    "incomplete_candidates_per_failed_epoch": {
      "1": 15,
      "2": 7,
      "3": 6,
      "4": 7,
      "6": 1,
      "7": 1,
      "12": 2
    },
    "candidate_total_in_failed_epochs": 6602,
    "converged_candidates_in_failed_epochs": 6490,
    "byte_size": 16909873
  }
]
```

本项新增 solver/native/provider/evaluator 调用均为 0；reference/raw/V3 error-series 打开均为 0；EXT03 gzip 打开为 0；无 Git 操作。当前文件为已有新结果的说明，不替换原输出、旧结果、历史失败或科学正确性审查。

源码身份按各 RUN 的原 `code_commit` / `source_hashes` 保留。六份 RUN 的提交：

- `BY2__EXT02__RAW_REPRO_V1`: `801ffe359c10466d8efd3d600a341cac1463aabf`; RUN `#/source_hashes` 为执行时记录，不是本项新增哈希。
- `BY2__EXT03__RAW_REPRO_V1`: `801ffe359c10466d8efd3d600a341cac1463aabf`; RUN `#/source_hashes` 为执行时记录，不是本项新增哈希。
- `BY2H__EXT02__RAW_REPRO_V1`: `9a844d518c559ca33d852a1c6d81f0f13df0ea59`; RUN `#/source_hashes` 为执行时记录，不是本项新增哈希。
- `BY2H__EXT03__RAW_REPRO_V1`: `9a844d518c559ca33d852a1c6d81f0f13df0ea59`; RUN `#/source_hashes` 为执行时记录，不是本项新增哈希。
- `BY2O__EXT02__RAW_REPRO_V1`: `9a844d518c559ca33d852a1c6d81f0f13df0ea59`; RUN `#/source_hashes` 为执行时记录，不是本项新增哈希。
- `BY2O__EXT03__RAW_REPRO_V1`: `9a844d518c559ca33d852a1c6d81f0f13df0ea59`; RUN `#/source_hashes` 为执行时记录，不是本项新增哈希。
