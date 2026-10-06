# 2026-01-05候选数据：完整流质量与可用性

本轮完整机器扫描8份机身txt，共981,565,440字节、49,718,334物理行、671,872个带时间戳消息块；原字节全部SHA256锁定。ZIP容器198,406,698字节，SHA256为`a12c5f05e1c89739f3c5cf3ab89e07a0b1d0a17858f1b119862d314ea46e3e39`，含8个记录目录、168个文件成员，未压缩总量912,569,335字节。没有全量解压，没有启动导航估计器、科学provider或评价器。

两组可以形成8个时间覆盖唯一对应的候选序列；不是预设xb/nmb与文件夹关系后截取。64个组合全部保留在`CANDIDATE_PAIRING_ALL64.csv`，仅8个有时间交集。这里确认的是采集时段对应，未确认精密时钟映射。

## 八段总表

接收机目录前缀统一为`vrtk2_a87c6e_2026-01-05-`、后缀`_minimal`；时间为UTC。重叠按机身stamp与GNSS1状态header原时间求交，不拟合偏移。

| 机身文件 | 接收机目录时间 | 机身帧数 | 实际平均捕获Hz | 时间重叠s | 双fixed有效HP配对/全部HP配对 | >100ms机身gap |
|---|---|---:|---:|---:|---:|---:|
| nmb1 | 11-16-59 | 93267 | 228.455 | 353.472 | 771/1830 | 0 |
| nmb2 | 11-25-11 | 81811 | 225.263 | 357.514 | 750/1805 | 0 |
| nmb3 | 11-32-27 | 81951 | 224.439 | 365.132 | 904/1916 | 0 |
| nmb4 | 11-39-50 | 78610 | 226.057 | 347.740 | 697/1780 | 0 |
| xb1 | 12-25-13 | 91753 | 231.908 | 395.640 | 0/2017 | 1 |
| xb2 | 12-33-29 | 84436 | 235.416 | 358.663 | 0/1882 | 1 |
| xb3 | 12-40-53 | 80306 | 231.803 | 346.436 | 0/1747 | 2 |
| xb4 | 12-49-30 | 79738 | 221.067 | 356.200 | 0/1781 | 0 |

fixed统计覆盖整个接收机记录，不冒充算法起点后的支持率。准入条件为同iTOW的HP两流、两台PVT均gpsFixOK且carrierSoln=2、HP invalidECEF位未置位；它是原V3输入规则的必要质量筛查，并不是已证明的实用精度。

## 机身流可以证明什么

8文件均为终端`script`捕获的`ros2 topic echo /sportmodestate`。所有已解析时间戳单调递增，无重复或倒退；中位dt约4.002ms，平均帧率221–235Hz。不能当成完整500Hz采集，不能按固定2ms填补缺失样本。4个大gap为xb1的197.954ms、xb2的168.003ms、xb3的199.980和221.983ms，完整位置见`BODY_GAPS.csv`；保留它们而非选择性删除。

7文件在末尾消息中被截断，只有nmb2的末次data消息完整并出现Ctrl-C。机器671,872个消息块包含这些末块；671,865个块具有所有预期长度字段。这不是671,865个独立、完整传感器采样的声明：例如nmb1末个加速度数值在字符中间截断，即便解析为有限浮点仍不能证明原消息完整；xb1末块只有stamp和部分quaternion。后续导入须按完整消息和真实时间准入，不能把末尾残片补齐。原文件不改写。

已出现的gyro/acc/rpy/SDK速度分量均为有限数值；观测到的加速度模长约0.20–34.47，SDK速度模长上限约1.45。四元数norm接近1；在所有完整q/rpy对中，wxyz按弧度计算与rpy的最大分量RMSE不超过4.97e-6rad，xyzw明显不一致。这支持内部序列顺序及角度单位解释，不是外部姿态精度验证。陀螺、加速度及速度的物理单位/坐标应结合采集接口确认；数值量级分别与rad/s、m/s²、m/s相容。惯性加速度包含重力响应，不能直接当去重力线加速度。

[官方Unitree IDL](https://github.com/unitreerobotics/unitree_sdk2/blob/63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36/include/unitree/idl/go2/SportModeState_.hpp#L31)定义position、velocity、imu_state及foot_*_body字段，但position/velocity没有frame_id、输出物理点或covariance元数据。不要把foot字段的body命名外推为SDK速度的实测body坐标证明。原provider对SDK速度采用的工程约定与新记录接口确认分开；SDK位置、速度、姿态不是独立真值。

加速度、姿态及SDK速度有连续重复值，逐字段次数全部保留在`BODY_FILE_PROFILE.json`。重复值可能来自发布/内部状态更新率不同，不能因时间戳变化就声称每行增加独立信息。首30s原始jerk候选仅作事件存在性诊断，未确定算法起点、offset或最优对齐，也未被解释为真实踢动事件。

## minimal包实物确有原始GNSS观测

16份GNSS raw完整流字节哈希均与既有原始登记相同。独立审计逐条验证29,558条RAWX及32,687条SFRBX的UBX class/id、声明长度、checksum和组长度，失败为0；RAWX含890,619条伪距/载波相位/Doppler字段，全部是实际非零有限值。RAWX全部message version1、GPSweek2400、leapS18、recStat1；无clkReset置位、倒退或重复原始epoch。SFRBX具有真实广播导航字，未在本轮解码星历或检验全部issue配套可用性。

[官方UBX接口描述§3.17.6–3.17.9](https://content.u-blox.com/sites/default/files/documents/u-blox-F9-HPG-1.32_InterfaceDescription_UBX-22008968.pdf)规定RAWX中的prMes单位m、cpMes为cycles、doMes为Hz，同时提供信号/lock/tracking质量。有限值不等于有效测量；prValid、cpValid与phase-std有效性分别统计在`ZIP_RAWX_FULL_FIELDS_PROFILE.json`。本轮不声称全部890,619条可进入同一求解器，也没有整数模糊度解算或Doppler定位。字段/格式与所引协议相容，MON-VER缺失使实际GNSS固件版本仍未建立。

原始双流的binary-exact week/rcvTow配对为0；描述性nearest配对的GNSS2−GNSS1局部时间大部分约−8ms，12:40段后期约−7ms，11:25有两处缺配导致nearest相隔192ms。RAWX的rcvTow是接收机本地、近似GPS时间，不能把该−8ms直接认定为真实同步误差、传输延迟或测量采样差。HP/PVT的civil iTOW另有大量精确配对，两种时间身份不同。`RAWX_CLOCK_DIAGNOSTIC.json`保留全部nearest差，不校正相位、不拟合钟差、不选择改善RMSE的容差。原始相位/SD/DD后续研究必须先声明异步和clock处理合同。

后四段两台PVT fixed解均为0，但依然有大量prValid/cpValid及Doppler观测。这些数据可能有价值地检验自然GNSS困难条件与航向不可用性；不能临时改BOTH_FIXED为float以取得好看的航向成绩。若原方法初始化需要A1，这四段的初始绝对航向资格也需事前声明，不能暗用商业融合yaw补上。前四段有fixed支持，但仍有no-fix段；nmb4即使双fixed筛查后基线长度P01约0.259m、中位约0.351m，也说明fixed标签不等于独立精度保证。

## 实际输出点与模式的新证据

8份userio-raw中共5,910条FP_A-TF2均通过ASCII XOR checksum，其中2,955条POI,VRTK变换全部为平移0、四元数[1,0,0,0]。实际记录因此支持八段的配置输出POI与VRTK同点同向，[官方TF说明](https://docs.fixposition.com/fd/fp_a-tf)区分POI与VRTK；这里依据真实消息而非教程默认值。`RECORDED_FP_TF_SUMMARY.csv`给出全部16个edge摘要及原userio流SHA。

tf_static每段仅有ENU/VISION、BODY/CAM、ECEF/ENU；tf.csv仅有ENU/BODY动态edge。userio还记录相同VRTK/CAM常量变换。没有实际GNSS1/2天线→VRTK、Go2 IMU→VRTK的实测变换，且ROS的BODY标签不能直接等同机器狗IMU。POI身份关闭只适用于本8段，不回贴原BY2/H/O；CAD和作者结构说明可支持名义连接，尚不构成外参不确定度的独立标定。

ODOMETRY记录的message schema为2，不是已识别的Fixposition软件版本；GNSS MON-VER=0，userio没有FP_A-TEXT版本公告，相关status/ntrip元数据未提供固件版本字段。融合状态分布保存在`RECORDED_OUTPUT_STATUS_AND_VERSION.json`；8段init_status全2、fusion_cam1全1、fusion_ws全0，按[官方ODOMSTATUS定义](https://docs.fixposition.com/fd/fp_a-odomstatus)分别为globally initialized、camera used、wheel speed not used，GNSS与IMU状态仍有退化/未使用时段。可据此将参考称为商业视觉–惯性–GNSS融合输出，不称为独立纯GNSS真值或无误差真值；本轮没有用其数值对时。

## 与原V3和研究历史的关系

9980行原始锁定登记中，8txt与16GNSS raw全部24/24命中XB_PG既有hash；ZIP容器本身未登记。候选日期2026-01-05与原V3的2026-03-06三流不同，formal GNSS源hash不重合。它们是“尚未纳入本轮正式V3矩阵的候选记录”，不是新收到就自动变成从未接触的盲测。历史目录还有处理结果/Excel成员，不能仅凭存在推断用于调参，也不能否认它们曾被处理。是否进入过参数/方法/坐标/起点选择，应由具体运行、历史日志与作者说明确定。

建议当前写：“Eight additional archived acquisition pairs were identified for prospective evaluation under the frozen numerical parameter model. Their raw-observation and timestamp coverage has been profiled; no new estimator performance is reported here.” 在执行前把所有八段及支持资格预注册，保留无A1/失败/不可用记录。若希望证明独立新地点泛化，还需要真实场景、采集与开发使用历史；不由xb/nmb名称或月份推断。

## 对时不能只等于裁切

作者说使用接收机位置/速度与机身IMU共同启动动作；没有使用Fixposition融合轨迹。共同事件可辅助约束时钟偏移，但动作响应也受PVT滤波和消息延迟影响。必须区分：

- 事件配对：哪个原始动作对应哪个接收机/IMU特征；目前作者提供操作描述，尚无每段事件账本。
- Epoch裁切：选`t0`和评价窗；只能决定范围，本身不识别时钟。
- 时钟映射：`t_G = a + b t_B`中a为offset、b为clock rate；单事件不能独立确定b。
- 延迟：接收、测量和算法时间之间的传输/滤波延迟，与a不能凭单个事件完全分开。

前后stamp接近且无倒退并不能量化这些误差。需要记录原始事件索引、每段映射、漂移/延迟假设及不确定度；不按参考RMSE优化offset或算法起点。现有绝对stamp只用于候选配对，不宣告精密同步完成。

## 阅读与执行范围

原始txt全文是机器流解析/字段统计，不冒充49,718,334行逐字人工审读。ZIP只全流读必要GNSS、接收机IMU、status、TF和userio消息身份/TF元数据，其它成员列入目录而未作语义阅读；未提取原始大包。初步格式检查曾查看首段trace前1800字节和POI odometry首行字段，未计算参考误差或用于对时。userio全流含融合odometry字节，审计仅统计消息名/TF元数据，没有解码其位置姿态作算法依据。一次初始EOF glob额外预览了同目录两份旧KF文本末512字节，随后限定到8个明确文件；这些旧数值没有进入配对、质量统计或新成绩。外层读取范围如实列在`CANDIDATE_READ_COVERAGE.csv`，不是科学估计器的在线访问审计。

本轮原始数据、原V3源码、配置、结果与冻结指标均未写；新科学实验和评价调用均为0。新数据下一步需要的合同见`CANDIDATE_USABILITY_MATRIX.csv`及`03_TIME_ALIGNMENT_AND_NEXT_EVIDENCE.md`。
