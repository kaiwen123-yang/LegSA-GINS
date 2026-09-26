# CLEAN5 P-06 BY2 传感器噪声标定记录

状态：`CALIBRATION_COMPLETE`；接受记录为 `PASS_CORRECTED_AUDIT_NO_RECOMPUTATION`。实际标定计算 1 次，重算 0 次；三轴均为 CALIBRATED。B/C 尚未执行。

预注册与计算提交：`8ea4076bb3a6c259ceddc225533b0d522620da00`。模型冻结提交以本文件所属提交为准。数学合约、实现及首次模型/表格字节未改。

`<CALIBRATION_ROOT> = <CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/00_CALIBRATION`。模型为 [CLEAN5_CALIBRATED_SENSOR_MODEL.yaml](../../configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml)，其 SHA-256 为 `4ce6ca6c544c2ba39988ea0b0631a60207a4cea36987c3a2139052fedd3a4871`。

基底 V2s，冻结当前样本积分；dvel 已含 s、dt、FLU→FRD 与安装角。`s=1.0308398903907543`，`g_local=9.801554354839126 m/s²`；窗口 [66,340] s。BY2H/BY2O 使用同一 s、vrw、abstd，禁止再标定。

以下数值直接转录现成 CSV 行，未重新拟合。vrw 单位 (m/s)/√h，abstd 单位 mGal，q 单位 m²/s³，c 单位 (m/s)²。N/E/D 按指定索引写入 body/FRD 求解器参数；这不是对物理 body 各轴协方差的识别。Go2 roll/pitch 沿用冻结 weak-prior 操作语义，无新增姿态对齐；不含 Coriolis。

| 轴/参数索引 | vrw | abstd | q | c | 完整非空窗数 | 状态 | 来源 |
|---|---:|---:|---:|---:|---:|---|---|
| north/0 | 9.478382094779873 | 4817.482008954474 | 0.024955479759623252 | 0.010830809489394968 | 4 | CALIBRATED | CALIBRATED_PARAMETERS.csv:2 |
| east/1 | 9.784198200134004 | 8259.572423450163 | 0.026591815116529294 | 0.013550612232080246 | 4 | CALIBRATED | CALIBRATED_PARAMETERS.csv:3 |
| down/2 | 7.6321402201126745 | 2257.241538343225 | 0.01618043453873932 | 0.020536668097236248 | 4 | CALIBRATED | CALIBRATED_PARAMETERS.csv:4 |

各 lag 残差样本方差采用 ddof=1；OLS 有截距、无权、不裁剪 c。

| lag/s | 样本数 | N 方差 | E 方差 | D 方差 | 来源行 |
|---:|---:|---:|---:|---:|---|
| 0.2 | 1370 | 0.024537905066082697 | 0.02820850489234666 | 0.015570559355558506 | LAG_VARIANCE_FIT.csv:2,3,4 |
| 0.4 | 1369 | 0.016668063033687612 | 0.02015801284776913 | 0.033100626394219824 | LAG_VARIANCE_FIT.csv:5,6,7 |
| 0.6 | 1368 | 0.023759190059108568 | 0.026035741773151377 | 0.041563699820744836 | LAG_VARIANCE_FIT.csv:8,9,10 |
| 0.8 | 1367 | 0.03466825456257017 | 0.04066286690525002 | 0.03490378824289428 | LAG_VARIANCE_FIT.csv:11,12,13 |
| 1.0 | 1366 | 0.024944587981647975 | 0.027629574936006564 | 0.02418059321659022 | LAG_VARIANCE_FIT.csv:14,15,16 |
| 1.5 | 0 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | LAG_VARIANCE_FIT.csv:17,18,19 |
| 2.0 | 1361 | 0.06518425503138911 | 0.07156804762060427 | 0.05480291424710643 | LAG_VARIANCE_FIT.csv:20,21,22 |

1.5 s 无 exact iTOW 端点对，UNAVAILABLE，不插值或替换。全部完整 1 s pair 的窗均残差加速度如下；跨窗标准差 ddof=1。尾段 [306,340] s 按预注册排除于 abstd。

| 轴 | 窗口/s | 样本数 | 均残差加速度/(m/s²) | 来源 |
|---|---|---:|---:|---|
| north | 66.0–126.0 | 296 | -0.05570374637108451 | WINDOW_MEAN_ACCELERATION.csv:2 |
| east | 66.0–126.0 | 296 | -0.06772208679278863 | WINDOW_MEAN_ACCELERATION.csv:3 |
| down | 66.0–126.0 | 296 | 0.1257728093911521 | WINDOW_MEAN_ACCELERATION.csv:4 |
| north | 126.0–186.0 | 296 | -0.04705993460926742 | WINDOW_MEAN_ACCELERATION.csv:5 |
| east | 126.0–186.0 | 296 | 0.02263644514433051 | WINDOW_MEAN_ACCELERATION.csv:6 |
| down | 126.0–186.0 | 296 | 0.1416768377031093 | WINDOW_MEAN_ACCELERATION.csv:7 |
| north | 186.0–246.0 | 296 | -0.03308359593786521 | WINDOW_MEAN_ACCELERATION.csv:8 |
| east | 186.0–246.0 | 296 | 0.12148568746690054 | WINDOW_MEAN_ACCELERATION.csv:9 |
| down | 186.0–246.0 | 296 | 0.09474612013029422 | WINDOW_MEAN_ACCELERATION.csv:10 |
| north | 246.0–306.0 | 296 | 0.04924704039782077 | WINDOW_MEAN_ACCELERATION.csv:11 |
| east | 246.0–306.0 | 296 | -0.03289260415208413 | WINDOW_MEAN_ACCELERATION.csv:12 |
| down | 246.0–306.0 | 296 | 0.1435114415840997 | WINDOW_MEAN_ACCELERATION.csv:13 |

`arw=[0.985,0.985,0.985]`、`gbstd=[9.38,9.38,9.38]`、`initbastd=[77.8,77.8,77.8]` 及 corrtime/其他科学参数保持原文。A1 噪声 1.5° 下，本协议不辨识 arw。c 仅作 GNSS 速度噪声诊断，不反馈。

首次外层审计将三份 trace_ 前缀的源码/文档误计为 trace 数据。原 CALIBRATION_FAILURE.json 和原审计保留。补充审计逐条验证这三次只读 open 属于 PID 26265 的 `/usr/bin/git status --porcelain=v1 --untracked-files=all`，相对路径 SHA 与冻结 Git blob SHA 均匹配；实际标定 Python PID 26260 未读取这些文件。Git 仅返回空 porcelain 状态，文件内容未进入标定数组或参数。

实际 trace/.bag/.fpl 数据打开 0/0/0，未声明受保护输入 0，越界写入 0；实际 raw 仅 body、PVT、status 三文件。补充阶段不调用数据加载或计算，只验证现成日志、原模型及表格哈希。33 项隔离测试通过；只读复核通过。

接受记录：`<CALIBRATION_ROOT>/AUDIT_CLASSIFICATION_REVIEW/CALIBRATION_ACCEPTANCE.json`，SHA-256 `0ddd3c93700ab8177497650d10739ef1357d8e5664183b09a4a7d4ae082e2e07`。过程 SHA-256 `58643fbcf04efd628cc29cd733b4ba3f7a56f379bc5f503987ac4ecd882c3349`。

| 冻结来源 | SHA-256 |
|---|---|
| LAG_RESIDUALS.csv | `c9210056d1b456dcc86bc87bd0feff78b37ac1db49878bd655932d8f4388b1a6` |
| LAG_VARIANCE_FIT.csv | `7e36b5ccc0e9ad83db54de084bf296a16d6282b50e492c53d402e1e2eff474c6` |
| WINDOW_MEAN_ACCELERATION.csv | `0bc4ed23671467fca6af4120fb25fc183da88c801d4b2b85aa442e060a61c14a` |
| CALIBRATED_PARAMETERS.csv | `543252c30425cf1a9b418de2bd7dbf95282045dbd3c43fbd980a59172d9d3cc9` |
| CALIBRATION_AUDIT.json | `3d650aad4429b4904c0f250a92196a7bb8193831e6acc1f716db44082f2baeec` |
| CLEAN5_CALIBRATED_SENSOR_MODEL.yaml | `4ce6ca6c544c2ba39988ea0b0631a60207a4cea36987c3a2139052fedd3a4871` |

分类：`NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL`；主链、原比较协议与 Outcome 不变。synthetic_data_used=false，semisynthetic_data_used=false，trace_used_online=false。
