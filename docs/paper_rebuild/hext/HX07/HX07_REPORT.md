# HX-07 报告

**HARD_STOP — V0/BY2 固定历元 157/1370，登记期望 153/1370，差 +4，超过允许 ±2。**

按任务 §2 的“超出即硬停并报告，不得继续”，在第一条 V0 后停止。未运行 BY2H/BY2O 的 V0、V1 或 V2；未启动任何参考评估。不得据此报告四星座或 fix-and-hold 的效果。

## 1. 起点与登记

起点 HEAD `2723868b6605e9b6239d9829762caa799fa98eb4`、分支 `stage/clean3-math-repair` 均匹配；29 条既有未跟踪路径及其 SHA-256 全部与 MS01_BASELINE.json 一致。开工磁盘余量 E: 125173804 KiB、G: 37113344 KiB，满足 40 GB / 30 GB 下限。登记时再次检查为 125173792 / 37096960 KiB，回执 `<HX07>/DISK_CHECK.txt`。

登记提交 **42a5b14d9f563f24b2d1596e40107ff4503f5ec5** 已 push：

```text
To github.com:kaiwen123-yang/LegSA-GINS.git
   2723868..42a5b14  stage/clean3-math-repair -> stage/clean3-math-repair
```

来源：`<HX07>/PREFLIGHT.json`、`REGISTRATION_RECEIPT.json`、`REGISTRATION_PUSH.log`。`<HX07>` 表示 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07`，`<CLEAN_ROOT>` 由本地 DATA_PATHS.CLEAN3R4.local.yaml 解析。

## 2. 输入与配置

六份官方 convbin 观测与 DG-01R 输出清单逐项核验通过。HX-02 原导航文件和原配置身份核验通过。官方 RTKLIB 提交 `180043ee24b6d2b168f98b64be15f69d50046b1a`；rnx2rtkp SHA-256：

```text
3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda
```

实际 V0 配置与 HX-02 逐字节相同，SHA-256：

```text
97f0fe4157ce31909538e696184a7faadad059c3099ab912cbe2e97b0fc9e14f
```

以 `-y 1` 只设置输出状态等级；未改配置文件的 out-outstat 字节。该级保存状态日志，但官方源码 rtkpos.c L331 在等级 ≤1 时不输出逐卫星残差；本报告不声称已取得完整残差日志。ratio 保留在 `.pos` 中，硬停后未继续做分布分析。

外部星历来自 [BKG 多系统广播星历](https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/065/BRDC00WRD_R_20260650000_01D_MN.rnx.gz)，下载 UTC `2026-09-27T12:39:31.791402+00:00`。文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| .rnx.gz | 664724f91cd3c8ca91f8a933ae879c13fb3fb77b7e8976d6e78a8d748d051aac |
| 解压 .rnx | 8d5222d82ea957d96a6d4bbe318a6f384532ed4a22016c92be84d78a3dac11cc |

| 系统 | 星历记录数 |
|---|---:|
| GPS G | 484 |
| Galileo E | 6378 |
| BDS C | 2423 |
| QZSS J | 127 |
| GLONASS R | 1412 |
| NavIC I | 304 |
| SBAS S | 16465 |

这是记录数，不是唯一卫星数。Galileo 存在门通过；外部星历尚未用于解算。来源：HX07_DOWNLOAD.json、HX07_INPUT_SHA256.json、`<HX07>/00_INPUTS/`。

## 3. V0 复现门与停止位置

| 序列 / 配置 | 登记固定数 / 分母 | 允许范围 | 实际 | 差值 | 状态 |
|---|---:|---|---:|---:|---|
| BY2 / V0 | 153 / 1370 | 151–155 | 157 / 1370 | +4 | HARD_STOP |
| BY2H / V0 | 179 / 1350 | 177–181 | 未执行 | — | NOT_RUN |
| BY2O / V0 | 112 / 1885 | 110–114 | 未执行 | — | NOT_RUN |
| 三序列 / V1 | 不设数值门 | — | 未执行 | — | NOT_RUN |
| 三序列 / V2 | 不设数值门 | — | 未执行 | — | NOT_RUN |

BY2 原生程序退出码 0，UTC 12:46:20.115433 至 12:46:24.501258。`.pos` 有 568 行，Q=1 为 157、Q=2 为 411、Q=5 为 0；568 行均成功关联到原 HX-02 配对表。配对表完整为 1509 行，闭窗 [66,340] s 内分母仍为 1370，其中 802 个历元无关联解（rtklib_q=-1）。复现门使用窗内关联后的 Q=1 数，没有改成 `.pos` 行数作分母。

来源：`<HX07>/RUNS/BY2_V0/COMMAND.json`、`ASSOCIATION_SUMMARY.json`、`HEADING_TABLE.csv`、`solution.pos`；停止回执 `<HX07>/HARD_STOP.json`、`V0_GATE.json`。

执行前已登记：DG-01R 观测只覆盖评估窗，原 HX-02 的 BY2/BY2O 含窗前观测；起点命令约定保持原样，未补回窗前数据。此覆盖差异可能影响初始历史，但本任务没有做归因试验，**不能判定 +4 的具体原因**。没有扩大容差、选择阈值、改变输入、修改参数或重试。

## 4. EXT01–EXT03 钟差只读核查

完整结论及逐项代码片段见 HX07_EXT_CLOCK_AUDIT.md；该核查已在原生执行前完成并随登记提交。

| 实现 | 观察到的源码处理 |
|---|---|
| EXT01 / EXT02 | SPP 估计接收机钟差，但双差调用仅传入 SPP 位置；双差用 receiver1 标签与两机均值伪距，生成共同卫星状态。SD/DD 没有显式两机接收时刻差几何项。 |
| EXT03 | 两机分别 pntpos，返回 dtr；build_epoch_blocks 仅传两机位置。每颗星共用一个卫星状态，SD 有对流层修正，DD 状态列为基线与模糊度。 |

三者均存在传播时间及广播卫星钟差处理，不能写成“直接在标签时刻取卫星位置”或“完全不估计钟差”。共同状态的构造未分别应用两机 NAV-CLOCK/SPP 接收机钟差。源码证据为 shared_raw_backend.py L1643–1717、phase1_runner.py L521–528、phase2_runner.py L1934–1960、phase3_runner.py L574–620/L739–753；bridge 调用官方 satposs，ephemeris.c L774–796 说明传播时间与卫星钟差扣除。

与 DG-01R 一阶影响 2.2–2.5 周量级一致（对应 BY2 与 BY2O）；逐序列值为 BY2 2.247626、BY2H 1.851675、BY2O 2.463785 周，来源 DG01R_CLOCK_OFFSET.csv 的 all_paired_RAWX / max_first_order_DD_cycles。该量级与源码事实并列报告，不能据此把所有误差归因于钟差，也不判断方法不适用。

## 5. 调用、访问和文件边界

| 项目 | 实际计数 |
|---|---:|
| rnx2rtkp | 1 |
| HX-02 航向评估 | 0 |
| 参考原始轨迹读取 | 0 |
| LegSA 解算 / 评估 | 0 / 0 |
| 其他外部方法 / convbin | 0 / 0 |
| 原生 execve | 1，仅登记 rnx2rtkp |
| 原生原始数据 / 参考打开 | 0 |
| 原生越界写入 | 0 |

原生 strace 审计通过，来源 `<HX07>/RUNS/BY2_V0/NATIVE_ACCESS_AUDIT.json` 与 NATIVE_OPENAT.strace。父进程设置原始数据/参考打开拒绝钩子。停止后再次核验输入及代码 pin **91/91**、RTKLIB 源码 **927/927**、既有未跟踪路径及哈希 **29/29 不变**。没有建立 scratch，因而无待清理的 scratch 文件。

旧结果全目录元数据扫描在硬停后终止，未生成完整快照，不把它当成全目录逐文件复核证据。已登记输入的字节核验与原生访问审计单独成立。v3/HX02–HX05 未被本任务改写。来源 `<HX07>/HARD_STOP_CHECKS.json`。

## 6. 交付与未执行项

已提交并 push：登记、91 项输入/代码清单、下载回执、三配置 diff、源码钟差审计、准备/执行/审计脚本。硬停报告、HX07_HARD_STOP.json、HX07_TABLE.csv 和 HX07_SEGMENTS.csv 保留在允许的仓库目录；表中的未执行/未评估字段明确标记，不能作为三配置性能表。

未执行：剩余 8 次原生运行、全部 9 次航向评估、BY2O 切片、ratio/基线残差分布、SFIG-HX7、结果提交及第二次 push。AGENTS.md 未追加“9 次运行/9 次评估”完成记录。硬停回贴不请求扩大本次授权。

## English text — incomplete experiment, not a manuscript result paragraph

The preregistered control run stopped this comparison before any constellation variant was executed. Using official convbin observations and the unchanged moving-base configuration, the primary sequence produced 157 fixed solutions among 1,370 registered paired epochs. The archived control count was 153, and the difference of four exceeded the allowed tolerance of two epochs. The output contained 568 position records: 157 fixed and 411 float, with no standalone solutions. Neither the four-constellation configuration nor its fix-and-hold variant was run. No reference trajectory was opened, and heading availability under reference evaluation, valid-epoch heading RMSE, and held-heading RMSE were not evaluated. These records establish a failed reproduction gate; they do not support a comparison of constellation choices or ambiguity-resolution modes. The cause of the count difference remains undetermined.
