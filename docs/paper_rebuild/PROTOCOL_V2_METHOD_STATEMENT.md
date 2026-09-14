**pre-correction — protocol v2 statement and numerical record preserved below.**

<!-- P13_METHOD_PRE_CORRECTION_BEGIN -->
# Protocol v2 method statement

人类决定（2026-09-13）：论文提出方法为 **F04（AB1111）**。方法由 KF-GINS 骨干、双天线短基线机身航向、scheme-C 质量感知门控、机身 roll/pitch 弱先验、Raw Doppler 辅助速度、腿部水平速度弱先验和 Source-Aware 加权组成。消融阶梯为 **F01→F02→F03→A04→F04**。A04（AB1011）是 v1 预注册规则的既有决定，作为无 Source-Aware 的消融行保留；原决定规则与 Outcome 不变。

协议 v2 的主评估点为 v3。下表来自已冻结的 541 核心表；附加族独立报告，不合并入核心统计。差值为候选减参考，负值表示该误差统计量降低。分布 P95 是有限逐 case RMSE 的第 95 百分位，即最差 5% 的进入阈值，不是最差 5% 的均值；算法失败另计。

| 层或对比 | 冻结证据（v3） | 来源及 CSV 物理行（含表头） |
|---|---|---|
| 双天线，F02−F01 | 航向 RMSE 配对中位差 −5.70214540134477°，n=541 | PAIRWISE_SUMMARY:1041 |
| 门控，F02→F03 | 逐 case 航向 RMSE 的 P95：27.69463843498005→12.920123968025251° | UNIQUE_METHOD_SUMMARY:3357,3761 |
| 辅助模块阶梯，F03→A04 | 航向 RMSE 的 P95：12.920123968025251→6.720069208034486°；roll/pitch 配对中位差 −1.2994137177604803/−0.7637280146069414°，n=526 | UNIQUE_METHOD_SUMMARY:3761,529；PAIRWISE_SUMMARY:361,321 |
| 单独 RP 消融，F04−A05 | roll/pitch RMSE 配对中位差 −1.11310497919139/−0.6428940882327567°，n=521 | PAIRWISE_SUMMARY:1531,1491 |
| RD，D05 的 F04−A03 | 故障窗水平 RMSE 配对中位差 −4.996628167587727 m，均值差 −5.0589279093657495 m，n=9 | PAIRWISE_CASE_LEVEL:18544,18557,18570,18583,18596,18609,18622,18635,18648 |
| HV，D05 的 F04−A06 | 故障窗水平 RMSE 配对中位差 −0.10316249601704364 m，均值差 −0.2023366410739 m，n=9 | PAIRWISE_CASE_LEVEL:36420,36433,36446,36459,36472,36485,36498,36511,36524 |
| SA，A04→F04 | 航向 RMSE 的 P95：6.720069208034486→3.157590053291289°；有限 case 均值：5.3842849624636075→3.870187833231392°；算法失败 A04=7、F04=11 | UNIQUE_METHOD_SUMMARY:529,4165 |

F03→A04 同时加入 RD、RP、HV，不能把这一步的全部变化归为 RP 的独立作用。上述单独 RP 行保留对应的模块消融。原拟写的 roll/pitch −1.2/−0.7° 不对应这两组冻结配对统计，本文使用表中的原值。

RD/HV 定位为“速度辅助冗余层／优雅退化阶梯”。接收机速度有效时，已有速度观测约束了同一速度状态，弱辅助项的边际变化可能很小；小的正常窗差值不等于失效场景下没有作用。D05 在位置与接收机速度同时中断时保留 RD；A1/A2 进一步关闭 RD，用于检验 HV 在唯一辅助速度来源条件下的表现。该解释是状态约束与信息冗余的机理说明，不是普遍收益保证。

附加族登记说明：ADDENDUM_FAMILIES_A1_A2 — pre-registered 2026-09-13, added after the 541-core results were seen, to cover a scenario absent from the library。A1/D61 包含 10/20/30 s、27 case；A2/D62 包含 10/20 s、18 case。全部 495 次新增求解与双版本评估仅进入 `13_AGGREGATE_ADDENDUM/{v3,v2}`。这是在真实 BY2 基础上注入中断的半合成实验，不能称为自然 GNSS 全断实录。

<!-- ADDENDUM_OUTCOMES_BEGIN -->
v3/v2 的冻结假设判定一致：H1 `PARTIALLY_SUPPORTED`；H2 `SUPPORTED`；H3 `OBSERVED_SOME_SEED_HARM`。H3 判定中 `full_vs_no_Go2` 的有害 case–metric 行数为 32，缺失行数为 0；此计数不是独立种子数。495 次求解、v3/v2 各 495 条评估均为 `COMPLETED`，算法失败为 0。

以下为 v3 的 F04−A06（full_vs_no_HV）族级冻结配对值；A1 n=27，A2 n=18。完整八项配对、各时长九 case 分组与逐种子符号见 [ADDENDUM_FAMILIES_A1_A2_RESULTS.md](ADDENDUM_FAMILIES_A1_A2_RESULTS.md)。

| 族 | 指标 | 均值差 (m) | 中位差 (m) | 中位差 bootstrap 95% CI (m) | 胜率 | Wilcoxon p |
|---|---|---:|---:|---|---:|---:|
| A1 | fault_window_horizontal_rmse_m | -0.011142076463065018 | -0.00690213830242925 | [-0.01614328016192701, 0.00110470758839476] | 0.6666666666666666 | 0.00441385778107854 |
| A2 | fault_window_horizontal_rmse_m | -10.881309529635626 | -5.45592910851764 | [-20.17804452336491, -2.2361079069689964] | 1.0 | 7.62939453125e-06 |
| A1 | outage_end_horizontal_error_m | -0.022014158767246488 | -0.013668375752843076 | [-0.03241384619519749, 0.0020710995034924906] | 0.6666666666666666 | 0.00441385778107854 |
| A2 | outage_end_horizontal_error_m | -31.19100264997546 | -15.971134595412632 | [-56.792582590804564, -6.915448530501524] | 1.0 | 7.62939453125e-06 |

来源：`<ADDENDUM_ROOT>/13_AGGREGATE_ADDENDUM/v3/PAIRWISE_SUMMARY.csv`，物理行 86、87、95、96（含表头，按上表顺序）；SHA-256 `b31b250a5af7fee5cc5b9a0e078f79ce52a51266daa400c9d7db8de3cba9a2ae`。
<!-- ADDENDUM_OUTCOMES_END -->

D06 所示的航向丢失条件下，机身先验可能在部分种子上有害。机身系速度向导航系的投影依赖姿态；航向约束丢失后，姿态与辅助速度误差可能耦合。因此保留逐种子正负号、失败数和完整不利结果。后续工作包括航向可观测性条件下的先验可信度诊断；本协议没有据此调参、改权、删除历元或修正输出。

相对 v1 预注册 A04 决定的修订理由：v1 的位置界失败发生于其噪声模型与实际传感器不匹配的条件；冻结 BY2 标定参数并盲传至 BY2H/BY2O 后，v2 的位置界在 v3 和并行 v2 评估下均为 PASS。原航向检验基于未人工注入退化的真实序列，而 SA 的论文定位是退化条件下的保护模块。人类依据协议 v2 的退化证据选择 F04；这不把原规则的 FAIL 改写为 PASS，也不声称所有改善都由单一噪声参数因果解释。

位置界来源：`<CLEAN5_CALIBRATED_ROOT>/08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.csv`，v3 位置第 21 行、v2 位置第 11 行 PASS，v3 航向第 20 行仍为 FAIL；`outcome_changed=false`、`new_outcome_created=false`。标定链仍标注 `NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL`。

参考轨迹表述：the fused navigation solution output directly by the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2); the estimator under test never reads it (file-access audit)。图中使用 `Truth`；参考不确定度由独立的对话 D 记录。文件访问审计证明估计器不读取该解，不能单独证明参考误差独立或参考无误差。

核心来源根：`<CANONICAL541_V2_ROOT>/13_AGGREGATE/v3/`。SHA-256：

| 来源 | SHA-256 |
|---|---|
| UNIQUE_METHOD_SUMMARY.csv | `2028886e334ee0791ec394626f3f730b26328533b755cee3cbf954b7496845d0` |
| PAIRWISE_SUMMARY.csv | `90dbfd24870cb8168f13942b92a93f5936a88118fdb94c5c62ba7cf12c24737e` |
| PAIRWISE_CASE_LEVEL.csv | `99958ef6902789803ebb9b5b5f6a63676a2781ef6d8ffc043cdc89469b7462ff` |
| CALIBRATED_CHAIN_ROBUSTNESS_CHECK.csv | `77211ce62a1ef3f05e9cf25585578a3735803cc62499bc322ae6cde0ca0b0cb9` |

<!-- P13_METHOD_PRE_CORRECTION_END -->

<!-- P13_METHOD_V21_BEGIN -->
## Protocol v2.1 — three sensor corrections

发现过程：残差审计 → 坐标约定修正 → 残差收缩。三项修改来自 P-11b/P-12 的观测残差审计；采用 BY2 数值并盲传至 BY2H/BY2O。

1. HV：原始 Go2 FLU 速度先转 FRD，使用 Go2 roll/pitch 与注入后的 A1 NED 航向旋转，再取水平分量。`v_H_NED = horizontal(k_HV * Rz(A1_NED) * Ry(-Go2_pitch) * Rx(Go2_roll) * diag(1,-1,-1) * v_body_FLU)`。`k_HV=1/0.962142`，`σ_HV=0.132838 m/s`；A1 线性插值，间隔大于 1.2 s 的开区间无效，原观测端点保留；A1 全断时 HV 全无效。

2. RP：FLU→FRD 后使用 `[roll, -pitch]`，std 保持 1.6°。三序列首个静止窗口 pitch 残差均值（deg）由 `[2.028821, 2.212328, -4.296193]` 变为 `[-0.444112, -0.420844, -0.412029]`；这是观测坐标核查。

3. 双天线航向：`status_fixed_yaw_std_deg` 与 `basic_dual_yaw_fixed_std_deg` 从 1.5° 改为 2.933193°。BY2 Euler yaw-rate increment-residual proxy 2.933193 degrees; BY2O 2.936449 degrees as a check, BY2H 8.406459 degrees reported without refit. Human supplied physical scale: 0.35 m baseline, approximately 2.5-3 degrees. scheme-C 阈值保持不变；2.933193° 小于 soft 阈值 3.0°。

HV 复现门先除以 k_HV，按原 H-A 统计验证；最终带标度的残差另报。frozen_parameter_hash 定义保持不变，三项修正以 SENSOR_MODEL_V21 组单独锁定。仅 F02 合法值校验新增接受 2.933193°；新二进制在 std=1.5° 下通过旧二进制桥接。

论文限制：0.132838 m/s 是 BY2 未标度 H-A 残差代理，包含 PVT、A1、时间及弱先验误差，不等同于独立辨识的白噪声。陀螺标度、arw/gbstd、安装角不改；P-12 数值和原理由如下，保留其 UNAVAILABLE/NOT_OBSERVABLE/APPROXIMATE 状态。

```json
{
  "gyro_scale": {
    "correction_applied": false,
    "z_slopes": [
      0.991971,
      0.944907,
      1.036122
    ],
    "z_bootstrap_95pct_CI": [
      [
        0.953341,
        1.043298
      ],
      [
        0.804485,
        1.049073
      ],
      [
        0.986089,
        1.09523
      ]
    ],
    "turn_segment_counts": [
      14,
      12,
      12
    ],
    "xy_scale": "NOT_OBSERVABLE",
    "reason": "All z intervals include one; finite turn samples and coupled A1/motion error do not identify a new correction."
  },
  "arw_deg_sqrt_h": [
    0.985,
    0.985,
    0.985
  ],
  "gbstd_deg_h": [
    9.38,
    9.38,
    9.38
  ],
  "p12_first_window_arw_proxies": {
    "BY2": [
      3.258305,
      1.017005,
      1.192574
    ],
    "BY2H": [
      1.033009,
      1.095999,
      2.189563
    ],
    "BY2O": [
      2.152673,
      1.038402,
      1.217219
    ]
  },
  "p12_BY2O_standing_arw_proxy": [
    15.531849,
    3.28569,
    5.93439
  ],
  "p12_pooled_gbstd_proxy_deg_h": [
    37.453926,
    24.707103,
    26.198129
  ],
  "noise_reason": "Short 4.59-4.87 s first windows and robot micromotion do not establish a white-noise Allan slope; standing-window proxies differ. Pooled gbstd is APPROXIMATE and includes temperature, real motion and Earth-rate projection. BY2/BY2H each have one prescribed window and no individual cross-window std. Existing per-sequence first-1000-frame gyro debiasing remains unchanged.",
  "installation_rpy_deg": [
    -1.0,
    0.0,
    0.0
  ],
  "p12_installation_roll_proxy_mean_deg": {
    "BY2": -3.422178,
    "BY2H": "UNAVAILABLE",
    "BY2O": -4.150564
  },
  "p12_installation_roll_sample_counts": {
    "BY2": 3,
    "BY2H": 0,
    "BY2O": 97
  },
  "p12_pitch_installation": "NOT_OBSERVABLE",
  "p12_yaw_effective_method1_deg": [
    4.544357,
    3.905588,
    1.617459
  ],
  "p12_yaw_effective_method2_deg": [
    3.952922,
    3.9083,
    1.162595
  ],
  "installation_reason": "Roll uses sparse/noisy baseline-gravity proxies and includes antenna height mismatch; pitch lacks an independent body-level reference; effective yaw conflates A1, slip and velocity error. The two yaw methods share observations and are not independent identification. Preserve all triggered P-12 flags.",
  "unchanged_calibrated_values": {
    "s": 1.0308398903907543,
    "vrw": [
      9.478382094779873,
      9.784198200134004,
      7.6321402201126745
    ],
    "abstd": [
      4817.482008954474,
      8259.572423450163,
      2257.241538343225
    ]
  },
  "other_parameters": "Keep all other scientific tokens, initialization, timing, switches, weights and physical transforms frozen.",
  "manuscript_limits_required": true
}
```

论文方法仍为 F04（AB1111），消融阶梯 F01→F02→F03→A04→F04。A04 的原决定、决定规则与 Outcome 保持不变。主评估 v3，并行报告 v2；F01 正式输出逐字节沿用 v2，50 次不变门重跑不替换正式输出。

| Sequence | Gate | Max absolute difference | Compared statistics | Final scaled HV residual σ (m/s) |
| --- | --- | --- | --- | --- |
| BY2 | PASS_HV_RP_REPRODUCTION | 8.326672684688674e-17 | 183 | 0.13145029910885764 |
| BY2H | PASS_HV_RP_REPRODUCTION | 2.7755575615628914e-17 | 183 | 0.21125519645608834 |
| BY2O | PASS_HV_RP_REPRODUCTION | 1.1102230246251565e-16 | 233 | 0.10363380102981933 |

F01 不变门：50/50 runs、350/350 完整文件；二进制桥接：44/44。三序列基础 GNSS15/18 非 yaw_std token 相同，yaw_std 全为 2.933193；注入表按原顺序保留预注册 yaw_std 倍乘，验证口径见 `docs/paper_rebuild/clean6/P13_APPENDIX.md`。IMU/RD 哈希门通过。

数据包：`<HANDOFF_ROOT>/c541_v21_handoff.zip`; SHA-256 `98a77b4601b897956a6d87f5bfa92e008b584add35e48e2b22a9088ddec07585`

新二进制 SHA-256：`96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`；旧二进制：`9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`。

聚合来源 code_commit：`f9e3d82f614a803a20cb4934f36687fa3e1ffdc6`；文档准备 code_commit：`a2048cdeb52fb3b49e626970a1bc0b36219ca354`。

v2.1 全精度 C00/三序列、H7–H11、族失败数和版本变化： [P13_FINAL_REPORT.md](P13_FINAL_REPORT.md)。

图包：`<HANDOFF_ROOT>/figures_v21_handoff.zip`; SHA-256 `20495ab65d1b7ae41a83de52aa34e80051b7154b45db4d5de63478a064e0c088`。v2.1 共 28 图、84 PNG/PDF/SVG 导出，已完成视觉核查；MFIG21 沿用原 v2 产物。
<!-- P13_METHOD_V21_END -->
