# H-EXT-01 配置对等审计、只读探针与序列适配

状态：`PASS_BY2_BYTE_IDENTITY`；共享参数合约保持 `DRAFT_PENDING_HUMAN_AUTHORIZATION`。

本次唯一求解为 BY2 文献默认 EXT05A/EXT05C 身份对；BY2H/BY2O 求解 0、评估器调用 0、三序列 trace 内容打开/哈希 0。身份输出不入性能表，BY2 文献行继续使用 P-07 冻结值。

## 起点与输出

分支 `stage/clean3-math-repair`，起点 `a40a232f8a08bd3ece8525931a06a3ba06017d29` 与 upstream 相等。两个登记未跟踪脚本保留。所有输入经 local YAML 与 CLEAN5 registry 解析；原缺少的 `hext_scratch` 已添加在忽略的 local YAML，文件系统由 `findmnt` 确认为 ext4。

起点 `df -h`：
```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/sdd 1007G 77G 880G 9% <SCRATCH_VOLUME_MOUNT>
G: 932G 699G 234G 75% <G_VOLUME_MOUNT>
```

运行输出：`<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/`；探针 `01_PROBE/<SEQ>/PROBE.json` 与 `PROBE.md`，状态计数补充 `P1_STATUS_SUPPLEMENT.json`；审计 `00_CONFIG_AUDIT/`；身份 `02_BY2_IDENTITY/`。本地执行与归档均保留，未清理任何外部文件。

## 配置对等审计

| 项目 | LegSA v2.1 取值与来源路径 | LC01/EXT05C 取值与来源路径 | 分类 | 数值换算与事实 |
| --- | --- | --- | --- | --- |
| A1 位置/UTC | GNSS1 HPPOSECEF；周2408、闰秒18；`CI:41–71; CP:65,99–109` | 同一gnss1-raw.csv、同一HPPOSECEF decoder；周2408、闰秒18；`EP#build_solution_position_provider; SB:523–551` | 共享-一致 | UTC=315964800+week×604800+iTOW_ms/1000−18；BY2闭窗[66,340]共1371历元，max‖ΔECEF‖=0 m、max绝对Δt=0 s |
| A2 位置R | diag(hAcc²,hAcc²,vAcc²)；hAcc中位/P95=.014/.016 m、vAcc=.012/.021 m；`CP:104–109; CI:62–64` | R1=pAcc1²·I3；pAcc1中位/P95=.019/.02545 m；`EP#build_solution_position_provider; PC#solution_provider` | 方法特有 | 逐历元pAcc/hAcc中位/P95=1.3333333333333335/1.792857142857143；pAcc/vAcc=1.5333333333333332/1.7500000000000002；R构造不改 |
| A3a IMU时基 | Go2 host stamp，offset=0 s；`IB:92,109; SC:630` | Go2 stamp.sec+nanosec×1e−9，offset=0 s；`EP#_imu_only_messages,#build_imu_only_provider` | 共享-一致 | absolute−sequence base_time；不加sys_stamp经验偏移 |
| A3b 坐标/安装 | FLU→FRD [x,−y,−z]，再active RzRyRx安装[-1,0,0]°；`IB:96–113; IM:95–101` | FLU→FRD，再active RzRyRx安装[-1,0,0]°；`EP#IMU_INSTALL_RPY_DEG,#build_imu_only_provider` | 共享-一致 | R=Rx(−π/180)·diag(1,−1,−1)；转换顺序一致 |
| A3c GNSS1杆臂 | FRD [0.03,0.03,−0.30] m；`SC:582` | FRD [0.03,0.03,−0.30] m；`PC#frames_and_geometry; EP#LEVER_IMU_TO_RECEIVER1_FRD_M` | 共享-一致 | 单位m，不改杆臂或安装角 |
| A3d 基线/航向 | GNSS2−GNSS1 status A1差分；−atan2(rel_e,rel_n)，再90°−body_candidate；`SC#frozen_parameters.dual_yaw_contract` | HPPOSECEF GNSS2−GNSS1三维向量；固定FRD [0,−0.350,0] m；EXT05C仅初始化用双接收机；`PC#frames_and_geometry; EF#measurement_jacobian` | 信息结构 | 天线物理顺序一致；标量A1航向和三维相对位置及相关R不可等同 |
| A4 加计PSD | vrw=[9.478382094779873,9.784198200134004,7.6321402201126745] m/s/√h；q=[0.024955479759623252,0.026591815116529294,0.01618043453873932] m²/s³；`SM:146–153,183–186` | [0.0289,0.0225,0.0576] m²/s³；`PC#process_noise_psd_paper_experiment` | 共享-不一致 | q=(vrw/60)²，最大互验误差3.469446951953614e−18；LC01/LegSA PSD比=[1.158062288458136,0.8461250163406164,3.5598549508725266] |
| A5 陀螺PSD | arw三轴0.985 °/√h → 8.209651003126647e−08 rad²/s；`SM:482–485` | [4e−4,4e−4,3.24e−4] rad²/s；`PC#process_noise_psd_paper_experiment` | 共享-不一致 | PSD=(0.985·π/180/60)²；LC01/LegSA std比=[69.80196488903431,69.80196488903431,62.82176840013088] |
| A6 加计标度 | s=1.0308398903907543；当前样本三轴未舍入FRD比力，转换/安装后、乘dt前；`IM:50–57,95–101; SM:176` | s=1.0，未施加；`EP#build_imu_only_provider` | 共享-不一致 | dvel_s=(current_force_frd×s)×measured_dt；时间/gyro token不变；非已舍入增量二次缩放 |
| A7 零偏 | 21态含gyro/accel bias；gbstd=[9.38]*3 °/h；abstd=[4817.482008954474,8259.572423450163,2257.241538343225] mGal；前1000帧gyro均值预扣除，solver初值bias=0；`SC:569–581; IB:114–132; SM:150–153,486–493` | 9态无bias状态；首个合法5 s gyro均值常量；加计bias不估计；`PC#imu_calibration; EF#PavlasekIEKF; EP#calibrate_static_imu` | 方法特有 | gbstd×π/180/3600转换为rad/s；abstd×1e−5为m/s²；初始协方差和bias状态结构冻结 |
| A8 静态标定窗 | 前1000帧gyro初始均值；BY2蹬脚下界62.579067 s、算法起点66 s；`IB:114–125; SC#window_contract.constants.by2_control` | used_preregistered_initial_interval=true；1031样本；绝对[1772784044.887078,1772784049.887078] s；`C4#/provider/calibration` | 方法特有 | 相对[44.887078046798706,49.887078046798706] s；gyro模中位=.015289418986737115 rad/s；accel模中位=9.507909327281775 m/s²；maxgap=.014250040054321289 s；不含蹬脚 |
| A9 重力 | g_local=9.801554354839126 m/s²；`SM:157` | 静态判据和传播用同一local normal gravity=9.801554418645956 m/s²；`EP#local_normal_gravity_mps2,#calibrate_static_imu; PR:462; C4#/provider/calibration` | 共享-不一致 | LC01−LegSA=6.380683004181265e-08 m/s²；LC01不是9.80665；各自局部位置产生微小差异 |
| A10 IMU间断 | 原始dt≤0或>0.1时drop增量；BY2H保留时间407.017058→413.041069及414.905067→415.081079；`SC:527; GAP` | 传播dt>0.1抛PavlasekFilterError；`EF:334–335` | 方法特有 | 长间隔6.024011 s跨初始化，首NAV=413.047045，无左NAV；内部.176012 s前后状态变化，loader使用保留行时间差；没有4.7 s保留增量步；机制待H-EXT-02 |
| A11 输出时间支撑 | P07 A04/CAL与V2S均56642/56642/1.0；56642÷274=206.72262773722628 rows/s；`PT#LegSA_CAL,LegSA_V2S及source_row EVALUATION_RESULT.json` | LC01/EXT05C均58014/58014/1.0；58014÷274=211.72992700729927 rows/s；`PT#LC01_EXT05A,EXT05C及EVALUATION_RESULT.json` | 信息结构 | 三元组=output_epoch_count/matched_epoch_count/coverage_ratio；同窗口不等于同NAV样本率/采样权重 |
| A12 评估器/点/窗口 | 同aa049248…；v3杆臂[.03,−.148095745932992,−.30] m；[66,340] s；`PE:34–55; CE#sequences.BY2` | 同aa049248…、同v3点和窗口；外部argv省略--std；`PT#LC01_EXT05A; EC` | 共享-一致 | v3 lever=[.03,.03−.5×b_med,−.30]，b_med=.356191491865984；体坐标三分量见下表，仅保留P07原值 |
| 方法结构 过程注入/初协方差 | 21态EKF；initposstd10 m/initvelstd1 m/s/initattstd2°；`SC#frozen_parameters.filter_contract,#initialization_contract` | 9态SE₂(3)左不变误差；初协方差att=(π/3)²I3、vel=.1²I3、pos=.1²I3；Van Loan；`PC#initialization; EF#continuous_error_matrices,#van_loan_discretize` | 方法特有 | 共享变体不改过程噪声注入方式、初始协方差、R构造、静态标定或几何阈值 |
| 信息结构 辅助观测 | 位置、A1 yaw、接收机速度、Raw Doppler及RP/HV；`SC#frozen_parameters.filter_contract,#solver_common` | LC01两位置接收机；EXT05C单位置更新；无RP/HV/Raw Doppler；`PC#methods,#solution_provider` | 信息结构 | 剩余差距不构成纯EKF/IEKF公式因果比较 |

完整来源行号、换算与附注见 [H_EXT_CONFIG_PARITY_AUDIT.md](H_EXT_CONFIG_PARITY_AUDIT.md) 与同名 CSV。

## P1/P2/P3/P4/P5/P6 三序列并排

| 项目 | BY2 | BY2H | BY2O |
|---|---|---|---|
| P1 HPPOSECEF GNSS1/GNSS2 | 1510/1510 | 1483/1483 | 2231/2231 |
| P1 RAWX GNSS1/GNSS2 | 1509/1509 | 1483/1483 | 2231/2231 |
| P1 common iTOW / 单调 | 1510 / True | 1483 / True | 2231 / True |
| P1 iTOW 间隔直方（两接收机相同） | {'200': 1509} | {'200': 1482} | {'200': 2230} |
| P1 >200 ms GNSS 缺口 | 0 | 0 | 0 |
| P1 HPPOSECEF−RAWX / 首端额外 HP 历元 | +2 ms 恒定 / 1 | +2 ms 恒定 / 0 | +2 ms 恒定 / 0 |
| P1 GPS 周 / 闰秒 | 2408 / 18 | 2408 / 18 | 2408 / 18 |
| P1 pAcc1 中位/P95 (m) | 0.0188 / 0.0253 | 0.0185 / 0.02609 | 0.018 / 0.0236 |
| P1 pAcc2 中位/P95 (m) | 0.0184 / 0.03873 | 0.0189 / 0.0387 | 0.0185 / 0.0419 |
| P1 pAcc > BY2 同接收机全程中位×3（GNSS1/GNSS2） | 0/20 | 0/24 | 0/52 |
| P1 GNSS2 status float 历元（独立口径） | 0 | 0 | 57 |
| P1 首 GNSS1 相对时刻 / 减 t_start (s) | 55.799999952 / -10.200000048 | 401.200000048 / -11.799999952 | 3143.400000095 / -42.599999905 |
| P2 IMU 样本数 | 63278 | 63222 | 95860 |
| P2 dt 中位 / 最大 (s) | 0.00401186943054199 / 0.0916762351989746 | 0.00400590896606445 / 4.74000597000122 | 0.00401592254638672 / 0.345998764038086 |
| P2 dt>0.1 s 缺口数 | 0 | 4 | 6 |
| P2 前 5 s 静态判据 / 需后备窗 | True / 否 | True / 否 | True / 否 |
| P2 首个满足窗绝对起点 (s) | 1772784044.887078 | 1772784394.943074 | 1772783501.5570683 |
| P3 BY2 控制复核 | PASS：1510/1509/63278/2408/18/200ms/+2ms | 不适用（独立观测） | 不适用（独立观测） |
| P4 size/SHA 核对 | 3/3；原 BY2 锁 | 3/3；CLEAN5 锁 | 3/3；CLEAN5 锁 |
| P5 baseline_median_m | 0.356191491865984 | 0.35418777593777223 | 0.35013463864843675 |
| P5 base_time / window | 1772784000 / [66.0, 340.0] | 1772784000 / [413.0, 683.0] | 1772780400 / [3186.0, 3563.0] |
| P5 trace sha（仅声明，未打开/哈希） | ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c | 8d11fe360753bfcdbc54f7bf793fcb25850c0997b7aaad4ec1c9f10859c0f84f | 4f7b3007c6a0b43ce1b0fb4908f23c042891154b4adbc7af4c3d8a47ca363cd9 |
| P6 IMU 起点（绝对 s） | 1772784044.887078 | 1772784394.943074 | 1772783501.5570683 |
| P6 前 5 s 绝对区间 | 1772784044.887078–1772784049.887078 | 1772784394.943074–1772784399.943074 | 1772783501.5570683–1772783506.5570683 |
| P6 蹬脚绝对时刻 / 序列起点 | 1772784062.579067 / 1772784066.0 | None / 1772784413.0 | 1772783554.3510494 / 1772783586.0 |
| P6 前 5 s 含蹬脚 | NO | UNDETERMINED_NO_DETECTED_KICK | NO |

BY2O 的 52 个 pAcc 超阈值历元来自 5 Hz HPPOSECEF；57 个 float 来自约 1 Hz GNSS2 status，不能互相替代。BY2H 未检测到蹬脚；其缺口内蹬脚仅为冻结假设，前 5 s 不含已检测事件的结论保持 UNDETERMINED。

### P2 全部 IMU gap 与 gap 后 1 s GNSS1 位置变化率

|序列|gap 相对起止 (s)|时长 (s)|相对窗口|后 1 s 变化率中位/最大 (m/s)|
|---|---|---|---|---|
|BY2H|407.017058372→411.757064342|4.74000597000122|BEFORE|1.1629548423 / 1.22953640913|
|BY2H|411.757064342→412.479047775|0.721983432769775|BEFORE|1.16652639377 / 1.22385846557|
|BY2H|412.479047775→413.037091970|0.558044195175171|WITHIN_OR_OVERLAPPING|1.20294853937 / 1.22385846557|
|BY2H|414.905067205→415.080781937|0.175714731216431|WITHIN_OR_OVERLAPPING|1.16207675212 / 1.19297257887|
|BY2O|3240.749052525→3241.017060041|0.268007516860962|WITHIN_OR_OVERLAPPING|1.29319380215 / 1.40294068217|
|BY2O|3301.289052486→3301.399059296|0.110006809234619|WITHIN_OR_OVERLAPPING|1.1358548493 / 1.2124127001|
|BY2O|3362.013047695→3362.359046459|0.345998764038086|WITHIN_OR_OVERLAPPING|0.0286032238435 / 0.0666952678411|
|BY2O|3392.541158438→3392.649062157|0.107903718948364|WITHIN_OR_OVERLAPPING|0.0177908972109 / 0.0273952781247|
|BY2O|3483.751065969→3483.917062998|0.16599702835083|WITHIN_OR_OVERLAPPING|1.27495683742 / 1.36275568033|
|BY2O|3544.833066702→3544.987059832|0.153993129730225|WITHIN_OR_OVERLAPPING|1.05181911348 / 1.18198512355|

变化率定义：gap 结束后闭区间 1 s 内，相邻 GNSS1 HPPOSECEF ECEF 差的模除实测 UTC 间隔；未插值。各 gap 的绝对起止、原始行号及净变化率在 JSON 中完整保留。

### A8 标定窗口与 A10 冻结间断原始记录

```json
{
  "A8": {
    "status": "AVAILABLE",
    "source": {
      "path": "<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/EXT05A_C00_NATIVE_SUMMARY.json",
      "sha256": "466b99cb075e5dd7e2e93bb3a27e4ca8df4ffbbffd5bd81ec561e053bc614dea"
    },
    "calibration": {
      "acceleration_norm_median_mps2": 9.507909327281775,
      "end_time_unix_seconds": 1772784049.887078,
      "gyro_bias_frd_radps": [
        -0.0076655634452167005,
        -0.0026948138158392793,
        -0.0011093268712426007
      ],
      "gyro_norm_median_radps": 0.015289418986737115,
      "local_gravity_mps2": 9.801554418645956,
      "max_internal_gap_seconds": 0.014250040054321289,
      "mean_specific_force_frd_mps2": [
        -0.13180068738317743,
        -0.14941227642414154,
        -9.506078096349812
      ],
      "sample_count": 1031,
      "start_time_unix_seconds": 1772784044.887078,
      "used_preregistered_initial_interval": true
    },
    "window_relative_s": [
      44.887078046798706,
      49.887078046798706
    ],
    "event_source": {
      "path": "<CODE_ROOT>/configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml",
      "sha256": "64bf78d5d4241294922fbc6c18eaeb8ad4c2e40663ba8e5306ab67e1d07d4e19"
    },
    "by2_control": {
      "kick_time_lower_bound": 62.579067,
      "required_end": 340.0,
      "required_start": 66.0,
      "start_reference": 66.0
    },
    "kick_time_absolute_lower_bound": 1772784062.579067,
    "contains_registered_kick": false,
    "initialization_start_absolute": 1772784066.0
  },
  "A10": {
    "status": "AVAILABLE",
    "imu_source": {
      "path": "<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS/BY2H/CALIBRATED_IMU.imu",
      "sha256": "d32e4891080e300e6edde4526146636f15ec54df945a0470c57fbbdc3aa5115c"
    },
    "nav_source": {
      "path": "<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/03_CALIBRATED_RUNS/CLEAN5_CALIBRATED_BY2H_A04/KF_GINS_Navresult.nav",
      "sha256": "9da51135029a5f54fb1e387c5df8b20c6e364458731644239332ee5f36710b01"
    },
    "nav_first_time_s": 413.047045,
    "nav_last_time_s": 682.99505,
    "gaps": [
      {
        "left_file_line": 2677,
        "right_file_line": 2678,
        "left_increment": [
          407.017058,
          -8.9e-07,
          2.209e-05,
          -1.052e-05,
          -0.00015581,
          -0.00064531,
          -0.01953954
        ],
        "right_increment": [
          413.041069,
          -0.0008024,
          0.00150449,
          0.00064846,
          -0.00072136,
          0.001436,
          -0.03357566
        ],
        "duration_s": 6.024010999999973,
        "left_nav": null,
        "right_nav": null,
        "nav_state_equal": null,
        "classification": "INITIALIZATION_NO_LEFT_NAV"
      },
      {
        "left_file_line": 3007,
        "right_file_line": 3008,
        "left_increment": [
          414.905067,
          -0.00012107,
          -0.00015155,
          0.00048608,
          -0.00109376,
          -0.00294075,
          -0.01949009
        ],
        "right_increment": [
          415.081079,
          0.00023702,
          -0.00022612,
          -0.00011646,
          0.0004978,
          0.00022049,
          -0.00560682
        ],
        "duration_s": 0.17601200000001427,
        "left_nav": [
          0.0,
          414.905067,
          39.984886192,
          116.343123538,
          41.432496659,
          1.072434351,
          -0.641533354,
          -0.332394868,
          -0.294065464,
          -1.835199364,
          334.206422856
        ],
        "right_nav": [
          0.0,
          415.081079,
          39.984887683,
          116.343123024,
          41.354679169,
          0.970011652,
          -0.394773587,
          1.214437677,
          -0.079701038,
          -1.672099491,
          334.579230431
        ],
        "nav_state_equal": false,
        "classification": "NAV_STATE_CHANGED_OVER_RETAINED_TIMESTAMP_GAP"
      }
    ],
    "four_point_seven_second_retained_increment_gap_present": false,
    "long_gap_propagation_claim": "NOT_OBSERVABLE_NO_NAV_BEFORE_INITIALIZATION",
    "source_semantics": "loader assigns dt=successive retained timestamps; first aligned IMU initializes without NAV; later dt enters bias compensation/mechanization/covariance"
  }
}
```

### P5 冻结依赖

|依赖|存在|SHA-256|匹配|
|---|---|---|---|
|evaluator|True|aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da|True|
|v21_sequences_v3|True|e26dfcd830d6c711ffbb7debd68293fbf7b7ea28240e16bce582381b61ea6a0b|True|
|figure_render|True|800df76ad82b68e3fca7aded30081f6d1ad01241175978baf440c9e0f290dd4e|True|
|parity_target|True|63ad6db8a65aafb3730cdcb4342dcd0b3ba1fad88784719ba920755dca169790|True|

CLEAN5 锁 44 行，SHA-256 `faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67`；H/O 六文件的 size/SHA 全部相等。该锁不包含 BY2；详见附录裁定。

## BY2 身份门

```json
{
  "native_process_exit": 0,
  "elapsed_seconds": 26.133260548999942,
  "trace_open_count": 0,
  "evaluator_invocation_count": 0,
  "trace_open_records": [],
  "strace_sha256": "e7980f095da330b006ac3ab1cafbb44567b1b307b147c2dc16d377048e2fbc6e",
  "target_sha256": "63ad6db8a65aafb3730cdcb4342dcd0b3ba1fad88784719ba920755dca169790",
  "default_only": true,
  "native_budget": 2,
  "performance_table_admission": false,
  "methods": {
    "LC01": {
      "method_id": "EXT05A_PAVLASEK_TWO_RECEIVER_IEKF",
      "expected_sha256": "ccd25c2e1309ba2870e57e2208f476a6b48eaba69f0d038f26be2f168bb2c695",
      "actual_sha256": "ccd25c2e1309ba2870e57e2208f476a6b48eaba69f0d038f26be2f168bb2c695",
      "hash_equal": true,
      "original_nav_exists": true,
      "byte_equal": true,
      "first_difference": null,
      "actual": "<HEXT_SCRATCH>/H_EXT_01_BY2_IDENTITY/EXT05A_PAVLASEK_TWO_RECEIVER_IEKF/EXACT_EVALUATOR_INPUT.nav",
      "original": "<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/POST_NATIVE_TRACE_EVALUATION/EXT05A_PAVLASEK_TWO_RECEIVER_IEKF/EXACT_EVALUATOR_INPUT.nav",
      "output_epoch_count": 58014
    },
    "EXT05C": {
      "method_id": "EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF",
      "expected_sha256": "915192d6fcefaf7bef33c4028b571d1b723f7e0759063e2955aebd3d1ee7ace8",
      "actual_sha256": "915192d6fcefaf7bef33c4028b571d1b723f7e0759063e2955aebd3d1ee7ace8",
      "hash_equal": true,
      "original_nav_exists": true,
      "byte_equal": true,
      "first_difference": null,
      "actual": "<HEXT_SCRATCH>/H_EXT_01_BY2_IDENTITY/EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF/EXACT_EVALUATOR_INPUT.nav",
      "original": "<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/POST_NATIVE_TRACE_EVALUATION/EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF/EXACT_EVALUATOR_INPUT.nav",
      "output_epoch_count": 58014
    }
  },
  "native_invocation_count": 2,
  "status": "PASS_BY2_BYTE_IDENTITY",
  "native_trace_audit": "PASS",
  "archive": {
    "file_count": 30,
    "bytes": 225268944,
    "retry_count": 0,
    "pending": 0,
    "scratch_retained": true
  }
}
```

## 代码与验证

身份运行基于起点 HEAD 加逐文件 SHA 锁定的本次适配代码；`NATIVE_FREEZE.json`/`RUN_INPUTS.json` 保留运行源码、原始输入和缓存哈希。最终冻结复核见运行根 `FINAL_CHECK.json`：两禁止改动源码逐字节不变、v2.1 三序列表和 figures/v21 RENDER_MANIFEST 哈希不变、AGENTS 仅两处插入、handoff 仅追加一行。

原有两组 EXT05/PHASE5 测试加新增适配、评估接口和 registry 测试：`51 passed in 1.20s`。新增测试包含关闭变体时参数逐字段相等、默认两方法合成 native 文件字节、NAV 窗口和 base_time、噪声公式/q 互验、三轴标度位置、gap 未实现接口、评估 argv 省略 STD、registry trace 路由。合成测试仅为代码验证，不进入真实数据表。

`git diff --exit-code -- src/legsa_gins/paper_rebuild/horizontal_literature/{phase5_runner.py,ext05_pavlasek.py}` 返回 0、输出为空。native 仅默认 BY2 对；共享参数求解与全部外部评估接口均未执行。

## 待人决定

1. H-EXT-02 的 gap 机制：不得将 provider 丢弃无效 dt 与求解器保持状态混为一谈；当前 `mirror_legsa_drop` 仅接口并显式抛出 NotImplementedError。
2. BY2O pAcc 膨胀历元是否标注；52 个 HPPOSECEF 超阈值与 57 个 status float 必须分别命名。
3. 确认 observed expected 计数与起始 HP/RAWX 覆盖差；计数不构成下一阶段执行授权。
4. 审批 DRAFT：新增 native 10、评估器 20；文献/S 两版三序列同时报告，按 BY2 C00 v3 yaw 规则统一正文版本，另一版完整进入补充材料。

## 附录：簿记裁定

- 最新 H-EXT 指令是独立外部对比授权；C-CLOSE 原文、v2.1 科学产物与 figures/v21 保持冻结。
- CLEAN5 44 行锁只有 BY2H/BY2O。BY2 通过同一个 registry/local 解析器，使用 calibrated contract 早已冻结的原 BY2 raw 锁；未改写任何锁，未把 trace 加入验证。
- 两接收机的期望 HP−RAWX 计数差决定唯一前缀长度（BY2=1、H/O=0），替代原 BY2 字面量 `[1:]` 守门；+2 ms、200 ms、严格同 iTOW 与数值解码不变，未做 timing search。
- A1 审计采用闭区间 66–340，共 1371 历元；LegSA provider 既有 start-exclusive 运行选择为 1370，单独报告，未调整窗口。
- 跟踪审计 CSV 的 CRLF 仅规范为 LF，以通过 git diff --check；单元格文本和数值未改变。
- 任务指定的所有 probe 问题采用 fail-soft；只有原测试失败与实际字节身份不等触发硬停。
- `stat -f` 的 ext2/ext3 类名不能区分 ext4；以 findmnt FSTYPE=ext4 记录 scratch。
- 默认参数身份成功也不代表 H/O 求解、变体性能或论文准入；草案授权仍待人决定。
