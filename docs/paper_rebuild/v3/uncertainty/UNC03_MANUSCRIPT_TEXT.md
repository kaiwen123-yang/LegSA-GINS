# UNC-03 Manuscript text: measurement uncertainty (English) with Chinese notes

Terminology rules applied: the reference is "the fused navigation output of the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2), which the estimator under test does not read"; no "same-source", "semisynthetic", "pre-registered", "hash-locked"; no internal code names; no calibration-constant values. Numbers trace to UNC01_UNCERTAINTY_BUDGET.md §§1–5 and are covered by UNC_CLAIM_CHECKS.csv.

## 1. Paragraph for the experimental setup / evaluation section (about 250 words)

**Measurement uncertainty.** The evaluation reference is the fused navigation output of the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2), which the estimator under test does not read. Its heading uncertainty is taken as 1.1° (the manufacturer's 0.4° at 1 m scaled to the 0.35 m antenna separation; the receiver's own reported attitude standard deviation is 0.9–1.0°), and its position uncertainty as 0.02–0.05 m (RTK accuracy indicator and reported covariance). These terms are common to every row and cancel in paired comparisons, but they bound the absolute values. Decomposing the retained error series reveals two further common-mode terms: a motion-induced heading component below 5 s of 1.1–1.4° RMS, identical for all thirteen estimators and falling to 0.06° when the robot stands still, and an along-track position offset of 0.03–0.04 m; they account for about half of the heading and one fifth of the horizontal mean-square error. Heading biases of 0.3–1.4° differ between estimators and reflect an uncorrected installation yaw between the IMU axes and the antenna baseline. The reported values are exact for the recorded windows and reproduce bit-for-bit under the same software version and configuration; as estimates for other windows of the same kind they carry moving-block bootstrap 95% intervals of about ±0.3° (BY2, BY2H) and ±1° (BY2O) in heading and up to ±0.05 m in horizontal position. Differences between methods on the same sequence are therefore reported with paired bootstrap intervals rather than a fixed threshold, and fault-matrix quantiles are resampled by fault type rather than by case.

## 2. Sentences for the limitations section

Three limitations concern the evaluation itself. The motion-induced common-mode heading term cannot be attributed with the retained data to time alignment at gait frequency, to the 10 Hz output rate of the reference, or to residual frame misalignment; it affects all methods equally and is excluded from the between-method comparisons. The installation yaw between the IMU axes and the antenna baseline was left at its nominal value, and each estimator resolves the resulting inconsistency differently; this contributes to the heading biases of 0.3–1.4° and to part of the difference between the proposed method and the loosely coupled baseline on BY2. Finally, the antenna-to-IMU lever arm was taken from the mounting design without independent verification; the height residuals bound its effect to about 0.02 m.

## 3. Sentence for the table notes (main three-sequence table)

Values are exact for the evaluated windows (bit-for-bit reproducible); the 95% moving-block bootstrap intervals of the proposed method are [1.60, 2.16], [1.60, 2.04] and [1.36, 3.61]° for heading and [0.045, 0.152], [0.045, 0.085] and [0.038, 0.073] m for horizontal position on BY2, BY2H and BY2O; paired intervals for each between-method difference are given in the supplementary material.

## 4. Optional sentence for the results section (BY2 comparison with the loosely coupled baseline)

On BY2 the proposed method's heading RMSE is 1.11° lower than that of the loosely coupled baseline; the paired moving-block bootstrap interval of the difference, [−0.22, +2.57]°, includes zero because the baseline's excess error is concentrated in episodes of heading wander, whereas inside the BY2O float segment the difference of 3.78° [2.20, 4.44]° is unambiguous.

## 5. 中文说明（逐句来源与写法理由）

- 第 1 段第 2–3 句（参考航向 1.1°、位置 0.02–0.05 m）：来源 CONVERSATION_HANDOFF.md:197（厂商 0.4°@1 m、0.35 m 换算）、CLEAN5_PARITY_PLAN.md:118-125、184-189（pAcc 中位 0.019 m；参考自报姿态 0.89–0.97°、位置 ≈0.05 m/轴）。写成区间是因为两个来源都不是标定过的误差界，只能给上下界。
- "common to every row and cancel in paired comparisons"：同一参考、同一历元（精确匹配 56 628–76 548 个）；配对差分序列见 UA01_C00_PAIRED_SERIES.csv。
- "motion-induced heading component … 1.1–1.4° RMS … 0.06° when the robot stands still"：UNC_FAST_COMPONENT_RANGE.csv（三序列 13/12/12 个估计器的 fast std 1.229–1.311 / 1.391–1.415 / 1.053–1.079°），BY2O 静止段 F04 fast std 0.059°（UA01_BY2O_SEGMENT_BANDS.csv）。它对所有方法一样，包括不用航向量测的 F01，所以按评估链共模项写；来源三选一（步态频率时间对齐 / 参考 10 Hz 输出加线性插值 / 坐标系耦合）在局限段说明"不能判定"。
- "along-track position offset of 0.03–0.04 m"：CLEAN5_STAGE2_CLOSEOUT.md §10 B3 行前向均值 +0.044 / +0.030 / +0.028 m（五个配置与 LC01 同值）。
- "about half of the heading and one fifth of the horizontal mean-square error"：快分量占 F04 yaw MSE 48 / 53 / 20%，前向偏置占水平 MSE 20 / 19 / 25%（UNC_YAW_DECOMPOSITION.csv、UNC_HORIZONTAL_BODY_DECOMPOSITION.csv）。BY2O 的航向份额只有 20%，所以正文写 "about half"时指 BY2/BY2H；若审稿人追问，用表注给三序列数值。
- "Heading biases of 0.3–1.4° differ between estimators"：UA01_C00_SERIES_STATS.csv 的 mean 列（F02 −1.39、F04 −1.09、LC01 −1.35、LC01-S −0.36，BY2）；安装偏航诊断 SENSOR_MODEL_CLOSEOUT_AUDIT.md:133-166（HUMAN_DECISION_REQUIRED，链未改）。这一项不抵消，所以必须在正文说明，否则 LC01-S 优于 F04 的 0.35° 无法解释。
- "exact for the recorded windows and reproduce bit-for-bit"：V3_01R_MANUSCRIPT_REPLACEMENT.md:8-9；"moving-block bootstrap 95% intervals ±0.3° / ±1° / ±0.05 m"：UNC_REALIZATION_INTERVALS.csv（F04：[1.604, 2.158]、[1.602, 2.037]、[1.364, 3.613]°；水平 [0.0452, 0.1520] m 等）。
- "paired bootstrap intervals rather than a fixed threshold"：UNC02_DISTINGUISHABILITY.md §1 的规则；"resampled by fault type rather than by case"：F04 yaw P95 2.447° 的按型区间 [2.00, 4.18] 与逐例区间 [2.11, 2.70]，逐例区间窄 3 倍是种子聚类造成的（UA01_DISTRIBUTION_QUANTILES.csv）。
- 局限段三句：分别对应预算表第 2、3、6 行；杆臂 z 的界来自 Up 残差均值 −0.017 / −0.007 / −0.019 m。
- 表注句与第 4 节可选句：数值来自 UNC_REALIZATION_INTERVALS.csv 与 UNC_DISTINGUISHABILITY.csv；第 4 节只在成稿对话决定采用 "方向成立、区间含零" 的写法时使用。
- 不写的东西：百分比改善、"significant"、单一 "true" 估计器 RMSE（见 UNC01 §2 第 3 条的重复计数问题）、BY2O 全窗持平而不说分段。
