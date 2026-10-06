# CLEAN5 P-01 输入对等目标、输入/参考几何审计与预注册

人类授权日期：2026-09-08。起点 `aed61a4892ceda36327269fc865922127edc3310`。本轮完成只读源检查、数值审计和求解前预注册；变体求解、provider 生成、评估器执行均为 **0**。未来 provider 家族限 `CLEAN5_PARITY_*`；主证据链 provider、结果与合约保持冻结。

本文件与 `configs/paper_rebuild/clean5/CLEAN5_PARITY_CONTRACT.yaml` 是明确要求的两个 tracked 交付；其余产物全部位于 `<CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/00_PARITY_TARGET_AND_AUDITS`，不纳入 Git。实际绝对路径由 ignored local YAML 提供。

本轮审计/预注册已完成；这不是变体执行准入。V1 未执行；V2 的 vAcc 语义、V3 的参考点身份，以及可选 V4 的协方差/测量杆臂仍有明确门限。缺证据的数值与分解均为 `UNAVAILABLE`。不从这些观察拟合偏移、不调参、不重跑冻结方法。

## A. 对等目标提取

只读冻结真实证据。未运行 provider、求解器、评估器；未用于任何拟合。

LC01 = EXT05A_PAVLASEK_TWO_RECEIVER_IEKF，映射见 CLEAN4/12_FINAL_EVIDENCE_INTEGRATION/RESULT_IDENTITY_LEDGER.csv 第 3 行。EXT05C 是单接收机更新诊断；二者不能混写。

## LC01

| 合约项 | 冻结证据 |
|---|---|
| 标识 | EXT05A_PAVLASEK_TWO_RECEIVER_IEKF |
| 传播 IMU | Go2 body by2.txt stamp/gyroscope/accelerometer only, FLU to FRD then RzRyRx(-1,0,0) degrees |
| 位置 | GNSS1 absolute + GNSS2−GNSS1 relative vector; UBX-NAV-HPPOSECEF, 5 Hz |
| 时标 | GPS epoch + 2408*604800 + iTOW*0.001 - 18 seconds; not reception stamp |
| std | pAcc*1e-4 m; R1=pAcc1^2 I3, R2=pAcc2^2 I3; LC01 stacked R=[[R1,-R1],[-R1,R1+R2]]. No vAcc or NAV-PVT speed observation. |
| 速度 | IMU propagated state, zero at verified static initialization; no receiver velocity measurement |
| 双接收机 | 更新=True; 初始化=True |
| 杆臂 / 输出点 | GNSS1−IMU FRD=[0.03,0.03,-0.30] m; GNSS2−GNSS1=[0,-0.350,0] m; 输出 IMU 点 |
| 评估器 | aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da; base_time=1772784000; [66,340] s |
| trace 列 | time, lat, lon, height, roll, pitch, yaw（原始列；不是 processed_lat/processed_lon/processed_height） |
| 冻结结果 H / 3D / Up / yaw RMSE | 0.1691391165921043 / 0.3790089605253968 / 0.33917510432958425 / 2.9948274600591076（m/m/m/deg） |
| 来源 | <CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/POST_NATIVE_TRACE_EVALUATION/EXT05A_C00_TRACE_METHOD_RESULTS.csv: 第 2 行；method_id=EXT05A_PAVLASEK_TWO_RECEIVER_IEKF |
| 支持 | 58014 retained rows, coverage=1.0, closed [66,340] s |

## EXT05C

| 合约项 | 冻结证据 |
|---|---|
| 标识 | EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF |
| 传播 IMU | Go2 body by2.txt stamp/gyroscope/accelerometer only, FLU to FRD then RzRyRx(-1,0,0) degrees |
| 位置 | GNSS1 absolute position only during updates; UBX-NAV-HPPOSECEF, 5 Hz |
| 时标 | GPS epoch + 2408*604800 + iTOW*0.001 - 18 seconds; not reception stamp |
| std | pAcc1*1e-4 m; R1=pAcc1^2 I3；不执行第二接收机更新；无 vAcc 或 NAV-PVT 速度观测。 |
| 速度 | IMU propagated state, zero at verified static initialization; no receiver velocity measurement |
| 双接收机 | 更新=False; 初始化=True |
| 杆臂 / 输出点 | GNSS1−IMU FRD=[0.03,0.03,-0.30] m; GNSS2−GNSS1=[0,-0.350,0] m; 输出 IMU 点 |
| 评估器 | aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da; base_time=1772784000; [66,340] s |
| trace 列 | time, lat, lon, height, roll, pitch, yaw（原始列；不是 processed_lat/processed_lon/processed_height） |
| 冻结结果 H / 3D / Up / yaw RMSE | 0.17100769332496335 / 0.3818199076097783 / 0.34138367077353726 / 12.048641737808111（m/m/m/deg） |
| 来源 | <CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/POST_NATIVE_TRACE_EVALUATION/EXT05A_C00_TRACE_METHOD_RESULTS.csv: 第 3 行；method_id=EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF |
| 支持 | 58014 retained rows, coverage=1.0, closed [66,340] s |

## 合同比较与限制

两者评估器 SHA、base_time、窗口、trace 与 Canonical 相同。各方法原生输出历元不同，不能把独立 RMSE 差直接当作同支持域的纯估计器差。EXT05C 和 LC01 的导航位置都是传播 IMU 点；适配器没有点补偿。局部变量名 receiver_ecef 并不改变这一事实。参考 trace 的实际 POI 与天线中点关系尚未建立（UNAVAILABLE），应交 B.2/B.5 源证据门处理。

冻结几何只推出 IMU→天线中点 FRD=[0.03,-0.145,-0.30] m；这不证明 trace 就是该中点。

两者都使用双接收机基线初始化 yaw，EXT05C 仅在后续更新中去掉第二接收机。LC01 为双接收机，因此 V4 条件成立。两者无 NAV-PVT 速度更新，V3−EXT05C(v3) 还包含 RV、RD、RP、HV、初始化、过程噪声及输出支持等信息结构差异，不能直接宣称纯滤波公式效应。

V1→V2 同时改动位置消息来源、std、更新速率与 RV/yaw 取样，速率项为预注册组合干预标签，并非单独 Hz 的因果分解。

源码位置：ext05_provider.py:117–229（iTOW、pAcc），:261–379（Go2）；phase5_runner.py:372–411（IMU 点输出），:423–470（双基线初始化），:1037–1100（无点补偿 LLA 适配）。当前 ext05_provider.py 哈希与冻结源快照相同；完整源快照与文件哈希见 JSON。

## Canonical V0 冻结配置

| 方法 | run | 配置 sha256 |
|---|---|
| F01 | RUN_00001 | 8f02e95e65668a4dc3e9654a195a2e9435a4e53a2a89afd2abae99926c19fae6 |
| F03 | RUN_00003 | 165f5e76ebd46c579fc3327c1b626703add04649d357b0fbd81b304ec3194726 |
| A04 | RUN_00006 | 8f2b51509ba7d811e2f42dea6acf199f6206260ca8fbd811bd1d32bb730669c1 |

完整运行配置、输入 provider 路径与当前 SHA-256、C00 来源行均记录在 A_TARGET_EXTRACTION.json；未改写任何冻结文件。

## B.1–B.5 输入侧与参考几何审计

Real raw audit only. 未用于任何拟合。No provider generation, solver, evaluator, or parameter/offset fitting. All 27 consumed files match designated raw hash locks; complete SHA-256 and lock identities are in B_RAW_SOURCE_HASH_AUDIT.json.

Population standard deviation (ddof=0). B.2 uses pos_valid and finite samples inside trace support; no extrapolation. Full-sequence statistics are primary here; BY2 66–340 appears separately. Trace time/lat/lon/height/yaw only, yaw fixed ENU convention, F=E cos(yaw)+N sin(yaw), R=E sin(yaw)−N cos(yaw).

## B.1 时标

| Quantity | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| sys−header seconds | 0.206685656 ± 0.005533307 (n=303) | 0.206682866 ± 0.005239342 (n=298) | 0.206804496 ± 0.010556683 (n=448) |
| header−status GPS→UTC seconds | 0.000000000 ± 0.000000000 (n=303) | -0.000000001 ± 0.000000014 (n=298) | -0.000000001 ± 0.000000011 (n=448) |
| header−nearest PVT seconds, inside PVT support | -0.000148562 ± 0.000002755 (n=302) | -0.000154442 ± 0.000000748 (n=296) | -0.000119057 ± 0.000013322 (n=446) |
| header−nearest TIM-TP seconds, inside TP support | -0.000148598 ± 0.000002730 (n=300) | -0.000154450 ± 0.000000744 (n=294) | -0.000119171 ± 0.000013243 (n=444) |
| PVT_support_excluded_status_n | 1 | 2 | 2 |
| TIM_TP_support_excluded_status_n | 3 | 4 | 4 |

NAV-PVT iTOW is GPS milliseconds in week 2408; conversion uses GPS−UTC=18 s. Status header matches its own status time_gps_wno/time_gps_tow conversion (floating-point tolerance). TIM-TP flags=27 has bit0=1, so its tow/week already use UTC: do not subtract 18 s a second time. RefInfo=63; qErrInvalid=1, so no precision claim from qErr. Nearest-epoch statistics do not optimize any offset. Full raw-support-edge statistics are retained in JSON; out-of-support edges are reported above rather than hidden.

TIM-TP flag reference (verified live 2026-09-09, section 3.18.3.1, printed page 167; PDF page index 166): [u-blox F9 TIM interface description](https://content.u-blox.com/sites/default/files/documents/u-blox-F9-TIM-2.24_InterfaceDescription_UBXDOC-963802114-13046.pdf).

## B.2 状态位置−trace，均值 ± 标准差 (m)

| Quantity | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| header F | 0.045523008 ± 0.073555995 (n=302) | 0.029237917 ± 0.032472894 (n=296) | 0.025827495 ± 0.036734305 (n=446) |
| header R | 0.175566320 ± 0.034888036 (n=302) | 0.184085126 ± 0.044023969 (n=296) | 0.174870661 ± 0.022875961 (n=446) |
| header U | -0.022261921 ± 0.038474342 (n=302) | -0.014026675 ± 0.038705011 (n=296) | -0.022924386 ± 0.031350632 (n=446) |
| sys_stamp F | -0.183983875 ± 0.089582314 (n=302) | -0.204714412 ± 0.063236738 (n=296) | -0.132277267 ± 0.122087340 (n=446) |
| sys_stamp R | 0.167399990 ± 0.037219720 (n=302) | 0.173794728 ± 0.048621969 (n=296) | 0.170048568 ± 0.028393236 (n=446) |
| sys_stamp U | -0.023199869 ± 0.037896344 (n=302) | -0.014457166 ± 0.037090422 (n=296) | -0.022588640 ± 0.031633426 (n=446) |

BY2 fixed 66–340 s support:

- header: F 0.048565799 ± 0.076482129 (n=274), R 0.175295584 ± 0.036446879 (n=274), U -0.022089378 ± 0.040040810 (n=274)
- sys_stamp: F -0.196723378 ± 0.076344005 (n=274), R 0.166879304 ± 0.038847595 (n=274), U -0.023384926 ± 0.039452213 (n=274)

## B.3 HPPOSECEF

| Quantity | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| gnss1 UBX-NAV-HPPOSECEF count | 1510 | 1483 | 2231 |
| gnss1 UBX-NAV-PVT count | 1510 | 1483 | 2231 |
| gnss1 UBX-NAV-RELPOSNED count | 1510 | 1483 | 2231 |
| gnss1 UBX-TIM-TP count | 302 | 296 | 446 |
| gnss1 pAcc mean±std m | 0.019676424 ± 0.003070056 (n=1510) | 0.019591571 ± 0.003108120 (n=1483) | 0.018922860 ± 0.002302443 (n=2231) |
| gnss1 pAcc min/median/P95/max m | 0.017300 / 0.018800 / 0.025300 / 0.041800 | 0.017300 / 0.018500 / 0.026090 / 0.040400 | 0.017300 / 0.018000 / 0.023600 / 0.034100 |
| gnss2 UBX-NAV-HPPOSECEF count | 1510 | 1483 | 2231 |
| gnss2 UBX-NAV-PVT count | 1510 | 1483 | 2231 |
| gnss2 UBX-NAV-RELPOSNED count | 1510 | 1483 | 2231 |
| gnss2 UBX-TIM-TP count | 302 | 296 | 446 |
| gnss2 pAcc mean±std m | 0.021286689 ± 0.007835466 (n=1510) | 0.022109171 ± 0.008193763 (n=1483) | 0.022976513 ± 0.009879734 (n=2231) |
| gnss2 pAcc min/median/P95/max m | 0.017300 / 0.018400 / 0.038730 / 0.069900 | 0.017300 / 0.018900 / 0.038700 / 0.076900 | 0.017300 / 0.018500 / 0.041900 / 0.083600 |

All 6 receiver streams have exact 200 ms iTOW spacing (5 Hz), and every HPPOSECEF epoch exactly equals a NAV-PVT and RELPOSNED epoch. Fractional seconds and counts:

- BY2: {"0.8": 302, "0.0": 302, "0.2": 302, "0.4": 302, "0.6": 302}
- BY2H: {"0.2": 297, "0.4": 297, "0.6": 297, "0.8": 296, "0.0": 296}
- BY2O: {"0.4": 447, "0.6": 446, "0.8": 446, "0.0": 446, "0.2": 446}

HPPOSECEF has scalar pAcc only (0.1 mm source units), **vAcc=UNAVAILABLE in HPPOSECEF**. NAV-PVT vAcc is vertical-position accuracy, whereas sAcc is speed accuracy. These must not be interchanged. Complete PVT vAcc/sAcc distributions are in B_AUDIT_<sequence>.json. Parser: raw_gnss.ubx_raw_binary_rebuilder.parse_bytes_cell/iter_ubx_frames (checksum validation), then existing horizontal_literature/shared_raw_backend.py:523–562 decode_nav_hpposecef. Zero invalid relevant frames.

## B.4 冻结接收机速度时标

| Quantity | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| gnss1 raw stamp−iTOW UTC seconds | 0.139904470 ± 0.010843468 (n=1510) | 0.139717200 ± 0.010995401 (n=1483) | 0.134677248 ± 0.010630809 (n=2231) |
| gnss2 raw stamp−iTOW UTC seconds | 0.134355423 ± 0.012687208 (n=1510) | 0.138065121 ± 0.011279892 (n=1483) | 0.124099748 ± 0.012979250 (n=2231) |

Frozen extractor paper_rebuild/ubx_nav_pvt.py:104–122 uses stamp.secs+stamp.nsecs×1e−9; Time is fallback when stamp.secs is absent. It does not use iTOW. The recorded delay is an input-clock audit; no velocity correction or new velocity provider was produced.

## B.5 A1、参考点和不确定度

| Quantity | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| A1 baseline length mean±std m | 0.355680355 ± 0.035253727 (n=302) | 0.351867533 ± 0.050403493 (n=297) | 0.348585279 ± 0.043279038 (n=446) |
| Half median A1 length m | 0.178095746 | 0.177093888 | 0.175067319 |
| header right mean minus half A1 median m | -0.002529426 | 0.006991238 | -0.000196658 |
| sys_stamp right mean minus half A1 median m | -0.010695756 | -0.003299160 | -0.005018752 |
| userio-raw.csv matched original rows | 602 | 592 | 892 |
| user_io-status.csv matched original rows | 302 | 297 | 446 |
| POI odometry rows | 3020 | 2967 | 4464 |
| odom_status rows | 3019 | 2966 | 4462 |

A1 is the difference GNSS2−GNSS1 of the two relative NED vectors after the exact frozen valid filter and header-epoch interpolation (input_generation/status_yaw_builder.py:184–224). Individual receiver rel_pos vectors are rover-to-base vectors and are not antenna separation.

All original matching CSV field values and line numbers are preserved in B_ORIGINAL_TF_POI_MESSAGES_<sequence>.json. In every sequence the transmitted POI→VRTK transform is translation (−0,−0,−0), quaternion (1,0,0,0). VRTK→CAM is (0.04260,0.00517,−0.01699), quaternion (0.503062,0.495851,0.506541,0.494447). Status file contains port/message counters, not a new antenna geometry configuration. The rightward descriptive residual is close to half the baseline; it does not prove a full POI/IMU/antenna-midpoint transform. An explicit source-backed full transform is **UNAVAILABLE**; do not derive it by fitting B.2.

Original example records (complete original records for all epochs are in JSON):

BY2
```text
$FP,TF,2,2408,460875.000000,VRTK,CAM,0.04260,0.00517,-0.01699,0.503062,0.495851,0.506541,0.494447*6A
$FP,TF,2,2408,460875.000000,POI,VRTK,-0.00000,-0.00000,-0.00000,1.000000,0.000000,0.000000,0.000000*7D
```

BY2H
```text
$FP,TF,2,2408,461220.000000,VRTK,CAM,0.04260,0.00517,-0.01699,0.503062,0.495851,0.506541,0.494447*61
$FP,TF,2,2408,461220.000000,POI,VRTK,-0.00000,-0.00000,-0.00000,1.000000,0.000000,0.000000,0.000000*76
```

BY2O
```text
$FP,TF,2,2408,460362.000000,VRTK,CAM,0.04260,0.00517,-0.01699,0.503062,0.495851,0.506541,0.494447*67
$FP,TF,2,2408,460362.000000,POI,VRTK,-0.00000,-0.00000,-0.00000,1.000000,0.000000,0.000000,0.000000*70
```
## B.5 covariance 摘要

| Quantity | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| pose.covariance sqrt diagonal 0 median/max | 0.055327560 / 0.505185337 | 0.055219299 / 0.698796204 | 0.049958103 / 0.289647878 |
| pose.covariance sqrt diagonal 7 median/max | 0.045867016 / 0.497016219 | 0.046404479 / 0.565935675 | 0.040363315 / 0.340768385 |
| pose.covariance sqrt diagonal 14 median/max | 0.061665107 / 0.536176525 | 0.061402830 / 0.564165182 | 0.054642973 / 0.383998040 |
| pose.covariance sqrt diagonal 21 median/max | 0.014308775 / 0.018418311 | 0.014490283 / 0.019605303 | 0.014504982 / 0.022797463 |
| pose.covariance sqrt diagonal 28 median/max | 0.016276199 / 0.026618551 | 0.016877487 / 0.024850105 | 0.018317136 / 0.034904740 |
| pose.covariance sqrt diagonal 35 median/max | 0.015465395 / 0.025233457 | 0.015880262 / 0.022996745 | 0.016936268 / 0.031935553 |
| twist.covariance sqrt diagonal 0 median/max | 0.087327432 / 0.194760558 | 0.087664277 / 0.183414311 | 0.081325257 / 0.161429990 |
| twist.covariance sqrt diagonal 7 median/max | 0.099461850 / 0.209133022 | 0.100044133 / 0.195431881 | 0.090143222 / 0.183323042 |
| twist.covariance sqrt diagonal 14 median/max | 0.067700141 / 0.109136886 | 0.068633284 / 0.111267765 | 0.064185722 / 0.104344973 |
| twist.covariance sqrt diagonal 21 median/max | 0.000641575 / 0.001235206 | 0.000641082 / 0.001155888 | 0.000561505 / 0.001093900 |
| twist.covariance sqrt diagonal 28 median/max | 0.000641575 / 0.001235206 | 0.000641082 / 0.001155888 | 0.000561505 / 0.001093900 |
| twist.covariance sqrt diagonal 35 median/max | 0.000641575 / 0.001235206 | 0.000641082 / 0.001155888 | 0.000561505 / 0.001093900 |

All 36 covariance entries per type have n/finite n/min/P05/median/mean/std/P95/max in JSON. Position covariance is in header ECEF; twist covariance is in child POI. Angular covariance square roots have rad or rad/s units; linear square roots have m or m/s units. These are estimator-reported covariances, not calibrated reference-error bounds or independent truth uncertainty.

## B.5 odom_status 状态分布 (原始枚举值:数量)

| Quantity | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| fusion_imu | {"1": 3019} | {"1": 2966} | {"1": 3840, "2": 622} |
| fusion_gnss1 | {"0": 4, "1": 2692, "2": 323} | {"0": 10, "1": 2617, "2": 339} | {"0": 6, "1": 4302, "2": 154} |
| fusion_gnss2 | {"0": 4, "1": 2692, "2": 323} | {"0": 10, "1": 2617, "2": 339} | {"0": 602, "1": 3705, "2": 155} |
| fusion_corr | {"0": 4, "1": 2692, "2": 323} | {"0": 10, "1": 2617, "2": 339} | {"0": 5, "1": 4302, "2": 155} |
| fusion_cam1 | {"1": 3019} | {"1": 2966} | {"1": 4462} |
| fusion_ws | {"0": 3019} | {"0": 2966} | {"0": 4462} |
| fusion_markers | {"-1": 3019} | {"-1": 2966} | {"-1": 4462} |
| gnss1_status | {"0": 4, "5": 321, "8": 2694} | {"0": 10, "5": 334, "8": 2622} | {"0": 6, "5": 152, "8": 4304} |
| gnss2_status | {"0": 4, "5": 321, "8": 2694} | {"0": 10, "5": 334, "8": 2622} | {"0": 602, "5": 160, "8": 3700} |
| baseline_status | {"2": 484, "3": 2535} | {"2": 516, "3": 2450} | {"1": 526, "2": 426, "3": 3510} |


## B.6 只读 C++ 输入编码审计

起点 `aed61a4892ceda36327269fc865922127edc3310`。下面四个 C++ 文件与科学冻结 `64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00` 逐字节一致，完整 SHA 见 JSON。未编译、未运行 C++、未生成 provider、未运行求解器。

| 编码 | 航向 | 接收机速度 | 结论 |
|---|---|---|---|
| 严格 15 列，有限正常值 | 默认有效 | 默认有效 | 没有独立逐行 skip 位 |
| NaN/Inf 或字段缺失 | 无显式 skip 语义 | 无显式 skip 语义 | UNAVAILABLE：不能保证合法逐观测禁用；流提取失败会导致整行不进入 rows，不能用于保留位置的跳过 |
| 有限 `yaw_std_deg >= yaw_std_hard_deg`（冻结 6 deg） | Scheme-C 先增加 attempt，然后 reject，未执行该 yaw EKF 更新 | 无关 | 可阻止接受航向，但不是 attempt-free skip；Basic 分支使用固定 std，不适用 |
| 有限超大速度 std | 无关 | 仍进入 EKFUpdate 并增加 velocity counter；只是低权重 | 不是无速度更新编码，且极大数存在数值风险 |
| 已有 18 列扩展 `position_valid velocity_valid yaw_valid` | 第 18 列为 0 真正跳过 | 第 17 列为 0 真正跳过 | 无需修改 C++；必须明确文件是 15+3 列，前三个数值块使用有限占位值 |

源码位置（相对 `<CODE_ROOT>`）：

- `cpp/legsa_v23_port_core/src/fileio/gnss_file_loader.cpp:38` 读取前 15 列；`:43` 只纳入流提取成功的行；`:50` 默认三种观测有效；`:53` 可选读取 3 个 0/1 列，`:69` 写入 has_position/has_velocity/has_yaw。扩展必须成组三列，不能只增加一位。
- `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:364` 检查 position；`:367` Basic 分支；`:377` 检查 has_yaw；`:383` 检查 has_velocity。
- `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:931` Scheme-C：`:932` 先增加 yaw attempt；`:935` 逐行读取 `gnss.yaw_std_rad`；`:938` std/residual hard gate；`:972` 才执行被接受的 yaw EKF 更新。
- `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:904` RV：`:912` 对输入 std 加地板及 0.05 m/s；`:926` EKFUpdate；`:927` 计数，没有专门的 std skip 门。
- `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:985` Basic 使用固定 std；大 yaw_std 无法禁用 Basic（本轮只预注册 A04/F01/F03）。
- `cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp:1366` 非 parity 的 formal 模式要求显式有效性；parity 模式仍可读该扩展。`:1436` 首条纳入行必须严格晚于 starttime，故 66 s 初始化行不算一次更新。
- `cpp/legsa_v23_port_core/src/fileio/file_saver.cpp:223` / `:261` / `:301` 输出状态位置，无写出时天线/POI 变换。

若强制严格 15 列并直接对 1 Hz 航向做保持，5 Hz 位置行会重复尝试同一 1 Hz 航向（最多五次，接受次数由门控决定），改变信息权重。可选方案：A04/F03 使用有限 6 deg 或更大 yaw std 强制拒绝非 A1 行，但 RV 无匹配时仍没有真正跳过；或者使用已有 18 列有效性扩展，在非 A1 行写 `1 rv_valid 0`、A1 行写 `1 rv_valid 1`，RV 未在 0.1 s 内匹配时写 `rv_valid=0`。本 P-01 将已有扩展作为无需改 C++ 的明确备选；严格 15 列且要求完整逐行 skip 的路线记为 BLOCKED_STRICT15_NO_RV_SKIP。不得删除位置行或全局关闭 RV 来假冒逐行输入对等。

以上三序列共用同一解析/更新源码；这不是三次 C++ 运行结果。

补充：`gi_engine.cpp:398–407` 在每个 GNSS 行调用 RD/RP/HV，不受 has_velocity/has_yaw 影响；`:996`、`:1080`、`:1137` 每次查找最近 provider，未设置消费去重。V1 改时间及 V2 改频率会改变辅助观测的选中历元/次数，即使 RD/RP/HV provider 字节不变。后续必须单列各源行 ID、选中时刻、重复选中、update/reject 计数；18 列只保证 yaw/RV 的显式 skip，不能保证辅助观测调度不变。V1−V2 因而还含辅助调度效应。

冻结二进制实际 SHA-256 已只读核对为 `9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`，未执行；源代码相等与二进制哈希相等不是运行验证。

## C. 求解前预注册阶梯

下表是预注册假设与预期方向，未观察任何变体求解结果。完整机读定义、源配置/provider SHA、匹配规则、计数与禁项见配套 YAML。

| 变体 | 唯一登记的改动 | 假设/预期方向 | 状态 |
|---|---|---|---|
| V0 | Canonical C00 冻结引用 | 固定参考，无新增假设 | 不重跑 |
| V1 | 1 Hz 状态流；仅 GNSS 时间列改为对应 header 历元；其余 GNSS 字节、IMU/RD/RP/HV 文件与 V0 相同 | 若接收延迟贡献沿航向误差，前向偏差幅值/位置误差可能减小；不预定 yaw 变化 | 已预注册，未执行；源行一一映射须验证 |
| V2 | 5 Hz GNSS1 HPPOSECEF/iTOW/pAcc；RV 最近 PVT ≤0.1 s；A1 每历元至多一行更新；18 列已有 validity 扩展跳过其他 yaw/无 RV 行 | 时标/离散采样、报文/std及调度的组合效应可能改善位置；不保证 | vAcc 语义 `UNAVAILABLE`，不可执行 |
| V3 | V2 相同 solver 输出，单独 v3 评估到天线中点；EXT05C 同样施加物理变换 | 若参考点身份成立，固定点差偏差可能减小 | 完整参考点身份 `UNAVAILABLE`，不可执行 |
| V4 可选 | 双接收机同 iTOW 的中点位置 | 对称接收机信息可能减少单侧误差；未知相关性不允许承诺 √2 收益 | LC01 双接收机条件成立；中点协方差/杆臂仍待预注册，不执行 |

V2 的 requested `pAcc/vAcc` 原文被保留。HPPOSECEF 无 vAcc；PVT `vAcc` 是垂直位置精度（m），`sAcc` 才是速度精度（m/s）。不能把它们互换，也不能悄悄沿用常量速度 std。须在后续 provider/求解前提交可溯源的 std 定义，当前相应来源记为 `UNAVAILABLE`。

本次选择 B.6 的已有 15+3 列格式作为“不改 C++”方案：第 16/17/18 列为 position/velocity/yaw 有效位，有限占位数字仅在对应 valid=0 时使用。A1 取冻结物理转换与 std，只在按 header 测量 UTC 对应的 HP 行 valid=1；时差阈值 0.1 s、平局取较早测量行、每个 A1 至多使用一次，匹配碰撞或缺失不能通过重复/删行消除。严格 15 列无法独立跳过 RV，单独路线记为 `BLOCKED_STRICT15_NO_RV_SKIP`。P-01 未进行 C++ 编译或运行测试；后续须先证明 parser/行数/counter 的实际行为。

V3 的冻结几何公式（FRD）：

```text
l_I→M = l_I→A1 + 0.5 b_A2−A1
      = [0.03,0.03,-0.30] + 0.5 [0,-0.350,0]
      = [0.03,-0.145,-0.30] m
p_M^ECEF = p_I^ECEF + R_NED→ECEF R_body→NED(method attitude) l_I→M
```

使用冻结物理 0.350 m，不把审计的半基线中位数或 B.2 残差当成拟合杆臂。各方法使用其自身姿态执行同一变换；不使用 trace 姿态来纠正估计。TF 只证明 POI 与 VRTK 为同点/同向，没有证明 trace 为天线中点；右向残差近半基线也不替代物理身份。因此 V3 当前 **UNAVAILABLE**。v3 必须新建独立评估器身份（实现 SHA 当前 UNAVAILABLE），保留 aa0492… v2 源及全部冻结数字。v3 是显式的物理评估点变换，不是回写 NAV 或误差驱动的输出修正。

可选 V4 中 `p_M=(p_1+p_2)/2`，`R_M=(R_1+R_2+R_12+R_21)/4`；跨接收机相关性来源为 UNAVAILABLE。把位置换到中点却继续使用 GNSS1 测量杆臂不合法；当前“参数逐字节相同”约束未放开，不能自动更改杆臂。V4 只登记为可选项，需先解决该约束和协方差定义。

分解对每个 H/3D/Up/yaw RMSE 分别登记：

```text
时标项   = V0 − V1
速率项   = V1 − V2
测量点项 = V2 − V3
估计器项 = V3 − EXT05C(v3)
```

前三项正值表示下一阶梯 RMSE 较低；估计器项正值表示内部方法比 EXT05C 高。所有当前分解值均为 **UNAVAILABLE**。这些是顺序描述性差值，不是独立物理误差或平方误差分量：速率项同时涉及报文、std、RV/yaw及 RD/RP/HV 调度；估计器项还保留辅助观测、初始化、过程噪声、实现及原生历元支持差异。不得称为纯采样率或纯滤波公式效应。

运行对象固定 A04（AB1011）为主，F01/F03 对照；BY2 窗口 66–340 s，base_time=1772784000，科学 solver `64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00`，二进制 SHA `9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`，v2 评估器 SHA `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`。BY2H/BY2O 本轮仅审计，未登记变体求解。

每个科学参数 token、模块开关、初始化、噪声、杆臂、阈值及窗口都逐字节复制各自冻结配置。仅 YAML 白名单中的 identity/path 行可替换，必须保留逐行变更清单；不得重序列化数值参数。后续若 provenance 或 counter 合约不接受新家族，应阻断，不放宽主链合约。V1 的 GNSS 非时间字节不变；V2 的科学参数和 IMU/RD/RP/HV 文件不变。相同辅助文件不代表相同调度，须单列源行、时刻、重复选中、更新与拒绝计数。

禁项：P-01 求解；调参；拟合时间/符号/杆臂/偏移；trace 用于 provider 或在线输入；改 C++；主链改写；NaN/超大 RV std 冒充 skip；重复使用 1 Hz 航向；按误差删历元；输出替换；v3 替换 v2；merge、tag、历史重写。新 manifest 须记录真实 data_mode、raw/provider hashes、合成标志、所有 forbidden 标志、code_commit/config_hash、变体/家族、参数 byte diff、评估器/参考点/覆盖与 terminal。

## D. 交付与验证边界

本轮只提交本文件与 `configs/paper_rebuild/clean5/CLEAN5_PARITY_CONTRACT.yaml`。外部审计根保留 A/B JSON、三序列报文清单及 TF 原文、可复现审计代码、B6 源码/二进制身份、C 合约副本及验证/交付记录。27/27 所用 raw 文件锁匹配；A 的 CSV 行、配置与源文件身份和 B6 逐行 skip 语义已只读复核。YAML 解析与 scoped diff 检查执行后，最终结果见外部 `P01_VALIDATION.json` / `P01_DELIVERY.json`。不将未运行测试写作已通过。

提交消息：`docs(clean5): parity target extraction, input-side/reference-geometry audits, pre-registered parity ladder`。Git 操作来自本次人类明确授权；本文件不授予任何后续变体求解或阶段转换。
