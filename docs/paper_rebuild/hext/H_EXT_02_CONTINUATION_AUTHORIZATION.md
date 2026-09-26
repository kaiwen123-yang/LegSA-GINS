# H-EXT-02 bounded continuation authorization — H-EXT-03

Authorization: `H-EXT-03 prompt 2026-09-16`. Status: `HUMAN_AUTHORIZED_PREREGISTRATION`. Contract: `H_EXT_CONTRACT_V1.yaml`, version `1.1`. Starting commit: `d8f1d013b4c1d68ddb1c2400cbfe35ac46cbea57`.

## Preserved original attempt

H-EXT-02 remains `HARD_STOP_EVALUATOR_CONSISTENCY`: 14 completed native runs; 17 evaluator invocations (16 passed, 1 failed), 11 uncalled slots. The original stop directory, failed evaluation, native outputs and package are immutable. The old package `<HANDOFF_ROOT>/hext_three_sequences_handoff.zip` has SHA-256 `efb64041e5add0b8d47542e446ae80abe3e038a9bdc0ee1d9620f4216764cc15`, 1,084,956,510 bytes. This continuation does not relabel the original failed attempt as a success.

## Authorized scope and budget

- Native calls: **0**. Reuse and hash-check all 14 original native outputs; no parameter changes or searches.
- Evaluator calls: **at most 11** original uncalled slots; expected **10** after the divergent FILE_START row is blocked. No retries. Each invoked evaluator child alone opens trace exactly once; no parent trace payload read or hash.
- Preserve protocol v2.1, its 20_FINALIZE artifacts, 28 publication figures and `RENDER_MANIFEST.json`, all frozen algorithm source and `ext05_pavlasek.py`. No NAV_10HZ substitution.
- New temporary output: `<HEXT_SCRATCH>/H_EXT_03`; archive through the existing stage root without overwriting original evidence. Rebuild 08 aggregate, render independent FIG02S/HEXT_RENDER_MANIFEST, update documentation and create `hext_three_sequences_handoff_v2.zip`.

## Human decisions D7–D12

### D7

硬停分类：读取 EXT05C-S/BY2H/FILE_START 的全率 native NAV，报告首个越界历元、最大 |位置−首历元| 与最大 |速度|；该行 native 状态 ALGORITHM_FAILURE_DIVERGED，其 v3/v2 科学评估槽为 NOT_RUN_ALGORITHM_FAILURE。已发生的第 17 次评估原记录 FAILED_EVALUATOR_CONSISTENCY 保留，不重试；科学槽分类不抹去历史进程调用。

### D8

评估前有界门（仅外部行）：native NAV 全行有限；位置相对首历元的三维欧氏范数 ≤ 1e4 m；速度三维欧氏范数 ≤ 50 m/s；高度相对首历元绝对值 ≤ 1e3 m。原生 NAV.csv 的固定 NED 米制坐标；全文件、不只评估窗。场地尺度约 300 m，阈值远离真实轨迹。不通过 → ALGORITHM_FAILURE_DIVERGED，不调评估器。14 次 native 全部执行并记录；已通过的 16 次评估回溯核对，不通过只报告不改结果。

### D9

D2 看到结果后修订：BY2H 论文对比行 = CONTRACT_START（协议起点，与提出方法相同；窗前 IMU 中断被协议起点排除）；FILE_START 保留为方法原生诊断行，同表列出。BY2、BY2O 保持 FILE_START。amended_after_results_seen=true；附 BY2H LC01 与 LC01-S × FILE_START/CONTRACT_START × v3/v2 共 8 行 H/yaw 数值；修订方向混合：航向略差、位置更好。旧 D2、run_matrix 的执行身份保留为历史，不改原 native。

### D10

主配置选择结果 S：BY2 C00 v3 yaw RMSE 1.5392385536245534 deg < 2.9948274600591076 deg；三序列统一使用 S 论文行，文献 LIT 行进入补充材料，表中两版都保留。

### D11

先确认 A10 两行 NAV 的真实来源；仅 v2.1 序列全率 NAV 如在 c541_v21_handoff.zip（SHA256 98a77b4601b897956a6d87f5bfa92e008b584add35e48e2b22a9088ddec07585）或 20_FINALIZE 归档内，可核包/成员哈希后只读提取至 hext_scratch 诊断；否则 UNAVAILABLE。禁止 NAV_10HZ 或旧校准链替代。

### D12

本任务起：评估器进程失败、身份不等或访问审计失败 = 硬停；一致性门失败先查 native D8：无界按 D7 分类继续，有界按 GINav 先例逐行 UNAVAILABLE_EVALUATION_FAILED、正式指标空缺并继续；均不重试。原 capture 阈值与科学计算不变。

## D7 observed native evidence before continuation

The hash-verified full `NAV.csv` contains 63,304 rows. SHA-256: `5d24956f642ceccaf5f84310c251d02c935e7abc789d6e2572804f113f30fc2c`. All numeric fields are finite. First D8 crossing: data row 2,446 / CSV line 2,447, relative time `418.59999990463257 s`, absolute `1772784418.6 s`; speed `51.19872445663034 m/s`, displacement `23.01454294544155 m`, relative height `9.62322100024769 m`. Maximum displacement `4.164517139545904e18 m`, maximum speed `4.2392617981840067e18 m/s`, maximum absolute relative height `3.7731674202350495e18 m`. These are native divergence diagnostics, not evaluator RMSE.

## D9 amendment evidence — results already seen

`amended_after_results_seen: true`. The following eight existing successful evaluations motivate the human-selected BY2H manuscript start. Both LC01 and LC01-S improve H while yaw worsens slightly; the amendment direction is mixed. Full source paths and SHA-256 values are pinned in the contract. FILE_START remains in the same table as native-method diagnostic evidence.

| Evaluator | Configuration | Start | H RMSE (m) | Yaw RMSE (deg) |
| --- | --- | --- | ---: | ---: |
| v3 | LC01 | FILE_START | 0.09745269819180266 | 2.1739364356142343 |
| v3 | LC01 | CONTRACT_START | 0.0746064486934978 | 2.208612313835051 |
| v3 | LC01-S | FILE_START | 0.10670864118045774 | 1.7940541340876093 |
| v3 | LC01-S | CONTRACT_START | 0.08373314985151889 | 1.9430028350481119 |
| v2 | LC01 | FILE_START | 0.1768954441095971 | 2.1739364356142343 |
| v2 | LC01 | CONTRACT_START | 0.16527957194800608 | 2.208612313835051 |
| v2 | LC01-S | FILE_START | 0.18635526660363833 | 1.7940541340876093 |
| v2 | LC01-S | CONTRACT_START | 0.17408779595517415 | 1.9430028350481119 |

## Source and unavailable conventions

A10’s two 11-column NAV rows come from `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/03_CALIBRATED_RUNS/CLEAN5_CALIBRATED_BY2H_A04/KF_GINS_Navresult.nav`, SHA-256 `9da51135029a5f54fb1e387c5df8b20c6e364458731644239332ee5f36710b01`, not protocol v2.1. That source cannot fill a missing v2.1 full-rate diagnostic. D11 checks the specified v2.1 ZIP/finalize member inventory and original native hashes; missing items remain UNAVAILABLE.

The GINav precedent is documented in `CLEAN5_DEGRADATION_SUBSET_RESULTS.md`, “横向 GINav 评估审计”: evaluator exit zero does not bypass consistency; a bounded consistency failure has no admitted RMSE, bias or coverage. D12 separates that row outcome from technical process/identity failures.

## Validation and freeze

Focused tests cover D8 boundaries/nonfinite/full-file semantics, no-repeat slot selection, D12 technical versus consistency failures, failure-aware aggregation and BY2H manuscript starts. The original native filter and its parameters are untouched. The preregistration commit is the H03 code freeze; its exact hash and test results are recorded in `<HEXT_ROOT>/03_CONTINUATION/PREREG/`. No evaluator starts before this commit is pushed.

Original 16 passed evaluations retain their bytes and values. Retrospective D8 disagreements, if any, are reported separately and do not alter admitted old results. Whole-stage calls and scientific-slot outcomes have separate ledgers: the old failed v3 process remains one actual call even though D7 makes both scientific slots `NOT_RUN_ALGORITHM_FAILURE`.

## Packaging identity

The result commit records the external validation-receipt location. Packaging after that commit embeds both H02 and H03 authorization/result commit hashes, validates each member SHA-256 and CRC, builds on ext4 and copies exclusively to G: with read-back verification. The final ZIP hash is not inserted into its own contents or parent commit. The v1 package remains byte-identical.

## Preflight evidence

`PASS_H03_PREFLIGHT`: v1 package SHA/size and 511 stage-member identities passed. All 14 full native NAV files were checked: 13 bounded, one `ALGORITHM_FAILURE_DIVERGED`. Retrospective checks on the 16 admitted H02 evaluations passed 16/16; none were altered. The preflight made zero native/evaluator/trace calls. Original 28 figures and RENDER_MANIFEST remain byte-identical.

D11 inventory finds no full-rate NAV in the 4700-member verified v2.1 package or 20_FINALIZE. All four requested NAVs are explicitly sealed-not-retained. Four original BY2O A04/F04 v3/v2 full-rate error series remain available (76,548 rows each), with SHA-256 independently pinned by archive receipts and the verified package index. Exact H03 occlusion windows are derived read-only from these full-rate errors. Existing frozen primary endpoints 3369.943066596985–3411.951585292816 are not relabeled as 3369.94–3411.95; ZIP 10 Hz display projections are not used.

Final preregistration validation: **94 passed**, including H03 continuation/aggregation, existing H-EXT, EXT05 filter and Phase-5 regression tests; zero real evaluator/native calls in tests. `git diff --check` passed; frozen `ext05_pavlasek.py` and `phase5_runner.py` have no diff. The original 16 successful evaluation rows are explicitly marked `result_reused=true`, with original scientific commits retained.
