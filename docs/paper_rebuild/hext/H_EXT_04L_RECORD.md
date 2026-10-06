# H-EXT-04L 只读收束记录

状态：`PASS_H_EXT_04L_READ_ONLY_CLOSEOUT`。起点 `6aefaa7b5411057ed933302bd79821b1690d04df`，分支 `stage/clean3-math-repair`。一次提交（本记录所在提交）并按用户授权 push；完整 Git 回执在 `<HEXT_ROOT>/11_READONLY_CLOSEOUT_H_EXT_04L/GIT_DELIVERY.json`，提交后写入，避免自引用。

## 授权与实际范围

本任务 native=0、evaluator=0、参考 trace 读取/哈希=0、provider 生成=0、物理删除=0。只读冻结 v2.1 全率误差、15/18 列 GNSS 输入、安装变换后 IMU 增量、原始 status 及求解器逐历元日志。合约升 v1.2；LC01 文献配置为主行，S 为补充，BY2H 使用 CONTRACT_START；amended_after_results_seen=true。算法参数、冻结主链和既有 H02/H03 产物均未重算或改写。

先只读规划，再按批准边界实施，最后由独立 reviewer 复核。终版表格、两张记分板、完整分段与三序列诊断见 [HORIZONTAL_THREE_SEQUENCES.md](../HORIZONTAL_THREE_SEQUENCES.md)。

## 数值与来源门

- v3/v2 原表各52行，除获准的 main_row/manuscript_row 标记外，全部原始 CSV 字段值保留。LC01 LIT/S 全配置全起点共16行单列，并附全部指标。
- BY2O 新表90行：两评估器 × 九方法 × full/主段/次段/段内并集/段外；F01/F02/F03 补齐。H03 原六方法36行的七指标逐值精确一致。
- 主段/次段为闭区间 [3369.94,3411.95] / [3495.94,3508.94]；段外为窗 [3186,3563] 的严格补集。
- v2.1 全率误差按核验过的包 SUBSET_MANIFEST 与 ARCHIVE_RECEIPT 双重 pin 核对；F01 为 v2.1 正式登记的旧文件字节复用，BY2 F01 使用 full_metrics_source_sha256，不使用展示投影哈希。
- 外部全率误差按核验过的 H03 包 MEMBER_MANIFEST 核对；BY2 LC01 文献行用 P07 原 EVALUATION_ARTIFACT_SEAL 的 error_series pin，未以数值相近代替字节身份。
- GNSS/IMU 由冻结 RUN_MANIFEST.provider_hashes 核对，运行配置与逐历元日志由 archive receipt 核对，status 由冻结合约 raw_inputs.status pin 核对。所有读入来源前后字节身份相同。
- 独立复核：full=inside+outside、inside=primary+secondary；加权平方 RMSE 重组一致；yaw all=straight+turn+omega_unmatched；另用 csv + math.fsum 对新增 F01/F02/F03 及 LC01 分段独立复算，与结果差 <1e-12。

冻结包身份：

| 包 | SHA-256 |
| --- | --- |
| c541_v21_handoff.zip | 98a77b4601b897956a6d87f5bfa92e008b584add35e48e2b22a9088ddec07585 |
| hext_three_sequences_handoff_v2.zip | 3ca39f1906f1faa9d98ca841852338e1397d1be560cb9f4d88ab5738d5692678 |

## 输入、日志与误差事实

BY2O GNSS18 全文件2231行、yaw_valid=1 为445行；窗内1886/378，主段210/42，次段65/13，段内并集275/55，段外1611/323（总行/有效行）。三序列 A1 >1.2 s 的缺口均0；零行清单明示零结果。BY2O status 窗内377/段内55/段外322历元，rel_valid、ant_valid 全True，ant_state 全2；两来源保持各自时标/分母。

BY2O 航向尝试/接受/拒绝：F02 段内55/55/0、段外319/319/0；F03/A04/F04 各段内55/50/5、段外319/314/5。三序列12组配置 QM=false、QA=false。

ω 来自冻结安装变换后的 dtheta_z/measured_dt；当前增量覆盖 (前时刻,当前时刻]，不二次变换/去偏、不外推，dt>0.1s 无支持。阈值 |ω|<5°/s 与 ≥5°/s；未关联历元单列，仍进入总体误差统计。中位数/P95 明确为绝对航向误差。BY2/BY2H 段内 N/A，段外为全窗。只报事实，没有写归因结论。

记分板的七指标为 H/3D/Up/yaw/yaw P95/roll/pitch；F04 对文献配置较低数 BY2/H/O=5/5/0，对逐指标 min(LIT,S) 为2/5/0。后者不是可执行组合方法。

## 图与 QA

两图复用 publication.style、qa、protocol_v21_render.figure_checks；LC01 文献柱与同柱位空心 S 标记、BY2H CONTRACT_START、结果后修订 caption 均核对。根代理与独立 reviewer 已实际查看两张 PNG，标签、单位、图例、区间、方法及值正确，无可见裁切/重叠。

| 图 | PNG尺寸 | 自动QA | 视觉QA | PNG SHA-256 |
| --- | --- | --- | --- | --- |
| FIG02S | 4182×2938 | 10/10 PASS | PASS | 17256ebdfe4f6bb0261a233f6b60c2362b84e64e0b27ec991f213e7300c6d98f |
| FIG02S-b | 4180×2507 | 10/10 PASS | PASS | f55c5b9a8d147eca1369bcb89295fea63589522f5400f67e837faaed813a6964 |

PNG/PDF/SVG 共6导出，逐字节核对 publication 副本。原28图目录全部119文件前后哈希一致；`RENDER_MANIFEST.json` 保持 `800df76ad82b68e3fca7aded30081f6d1ad01241175978baf440c9e0f290dd4e`。仅 HEXT_RENDER_MANIFEST 及两张获准扩展图更新；旧 FIG02S/HEXT manifest 共7文件保留在 `R/figures/previous_H_EXT_03`，旧 S/10_FIGURES 不变。

## 验证命令

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /usr/bin/python3 scripts/paper_rebuild/hext04l_closeout.py --code-commit 6aefaa7b5411057ed933302bd79821b1690d04df
PYTHONPATH=src python3 -m pytest -q tests/paper_rebuild/test_hext04_heading_provider.py tests/paper_rebuild/test_hext04_matched.py tests/paper_rebuild/test_hext04l_reporting.py tests/paper_rebuild/test_hext04l_readonly_closeout.py tests/paper_rebuild/test_hext04l_figures.py tests/paper_rebuild/test_hext_figures_gap.py
git diff --check
```

聚合最终验证：**42 passed**；14条第三方 Matplotlib/pyparsing 警告，未使用3D投影。纯库合成测试独立于真实数据表，未调用 native/evaluator，未生成真实运行证据。主行/记分板可由 hext04l_reporting.py 重现；图 CLI 为 hext04l_figures.py，要求实际完整 HEAD 与参数一致。各新 manifest 的 code_commit 是起点，实际 implementation/renderer 文件 SHA 单独记录，不能把未提交源码冒称为起点源码。

## 草案处置与簿记

1. H-EXT-04 LC01-M/LC01-2D/S5 执行部分取消。仅 heading_provider.py、matched.py 中 D4 变换/调度/2D 投影及纯库测试纳入，NOT_AUTHORIZED_FOR_EXECUTION；删除的是拟提交库文件中的执行包装部分，其完整原稿已复制到 `<HEXT_SCRATCH>/H_EXT_04L/DRAFT_PRESERVATION`，未物理删除草案。
2. ext05_sequence_runner.py 仅保留单历元更新的可选 measurement callback 和实际创新维数日志支持；_run_h02_filter_sequence 与 run_h02_native 已按 HEAD 原内容恢复，未提交 H04 native 扩展通路。T5 待预注册；额外身份验证预算问题作废。其他 H04 执行/评估/trace诊断草案以及两个无关本地脚本均保留未跟踪、明确排除提交。
3. 数据派生两次前置工程检查在写输出前停止：BY2 审计没有 integration_convention 显式键；P07 seal 的键为 files_sha256。按实际冻结元数据修正读取，无 native/evaluator/trace，无部分结果冒作完成，无指标或身份门放宽。
4. 图 CLI 曾传入错误完整 commit 后缀，渲染时即发现；按实测 HEAD 修复新图元数据，保留原错误元数据和 FIGURE_METADATA_CORRECTION.json，未改像素/指标、未重绘。CLI 增加实际 HEAD 门，最终 manifest 使用正确起点。
5. 原 H03、v2.1、raw、provider、28图、历史失败与既有包保持不变；所有新派生/图在外部输出根，Git 不含运行产物、figure、manifest、archive 或 local path config。

## 本次产物字节身份

`R=<HEXT_ROOT>/11_READONLY_CLOSEOUT_H_EXT_04L`。

| R内文件 | 行数（如适用） | SHA-256 |
| --- | --- | --- |
| BY2O_SEGMENT_SUMMARY.csv | 90 | a68d5a36eb1ccf808a28842af309d1cccb9748c8e667b6b4ac2bf63580fe0e72 |
| GNSS_YAW_VALIDITY.csv | 12 | 4b21fe978402f0e7ba6f3bef0b16967d111c3dc48d7d60dfc1d767e108c181d3 |
| GNSS_YAW_10S_DISTRIBUTION.csv | 95 | ba7b148df9f4da73473828c0c368ff93f99f86ee3f4fbbe32873bcf4dde388ad |
| A1_GAPS_GT_1P2S.csv | 0 | 7703741f562b3f2c276fc35a9aba6f2de114df21e80f56ebf257cdb5ea03115c |
| STATUS_VALIDITY.csv | 27 | ca2b93124548c8284d53caab9610ac75aa96bd3668aef40ec468efd15607d39a |
| SOLVER_YAW_UPDATES.csv | 36 | f4298fe0ff93311263858c9d1a0cba92d3bde63c922bae215963d5d48d91760c |
| YAW_ERROR_DIAGNOSTICS.csv | 252 | 0024ade723ffb827bd77213c9d061f8e0a82c0cf362b6679c39cfa15f2771091 |
| IMU_OMEGA_ASSOCIATION.csv | 3 | 94978570204df7da45782578a66e738d8b4f8ff3e2b6bf50941059f479c44655 |
| CONTROL_SEGMENT_APPLICABILITY.csv | 2 | a05cdc440f00bf1ba49d4dae72540e66c616b378d8c9e81b7ec5e217a98a55fc |
| H03_SEGMENT_PRESERVATION.csv | 36 | cfa24f8f3a1061a8cf53f65b592b42c82b82695e54d498854f3f2f7cba7b9900 |
| DATA_MANIFEST.json | — | 5a9c2740fb5e856ede39384f1d58bb4c11c39162ea870ce9c0c399f30d378258 |
| FINAL_SUMMARY.json | — | 19c93b5d4a975cba2de5404c592638814d5b7223fe6e66bc74220bde6a9f94e5 |
| figures/HEXT_RENDER_MANIFEST.json | — | fdb7977c747f62dc175c9bd382c7402ec3034435631ab8f9eb95ade9330051ea |
