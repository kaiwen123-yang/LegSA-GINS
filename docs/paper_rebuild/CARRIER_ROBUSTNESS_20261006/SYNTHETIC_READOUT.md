# 载波异常与影子准入：固定 72 次合成试验

72 次 CILS、504 个配对未来条件已全部完成。72 次搜索均有注册目标的全局候选证书，没有超时、无输出或补跑；这不是 72 次可信 FIX。24 个 calibration seed 与 48 个 heldout seed 完全分离，两个批次使用同一事前冻结的 α=0.01（两门各 0.005），没有按 calibration 或 heldout 结果调整门限。

每个 seed 的前 5 个 clean 历元只选择一次 best/second，整数随后冻结；全部故障从未来第一个历元开始。后 5 历元中每个基线独立变化，GLRT 只诊断，不修正载波、不替换整数、不反馈准入。216 个输入文件分开保存选择、未来及真值；只有 ADMISSION_SEAL 写出后才读真值汇总。

## 结论与失败边界

- heldout CLEAN 正确整数影子接纳为 M3 10/16、M4 15/16、三信号组 M9 16/16。CLEAN 的 44 个正确主候选中 41 个接纳、3 个因竞争候选未排除而未决；4 个错误主候选均被拒绝。
- heldout 没有错误整数影子接纳，但 calibration 有两例错误整数接纳及一例漏检周跳、共享整数模型不可表示时的接纳。三条危险判定来自两个独立 seed，不能当作三个独立噪声实验。
- 正确整数仍可能产生严重测量偏差。heldout 的参考星 +0.25 周条件接纳 21 个正确整数，接纳子集的每例三维基线角 RMSE 均值 13.562°，最高 15.352°；不能称为正确航向测量。
- M9 冗余模型在这 16 个 heldout seed 上拒绝全部 target/pivot 非整周偏差、漏检周跳和双信号偏差；这是固定模拟几何及 Q 下的结果，不是跨场景风险保证。时间相关噪声条件违反独立 Q 假设；即使候选正确，原名义 Type-I 推导也不适用。
- 缺测条件只保留两个目标的码/相位行，所有情况未决；没有用补帧、延长窗口或事后参数使其接纳。

## 各批次、几何与条件的完整判定

“正确/错误”只指已接纳整数是否等于合成真整数；“不可表示接纳”单列。拒绝和未决不混为零误差。每格支持 calibration 为 8，heldout 为 16。

| 批次 | 几何 | 条件 | 正确接纳 | 错误接纳 | 不可表示接纳 | 拒绝 | 未决 |
|---|---|---|---:|---:|---:|---:|---:|
| CALIBRATION | M3 | CLEAN | 3 | 0 | 0 | 1 | 4 |
| CALIBRATION | M3 | TARGET_QUARTER | 3 | 1 | 0 | 4 | 0 |
| CALIBRATION | M3 | PIVOT_QUARTER | 5 | 0 | 0 | 1 | 2 |
| CALIBRATION | M3 | UNDETECTED_SLIP | 0 | 0 | 1 | 7 | 0 |
| CALIBRATION | M3 | TEMPORAL_RHO08 | 4 | 0 | 0 | 1 | 3 |
| CALIBRATION | M3 | INSUFFICIENT_SUPPORT | 0 | 0 | 0 | 0 | 8 |
| CALIBRATION | M3 | TWO_SIGNAL_BIASES | 0 | 1 | 0 | 7 | 0 |
| CALIBRATION | M4 | CLEAN | 8 | 0 | 0 | 0 | 0 |
| CALIBRATION | M4 | TARGET_QUARTER | 0 | 0 | 0 | 8 | 0 |
| CALIBRATION | M4 | PIVOT_QUARTER | 3 | 0 | 0 | 5 | 0 |
| CALIBRATION | M4 | UNDETECTED_SLIP | 0 | 0 | 0 | 8 | 0 |
| CALIBRATION | M4 | TEMPORAL_RHO08 | 8 | 0 | 0 | 0 | 0 |
| CALIBRATION | M4 | INSUFFICIENT_SUPPORT | 0 | 0 | 0 | 0 | 8 |
| CALIBRATION | M4 | TWO_SIGNAL_BIASES | 0 | 0 | 0 | 8 | 0 |
| CALIBRATION | M9_MULTIFREQUENCY | CLEAN | 8 | 0 | 0 | 0 | 0 |
| CALIBRATION | M9_MULTIFREQUENCY | TARGET_QUARTER | 0 | 0 | 0 | 8 | 0 |
| CALIBRATION | M9_MULTIFREQUENCY | PIVOT_QUARTER | 0 | 0 | 0 | 8 | 0 |
| CALIBRATION | M9_MULTIFREQUENCY | UNDETECTED_SLIP | 0 | 0 | 0 | 8 | 0 |
| CALIBRATION | M9_MULTIFREQUENCY | TEMPORAL_RHO08 | 8 | 0 | 0 | 0 | 0 |
| CALIBRATION | M9_MULTIFREQUENCY | INSUFFICIENT_SUPPORT | 0 | 0 | 0 | 0 | 8 |
| CALIBRATION | M9_MULTIFREQUENCY | TWO_SIGNAL_BIASES | 0 | 0 | 0 | 8 | 0 |
| HELDOUT | M3 | CLEAN | 10 | 0 | 0 | 4 | 2 |
| HELDOUT | M3 | TARGET_QUARTER | 0 | 0 | 0 | 16 | 0 |
| HELDOUT | M3 | PIVOT_QUARTER | 9 | 0 | 0 | 6 | 1 |
| HELDOUT | M3 | UNDETECTED_SLIP | 0 | 0 | 0 | 16 | 0 |
| HELDOUT | M3 | TEMPORAL_RHO08 | 10 | 0 | 0 | 4 | 2 |
| HELDOUT | M3 | INSUFFICIENT_SUPPORT | 0 | 0 | 0 | 0 | 16 |
| HELDOUT | M3 | TWO_SIGNAL_BIASES | 2 | 0 | 0 | 14 | 0 |
| HELDOUT | M4 | CLEAN | 15 | 0 | 0 | 0 | 1 |
| HELDOUT | M4 | TARGET_QUARTER | 1 | 0 | 0 | 15 | 0 |
| HELDOUT | M4 | PIVOT_QUARTER | 12 | 0 | 0 | 3 | 1 |
| HELDOUT | M4 | UNDETECTED_SLIP | 0 | 0 | 0 | 16 | 0 |
| HELDOUT | M4 | TEMPORAL_RHO08 | 15 | 0 | 0 | 0 | 1 |
| HELDOUT | M4 | INSUFFICIENT_SUPPORT | 0 | 0 | 0 | 0 | 16 |
| HELDOUT | M4 | TWO_SIGNAL_BIASES | 0 | 0 | 0 | 16 | 0 |
| HELDOUT | M9_MULTIFREQUENCY | CLEAN | 16 | 0 | 0 | 0 | 0 |
| HELDOUT | M9_MULTIFREQUENCY | TARGET_QUARTER | 0 | 0 | 0 | 16 | 0 |
| HELDOUT | M9_MULTIFREQUENCY | PIVOT_QUARTER | 0 | 0 | 0 | 16 | 0 |
| HELDOUT | M9_MULTIFREQUENCY | UNDETECTED_SLIP | 0 | 0 | 0 | 16 | 0 |
| HELDOUT | M9_MULTIFREQUENCY | TEMPORAL_RHO08 | 15 | 0 | 0 | 1 | 0 |
| HELDOUT | M9_MULTIFREQUENCY | INSUFFICIENT_SUPPORT | 0 | 0 | 0 | 0 | 16 |
| HELDOUT | M9_MULTIFREQUENCY | TWO_SIGNAL_BIASES | 0 | 0 | 0 | 16 | 0 |

## 接纳子集的三维基线角误差

下表汇总 heldout 的三个几何层；完整按批次/条件/几何、正确/错误/不可表示整数分开的均值、最大值和 case ID 保存在 SYNTHETIC_SUMMARY.json。这里的“最高 RMSE”是每例 5 个未来历元 RMSE 的最大值，不是最大单历元角误差。没有接纳时为 NA。

| 条件 | 正确整数接纳数 | 接纳 RMSE 均值（°） | 最高 RMSE（°） | 最大单历元角（°） |
|---|---:|---:|---:|---:|
| CLEAN | 41 | 1.758353 | 3.173906 | 5.471427 |
| TARGET_QUARTER | 1 | 7.687811 | 7.687811 | 8.424639 |
| PIVOT_QUARTER | 21 | 13.562439 | 15.352341 | 18.474505 |
| UNDETECTED_SLIP | 0 | NA | NA | NA |
| TEMPORAL_RHO08 | 40 | 1.644549 | 4.355732 | 4.941373 |
| INSUFFICIENT_SUPPORT | 0 | NA | NA | NA |
| TWO_SIGNAL_BIASES | 2 | 17.640436 | 18.243762 | 21.110923 |

## 必须保留的 calibration 反例

| Case | 条件 | 判定含义 | 基线角 RMSE（°） | 最大单历元角（°） | GLRT 检出 |
|---|---|---|---:|---:|---|
| CALIBRATION_M3_01 | TWO_SIGNAL_BIASES | WRONG_INTEGER_SHADOW_ACCEPTED | 55.006661 | 57.623570 | False |
| CALIBRATION_M3_05 | TARGET_QUARTER | WRONG_INTEGER_SHADOW_ACCEPTED | 52.023537 | 56.266341 | False |
| CALIBRATION_M3_05 | UNDETECTED_SLIP | UNREPRESENTABLE_SHADOW_ACCEPTED | 70.413212 | 73.048715 | False |

两例错误主候选都来自 M3 前 5 历元选择。未来故障改变观测，使原错误主候选通过残差和长度两门；对应持久单信号 GLRT 也未检出。它们不是重新利用 future 搜索到的新 N。漏检 +1 周案例的共享整数真值跨选择/验证段不可表示，不能放入普通整数正确率分母。

## 统计与模型口径

每个条件只有 48 个独立 heldout seed（每几何 16）；不能把 336 个 heldout 配对条件合并成 IID 风险试验。各几何层 0/16 错误接纳的双侧 95% Wilson 上限约 19.36%；跨三种固定几何的 0/48 上限约 7.41% 只作混合样本的描述性近似，不能当真实场景错误固定风险。即便整数正确，非整周偏差仍可使角误差显著增大，因此该整数指标也不是完整测量安全指标。

m=3/4 使用 GPS L1，m=9 使用 GPS L1/L2 与 Galileo E1 各 3 个 DD；多频波长不同。原始 SD 到 DD 的共享参考星协方差被完整保留，GPS 两频 raw-SD 相关系数固定 0.35。相位 σ 为单接收机 0.004 m 工程设定，不是 RAWX 0.004 cycles。fault-free 条件由同一完整 Q 生成和估计；时间相关条件仅从未来段起引入 ρ=0.8，且仍故意使用独立历元工作 Q。

原 sealed SUMMARY 的 mean_baseline_angle_rmse_deg 包括所有可评分的主候选（含未接纳、错误整数），仅是候选诊断。新公开摘要增加 shadow_accepted_angle_subsets，不能将前者当正确固定精度。mean_observation_model_exact 是对逐历元真整数的条件均值口径；漏检周跳还须同时检查 model_truth_representable=False。

Holm 只控制指定正确 N、已知 Gaussian Q 等条件下共同无故障零假设的名义族错误；异常存在时多个相关模板可以共同显著，不能声称定位误报率受控，亦不能仅凭两机 SD 定位到 RX2。

## 封存与复核

源码冻结提交 6162833。搜索耗时 58.653 s；72 次搜索与 504 条判定均已封存。独立来源链检查验证 PLAN/registration/72 候选/504 判定/216 输入及全部主候选 fingerprint。FINAL_SEAL 唯一非科学例外是 DRIVER.log 最后追加一行 SEALED；追加前字节的 SHA 与原清单完全相等，原清单保留，详见 SYNTHETIC_SEAL_CHAIN_REVIEW.json。没有因此重跑或改数值。

交付：SYNTHETIC_RESULTS.csv 保留 504 条完整判定；SYNTHETIC_SUMMARY.json 给全部分层计数、接纳子集角误差与区间；SYNTHETIC_PREREGISTRATION.json 保存事前预算与输入哈希。下一步应研究故障可辨识性和检出能力，当前证据不支持放宽门限或向生产融合输出可信 FIX。
