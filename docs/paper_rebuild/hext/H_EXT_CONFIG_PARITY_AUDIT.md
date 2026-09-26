# H-EXT-01 配置对等审计

状态：`READ_ONLY_AUDIT_COMPLETE`。本表审计配置、原始观测及已冻结的指定证据；不产生新的性能评估。路径由 local YAML 与 sequence registry 解析。审计进程 strace 实测 reference-trace opens=0、solver=0、evaluator=0；三条 trace 均未打开、未哈希。

LegSA 参数指 v2.1 继承的标定链。A10 采用指定的冻结 BY2H V2s/CAL 原运行；A11/A12 采用 P-07 原横向 v3 行，均不冒充 v2.1 新结果。CSV 展开完整来源路径；下表来源短码在文末逐一展开。

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

## A1/A2 逐历元证据

两个实际入口为`clean5_parity.input_audit.decode_receiver`和`shared_raw_backend.reconstruct_ubx_stream(decode_nav_hpposecef_semantics=True)`，共同调用HPPOSECEF decoder。ECEF比较发生在LLA转换/输出舍入之前，不是算法输出比较。LegSA周值来自status，LC01来自RAWX，均2408；RAWX闰秒集合[18]与LegSA固定18一致。闭窗包含66和340端点，共1371；运行时start-exclusive则为1370。

每历元证据：`<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/00_CONFIG_AUDIT/A1_A2_BY2_EPOCH_COMPARISON.csv`。GNSS1原始SHA-256 `5d2ac46d28c14470cd8b2c910d8cba12492bed0e72517e98496188851f5bc027`，27,874,623 bytes；status SHA-256 `9761d2d7055356857bd7b26a251fdd60fdf6c2b18a882dac74bc35d164e42e08`。

| 比较口径 | pAcc/hAcc | pAcc/vAcc |
| --- | --- | --- |
| 逐历元比值中位数 | 1.3333333333333335 | 1.5333333333333332 |
| 逐历元比值P95 | 1.792857142857143 | 1.7500000000000002 |
| 两个中位数之比 | 1.357142857142857 | 1.5833333333333333 |
| 两个P95之比 | 1.590625 | 1.2119047619047618 |

pAcc单位0.1 mm，乘1e−4得到m；NAV-PVT hAcc/vAcc单位mm，乘1e−3得到m。上述是std比；相应方差比再平方。LC01堆叠绝对/相对位置的−R1交叉块是方法特有结构，本任务不改。

## A6 标度施加约定

`IM:98–101`取当前原始帧，先FLU→FRD，再安装旋转，保存未舍入`_current_specific_force_frd`。`IM:50–57`三轴同乘s，再乘原始测得的相邻dt，最后沿用`.12g`中间值、时间`.6f`与增量`.8f`序列化；`IM:60–70`验证时间和gyro token不变。LC01输入已是安装后的FRD角速率/比力；共享标度接口在该比力向量上、传播前施加同一s，不授权改变LC01采样或传播约定。

## A8 标定窗与BY2事件

| 项目 | 冻结记录 |
| --- | --- |
| used_preregistered_initial_interval | true |
| sample_count | 1031 |
| start/end UTC s | 1772784044.887078 / 1772784049.887078 |
| start/end relative s | 44.887078046798706 / 49.887078046798706 |
| gyro_norm_median_radps | 0.015289418986737115 |
| acceleration_norm_median_mps2 | 9.507909327281775 |
| mean_specific_force_frd_mps2 | [-0.13180068738317743,-0.14941227642414154,-9.506078096349812] |
| local_gravity_mps2 | 9.801554418645956 |
| max_internal_gap_seconds | 0.014250040054321289 |
| gyro_bias_frd_radps | [-0.0076655634452167005,-0.0026948138158392793,-0.0011093268712426007] |
| BY2蹬脚 | 合约下界62.579067 s（绝对1772784062.579067）；冻结事件记录62.57906699180603 s，见`docs/paper_rebuild/CLEAN5_SOLVER_RUN_RECORD.md:200` |
| BY2算法起点 | 66 s（绝对1772784066） |
| 窗口含蹬脚 | false；终点49.887078046798706早于蹬脚 |

C4 summary SHA-256：`466b99cb075e5dd7e2e93bb3a27e4ca8df4ffbbffd5bd81ec561e053bc614dea`。静态判据为gyro模中位<0.05 rad/s、accel模中位与局部g之差≤0.5 m/s²、maxgap≤max(0.1,5×全流中位dt)。通过该判据不使常量gyro均值与LegSA零偏状态成为同一设计。

## A10 BY2H冻结间断事实

输入`GAP`中的V2s bundle记录s=1.0308398903907543、63217行/63222原始帧/4个被丢弃dt。增量SHA-256 `d32e4891080e300e6edde4526146636f15ec54df945a0470c57fbbdc3aa5115c`；同一CAL A04运行的NAV SHA-256 `9da51135029a5f54fb1e387c5df8b20c6e364458731644239332ee5f36710b01`。bundle/run manifest的provider与NAV哈希吻合，元数据投影见`00_CONFIG_AUDIT/A10_FROZEN_LINEAGE.json`。

| 增量左/右行号（1起） | 左/右时间（相对base_time s） | 保留行时间差s | 冻结NAV事实 |
| --- | --- | --- | --- |
| 2677/2678 | 407.017058 → 413.041069 | 6.024010999999973 | 起点413之前无NAV；413.041069仅初始化；首NAV=413.047045，不能声称保持后续接或4.7 s传播 |
| 3007/3008 | 414.905067 → 415.081079 | 0.17601200000001427 | 两行NAV存在且状态不同；vD由−0.332394868变为1.214437677 m/s |

间断两侧增量（time,dtheta_xyz,dvel_xyz），从原文件数值直接读取：

```text
407.017058 -8.9e-07 2.209e-05 -1.052e-05 -0.00015581 -0.00064531 -0.01953954
413.041069 -0.0008024 0.00150449 0.00064846 -0.00072136 0.001436 -0.03357566
414.905067 -0.00012107 -0.00015155 0.00048608 -0.00109376 -0.00294075 -0.01949009
415.081079 0.00023702 -0.00022612 -0.00011646 0.0004978 0.00022049 -0.00560682
```

内部间断两侧NAV原数值（11列）：

```text
0.0 414.905067 39.984886192 116.343123538 41.432496659 1.072434351 -0.641533354 -0.332394868 -0.294065464 -1.835199364 334.206422856
0.0 415.081079 39.984887683 116.343123024 41.354679169 0.970011652 -0.394773587 1.214437677 -0.079701038 -1.672099491 334.579230431
```

源代码事实：`cpp/legsa_v23_port_core/src/fileio/imu_file_loader.cpp:36`重新以相邻保留时间差赋dt；同包`src/runtime/port_runtime.cpp:1405–1425`只用首个对齐IMU初始化、之后才输出；`src/kf_gins/gi_engine.cpp:308–309,322,787,822–824`及`src/kf_gins/insmech.cpp:28–60`使用dt做零偏补偿、机械编排和协方差传播。因此，预处理drop不等于滤波状态保持。所读冻结文件没有4.7 s保留增量步；原始流gap不可直接替代求解器保留行的步长。H-EXT-02需人决定外部gap机制；本任务不桥接、不补样、不重跑。

## A11/A12 P-07冻结支撑与体坐标偏差

以下数值来自PT及逐行的EVALUATION_RESULT.json，评估器未执行，reference trace未读。rows/s统一为output_epoch_count/(340−66)，不是配置500 Hz，也不是1/median(dt)。偏差分量是forward/right/up。保留P-07标签避免将历史A04行称为v2.1行。

| P-07行 | output_epoch_count | matched_epoch_count | coverage_ratio | rows/s | forward bias m | right bias m | up bias m |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LegSA_frozen | 56642 | 56642 | 1.0 | 206.72262773722628 | -0.1892967839397054 | 0.005696757229381533 | -0.11056926388320787 |
| LegSA_V2S (A04) | 56642 | 56642 | 1.0 | 206.72262773722628 | 0.053416821197953226 | 0.0006421539635069319 | -0.006208178312822657 |
| LegSA_CAL (A04) | 56642 | 56642 | 1.0 | 206.72262773722628 | 0.04372705881946374 | -0.000542094477631014 | -0.017455246835187836 |
| LC01_EXT05A | 58014 | 58014 | 1.0 | 211.72992700729927 | 0.044245598415972275 | 0.00021692112054168795 | -0.03516772470078074 |
| EXT05C | 58014 | 58014 | 1.0 | 211.72992700729927 | 0.013471659270362939 | 0.003411556688292533 | -0.03635068399100266 |

A04主审计行是LegSA_CAL；其余两个A04身份也明列。PT SHA-256 `d91f53aaf855efc8c533a6f15a9c6c933e87bafb2bcc9bd169ba862163c82c01`。各JSON及可用NAV哈希在审计JSON内。LC01/EXT05C v3 NAV实数58014行，median(dt)=0.00400996208190918 s；原A04 NAV实数56642行，median(dt)=0.004013000000000488 s。各自coverage=1不证明相同输出支撑。

## 不作为双方共享参数的项

- sys_stamp约0.205 s问题属于旧status接收时间与观测时间区分；当前位置入口均为HPPOSECEF iTOW→UTC，不能再减0.205 s。Go2 offset仍为0。
- HV/RP是LegSA特有辅助观测；LC01/EXT05C没有对应更新，不得以共享参数为由增加该先验。
- v2.1 A1航向std 2.933193°只属于LegSA标量A1航向观测；LC01三维相对位置R来自pAcc，不能替换成该角度std。
- q报告轴名north/east/down；冻结代码把这个顺序直接写入IMU噪声三分量，没有旋转拟合。共享变体按冻结三分量顺序引用，各方法的过程噪声注入矩阵仍保持原实现。

## 来源短码与复核

- `CP` = `src/legsa_gins/paper_rebuild/clean5_parity/providers.py`。
- `CI` = `src/legsa_gins/paper_rebuild/clean5_parity/input_audit.py`。
- `EP` = `src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py`。
- `EF` = `src/legsa_gins/paper_rebuild/horizontal_literature/ext05_pavlasek.py`。
- `SB` = `src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py`。
- `PR` = `src/legsa_gins/paper_rebuild/horizontal_literature/phase5_runner.py`。
- `IM` = `src/legsa_gins/paper_rebuild/clean5_imu_parity/providers.py`。
- `IB` = `src/legsa_gins/input_generation/imu_txt_builder.py`。
- `SM` = `configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml`。
- `SC` = `configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml`。
- `PC` = `configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml`。
- `PE` = `src/legsa_gins/paper_rebuild/clean5_parity/evaluation.py`。
- `EC` = `src/legsa_gins/paper_rebuild/clean5_parity/external_completion.py`。
- `CE` = `configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml`。
- `PT` = `<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/HORIZONTAL_TABLE_V3.csv`。
- `C4` = `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/EXT05A_C00_NATIVE_SUMMARY.json`。
- `GAP` = `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS/BY2H/CALIBRATED_IMU.imu` 和 `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/03_CALIBRATED_RUNS/CLEAN5_CALIBRATED_BY2H_A04/KF_GINS_Navresult.nav`。

脚本`scripts/paper_rebuild/hext_config_audit.py`；实现`src/legsa_gins/paper_rebuild/hext/config_audit.py`。观察文件为`<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/00_CONFIG_AUDIT/CONFIG_AUDIT_OBSERVATIONS.json`；访问审计为同目录`CONFIG_AUDIT_ACCESS_AUDIT.json`、`CONFIG_AUDIT_OPENAT.strace`。外部证据保持untracked。

簿记附注：CLEAN5扩展锁44行只覆盖BY2H/BY2O；BY2由同一解析器显式回到其原始锁，未改锁。以实际V2s/NAV描述替代4.7 s预期属于事实记录，不改任何冻结产物。
