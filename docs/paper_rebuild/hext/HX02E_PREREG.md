# HX-02E 官方 Hartley InEKF 三序列预注册

状态：真实序列尚未执行；身份示例与驱动合成检查已通过。起点 ac2d9e4e7b2f69cc8c27a930d32b5854d3fe5317，git pull --rebase 已完成。当前任务授权覆盖此次新增官方比较，不改写已有阶段。

路径变量沿用任务定义：W、V3、STAGES、HX02、HX02E、SCRATCH、EXTERNAL。EXTERNAL 由 $W/configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml:hx02_external_root 解析；新运行暂存 $SCRATCH/HX02E，结果逐文件核验后归档 $HX02E，结束清空 scratch，不做交接包，不向 E: 直接写文件。

方法与决策：RossHartley/invariant-ekf@ef16e8a1df72f9272111a488880e3fe9d161f59f，一行不改，不联网获取、更新或打补丁。引用 Hartley et al. RSS 2018，doi 10.15607/RSS.2018.XIV.050；IJRR 2020，doi 10.1177/0278364919894385。此代码是作者公开的早期实现；选择论文参数不将其改称为完整 IJRR 解析离散化实现。无数值门槛：OFF-LIT 与 OFF-DEF 均作为论文“四足状态估计”类对比配置，结果好坏和失败均保留；HX-02 移植行及 HX-02D 诊断退至补充材料，不修改其原文件。

## 输入、帧与运行清单

使用 HX-02 的 H5_INPUT_CACHE.bin，不重新生成检测器，不读参考选参数。IMU 为 FLU 角速度和比力；缓存中已经有绕 X 的 −1° 安装修正，按存储值直接传入，不再次修正，不转换为 FRD。官方世界 z 向上，g=[0,0,−9.81] m/s²（src/InEKF.cpp:43–52）。缓存每记录含时间、gyro、accel、足力、足位置与接触标志；足序 FL/FR/RL/RR，足位置取 foot_position_body。

每个 Kinematics 的平移为足相对机体位置，旋转为单位阵。官方库不含接触检测，Cassie 示例的接触来自其控制器，本平台日志无控制器接触标志，故用足力阈值。控制器来源说明沿用任务给定信息；代码可核实 gen_data_file.m:49–61 读取 contact.Data、kinematics.cpp:104–118 调用 setContacts，而不从足力计算接触。Go2 检测沿用 HX-02 缓存：on FR/FL/RR/RL=34.2/33.8/30.6/32.0，off=24.8/25.2/23.4/24.0，登记最短驻留 0.012035608291625977 s；该秒数由三样本时长来源登记；实际实现按候选状态持续秒数比较（hartley_h5.py:296–332），不是简单计数三个样本；本次直接复用缓存标志。出处：HARTLEY_PARAMETER_SOURCE_REGISTRY.csv:48–50，hartley_h5.py:stream_h5_prefix，缓存清单。

| 序列/起点标签 | 评分窗 s | b_med m | 缓存 SHA256 |
|---|---|---|---|
| BY2 C00 | [66.0, 340.0] | 0.356191491865984 | c169e26d66f35fe200bb17a695353cd2d751482df1cd97996a7a8afff8662065 |
| BY2H CONTRACT_START | [413.0, 683.0] | 0.35418777593777223 | 732d45c70815ba65c7832ecbfb41edf5c571fd4e80fb13df497a99fe9863436e |
| BY2O FILE_START | [3186.0, 3563.0] | 0.35013463864843675 | 8786456127571475e88a89a47ab30f118b09a789e521690b82170985e4aaec35 |

运行顺序固定为 BY2 OFF-LIT、BY2 OFF-DEF、BY2H OFF-LIT、BY2H OFF-DEF、BY2O OFF-LIT、BY2O OFF-DEF。预算为真实序列原生 6 次、相对位姿评估至多 6 次；输出可用时每支一次。LegSA 解算/评估均为 0。示例 2 次、驱动合成门 4 次单独计数，不混入真实序列计数。

初始化属于驱动选择：从首个保留缓存历元 t0 开始，取 [t0,t0+1 s) 比力均值；roll=atan2(fy,fz)，pitch=atan2(−fx,hypot(fy,fz))，R=Ry(pitch)Rx(roll)，yaw=0；速度、位置、陀螺与加速度零偏均为 0。不设静止门。BY2H 在合约 413 s 后首个可用记录运动中初始化，不向 413 s 外推，也不因运动推迟。实际 t0、记录数、初始化样本数写入执行记录。

每个后续历元用前一 IMU 样本和实际 dt 调用 Propagate，随后对当前四足调用 setContacts、CorrectKinematics；包括非接触足以触发官方移除逻辑。不对间隔做插值、子步或额外 dt 截断。

## 公开 API 与参数映射

所有库路径均相对 $EXTERNAL/hartley/invariant-ekf。薄驱动不复制、不重写库内传播、校正、接触增删或协方差更新数学。

| API | 头文件与行 |
|---|---|
| InEKF(RobotState, NoiseParams) | include/InEKF.h:80 |
| getState / getNoiseParams / getEstimatedContactPositions | include/InEKF.h:82 / 83 / 87 |
| setState / setContacts / Propagate / CorrectKinematics | include/InEKF.h:88 / 91 / 93 / 96 |
| Kinematics(int, Matrix4d, Matrix6d) | include/InEKF.h:33 |
| NoiseParams() | include/NoiseParams.h:24 |
| setGyroscopeNoise / setAccelerometerNoise | include/NoiseParams.h:26 / 30 |
| setGyroscopeBiasNoise / setAccelerometerBiasNoise / setContactNoise | include/NoiseParams.h:34 / 38 / 46 |
| RobotState() | include/RobotState.h:28 |
| setP / setRotation / setVelocity / setPosition | include/RobotState.h:53 / 55 / 56 / 57 |
| setGyroscopeBias / setAccelerometerBias | include/RobotState.h:58 / 59 |
| getTheta / getP / getRotation / getVelocity / getPosition | include/RobotState.h:41 / 42 / 43 / 44 / 45 |
| getGyroscopeBias / getAccelerometerBias / dimP | include/RobotState.h:46 / 47 / 50 |

以下噪声数值直接送入标量 std setter，由官方 setter 平方；不按结果或采样间隔重新缩放。OFF-LIT 来源为 $W/configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_PARAMETER_SOURCE_REGISTRY.csv:4–8，对应 IJRR Table 1；OFF-DEF 为官方接触示例 src/examples/kinematics.cpp:59–63。OFF-DEF 的 contact=0.01 是示例覆盖值，不能误写成 NoiseParams 构造器的 0.1。

| 参数/setter | OFF-LIT | OFF-DEF |
|---|---:|---:|
| gyro / setGyroscopeNoise | 0.002 | 0.01 |
| accel / setAccelerometerNoise | 0.04 | 0.1 |
| gyro bias / setGyroscopeBiasNoise | 0.001 | 0.00001 |
| accel bias / setAccelerometerBiasNoise | 0.001 | 0.0001 |
| contact / setContactNoise | 0.05 | 0.01 |

OFF-LIT 初始标准差为姿态 30°（转弧度后平方）、速度 1 m/s、IMU 位置 0.1 m、初始接触足各 0.1 m、gyro bias 0.005 rad/s、accel bias 0.05 m/s²（参数登记 CSV:10–16）。初始无接触状态通过 RobotState.setP 配置；首条量测由官方 CorrectKinematics 建立活动接触后，以 RobotState.setP 和 InEKF.setState 一次性设置含初始足的独立对角 P。此后不重置 P；新接触协方差由官方 src/InEKF.cpp:516–545 增广。论文左右足初始标准差映射到四个初始活动点足。无原始关节与 Jacobian，Table 1 编码器 1° 不另加入 FK 协方差。

OFF-DEF 不设置 P，保持 RobotState() 的 I15（src/RobotState.cpp:22–23；接触示例:39、57–66 未覆盖）；首个及后续接触协方差均由官方增广。两支均不使用 landmark 更新，默认 landmark noise 不参与结果。

运动学协方差采用 [旋转,平移] 排列：diag(10^6·I3 rad²,0.010²·I3 m²)，交叉项为零。旋转大值表示点足方向不约束；该官方版本实际仅读取平移块 covariance.block<3,3>(3,3)（src/InEKF.cpp:454、537），旋转块不会参与更新。OFF-LIT 的 FK std 来源为 HX-02 的 0.010 m 登记。

OFF-DEF 例外已获用户明确裁定：同样采用 0.010²·I，并披露为 Go2 平台输入配置。官方示例没有固定运动学默认矩阵：kinematics.cpp:138–140 逐条读取数据；gen_data_file.m:36、64–72 用 Cassie 的 0.5° 编码器协方差和逐历元 Jacobian 生成。这里不把 Go2 固定矩阵冒充官方示例默认值。裁定原文：“采用 0.010²·I，明确披露平台配置（推荐）”。

## NAV 与评估

每个输入 IMU 历元写一行 NAV，包含 timestamp_ns、世界位置/速度、roll/pitch/yaw（度），并保留原生旋转矩阵 r00…r22 及零偏。输出点为 Go2 body IMU 原点，世界 z 向上。直接复用 hx02_relative_pose_evaluation.py:read_hartley_nav、lever_flu、interpolate_estimate、branch_alignment、branch_metrics；不另写姿态转换公式。

FRD 杆臂 [0.03,0.03−0.5·b_med,−0.30] m 由原适配器变为 FLU，再按 p_mid=p+R·l_FLU 平移到天线中点。每支用自身输出在评分窗首 10 s 独立做 yaw + 三维平移对齐，之后不重拟合；不估计 roll、pitch、尺度或时差。10 Hz 闭窗网格，位置线性插值、姿态 SO(3) 插值，只在支持区间内评分，不外推。

参考仅通过未修改的 hext/hx02_evaluation_process.py 启动 REGISTERED_CHILDREN[RELATIVE_POSE]；每次 strace -f -yy 审计，恰好一次成功 O_RDONLY 打开对应 trace，同一批读取字节核 SHA256。控制器和原生程序不能打开 trace/bag/fpl；控制器只携带参考路径及登记哈希。控制器另有 Python 打开文件守卫与独立不跟随子进程的 strace，原生子进程单独完整审计。

每支报告位置漂移 m/100 m、航向漂移 °/min、对齐后水平/高程/yaw RMSE、最大水平误差、参考路程，以及 1/5/10 s 平移和 yaw RPE。定义完全沿用 HX-02；漂移为带截距 OLS，非终点百分比。

健全性仅报告：评分窗口内展开的原生 FLU/up-world yaw 增量减原始 Go2 gyro-z 左保持积分，OLS 对分钟的速率，不扣零偏；Go2 实测约 −4°/min 仅作背景，不设门槛。原始 gyro 从钉住 Go2 前缀只读解析并与缓存安装旋转后逐历元核对。原生位置路程在同一 10 Hz 支持网格算水平路程。参考分母 BY2=328.4713109046748 m、BY2O=337.4220465887643 m，直接取 HX-02；BY2H 取此次评估结果。输出来源字段逐值写入长表。

## 身份门、失败与硬停

官方构建按 README 的 CMake/make 流程。因官方 CMake 将 bin/lib 写入源码目录，构建使用 $SCRATCH/HX02E/BUILD/official 的逐文件相同副本，原仓库只读；禁用 CMake 用户包注册写入，TMPDIR 指向 scratch。官方所有受版本控制文件及构建副本逐项核 SHA256，库 HEAD 与 status 前后检查。驱动链接该副本构建出的官方 libinekf.so。编译不改任何源码。

官方 kinematics 与 landmarks 示例各运行一次，输出及 strace 位于 $HX02E/00_CONTROL/OFFICIAL_EXAMPLE。仓库无附带可比对的 C++ 预期输出，因此只记录输出哈希和执行情况，不宣称数值回归验收。若发现附带预期输出且不一致则硬停。

驱动合成门（无参考）分别覆盖两配置：静止 300 s、dt=0.004 s、四足固定接触，最大位置漂移 <0.05 m、最大 yaw 变化 <0.1°；绕 z 恒速 0.1 rad/s 持续 60 s，固定世界足点按已知输入姿态变到机体系，最大 yaw 对积分差 <0.1°。未通过立即硬停，不修复后重试。

已完成门结果：静止两支位置/yaw 均为 0；绕 z 最大 yaw 差 OFF-LIT=2.8421709430404007e−13°、OFF-DEF=1.4779288903810084e−12°。四项均通过，调用及输入输出哈希见 DRIVER_GATES/GATES.json；两个示例均 exit=0，六个门进程参考打开为 0（GATE_ACCESS_AUDITS.json）。landmarks 示例仅作为官方示例运行记录，不据此宣称真实 IMU 传播已验证。

真实运行失败规则：位移 >10000 m、速度 >50 m/s、高度位移 >1000 m 或非有限状态为 ALGORITHM_FAILURE_DIVERGED；返回 0 无输出为 NO_OUTPUT；非零异常退出、信号、600 s 超时为 ABNORMAL_EXIT。发散及失败仍保留原生输出、stderr、失败行；不调参、不重试、不删行。有可评估的有限前缀则报告其覆盖分母；无至少两个可用 NAV 历元则指标为空并记录评估未调用，不伪造“6 次评估”。

硬停：官方源码/HEAD/status 不符；示例预期输出不符；驱动合成门不通过；任何 LegSA 解算或评估；控制器/原生打开参考；65 pin 不一致；E: 可用 <40,000,000,000 bytes，G: <30,000,000,000 bytes，scratch >20,000,000,000 bytes。HX-02/HX-02D 或 423 项方法本体变化亦停止。硬停保留报告、提交并等待，不擅自续作。

65 pin 开始及每次提交前核对；开始与预注册提交前均为 65/65，其中 CSV 59/59。受保护起始清单为 HX-02 12678 文件、HX-02D 82 文件；既有 29 个未跟踪文件保持不动。结果提交前再次核对所有保护项。表格与代码生成不改变任何旧科学文件。

## 文件身份

未修改的官方全部 58 个受版本控制文件（包含数据和二进制附件）在 OFFICIAL_SOURCE_START.json:tracked_files 逐文件登记。下面列出全部 22 个源码/构建描述文件；原仓库、构建副本、任务结束原仓库均与此清单核对。路径相对官方仓库。

| 官方源码文件 | SHA256 |
|---|---|
| CMakeLists.txt | 9dcc3958db67ebb431744acf41d67f4af9eac9b463c7b1bdf45793e3211f8e97 |
| include/InEKF.h | d0bea67bdf1e7318383c6cfaf399ba01237b94e59a79427fdbf185eb74447efd |
| include/LieGroup.h | a09e370efc36f783cf895fcd4a6544e0c3ca4e87cc0d2cf51010799df3836b87 |
| include/NoiseParams.h | 99aa1298f4bb32c0744d9c02daafa7e29be64cddcb0f87e02998ce5af82038a3 |
| include/RobotState.h | b991ce7f6163e777b9e8cccf14f02c1cd3d987d75f914118d1587c42e30a9a53 |
| inekfConfig.cmake.in | 1d7830e482f8a0330f7f169c430f4800113a576093814360fefdf7cb0e6582a1 |
| src/InEKF.cpp | 15eb9856edd752c05886e92de731231dabfffdccf778dbd26b72635b9e562c92 |
| src/LieGroup.cpp | 1672833749105473271e28d31095eaeda58ea26452e0ba06c5244035d5125bb9 |
| src/NoiseParams.cpp | e75acc4cf2db08e159d039d6a7deb3bf719d9bdb7e24bf54708b4617624e043d |
| src/RobotState.cpp | 8ff619510d8576120935fdc2515bd8eb9b2ab8e6ff76d49040e69c1de5843b25 |
| src/examples/kinematics.cpp | 3e8b7a2f98bf7510f9f8da5a44c2b44579bb7660eee997ce17290a241e424dad |
| src/examples/landmarks.cpp | 053732da6944ecb3fd2a26110c3b8d2f83875d6b10e6f3d0a1dcc17845f51c1e |
| src/examples_matlab/GenIMUFromTraj.m | 704b70455b3a48b049bfa4e712e879d833193715bc613c0d5b00a8bfafe0c7c8 |
| src/examples_matlab/GenTrajFromIMU.m | a336831943a4eb8d530dc4b76c1a6868113e303bb26503477f6e6d25e9191e0a |
| src/examples_matlab/InEKF/RIEKF.m | bfa707481f2994e8d6e32faeace36973171dac5e7abf6fb9ff4eca301bd11675 |
| src/examples_matlab/InEKF/RIEKF_InitFcn.m | 3e4d2f2a28e8ad5059baf82a7f151d08b4a90cf1264836b1cff0464b408c3507 |
| src/examples_matlab/InEKF/Rotation_to_Euler.m | bc20a6521f783d04e7f1a35ea5212ea43a18ae5ae93962d9c5b224ca1e794bf9 |
| src/examples_matlab/InEKF/plot_results.m | f7ce461c9af9755a09a46de674210da706baae0d5d72be0c190a70d45066c1ae |
| src/examples_matlab/gen_data_file.m | 9341af18d368a3d6a9e869bbd9759e794ed432970da381b65b70a36d7544d0f1 |
| src/examples_matlab/run_RIEKF_test.m | d68dc7b702a9345bb02c06943e936b97c1abe01509c4939bccbd7f38ca379fc8 |
| src/tests/correction_speed.cpp | c7b7839e5d508585d422e217d46a79e3ee928f8908ca6d67ea997c72f769bdc1 |
| src/tests/propagation_speed.cpp | 66c1817efc39246ab42e3c8aa37f734de1f1e5043fc5795f2e5138121d7adafe |

驱动、构建、执行、测试、参数、复用适配器/评估器及合约身份如下，路径相对 $W。

| 文件 | SHA256 |
|---|---|
| scripts/paper_rebuild/hx02e_build.py | f3fe7405736d48e328b6aa45c84d2eb1149d6c01865f9252b84d637b7809ff68 |
| scripts/paper_rebuild/hx02e_execute.py | e4dbc1eaad3cfa1d664c823d27483db2a3df8d59cb3a726f758f692009f51740 |
| scripts/paper_rebuild/hx02e_report.py | c573ddc96ca872487675322e549118d0d70006ce9de10b7e0fa09dd88fb4a505 |
| src/legsa_gins/paper_rebuild/hext/hx02e_official_driver.cpp | 0be82d5f5ff271f55efba844df1b32a27cbd773f17b363f7b87d4e180aeff424 |
| tests/paper_rebuild/test_hx02e_official_driver.py | ca9cea58262b42f18c35c3b42d287d6d68234f251a57168f0c2ce3f4b6d8bacb |
| configs/paper_rebuild/hext/HX02E/OFF-LIT.cfg | 9579398d8d907b8fa1957fd6f779c1d41c7773bfecc0519b5f87678cdd77166b |
| configs/paper_rebuild/hext/HX02E/OFF-DEF.cfg | 7cb34c1db3e1152cc96bd923a0ddeb76d3201b7bdfd0dda5f22dd78a0caa3164 |
| src/legsa_gins/paper_rebuild/hext/hx02_evaluation_process.py | c94093d1fbf94c9f4db9f6f59334666ea8897c59bcd67654afd4a9914c7764fb |
| src/legsa_gins/paper_rebuild/hext/hx02_relative_pose_evaluation.py | d5a024d2218aeae3c1c24c211b170cabad7b4c730fd02b43c270fe2d6f1fa4d1 |
| src/legsa_gins/paper_rebuild/hext/hx02d_reference_free.py | 1bcfa0476ee3e340f2b9818bd78d2441d28ea509ef0ad70a2773e23221d3545a |
| src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7.py | 84ee803f7c707d6568227107cc7bfb317725ea9bd5f3a2bd3aac032b1f10beb7 |
| src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7c.py | 41db1e79cb439a9dbee0b972a69f42e0b8e74885f24a7b277848a4cf59cc5233 |
| src/legsa_gins/paper_rebuild/clean5_sequence/io_audit.py | 418819bff1b4eec124850314ef12a83c2d935b10dc1b1db7b9b5110098ed12d7 |
| src/legsa_gins/paper_rebuild/subprocess_guard.py | e582ee3d29dbd17246398e8e35bf8f006cf48e8aa71de92550739666ae39fac7 |
| configs/paper_rebuild/hext/HX02E/CONTRACT.json | d8511bd8bbbe84a77a257ba04b6794c22a9aa4517580899cdbfcf71d18ca0f9f |

构建产物身份（路径相对 $SCRATCH/HX02E/BUILD）：

| 产物 | SHA256 |
|---|---|
| hx02e_official_driver | 0fa3ca6a3b553ab9bd16acd9b5c8844c4e54600f185d5476bc5028312dbf6944 |
| official/bin/kinematics | 765e4d9bec9d4e3d2d65d6550babdadc7c94e50390b455fdbf7c03918e675014 |
| official/bin/landmarks | 5e8560159aa6a6db7e47969c71d9eaa03d5cfd4a2c6e059fd739642df0638798 |
| official/lib/libinekf.so | 3d1b190b0f933adbb3a042ac3d36e14e05ef2a68c788f3794e07287c1c30405a |

提交顺序：先提交并 push `prereg(hx02e): official Hartley InEKF on three sequences`，回报本文全文；随后六个固定运行及审计，归档并清空 scratch，提交并 push `results(hx02e): official Hartley InEKF on three sequences`，AGENTS.md 追加一行。
