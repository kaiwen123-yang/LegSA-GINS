# XB_PG 2026-01-05 四段数据审查

结论：四段原始数据和四个Go2高层日志已完成全文件流式扫描，88个文件逐项有SHA256、字节数、消息/记录数和损坏原因。它们适合严重GNSS退化下的原始观测与现有GNSS原生算法探索，**目前不能支撑完整F04迁移**。四段双fixed全部为0，且Go2安装/时钟与评价点的身份尚未闭合。可执行的receiver-only RTKLIB/RD由本轮探索协议约束，实际调用与结果见 RUNS.csv/METRICS.csv；本报告不把输入质量统计充当算法性能。

## 1. 分段裁决与完整分母

| 段/目录时间 | 唯一重叠Go2 | GNSS RAWX时长/s | 相交时长/s | Go2完整消息 | 同iTOW双HP位置 | 双fixed | 双HP差长度中位/m |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 / 12-25-13 | xb1 | 405.200 | 395.636 | 91752 | 2017 | 0 | 11.260 |
| S2 / 12-33-29 | xb2 | 376.200 | 358.659 | 84435 | 1882 | 0 | 14.095 |
| S3 / 12-40-53 | xb3 | 351.399 | 346.431 | 80305 | 1747 | 0 | 14.935 |
| S4 / 12-49-30 | xb4 | 356.000 | 356.000 | 79737 | 1781 | 0 | 35.175 |

S1–S4对应原始目录后缀12-25-13、12-33-29、12-40-53、12-49-30；本机路径只经ignored local config解析。16项交集全部保存于 SEQUENCE_PAIRING.csv，12个非对角项为零，配对由绝对时轴计算而非文件顺序推定。交集不等于已验证的硬件同步。四段来自同日，不是四个独立场地/设备试验；既有导出Excel及解析脚本表明数据曾被处理，参数/安装/方法是否曾据此选择仍UNKNOWN，不能命名盲测。

逐模块裁决见 INPUT_SUPPORT.csv（每段10项）。位置、RV、RAWX/SFRBX和Go2字段实际存在；尚未适配、物理身份不明、算法失败、参考限制分别登记。F01卡在Go2时间/安装和APC杆臂；F02/F03/A04/F04还缺合法双航向观测。不会把删减组合保留F04名称。

## 2. 全量解析与异常

CSV用Python csv规则恢复引号和多行cell；bytes只用ast.literal_eval并验证类型。按帧字节识别协议，不信任name列作为消息类型证据；UBX检查sync、payload长和双累加校验，RTCM检查长度与CRC24Q，NMEA/FP_A检查XOR，NOV_B检查header/payload及CRC32。八条GNSS UBX流保持所有原记录顺序、保留全部星历历史，未按参考/输出窗口裁剪。userio的NOV_B-INSPVAX单列为商业融合参考，不进入GNSS UBX。

每个Go2日志逐行处理ANSI/OSC、CRLF、退格，按stamp与---分块。固定数值schema明确拒绝重复键、坏维度、非有限数及残缺块；不使用eval，不补零，不排序/插值/重采样原始消息。四元数按wxyz重建ZYX RPY，与原rpy全量最大差均小于3.3e-7 rad；这是表示一致性验证，不证明姿态独立精度。

| 源 | 坏块/记录 | 行 | 拒收原因 |
| --- | --- | --- | --- |
| xb1 | 91753 | 6789655–6789661 | missing_or_bad_dimension:imu_state.quaternion |
| xb2 | 84436 | 6248197–6248228 | missing_or_bad_dimension:velocity |
| xb3 | 80306 | 5942577–5942625 | non_yaml_line |
| xb4 | 79738 | 5900545–5900602 | missing_or_bad_dimension:foot_position_body |
| S1 GNSS2 | CSV 26305 | 26305 | truncated_ubx_payload |

所有其余源的CSV列数/时间解析与帧校验无报错。Excel通过ZIP/XML逐sheet逐row扫描（每段两表分别408/379/354/358行，含标题），来源/加工公式身份未闭合，未用于输入或评价。ntrip-info及user_io-status只输出白名单计数/身份，网络/账号/设备文本不进入Git。完整payload和逐历元cache仅在 <AUDIT_ROOT>/data_audit/。

## 3. Go2实际采样与数据角色

| 日志 | 完整消息=唯一stamp | 平均Hz | dt P50/ms | dt P95/ms | 最大缺口/ms | gyro相邻相同 | acc相邻相同 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| xb1 | 91752 | 231.908 | 4.0027 | 6.1170 | 197.954 | 2.466% | 24.195% |
| xb2 | 84435 | 235.416 | 4.0014 | 6.0588 | 168.003 | 2.492% | 24.752% |
| xb3 | 80305 | 231.804 | 4.0020 | 6.0721 | 221.983 | 2.163% | 23.725% |
| xb4 | 79737 | 221.068 | 4.0049 | 6.8170 | 28.094 | 1.703% | 20.895% |

四日志的stamp重复和乱序均为0；每条被接纳消息的下列字段均完整且数值有限。边界坏块分别计入拒收分母，未将其清洗成完整消息。约2ms局部间隔不能推成500Hz独立IMU；真实平均速率与缓存重复必须同时考虑。

| 字段 | 维度 | 单位/坐标证据 | 允许角色 |
| --- | --- | --- | --- |
| imu_state.quaternion / rpy | 4 / 3 | wxyz / rad；全量重建互验；世界yaw基准未认证 | 弱姿态/状态诊断 |
| gyroscope / accelerometer | 3 / 3 | SDK惯例rad/s、m/s²；与body刚性安装仍待绑定 | 候选传播IMU，不能替代安装/时间证明 |
| velocity / position | 3 / 3 | m/s / m；捕获SDK精确world/body契约未知 | 弱先验/诊断，不是真值 |
| foot_force | 4 | 设备估计接触力；不是独立接触真值 | contact诊断 |
| foot_position_body / foot_speed_body | 12 / 12 | 官方示例标body frame、relative to body；m与m/s | 足端诊断，非关节编码器FK |
| mode / gait_type / error_code | 1 / 1 / 1 | 离散代码；四段gait=1、error=0 | 状态质量标记，不证明运动模型正确 |

| 日志 | roll范围/deg | pitch范围/deg | 内部速度模中位/m/s | P95/m/s | 内部速度模<0.1比例 |
| --- | --- | --- | --- | --- | --- |
| xb1 | -9.17..7.39 | -9.82..4.45 | 1.006 | 1.162 | 10.60% |
| xb2 | -6.25..5.81 | -11.08..4.38 | 1.088 | 1.220 | 9.42% |
| xb3 | -4.59..6.16 | -3.25..3.61 | 1.083 | 1.214 | 7.94% |
| xb4 | -5.44..8.30 | -3.53..7.37 | 1.062 | 1.229 | 11.91% |

速度和RP范围只描述机器人内部状态；<0.1 m/s是描述性静止代理，未用于选择运行窗/调参，不能称独立静止真值。四段yaw穿越±180°，后续任何插值和误差必须圆周处理。没有关节编码器、低层motor_state、独立FK或已验证的足速导数定义。

## 4. GNSS完整消息与物理语义

| 源 | RAWX | SFRBX | HPPOSECEF | PVT | RELPOSNED | PVT gnssFixOK | pAcc P50/m | pAcc P95/m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1/G1 | 2027 | 1107 | 2027 | 2027 | 2027 | 1790 | 1.585 | 70.374 |
| S1/G2 | 2027 | 1270 | 2017 | 2017 | 2017 | 1851 | 1.163 | 22.750 |
| S2/G1 | 1882 | 963 | 1882 | 1882 | 1882 | 1691 | 1.893 | 45.519 |
| S2/G2 | 1882 | 1229 | 1882 | 1882 | 1882 | 1800 | 1.171 | 15.678 |
| S3/G1 | 1758 | 889 | 1757 | 1757 | 1757 | 1591 | 2.023 | 38.847 |
| S3/G2 | 1758 | 1323 | 1751 | 1751 | 1751 | 1623 | 1.038 | 21.215 |
| S4/G1 | 1781 | 950 | 1781 | 1781 | 1781 | 1613 | 2.083 | 41.439 |
| S4/G2 | 1781 | 1370 | 1781 | 1781 | 1781 | 1717 | 1.000 | 15.430 |

NAV-PVT fixType只出现0或3，carrier solution只出现0或1，fixed=2不存在。generic status fix_type是另一枚举（实见1/5/7），不映射成NAV-PVT的carrier位。invalidEcef=false仅表示HP数值有效，不等于RTK固定或亚米误差。pAcc来自0.1mm整数缩放，是接收机自报精度量，未拆成三个相互独立轴的σ。

HPPOSECEF的cm整值加signed 0.1mm高精度增量，GNSS2−GNSS1用相同iTOW作ECEF差；范数与任何正交局部坐标变换不变。四段长度P95分别75.821/62.716/108.295/64.295m，全部差向量的最小长度仍为1.167/5.760/3.211/12.021m。这是观测间不一致，不能拿其中最佳窗口反推出安装或航向偏置。双fixed连续时长四段全部0s。

两机RELPOSNED的refStation相对量length中位在2925–2943m，isMoving全false；status rel_pos的量级与之相符。文档定义和字段量级共同反证“它就是机载短基线”。RAWX含GPS/SBAS/Galileo/BeiDou/QZSS/GLONASS信号、Doppler Hz、载波频率ID、C/N0、锁定/有效位；SFRBX存在不自动保证相应星历可解或整个时窗可用。完整流留给既有native RTKLIB及RD helper验证星历覆盖、卫星状态与钟差，不能把PVT velocity冒充RD。

## 5. 时间、几何、IMU身份

GPST由RAWX week=2400、leapS=18（leapSec有效位已检查）和rcvTow转换为整数Unix ns；PVT/HP的iTOW单列，不将到达Time充当测量时间。S1/S2两机RAWX标签恒差8ms，S3从8ms变为7ms，S4为7ms；没有把它们平移到吻合。文件名12点、终端Script started的20点+08:00在时区语义上可相容，但终端开始不是传感器首历元，也没有将8小时施加给stamp。

RAWX到达减measurement：G1中位约55–58ms，G2约64–67ms，完整P01/P95/极值在S*.json。status同时保留header、sys_stamp及到达Time的差分布。Go2终端没有每消息独立到达时间，stamp是否是设备采样/ROS发布/系统时刻未获采集实现证明；目前只能确认绝对时间范围一一重叠，不能估拟合延时进入试跑。

tf_static完整3边为ENU→VISION、BODY→CAM、ECEF→ENU；动态tf只描述设备导航帧链。完整userio的FP_A-TF另证四段POI→VRTK均零平移、wxyz单位四元数，VRTK→CAM固定[0.04260,0.00517,-0.01699]m。它们没有Go2 body/IMU或GNSS APC，不能把名为BODY的内部帧自动当Go2机体。

同日旧审查的frame_registry/config确实载有GNSS1右/2左、0.35m及APC [0.02,±0.175,-0.02]m，但该配置明确绑定11-16-59与nmb1；没有本四段mount_session连续性证明。该线索仅用于安装provenance，不作新性能证据，亦未读取/采用其旧性能结果。BY2的−1°安装、[.03,.03,−.30]m杆臂未迁移。

imu-data.csv的frame_id=imu，约200Hz，来自Fixposition记录集合且与其姿态/IMU输出相容；没有证据把它识别成Go2 body IMU。按项目数据角色，它始终只作接收机内部传感器诊断，传播候选来自独立的Go2日志，未把二者混合/重复融合。其具体导出producer版本与bias-corrected/raw性质尚未有采集版本证明，标UNVERIFIED。

## 6. 商业参考资格与可复用转换

trace六个非processed字段逐行复现poi_geodetic，数值差最大5.7e-14；trace Time与该源到达Time差≤0.5µs。processed_lat/lon反置且嵌套，并非另一个更准确参考。poi原header所有测量时间恰重复两次，重复行位置/姿态完全相同；四段唯一历元4057/3766/3516/3564，10Hz。若以后评价，应在独立版本转换中保留第一条完全相同重复、记录原两行索引，且使用header测量时轴。此规则由原始字段一致性建立，未看算法误差后挑选。

原userio中NOV_B-INSPVAX已全量CRC32验证：4053/3763/3514/3562条；与poi header精确匹配的4052/3762/3513/3560条lat/lon/height数值完全相同。其ins_status=3，time_status=180；position type实际有0/16/34，说明GNSS质量/融合状态仍须逐历元报告，不能把连续商业输出称为连续独立真值。官方说明INSPVAX与FP_A-ODOMETRY表达同一融合结果，POI点由输出配置定义；本四段raw TF证明POI=VRTK设备点，但GNSS APC到该点及Go2到该点仍缺。

poi_smooth_odometry与非平滑odometry不同产品，不能按误差较小者选用。厂商说明平滑输出在GNSS修正时可持续漂移，并可能重初始化；它没有独立真值资格。Excel两表只作为已处理数据线索，没有可追溯生成代码/完整公式证明时不选作参考。

## 7. 复现入口、证据与边界

```bash
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 scripts/paper_rebuild/audit_xbpg/data_scan.py --local-config configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml --part all
PYTHONPATH=src python3 scripts/paper_rebuild/audit_xbpg/data_summary.py --local-config configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml
PYTHONPATH=src python3 scripts/paper_rebuild/audit_xbpg/data_report.py --local-config configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml
PYTHONPATH=src python3 -m pytest -q tests/paper_rebuild/audit_xbpg/test_data_scan.py
```

本轮解析单元测试16项通过，覆盖负数/科学计数、ns精度、维度/重复键/NaN/缩进、终端控制、尾截断、禁止eval、UBX checksum/长度、有符号HP/flags字节、PVT carrier位、RAWX numMeas、NOV_B CRC和乱序重复统计。合成测试仅进测试代码，不混入REAL_RAW数据表。解析不是原生滤波器验收；原生运行由总报告单列。首轮GNSS扫描曾因本机缺openpyxl停止，已用标准库XML实现修正后完整重扫；该技术失败未导致原始文件变更。

DATA_COVERAGE.csv为88文件身份与读取深度；DATA_QUALITY.csv为88源统计；SEQUENCE_PAIRING.csv为4×4交集；INPUT_SUPPORT.csv为40模块裁决；DATA_FINDINGS.csv为11项证据裁定。每个S*.json含逐字段数量/分位数、每消息协议数量、坏记录位置；xb*.json含全部Go2字段维度/重复/变化统计。完整缓存和UBX在 <AUDIT_ROOT>/data_audit/decoded/，不上传Git。没有删除raw、改变冻结provider/solver/config、运行旧矩阵、用参考选安装/时差，亦未创建ZIP。

实现关键组：data_scan.py 的parse_go2_block负责数值语法/维度与精确stamp；scan_go2负责有损边界记账；ubx_frames/decode_ubx负责校验与原单位；decode_novb只恢复reference lineage；scan_raw保存按输入顺序有效UBX；scan_csv区分测量/系统/到达时刻及敏感文本；scan_xlsx扫描内部XML；data_summary.py只从观察缓存算配对/基线与源间一致性，不导入求解器、评估器或旧provider。它们是本轮新适配，不替换正式算法。

仍未闭合：Go2采集SDK/时钟同步版本、四段mount/APC杆臂与body yaw初始基准、receiver IMU导出producer与bias语义、旧Excel生成身份、数据是否参与过参数选择。解决前不报告F04优势或完整论文复现；receiver-only原生探索和输入诊断可继续。

## 原始技术来源

- [Unitree SportModeState官方消息](https://github.com/unitreerobotics/unitree_ros2/blob/master/cyclonedds_ws/src/unitree/unitree_go/msg/SportModeState.msg)：字段及维度；[官方读取示例](https://github.com/unitreerobotics/unitree_ros2/blob/master/example/src/src/read_motion_state.cpp)：足端坐标相对body。当前master不等于已定位2026-01-05采集版本。
- [Unitree官方部署代码](https://github.com/unitreerobotics/unitree_rl_gym/blob/main/deploy/deploy_real/deploy_real.py)标IMU wxyz；本轮独立全量rpy重建互验其表示，不用网站说明替代本机数值检查。
- [Fixposition官方UBX协议结构](https://github.com/fixposition/fixposition-sdk/blob/main/fpsdk_common/include/fpsdk_common/parser/ubx.hpp)：PVT/RELPOSNED flags与单位；其原始u-blox接口文档链接保留在文件头。
- [Fixposition INSPVAX](https://docs.fixposition.com/fd/nov_b-inspvax)、[官方Integration Manual](https://docs.fixposition.com/__attachments/185991190/VRTK2_integration_manual_v2.1.2.pdf)：融合来源、字段offset/单位、POI。
- [NovAtel CRC32定义](https://docs.novatel.com/OEM7/Content/Messages/32_Bit_CRC.htm)：初值0与polynomial 0xEDB88320；本轮按帧验证。
- [Fixposition平滑输出说明](https://docs.fixposition.com/fd/what-is-the-smooth-odometry-output)：平滑轨迹连续不等于绝对无漂移。
