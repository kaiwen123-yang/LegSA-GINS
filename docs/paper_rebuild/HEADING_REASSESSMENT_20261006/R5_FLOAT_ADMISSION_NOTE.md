# R5 的 GNSS1 FLOAT 实际输入准入补充

原 R5 NMB1–NMB4 的正式记录 native_window 内，共有 **636 个 GNSS1 FLOAT 历元**已经被 GNSS18 标记为位置和接收机速度可用，航向均不可用。因此“系统只接受 FIX”不符合现有输入；正确表述是当前位置／接收机速度允许有效 non-FIX，而这套由两接收机独立位置构成的航向仍要求双 FIX 和基线长度门限。

| 序列 | GNSS1 FLOAT | 位置有效 | 接收机速度有效 | 航向有效 | OTHER_VALID 的位置／速度有效 |
|---|---:|---:|---:|---:|---:|
| NMB1 | 171 | 171 | 171 | 0 | 42 |
| NMB2 | 182 | 182 | 182 | 0 | 39 |
| NMB3 | 130 | 130 | 130 | 0 | 45 |
| NMB4 | 153 | 153 | 153 | 0 | 41 |
| 合计 | 636 | 636 | 636 | 0 | 167 |

这里的“实际准入”精确定义为：读取 R5 已封存的 `GNSS18.gnss`，以 R5 RUN_PLAN_T03 的 native 起止时刻裁剪，使用原始 ZIP 内同 session 的 GNSS1 NAV-PVT UTC 时间逐项精确配对，统计第 16／17／18 列原有有效标志。4 组配对均 missing=0、时间容差为 0；没有生成新 provider，没有重新运行导航算法或评价器。这并不是重新逐次核对最终 EKF 接受数，也不单独证明 FLOAT 的定位精度。F03/F04 共享输入，不把这些历元重复计数。

NMB1 的 native_window 为 [40621.403808498384,40972.56780471802] UTC-day s；NMB2 为 [41112.80181040764,41467.61380090714]；NMB3 为 [41569.003810548784,41929.74181237221]；NMB4 为 [41996.00179710388,42338.60179510117]。这与 [02 原始审查](02_DATA_AND_FIX_AUDIT.md) 的 full-session、原 body support、body−1.1 s 三种统计口径不同，不能混用分母。

与主结果的关系：[BY2/H/O provider 状态统计](PROVIDER_FIX_COUNTS.csv) 中，BY2、BY2H 的 GNSS1 在主窗内均为 FIX；BY2O 有 291 条 GNSS1 FIX / GNSS2 FLOAT，位置和 RV 有效、yaw 无效。该 291 条证明“不要求两接收机同时 FIX 才保留位置／速度”，但不能代替上述 636 条“主接收机自身 FLOAT 的位置／速度准入”证据。

来源与复现：

- [完整计数 CSV](R5_FLOAT_PROVIDER_ADMISSION.csv)：包括 FULL_GNSS18 与 NATIVE_WINDOW 两种域、全部接收机状态，40 行。
- [来源、窗口与哈希 JSON](R5_FLOAT_PROVIDER_ADMISSION.json)：ZIP、四个 raw member、四个 GNSS18、R5 plan 与脚本 SHA256。
- [只读统计脚本](../../../scripts/paper_rebuild/heading_reassessment_20261006/count_r5_float_admission.py)：检查原始 UBX 长度与 checksum，当前 ZIP/member/provider 哈希与既有记录一致后才计数。输出为 UTF-8 / LF。
- 原有效性定义见 [R5 provider builder](../EXISTING_DATA_R5_20261005/new_data/run_new_sequences.py) 的 `raw_epochs()` / `gnss_inputs()`：位置由 GNSS1 fixType=3、gnssFixOK、UTC 有效、HP 有效判定；RV 由 GNSS1 fixType=3 与 gnssFixOK 判定；carrier FLOAT 本身不是位置／RV 拒绝条件。

复现命令（Ubuntu-22.04 WSL，输出前缀应为尚不存在的文件）：

```bash
python3 scripts/paper_rebuild/heading_reassessment_20261006/count_r5_float_admission.py \
  --code /home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001 \
  --raw /mnt/g/LegSA-GINS-project/data/raw/XB_PG/2026-01-05 \
  --plan docs/paper_rebuild/EXISTING_DATA_R5_20261005/new_data/RUN_PLAN_T03.json \
  --out /tmp/R5_FLOAT_PROVIDER_ADMISSION_RECHECK
```
