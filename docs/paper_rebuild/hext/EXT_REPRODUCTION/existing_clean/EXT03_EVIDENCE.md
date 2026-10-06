# EXT03：CLEAN4 旧实现、全部模式与适用性结果

本页只转录既有记录。没有执行 EXT03、provider、evaluator 或测试，也没有校验旧哈希。所有下述原件相对 `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON`；小型完整源副本在 [horizontal_sources](horizontal_sources/)，路径、原行值和读取深度在 [CLEAN4_CLEAN7_INDEX.csv](CLEAN4_CLEAN7_INDEX.csv)。

原文身份为 Yang 2024，*GPS/BDS Dual-Antenna Attitude Determination With Baseline-Length Constrained Ambiguity Resolution: Method and Performance Evaluation*，DOI `10.1109/TIM.2024.3374423`。`11_REPORT/PHASE3_STATUS.json` 原复现层级是 `FAITHFUL_ALGORITHM_REPRODUCTION WITH_DECLARED_UNSPECIFIED_STOCHASTIC_INSTANTIATION`。它不是“所有参数都由论文唯一指定”。

## 应直接读取的文件

- `04_EXT03_YANG2024/C00/EXT03_C00_NATIVE_SUMMARY.json`：原生输入/源码/模型登记、10 个模式身份。
- 同目录 `EXT03_C00_MODE_SUMMARY.csv`、`EXT03_C00_SENSITIVITY_SUMMARY.csv`、`EXT03_STOCHASTIC_PARAMETER_REGISTRY.csv`：完整旧模式与参数来源；不是本轮新增网格。
- 同目录 `EXT03_C00_NATIVE_HEADING_RESULTS.csv`、`EXT03_C00_FAILURE_LEDGER.csv`：15090 条原生历元、7968 条失败完整读取；大副本在 `<EXT_REPRO_ROOT>/collection_detail/existing_clean/horizontal_sources/`，原件路径不变。历元数不能当作 native 进程数。
- `POST_NATIVE/EXT03_C00_PROXY_SUMMARY.csv`：30 行，原 proxy 关系及 ratio-fixed 不一致记录。
- `POST_NATIVE_RECOVERY_RTKLIB_TIME_ASSOCIATION_R1/EXT03_C00_TRACE_SUMMARY_R1.csv`：40 行，保留 float / invalid / paper_ratio_fixed / ALL_VALID 和各自分母。
- `11_REPORT/PHASE3_STATUS.json` 与 `PHASE3_EXT03_C00_REPORT.md`：旧最终状态与声明边界。
- `11_REPORT/PHASE3_EXT03_C00_NATIVE_SOURCE_PROVENANCE_R2/RECOVERY_MANIFEST.json`、`SOURCE_RECOVERY_FREEZE.json`、`POST_FREEZE_FILECHANGES.json`：旧冻结源码恢复记录。

## 全部模式原数

下表直接转录 `EXT03_C00_MODE_SUMMARY.csv` 第 1–10 数据行；每行原总数均为 1509。

|行|system_mode|constraint_mode|baseline_sigma_m|valid_count|paper_ratio_fixed_count|invalid_count|
|---:|---|---|---:|---:|---:|---:|
|1|GPS_DUAL_FREQUENCY|UNCONSTRAINED|空|768|230|741|
|2|GPS_DUAL_FREQUENCY|CONSTRAINED|0.01|768|249|741|
|3|BDS_DUAL_FREQUENCY|UNCONSTRAINED|空|966|460|543|
|4|BDS_DUAL_FREQUENCY|CONSTRAINED|0.01|966|450|543|
|5|GPS_BDS_DUAL_FREQUENCY|UNCONSTRAINED|空|609|41|900|
|6|GPS_BDS_DUAL_FREQUENCY|CONSTRAINED|0.001|609|83|900|
|7|GPS_BDS_DUAL_FREQUENCY|CONSTRAINED|0.005|609|83|900|
|8|GPS_BDS_DUAL_FREQUENCY|CONSTRAINED|0.01|609|105|900|
|9|GPS_BDS_DUAL_FREQUENCY|CONSTRAINED|0.02|609|72|900|
|10|GPS_BDS_DUAL_FREQUENCY|CONSTRAINED|0.05|609|72|900|

原最终状态 `native_row_conservation` 记录 10 模式、15090 行、7122 有效、7968 失败，与实读文件行数相符。第 8 行是既有主模式；没有从结果更好的模式重选主模式。`ambiguity_correctness_known=false` 适用于所有模式；“paper-ratio-fixed”只是原规则状态。

主模式原 `valid_rate=0.40357852882703776`，`paper_ratio_fixed_rate=0.06958250497017893`。这些分母是 1509 个原生配对历元。原 proxy 表第 15 行的 `proxy_inconsistent_ratio_fixed_count=101`，分母为该行 105 个 ratio-fixed，不能说 101 个已被独立真值证实错误。

恢复 trace 表第 35 行（`solution_state=ALL_VALID`）原 `rmse=84.34382296702495°`，`valid_count=609`、`valid_matched_count=541`、`fixed_window_input_count=1370`、`valid_coverage=0.3948905109489051`。这里的 541 是该主模式的匹配历元数，与 Canonical-541 案例集合没有关系。第 15 行（`paper_ratio_fixed`）原 `rmse=40.63084624232342°`，`count=105`；第 13 行 float 原 `rmse=91.81238899179856°`、`count=436`。无效行的 RMSE 留空，未填成零。

## 旧 PASS 的准确含义

原终态为 `PASS_PHASE3_EXT03_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT`。旧状态记录 focused tests 85 PASS，full tests 783 PASS / 10 skipped / 14 warnings。上述数字都是旧回执；本轮测试调用为 0，也没有把这些 PASS 解释为物理航向准确、相位偏差已经解决或跨序列复现成功。

`provenance.phase_bias_calibration=false`。原 `POST_NATIVE/EXT03_C00_PHASE_BIAS_RELATIONSHIP.json` 也已完整读到；它保留旧描述关系，未用于本轮标定、调参或推断因果。原 HPPOSECEF proxy 与 trace 仍是既有诊断/参考，不是独立真值。旧初步状态、原 POST_NATIVE、RTKLIB 时间关联恢复版本和最终报告同时保留；恢复 status 明示 `supersedes_for_rtklib_time_association_only=true`。

## 可供下一小项使用的身份入口

原生摘要 `provenance.code_commit=b6fac17b91ef33e7e3296de5f439939f3b7a1f5e` 的原语义是 `BASE_HEAD_ONLY_WITH_HASHED_RUNTIME_SOURCE_OVERLAY`，不能单靠该 Git SHA 代替原生源码身份。最终状态记载的 `final_commit=82b8035863ab3f40a694d4ac0ce55c9166671941` 是旧收尾身份，不能改写前者。

记录的 native source fingerprint 为 `35dd196aef5ae310e328705de2f483238e9e15bc9cbd67364d73de4950e1235a`。R2 恢复目录存在 `phase3_runner.native_frozen.py`、`POST_FREEZE_NATIVE_TO_CURRENT.patch`、`SHA256SUMS`；本轮只定位这些源码/patch，不做实现审查。R2 JSON 原字段为 `recovery_role=SOURCE_PROVENANCE_ONLY`、`native_rerun=false`、`native_files_mutated=false`、`all_eight_runtime_sources_reconciled=true`（末项来源于最终 STATUS）。这些是旧记录，而非本轮新验证。

当前源码与测试入口：

- `src/legsa_gins/paper_rebuild/horizontal_literature/ext03_yang2024.py`
- `src/legsa_gins/paper_rebuild/horizontal_literature/phase3_runner.py`
- `configs/paper_rebuild/horizontal_literature/PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml`
- `scripts/paper_rebuild/run_horizontal_literature_phase3.py`
- `tests/paper_rebuild/test_horizontal_ext03_yang2024.py`
- `tests/paper_rebuild/test_horizontal_phase3_c00.py`

本页不确认当前源码与旧冻结版本字节相同，不确认新适配器可运行。大 DD、KF state、cycle-slip、ambiguity-state、proxy/trace 逐历元诊断载荷仅登记位置；与完整读取的小型汇总、原生 heading/失败表分开。没有打开原始 GNSS 或 reference 数据。
