# LegSA-GINS：原 V3 的代码、配置与指标故事

本块解释原 V3 已有的完整矩阵，不更改、纠错或重跑该矩阵。论文正式方法名是 **LegSA-GINS**；`F04 / AB1111 / LegSA_Paper_V1` 保留作证据与代码映射。第一块任务/指标账本已在 `baf4e9157c7b82d611271f15ae9b7e68f3014ab3` 提交，本块只追加解释、较小表与第二收据，第一块 18 文件保持原字节。

原科学执行冻结为 `7d43b9af26120ed5dde21f53e515386361072ba6`，原二进制 SHA256 为 `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`。本轮从该 Git revision 读取旧源，而不是用当前后续诊断修订后的 C++ 解释旧矩阵。此前逐行阅读的 33 个 C++ 文件（32 全读、1 选读）与该 revision 均同 blob；[身份凭据](ORIGINAL_CPP_INHERITED_READ_IDENTITY.json) 逐项保留哈希、阅读范围和原覆盖表位置。本轮新增全文/选读另记 [READ_COVERAGE_02.csv](READ_COVERAGE_02.csv)，继承全文不冒充本轮新逐字阅读。

## 1. 方法到底在做什么

LegSA-GINS 是以机体 IMU 传播和误差状态 EKF 为主线的 GNSS/INS 系统。GNSS1 位置、接收机速度和双接收机基线导出的标量航向提供常规观测；Raw Doppler 衍生速度、Go2 横滚/俯仰与 Go2 水平速度弱先验补充约束；LSIM/OIM 使用来源质量和滤波创新保守放大观测协方差。提议方法的研究对象是这组来源明确、有效性明确、权重明确的组合及其条件效果，继承的惯导骨架本身不作为新算法贡献。

正式配置不使用腿部正运动学、关节/接触因子、Go2 位置或姿态真值、FGO 反馈、QA fallback 或多状态 QM。库中存在这些研究/诊断入口，不能把“代码存在”写成“本次正式矩阵启用”。六个在线来源是 position、receiver velocity、dual heading、Raw Doppler velocity、Go2 roll/pitch、Go2 horizontal velocity；原完整矩阵的开关、更新/接受/拒绝计数均可在第一块 ACTION 账本定位。

误差状态代码有 21 个槽位：位置误差、速度误差、失准角、陀螺偏置、加速度计偏置各三维，再加两组三轴 scale。原矩阵六个 scale 状态的初值、初始协方差及驱动噪声均冻结为零，因此有效估计空间为前 15 维；这不是在线完成六轴 scale 标定的证据。源代码为 `types.hpp:40–60` 与 `gi_engine.cpp:786–851`，均指上述原 revision。

[METHOD_SOURCE_MAP.csv](METHOD_SOURCE_MAP.csv) 给出 21 个组件/函数的源路径、原 revision、SHA256、行号、论文含义和适用边界，供正文方程与 SI 实现表直接引用。

### 1.1 传播与滤波更新

`INSMech::insMech` 按速度→位置→姿态传播，保留双子样圆锥/划桨补偿、地球旋转、运输率与重力项。IMU 输入已经按冻结生成合同转成 FRD 增量，loader 不再转换一次。误差传播按实际代码中的 F/G 块构造 `Phi=I+F dt`，过程噪声用对称离散式；正文应写这一实际实现，不笼统声称移植了原教材所有动态项。

`EKFUpdate` 用 `S=H P H^T+R`、`K=P H^T S^-1`，误差均值累计 `dx += K(dz-H dx)`，协方差使用 Joseph 形式。反馈时位置/速度减去估计误差，姿态以小旋转左乘四元数，偏置/scale 加回，再清零误差均值。原 `newImuProcess` 按 GNSS 时刻在前/后 IMU 边界或中间插入更新；中间分割现有增量，而不是新增真实 IMU 样本。

这一路径的作用是让每种辅助来源进入同一个滤波状态和协方差，而非修改已输出轨迹。依赖的假设至少包括：FRD/NED 符号合同正确；增量与时间定义一致；固定安装杆臂可用于天线观测；小失准角线性化适用；配置过程先验可描述当前工况；各观测 R 的工程近似足以支持该研究配置。关键不变量是来源身份不替换、同一次 native 的 NAV/STD 配对、观测更新先于状态反馈。外部边界是实际安装不确定度、同源观测相关性、有效过程先验的跨工况适用性；本块不把它们当作已独立标定。

### 1.2 位置、接收机速度与航向

位置残差为预测 GNSS1 天线位置减去接收机位置，包含 `Cbn * antlever`；接收机速度残差包含 `Cbn * (omega_b × antlever)`。RV 与 RD 是不同输入角色，不能把关闭 RD 描述成关闭所有 GNSS 速度，也不能把保留 RV 的效果归因于 Raw Doppler。

原航向路径是基线导出的**标量 heading**。预测取原滤波 Euler yaw，残差 wrap 到半周区间，原小角模型 Jacobian 仅有 `H_phi_z=-1`。scheme-C 的标准差 soft/hard 门是 3/6 deg，残差 soft/hard 门是 6/15 deg，soft 区放大 R 倍数 2.5；达到 hard 门即拒绝。基础 position-and-heading EKF 使用固定 2.933193 deg 的直接标量更新，不应用 scheme-C 或 source-aware。

这描述的是原矩阵冻结的标量/小倾斜工作模型。基线水平投影角加安装转角在一般三维姿态下不自动等于 Euler yaw；本块保留原结果并说明姿态、安装与测量定义边界，不把后续诊断版投影 Jacobian 或 3D 基线因子追溯绑定给原结果。

### 1.3 RD、RP、HV 的真实角色

RD 的 native 输入是已由 RAWX 与卫星状态后端求出的三维速度产品，滤波器消费该速度及 STD/卫星数/lineage/status。它不是 native 每颗卫星伪距或 Doppler 的紧组合更新，也不是 NAV-PVT RV 的改名。原门限是至少 5 星、匹配时间容差 0.05 s；SA 关闭时保留 3 m/s 残差门，SA 打开时异常残差进入来源策略而不是把这个门一律重复执行。

RP 是 Go2 roll/pitch 二维弱先验，当前配置 STD 两轴均为 1.6 deg，匹配容差 0.02 s。HV 是 Go2 SDK body velocity 经冻结姿态旋转构造的导航系水平二维弱先验，匹配容差 0.08 s，垂向观测关闭；水平观测仍可能通过滤波协方差影响垂向状态，不能声称 HV 不会改变 V。HV 沿用历史 A1 heading 和 Go2 R/P 构造的旋转，V3 只升级在线标量航向，未重新生成 HV。

`gnssUpdate` 的完整条件顺序是 position→heading→RV→RD→HV→RP，再进行状态反馈。三个辅助更新仍由有效 GNSS event 调度；当 position/RV/heading 全部无效时，原路径不会单独为 RP/HV 创建新调度事件。该行为是冻结方法的能力边界，不能仅凭有连续 RP provider 就声称实际断星时仍连续接受 RP/HV。

它们依赖的假设包括：provider 时间基准已一次对齐；RV/RD 都指向 GNSS1 天线速度且杆臂定义一致；SDK 输出能作弱先验；旋转和安装声明跨序列适用；provider STD 是可用工程权重；同一源的重复/相关信息没有被误称独立真值。三项不变量是 lineage-valid 才接纳 RD、HV 不作垂向直接观测、辅助来源不读评价 reference。相关风险是 RV/RD 同接收机相关、HV 依赖历史 heading、RP 与参考姿态并非独立无误差。

### 1.4 来源感知权重究竟应用了什么

原正式分支是 `clean_v1_conservative_quadratic`。LSIM 只看来源自身 valid/status、STD、时间差、卫星数和质量元数据；OIM 看 `sqrt(dz^T S^-1 dz / dof)`，S 包含 `H P H^T`，不是用评价误差给观测加权。若求逆不可用，代码保留基于创新协方差迹的 fallback 归一化，这个工程分支也应被方法说明覆盖。

deadband=1.5；超出后使用 `1+alpha*delta^2`，moderate>2.5/strong>4 时分别采用 1.2/1.6 倍系数。实际最终 alpha 为 position .00003、RV .04、heading .03、RD .35、RP .02、HV .03。总倍数取 `max(LSIM,OIM)` 后按来源 cap 截断：5/8/10/15/10/10；只允许 R inflation，不缩小 R。rolling 31 样本的 median/MAD 只记录相对异常与 reason，未再修改权重。

QA11E 的 Huber/Cauchy/Tukey/IGG3/Barron/DCS/switchable 形状在另外的 module analogue 分支中转换成等效 R 倍率。它们没有被原 LegSA-GINS 正式主族调用，也不能由该库入口宣称作者整套鲁棒优化方法已完整复现。

这一步为可疑来源减小影响，不能仅由名字推出更精确或“最优”。其假设至少包括：创新协方差近似可用；dof 归一化具有当前工程意义；各来源 metadata 的质量语义成立；固定 cap 和 alpha 能描述研究场景；各步 EKF 线性化适用；时间历史诊断不被误作额外真值。R 不缩小、权重不访问参考、rolling 不隐式二次调权是三项关键不变量。统计相关、模型欠准确及元数据缺失是三项必须随结果解释保留的限制。

## 2. 数据和配置是怎样进入原 V3 的

原 V3 相对于已经冻结的 CLEAN6/V2 GNSS18 底表，只替换 yaw（零基列13）与 yaw_valid（列17）；时刻、位置、RV、各 STD 和其他 valid token 不变。V2 底表的位置来自每个原始 NAV-HPPOSECEF iTOW，速度来自同 iTOW NAV-PVT，并非把早期约 1 Hz status 位置复制/插值五次。因而“仅改 heading”是 **V3 对冻结 V2 底表** 的合同，不是相对于整个早期 V0/status 项目的同信息量声明。

R5 在双接收机原始位置共同的精确 iTOW 构造 GNSS2−GNSS1 基线，使用冻结 A1 安装/坐标转换，并要求两端 PVT carrSoln=2。两端位置精确共键，不插值第二接收机位置、不用状态输出或参考修正角度。适配器 rel_acc 零只是未使用的格式占位，不能解释为零噪声。

受控 case 使用已冻结的故障内容与时间区间。旧一秒 cell 的 yaw 差分/缺测被迁移到 `[t_i,t_i+1)`，未重新抽样独立的 5 Hz 噪声。D08–10 用固定锚定相位的 5/2/1 Hz time bin，D57 精确键失配仍 valid=0，不能为得到结果做时间回正；STD 与 HV 按原字节保留。详细 case/family/seed 身份已在第一块 CASE/TASK 账本逐项登记。

[CONFIG_CONTEXT_STORY.csv](CONFIG_CONTEXT_STORY.csv) 的 33 行覆盖 11 方法×3 序列全部唯一非路径数值模型；它们由全部 6,468 份留存真实 V3 config 机器复核后归并，非挑选样例。BY2 窗口 66–340 s，BY2H 413–683 s，BY2O 3186–3563 s；同序列各方法共用初始化，包括双 heading 参与初始 yaw。F01 的读者名称因此明确“无在线双 heading 更新”，不能称为从初始化起完全不使用第二天线。

所有方法沿用已冻结 IMU 有效模型，ARW=[.985,.985,.985] deg/sqrt(h)，VRW=[9.478382094779873,9.784198200134004,7.6321402201126745] m/s/sqrt(h)，gbstd=[9.38]*3 deg/h，abstd=[4817.482008954474,8259.572423450163,2257.241538343225] mGal，相关时间 1 h。loader 将角度、小时、mGal、ppm 转成内部 SI 单位。该模型是 BY2 GNSS1 PVT 速度增量与 Go2 R/P、A1 heading 等输入拟合的有效先验，并非商用融合 reference 测得的独立纯 IMU 噪声；BY2 用于拟合与评价、H/O 使用同一冻结模型的迁移关系，应在 Methods 明说。该解释不新增标定或改变任何参数。

[CONFIG_COMPARISON_DIFFS.csv](CONFIG_COMPARISON_DIFFS.csv) 全列出 30 个模型对比。四个单模块消融在每个序列仅变一个 enable flag 与 algorithm/ablation 身份字段；基础方法对比则是多个功能差异。尤其 position-and-heading EKF 到 LegSA-GINS 还增加 RV，不能把全部差值都算成 RD 或 SA 的独立贡献。所有完整参数原值仍在第一块 CONFIG_MODEL_FACTORS.json，不能只根据短表代替真正配置。

## 3. 128 个指标到底意味着什么

实际归档 evaluator SHA 为 `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`。它将参考插值到 NAV 时刻，LLH→WGS84 ECEF→首个匹配参考点固定 ENU，误差为 estimate−reference。ENU Up 是向上，不能把 Up 的有符号值直接标成 Down。参考 ENU yaw 转为 NED heading `(90-yaw) mod360`，角度误差 wrap 到 `[-180,180)`。reference 是商用融合轨迹，不是已经证明独立的真值。

六个有符号分量 N/E/Up/roll/pitch/yaw 各 17 个统计量；H、3D 非负范数各 13 个，共 128。RMSE 是样本平均平方根，不是时间加权 RMSE；std 是总体 std（ddof=0）；分位数针对绝对误差或非负范数；final 是**最后一个匹配时刻**的误差，不自动等于固定窗口精确终点。

IAE/ISE 是 matched time 上的梯形积分：位置 IAE/ISE 单位分别 m·s / m²·s，角度分别 deg·s / deg²·s。原字段名仍保留 `_iae_m/_ise_m/_iae_deg/_ise_deg`，本块没有改原命名或数据，而由 [METRIC_QUANTITY_DICTIONARY.csv](METRIC_QUANTITY_DICTIONARY.csv) 逐字段补明真实量纲。存在间隔时这是一种匹配支撑上的梯形近似，不证明缺测区间的连续实际误差。

`bias` 与 signed_mean 相同、median absolute 与 P50 相同，非负范数 mean 与 MAE 相同；128 个字段不是 128 个相互独立研究终点。`matched_epoch_count/output_epoch_count` 的 coverage 分母是原 NAV 在固定窗内的输出数，reference_epoch_count 单列，不能把 NAV 高频插值匹配数当新增独立参考样本。

同一 native 产生两套评价合同：v2 直接用 IMU 点 NAV，v3 只用估计姿态与声明 lever `[.03,.03-baseline_median/2,-.30]` 变换位置三列，再用同一 evaluator。时间、速度、姿态不变，无基于参考拟合、对齐或输出纠偏。STD 两套均使用原始同次 native 的 STD，v3 没有 covariance transport，因此只可作为诊断，不提供完整 NEES 或该声明点的已校准不确定度。

失败 native 不运行 evaluator，原 566 个评价槽位保留 NOT_RUN_ALGORITHM_FAILURE 和空指标。完整任务分母与失败类别仍进入汇总；不能把失败行删掉后称为全部 case 的平均性能。已完成 12,370 次评价全都有技术访问与数值 consistency 验收；本块读取保存结果，不重新启动它们或新读 raw/trace。

评价路径的目的有两层：执行同一固定数学合同，并独立观察访问和一致性。它假设参考时间/列语义成立、ENU/NED变换成立、时间插值适用、声明 POI/杆臂具有研究意义、参考有当前时间支撑、原 STD 是同次输出；不变量是只在 evaluator child 读 reference、原 NAV/STD 内容不改、失败不填成绩。外部边界包括共享 GNSS 的参考相关性、未实测 reference POI、未运输协方差。观察器的 consistency check 不会替换 evaluator 数组，也不是一份新的独立真值。

## 4. 三序列自然全窗的完整方法结果

下表只显示原 v3 声明 POI 合同、全部 11 方法×3 序列。六位小数仅用于阅读；[NATURAL_METHOD_RESULTS.csv](NATURAL_METHOD_RESULTS.csv) 保存全部 66 行（含 v2 IMU 点合同）原标量 token、run/case 身份、输出支撑、源行和输入/结果 hash；全受控矩阵的 128 指标仍在第一块 METRIC ledger，不被这张自然序列表替代。

|序列|论文读者名称|H / V / 3D RMSE (m)|roll / pitch / yaw RMSE (deg)|匹配/输出|
|---|---|---|---|---|
|BY2|GNSS/INS EKF (no online dual-heading update)|0.091771 / 0.047881 / 0.103511|3.331296 / 2.933248 / 8.089647|56642/56642|
|BY2|Position-and-dual-heading EKF (receiver-velocity update disabled)|0.101922 / 0.048068 / 0.112688|3.335252 / 2.922796 / 2.231952|56642/56642|
|BY2|Position/velocity-and-dual-heading EKF|0.099920 / 0.047874 / 0.110797|3.324661 / 2.928910 / 1.915591|56642/56642|
|BY2|LegSA-GINS|0.097906 / 0.048996 / 0.109481|2.254340 / 2.265491 / 1.886272|56642/56642|
|BY2|LegSA-GINS without Raw Doppler|0.098050 / 0.048416 / 0.109352|2.253619 / 2.265349 / 1.885676|56642/56642|
|BY2|LegSA-GINS without source-aware weighting|0.096920 / 0.050019 / 0.109066|2.067087 / 2.141149 / 1.886001|56642/56642|
|BY2|LegSA-GINS without Go2 roll/pitch prior|0.098639 / 0.048478 / 0.109908|3.326344 / 2.929300 / 1.913840|56642/56642|
|BY2|LegSA-GINS without Go2 horizontal-velocity prior|0.098997 / 0.048992 / 0.110456|2.254502 / 2.265422 / 1.886870|56642/56642|
|BY2|LegSA-GINS without Go2 roll/pitch prior, Go2 horizontal-velocity prior|0.099859 / 0.048474 / 0.111002|3.326637 / 2.929498 / 1.914423|56642/56642|
|BY2|LegSA-GINS without source-aware weighting, Go2 roll/pitch prior, Go2 horizontal-velocity prior|0.099760 / 0.049460 / 0.111348|3.325209 / 2.928598 / 1.914867|56642/56642|
|BY2|LegSA-GINS without Raw Doppler, Go2 roll/pitch prior, Go2 horizontal-velocity prior|0.099984 / 0.047858 / 0.110848|3.324775 / 2.929068 / 1.913875|56642/56642|
|BY2H|GNSS/INS EKF (no online dual-heading update)|0.062926 / 0.044904 / 0.077305|2.784918 / 1.883794 / 7.137488|58580/58580|
|BY2H|Position-and-dual-heading EKF (receiver-velocity update disabled)|0.071501 / 0.045410 / 0.084702|2.782334 / 1.882584 / 2.283241|58580/58580|
|BY2H|Position/velocity-and-dual-heading EKF|0.068667 / 0.044901 / 0.082044|2.784099 / 1.882176 / 1.940801|58580/58580|
|BY2H|LegSA-GINS|0.068362 / 0.045352 / 0.082038|1.966253 / 1.698295 / 1.933770|58580/58580|
|BY2H|LegSA-GINS without Raw Doppler|0.068700 / 0.045364 / 0.082325|1.966769 / 1.698016 / 1.932567|58580/58580|
|BY2H|LegSA-GINS without source-aware weighting|0.070046 / 0.045895 / 0.083742|1.837274 / 1.659245 / 1.933907|58580/58580|
|BY2H|LegSA-GINS without Go2 roll/pitch prior|0.067847 / 0.044925 / 0.081372|2.784606 / 1.881637 / 1.940927|58580/58580|
|BY2H|LegSA-GINS without Go2 horizontal-velocity prior|0.068892 / 0.045355 / 0.082481|1.966031 / 1.698355 / 1.934036|58580/58580|
|BY2H|LegSA-GINS without Go2 roll/pitch prior, Go2 horizontal-velocity prior|0.068334 / 0.044928 / 0.081781|2.783532 / 1.882335 / 1.941106|58580/58580|
|BY2H|LegSA-GINS without source-aware weighting, Go2 roll/pitch prior, Go2 horizontal-velocity prior|0.068390 / 0.045419 / 0.082098|2.783964 / 1.880996 / 1.941317|58580/58580|
|BY2H|LegSA-GINS without Raw Doppler, Go2 roll/pitch prior, Go2 horizontal-velocity prior|0.068666 / 0.044948 / 0.082069|2.783734 / 1.882120 / 1.940210|58580/58580|
|BY2O|GNSS/INS EKF (no online dual-heading update)|0.062842 / 0.043746 / 0.076569|1.863894 / 1.742730 / 5.739038|76548/76548|
|BY2O|Position-and-dual-heading EKF (receiver-velocity update disabled)|0.054725 / 0.046174 / 0.071602|1.879463 / 1.731210 / 2.309491|76548/76548|
|BY2O|Position/velocity-and-dual-heading EKF|0.054709 / 0.043712 / 0.070027|1.874915 / 1.734025 / 2.432184|76548/76548|
|BY2O|LegSA-GINS|0.054543 / 0.045859 / 0.071260|1.507112 / 1.695031 / 2.433815|76548/76548|
|BY2O|LegSA-GINS without Raw Doppler|0.054465 / 0.045936 / 0.071250|1.506793 / 1.695143 / 2.435462|76548/76548|
|BY2O|LegSA-GINS without source-aware weighting|0.053942 / 0.044177 / 0.069723|1.450063 / 1.678412 / 2.429173|76548/76548|
|BY2O|LegSA-GINS without Go2 roll/pitch prior|0.054011 / 0.045365 / 0.070535|1.876592 / 1.734154 / 2.434144|76548/76548|
|BY2O|LegSA-GINS without Go2 horizontal-velocity prior|0.055421 / 0.045860 / 0.071935|1.507126 / 1.694950 / 2.432539|76548/76548|
|BY2O|LegSA-GINS without Go2 roll/pitch prior, Go2 horizontal-velocity prior|0.054850 / 0.045369 / 0.071182|1.876187 / 1.733562 / 2.433866|76548/76548|
|BY2O|LegSA-GINS without source-aware weighting, Go2 roll/pitch prior, Go2 horizontal-velocity prior|0.054777 / 0.043654 / 0.070044|1.876384 / 1.733951 / 2.428660|76548/76548|
|BY2O|LegSA-GINS without Raw Doppler, Go2 roll/pitch prior, Go2 horizontal-velocity prior|0.054752 / 0.045437 / 0.071150|1.874847 / 1.733944 / 2.435553|76548/76548|

自然序列不是九个独立随机重复。BY2/H/O 的相近位置误差表示当前固定输入、模型、初始化和参考合同下的表现，不能单由自然全窗平均把每个模块都说成稳定改善。消融的明确单开关身份、全故障类型/失败/尾部的条件结果及参数选择历史在后续故事块继续呈现；本块不按成绩筛选方法或遗漏坏行。

## 5. 文件入口与下一块

- 原全矩阵证据根：`<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3/`；完整 registry 位于 `<V3_SCRATCH>/00_PREREGISTRATION/REGISTRY.json`。
- 留存真实配置与 NAV/STD/result 根逐任务见 TASK ledger；原 CONFIG/Git source 与现在诊断版本分开引用。
- 本块五个小表共 278 行（33+30+66+128+21），第二数据收据为 [SECOND_BLOCK_DATA_RECEIPT.json](SECOND_BLOCK_DATA_RECEIPT.json)。
- 原主线全文/继承/选读范围和不能声称逐字阅读的结构化资料分开记录；未将机器遍历、哈希或导出的 CSV 说成全仓每字人工阅读。
- 下一块串联 CLEAN1→输入/有效模型→CLEAN6→T5a/T5b→原 V3 的选择历史，以及全 CORE/ADD/H/O 的失败、尾部和全部比较输入层级。本块没有启动新实验，也没有变更当前论文算法名之外的科学身份。
