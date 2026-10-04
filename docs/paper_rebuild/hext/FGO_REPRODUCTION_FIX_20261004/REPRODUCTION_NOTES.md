# 第一步最终收据：三篇FGO的修正、真实运行与可宣称范围

日期：2026-10-04。本阶段实现了所选论文算法分支的实际计算链，完成三序列×三方法的9个新身份、全部native封存后统一离线评价、指标独立复核及三序列图。**不能宣称三篇作者完整程序和全部原论文实验已经等价复现；也不能宣称9格全部得到全窗有效输出。** OiSAM严格一次初始化后，BY2H正式窗0/271，BY2O55/378，缺口事实保留。以下结论只绑定本报告列出的真实源、配置、输入、二进制和运行身份。

## 1. 存储、身份与执行顺序

- 工作区：`/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001`；分支`fix/fgo-v3-reproduction-20261004`；基线HEAD `0625cea2c137859d1319c2e1011178cea19af10a`。本轮未commit/push。**执行含未提交修正，单写基线HEAD不足以识别代码。**
- 真实科学阶段：`/home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_REPRODUCTION_FIX_20261004/FGO_REPRODUCTION_FINAL_20261004T054410Z`。位于E宿主的WSL ext4。`runs/<sequence>/<method>/PAPER_CONTRACT/`内保存真实STATES、SOLVER_EVENTS、RUN、SOURCE_SNAPSHOT及ACCESS；`evaluation/<sequence>/`保存误差、轨迹、参考转换、METRICS和EVALUATION。
- 可在Windows直接查看的小结果：[完整表](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/COMPARISON_TABLE.csv)、[新方法表](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/METRICS.csv)、[9身份账本](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/RUNS.csv)、[源差异](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/TRACKED_SOURCE_DIFF.patch)。小目录另有27份源/配置快照、7份测试/独立oracle快照、5份支持依赖快照；不把这些身份副本当作全部代码都逐行审核过。
- 事前22份直接执行源aggregate SHA256 `1ae538d65e116028f90d80f0a721619b23ff514f0c11159a908cf303b6e009bd`；aggregate为sort_keys后的source_hashes JSON字节哈希。精确每文件值及三方法配置见[FGO_FINAL_SOURCE_PREREGISTRATION.json](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL_SOURCE_PREREGISTRATION.json)。roots SHA `59daf183093c2f936e622022d430526b114ed08a45f3baa8e19bfe5dcb42aff2`。四份RAW/方法新合同都明确选定；旧配置未改名覆盖。
- 3输入准备→9native终态→全9封存（UTC05:50:44）→3离线评价（UTC05:51:59起）→表/图/独立数值复核。每个native的22源和方法配置before/after一致，snapshot与各输出hash独立复核。额外4份评价数学依赖在评价前后另行pin；重力helper当前字节等于基线源，未追称为运行前已封存的全import图。
- [全9封存](G:/LegSA-GINS-project/修复_20261004/FGO_ALL_NINE_NATIVE_SEAL.json)记native9、当时evaluator0、在线reference payload open0；[离线日志](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL_OFFLINE_EVALUATION_JOURNAL.json)记每序列一次实际参考open。sys.audit拒读与外部strace一致；输入准备也未读参考。离线评价3次参考读取、只读审查另有读取，与native在线0必须分账。
- 用户整理空间前的prepared-only `.../FGO_REPRODUCTION_FIX_20261004/stage`保留，native/eval为0；此最终stage重新准备并冻结身份。旧G盘14次FGO及冻结V3/动基线/RTKLIB/LC01原结果没有覆盖或重新运行。根任务另外的新V3修复阶段不属于本FGO表中的保留V3。

## 2. 原文和作者可取得性

新增文献ZIP实际34个PDF，不按ZIP文件名认定只一篇；123310825bytes，SHA `a966501aad8482755602c864538c504b442914912854c965f0b35cb6d43d90f7`。成员逐hash核准见STEP1_LITERATURE_ZIP_INVENTORY，未将34篇身份核对说成34篇全文语义审核。

| 方法 | 核准版本、PDF身份与关键页 | 原作者程序/实验取得情况 |
|---|---|---|
| OiSAM | Yang et al., Satellite Navigation 6:23,2025；[DOI](https://doi.org/10.1186/s43020-025-00173-w)；18页，SHA `1b3a9c79c0285cdf6f41e95b3c3215218bc202df9978376e6bb453c83d693a6e`；p4 Eq4–7模型、p10–12 Givens/A-JSWR与实验设置、p17数据声明 | 同文OiSAM自身代码未取得；实际固定[OB_GINS](https://github.com/i2Nav-WHU/OB_GINS)作者完整模型平台，不等于取得OiSAM作者程序；原文ADIS16465及Leader A15、多600s段/全部对照/作者计时未全部复现 |
| Wen TC | NAVIGATION68(2):315–331,2021；[DOI](https://doi.org/10.1002/navi.421)；17页，SHA `7b94be96194b77b4d4ddc128f7b0df0729765299c789a747a47a79edb322273f`；p4 Eq3、p6伪距与运动、p7 Eq25与AHRS/INS合同 | [作者实验室页面](https://www.polyu.edu.hk/aae/ipn-lab/us/en/publications/2021-factor-graph-optimization-for-gnssins-integration-a-compar/)链接[GraphGNSSLib](https://github.com/weisongwen/GraphGNSSLib)，库明示论文/代码并不完全一致；未取得同文XSens Ti10 AHRS完整TC原程序/全部原路线参考 |
| GNC | IEEE TVT71(1):297–310,2022；[DOI](https://doi.org/10.1109/TVT.2021.3130909)；14页，SHA `7d13d97ccfb8b15d936f4c244579e220691fb252df3aa0f839d0bb33778dc11f`；p5 Eq18–21、p6 Eq22–23及Algorithm1 | GraphGNSSLib引用该文，但已取得公开入口为普通码/Doppler+Huber/Cauchy/NULL，不能宣称其包含同文GNC作者程序；原作者协方差、数值容差、初始化及所有实验身份未取得 |

三份PDF与旧02审查全文同字节；全文页文本审核和关键公式页目视继承有记录范围，本次重新核与实现直接有关的公式/算法框。公共来源的存在不等于作者原路线、设备、参考及所有统计都已相同。没有取得程序也不证明世界上不存在该程序。

## 3. OiSAM：实际模型、算法和失败边界

### 3.1 已落实的模型和更新链

旧GTSAM CombinedImuFactor与原文引用的Earth预积分模型不同。本轮主合同实际调用固定OB_GINS `PreintegrationEarth`，作者commit `e96c69ae84d09f0e8c1c69bdd9323eaec020db86`，GPL-3.0-or-later；作者科学源不修改。C++薄桥接编译实际base.cc/earth.cc，9份源/header逐hash gate，g++11.4.0；库SHA `cae868f51f6ef0dda3054452126271d2826477d2bebe7b563d835fa53b721b91`。编译来源/命令/对象在事前登记的upstream_obgins_build。

桥接只扩展噪声对角以表达机器人事前各轴噪声，传播、coning/sculling、Earth/Coriolis、协方差、残差白化及偏置Jacobian仍调用原类。各向同性退化与直接作者类oracle逐量比较，以及GTSAM局部chart转换有限差分等回归通过。这证明所测因子/坐标桥接的实现一致性，不是所有姿态/时长/参数的形式证明。[桥接](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/obgins_bridge.cc:36)、[实际模型与二进制gate](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/obgins_preintegration.py:25)。

独立OiSAM执行结构化Givens，对H=JᵀJ使用对应block带宽，保存prefix/tail缓存；真实30/40节点A-JSWR、roll/pitch/yaw阈值3°/3°/15°、Schur边缘化、Ceres重新线性化，20次上限未按成绩增加。GTSAM用于因子/状态坐标，不调用iSAM2代替OiSAM。缓存截取位置是对原文增量QR文字的明确数学解释，未取得原Oi程序核实作者逐字选择。[Givens](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/oisam.py:86)、[边缘化及更新](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/oisam.py:261)。

机器人初始化速度明确由GNSS1天线转到IMU，`v_IMU=v_GNSS1−R(ω×lever)`；ω取最近已完成校准增量除以真实未四舍五入raw dt。先前静态陀螺均值的移除以bias和Earth rate合同表示，避免重复安装旋转/scale/均值移除。不读V3 NAV或参考初始化。

仍有明确适配：机器人各轴噪声与初始先验、固定逐序列重力而非作者native每GNSS更新的重力、Gaussian GNSS与作者native默认Huber、GTSAM chart和Python/Ceres工程实现。它们影响统计/计算，不可标成原作者全程序完全相同。

### 3.2 严格单次初始化的真实结果

主合同每序列一次初始A1，连续heading factor0；首次必需IMU区间缺失后不再初始化、不补伪增量、不恢复yaw。所有后续缺失保留原窗分母。[严格分支](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/oisam.py:481)。

| 序列 | 实际初始化/全输入有限行 | 正式窗支持 | 首个不可积分节点/终态 | 实际Ceres |
|---|---|---|---|---|
| BY2 | 56s初始化一次；56–340s共285行 | 275/275 | COMPLETED | 70次全部CONVERGENCE，最多18步 |
| BY2H | 402s初始化一次；402–407s共6行 | 0/271，正式窗413–683s | 408s IMU_GAP_INTERVAL_NOT_COVERED；INPUT_UNSUPPORTED_IMU_GAP | 5次全部CONVERGENCE，最多5步，尚未到增量窗warmup |
| BY2O | 3144s初始化一次；3144–3240s共97行 | 55/378，正式窗3186–3563s | 3241s同类缺口；其后322行AFTER_INPUT_GAP_NO_REINITIALIZATION | 38次全部CONVERGENCE，最多7步 |

记录有输入前导seed，不改变正式窗来获取更好支持。旧H/O分别2/7次重初始化获得的成绩属于旧分支，不能填进新严格主表。BY2H无RMSE；BY2O约0.056m的3D RMSE仅对55个有效历元，不能描述全窗厘米级。

旧BY2O3286s可用解但NO_CONVERGENCE的事件完整保留。新严格分支在3241s已停止，**没有观察3286s求解，所以不能声称修正了原3286s数值成因**。终止分类和20步预算报告已落实；同历元原问题仍属于未在新主分支验证的边界。

### 3.3 作者连续数据的两个独立验证身份

先前固定OB_GINS作者完整原demo实际exit0（1617s示例，ODO开启/原8GNSS outage，路径替换，Ceres2.1），收据FGO_USER_PAUSE_RECEIPT保存。它验证作者平台原入口可运行，**不是OiSAM程序**。

本次另外事前登记已有作者ADIS16465+GNSS_RTK.pos连续357473–358073s（600s、601节点），用同一新OiSAM算法核心完成601/601。原作者配置初始yaw276°、零IMU速度，A1=0、初始化一次、IMU600/GNSS601、增量513、QR59、重新线性化87次全部CONVERGENCE、最多12步、边缘化572；14.205s。没有读author truth.nav/old NAV/err或机器人参考，未做精度评价。见[FGO_AUTHOR_CONTINUOUS600_RECEIPT](G:/LegSA-GINS-project/修复_20261004/FGO_AUTHOR_CONTINUOUS600_RECEIPT.json)及实际ACCESS。

这一完整连续输入示例补证核心确实执行至输出；仍为选定算法的独立诊断，不属于九格机器人表。未使用ODO/模拟outage，Gaussian GNSS、工程初始先验、固定源初始重力；不是原文所有600s段/Leader A15/所有原实验，也不是未取得的作者Oi程序逐字等价。

## 4. Wen TC：原文离散式、AHRS与观测性

主状态含当前位置/速度/加速度偏置及每观测历元GPS/BDS接收机钟差；伪距+运动+AHRS/INS联系真实共同求解，不只添加一个INS模块后套旧导航结果。Eq3/Eq25使用右端体偏置与加速度、当前右端position的R_GL和完整导数；改掉旧左端bias式。LM前后先消去接收机钟差再检查**未加阻尼**的平移状态秩；没有借LM damping伪装可观测。初始位置/速度人工prior没有添加；无Doppler因子、无伪姿态输出。[右端式/残差](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/wen_tc.py:240)、[秩检查](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/wen_tc.py:177)。

Go2厂家姿态quat作为外部AHRS，事前FRD、局部NED→ECEF、一次A1 gauge、比力扣固定初始重力的角色逐项记录。高率区间必须实测支持；真实gap不填速度/加速度，只不创建缺失INS边，GNSS/运动/bias节点仍保留。[AHRS interval](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/wen_ahrs.py:158)。此Go2 AHRS的动态误差/时间延迟/线性加速度统计未证明等价原文100Hz商用XSens Ti10；使用seed固定局部AHRS基底与图内当前R_GL也属于明确适配。

真实BY2/H/O accepted LM步5/6/6，代价399744.961→22678.522、229526.669→25397.914、417428.718→34327.547；均COST_TOLERANCE且无阻尼可观测矩阵前后full rank。实际INS边283/271/410，缺失边1/10/9。好收敛不意味着原设备接口/原数据全部等价；新的真实误差也不能单凭差值归因于某一个修正。

## 5. GNC：GM目标、权重次序和最后状态

主分支明确`EQ21_SQUARED_GM`。Eq18/19辅助目标对w驻点对应`w=(theta*c²/(r²+theta*c²))²`；原文p6印刷Eq22未平方只保留独立DIAGNOSTIC，九格不执行该分支、不称两式同一目标。theta初始严格Eq23无max(1,...)；Algorithm1依次固定Step2权重解state→Step3更新权重→theta/1.4→减后<1停止，无theta=1 clamp或尾部交替。[公式分支](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/gnc.py:66)、[实际循环](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/gnc.py:440)。

真实BY2/H/O outer23/22/17；theta initial1907.6284/1206.2804/266.8401，最后用于state的theta1.16326056/1.02981572/1.22518763，减后0.83090040/0.73558266/0.87513402。所有inner solve收敛、消钟差后full rank；权重式复算最大差0、Eq18/Eq19等价代价最大差7.28e−12。最后Step3新权重**没有再参与返回state**；与最后Step2已使用权重最大差0.1577/0.1492/0.1528。STATE_SOLVE_WEIGHTS/lastStep3各自保存；图权重caption明示last Step3。[角色](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/gnc.py:533)。

实际GNSS1码+Doppler，raw Doppler符号−λD并含卫星速度/钟漂/一阶Sagnac导数，状态为位置/接收机clock，输出速度用相邻位置差。真实Doppler graph协方差固定(.6m/s)²I；WLS拟合协方差仅诊断，不能写进主目标使用full WLS covariance。数值backtracking/秩gate/容差是事前工程配置，原作者同文精确设置未取得。打印公式的作者最终采用选择尚未由原程序消歧，数学一致分支不是声称作者代码逐字等价。

旧GNC_2022配置完整保留；新strict solve拒绝legacy max_final_alternations/weight_tolerance，不能用新源码默认入口冒充重播旧14运行。重播旧结果需旧source/config身份；本阶段roots明确指向新合同。

## 6. 共用原始GNSS和初始化的工程合同

仅使用GPS L1CA/BDS B1I原始未差分码、对应TGD/iono/trop/卫星钟及一次几何Earth旋转，GPS/BDS clocks分开。同物理广播身份的钟差冲突被排除，O真实92观测/92历元，BY2/H为0；候选/拒绝账本保留。原始码support来自同GNSS源，但Wen的AHRS/IMU和GNC的Doppler不同，仍非同输入求解器排名。

初始化fallback SPP显式`spp_earth_rotation_delay=iterated_geometric`，消除旧按含接收机clock的P/c旋转错误；正常已接受RTKLIB coarse可不触发fallback，不能无证据称这一改动造成某组分数提升。[SPP](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/raw_inputs.py:178)。shared_raw_backend SHA `02bab4f6835a75cad4828659c9d222e6fd8d34e01485038f4cd357e690c4ec49`与横向V2冻结源一致，before/after未漂移。其余三份共享源每文件pin见身份JSON。

输入整段scheduled285/282/420含seed；Doppler同数，H/O seed名义slot401/3143缺测不移入正式窗。正式窗始终BY2 66–340、H413–683、O3186–3563。没有按误差删坏历元、改warmup或重复A1改善新支持。raw码时间约整数前2ms，closed window边界使Wen/GNC各少1，保留原分母且不重定时。

## 7. 新真实自身支持结果

H/V/3D为实际有效支持上的RMSE；缺失数额单列在原275/271/378分母。NA没有定义，不能填0。Wen/GNC没有自行估计姿态成绩。

| 序列 | 方法 | H / V / 3D RMSE(m) | yaw RMSE(°) | 匹配/原期望 | 求解+适配(s) |
|---|---|---|---|---|---|
| BY2 | OISAM | 0.105788 / 0.043647 / 0.114439 | 4.652921 | 275/275 | 48.727977 |
| BY2 | WEN_TC | 7.692119 / 11.281932 / 13.654694 | NA | 274/275 | 39.213737 |
| BY2 | GNC | 2.173503 / 4.543968 / 5.037039 | NA | 274/275 | 0.579792 |
| BY2H | OISAM | NA / NA / NA | NA | 0/271 | 36.642451 |
| BY2H | WEN_TC | 7.672239 / 12.139729 / 14.360929 | NA | 270/271 | 38.796025 |
| BY2H | GNC | 2.134279 / 4.212907 / 4.722683 | NA | 270/271 | 0.499028 |
| BY2O | OISAM | 0.040439 / 0.039280 / 0.056376 | 0.979876 | 55/378 | 59.316959 |
| BY2O | WEN_TC | 9.583724 / 16.424586 / 19.016172 | NA | 377/378 | 58.543607 |
| BY2O | GNC | 2.724164 / 2.945937 / 4.012433 | NA | 377/378 | 0.567325 |

共同三方法只在**每方法距同名义秒≤5ms**的有效支持求交集，pair实际间距可≤10ms，不是彼此5msgate；BY2/H/O分别274/0/54。H不能排名。O共同54上OiSAM 3D0.056492、Wen13.755172、GNC3.967274m，仍只对应短段，不是整个O窗口成绩。Wen/GNC共同GNSS1支持274/270/377；OiSAM/旧V3共同POI支持274/0/54，表保留各自原count及原分母。

位置物理点不能混淆：OiSAM真实IMU状态由估计姿态按既有transform移到POI中点；Wen/GNC直接GNSS1天线，与参考中点用参考姿态/baseline移点后比较。OiSAM输入是RTK位置+body IMU，一次A1；原始码方法输入层次和辅助不同；保留V3又用额外航向/约束。因此共同支持也不代表同输入或同精度上限的求解器公平排名。

## 8. 评价、参考和计时的边界

评价不调用solver或插值估计输出，只对frozen reference LLH/RP线性、yaw unwrap后转换NED；参考先插值再物理点shift，OiSAM先用实际估计姿态移点。参考原始hash由同一次打开的字节核准。native时刻必须finite、strict ordered且名义1Hz键唯一；reference由原冻结reader numeric/dropna/sort合同处理，当前FGO不新增内部gap/duplicate拒绝门槛。**range内线性插值不是证明内部参考每段都有独立实测支持**，参考支持/设备物理定义另见审查12及REFERENCE_DEVICE_INDEPENDENCE_REVIEW。本阶段没为追求成绩改这些协议。[评价完整链](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison/evaluation.py:90)。

参考为商业融合系统共享GNSS评价参考，独立绝对truth尚未成立；图legend旧字段“Truth”须在图注定义为shared evaluation reference。参考姿态参与GNSS1物理移点，不是任何native的连续姿态输入。离线批处理Wen/GNC用窗口未来观测；OiSAM逐当前节点增量，IMU终点完整等待最大BY2/H/O约11.05/5.34/12.97ms。预先离线读取载荷与真正物理信息到达/时延不同，不能只用时间戳判实际在线未来泄漏。

STD是输入先验/权重，不是这九运行已经输出验证的状态置信度。未生成可验证P时不报告NEES；独立复算RMSE不是独立ground truth精度认证。

计时为输入读取/hash/AHRS/求解/写出适配wall time，不包含共同input准备和离线评价/编译。OiSAM BY2graph单独10.268567s而总48.727977s，Wen总含高率AHRS处理；GNC总约0.5s。机器Intel Core Ultra9 275HX，WSL Ubuntu22.04/kernel6.6.87.2，OMP/BLAS1线程；横向任务并发影响wall time。不能以此比作者C++、最坏在线延迟或简单计算效率排名。NumPy1.26.4/SciPy1.11.4/GTSAM4.2/pyceres2.6(Ceres2.2)/pandas2.2.3/matplotlib3.8.4实际版本见身份收据。

## 9. 回归、数值复核与图

最终冻结源码69项联合回归通过（13.05s），命令/测试XML/日志保留[FGO_FINAL_FROZEN_JOINT_REGRESSION](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL_FROZEN_JOINT_REGRESSION.xml)；前一次69是同组的冻结前运行，不累加成138个独立测试。先前19/26/20等子集不相加冒充新增独立测试。测试覆盖作者预积分oracle、chart及因素Jacobian、右端bias、去重力和gap、Givens/Schur、GNC驻点/停止/权重角色/秩亏/失败输出。两种源/config mismatch探针验证runner在RUN目录创建前拒绝，未调用solver。[gate收据](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL_IDENTITY_GATE_RECEIPT.json)。

独立NumPy直接读封存errors/state/events，复算9自身和9共同支持：N/E/U到H/3D范数、RMSE差≤1e−10、时间/分母/状态/22snapshot/所有native output hash、Oi一次初始化与缺口tail、GNC权重/成本/theta及Wen秩/真实终止均通过。没有打开raw reference或重新调用evaluator。[数值收据](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL_NUMERICAL_VERIFICATION.json)。这些实际针对性证据不构成所有数学/输入条件的形式证明。

三图有PNG4320×4920/600dpi、PDF和SVG，实际逐图像素目视审核；没有Wen/GNC虚构yaw曲线，H空窗明示无输出，O缺口后不连线、没clip极值。[BY2](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/figures/FGO_BY2.png)、[BY2H](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/figures/FGO_BY2H.png)、[BY2O](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL/figures/FGO_BY2O.png)。H两个缺失说明初稿位置重叠，外部仅文本注释reflow，不改数据、轴界或冻结plot源；前版完整保留。VISUAL_QA/layout_only/figurehash均收据绑定。

部分历史NAV载荷已不可取，本阶段图明确BY2 LC01、H V3/LC01两策略、O V3/LC01 trajectory unavailable；保留已有error曲线，未从error反造trajectory、未用新V3替旧曲线。图反映真实可获得载荷边界。表100行含新27类支持记录与保留系统/变体，100不是100个新native。

FGO owned diff --check通过；全工作区另有别的协作者文件变化，未据此声称整个项目检查通过。新科学数据不覆盖旧14结果，源仅本地分支，无commit/push。

## 10. 修正闭合分级及后续论文必需表述

| 项目 | 本阶段已闭合 | 未闭合/不能宣称 |
|---|---|---|
| H1 Earth模型与核心 | 实际固定原作者Earth预积分库及oracle/解析坐标回归；真实Oi Givens/A-JSWR/Ceres执行；连续作者数据601节点端到端 | 原Oi作者程序、全部数学条件证明、原作者全部模型参数/先验/robust loss与全部实验不相同/未取得 |
| H2 缺口和重复初始化 | 一次A1、真实不支持tail、原分母及状态账本；H0/O55不隐瞒 | 唯一恢复真实未采集IMU不可能；若另做连续segment重初始化必须另身份且不可混主表 |
| H3 Wen数学与接口 | 右端bias式/Jacobian、未阻尼rank、缺边不伪填、AHRS角色明确，真实全窗图state生成 | Go2和原XSens AHRS动态统计/arrival/重力/杆臂接口等价缺证；同文完整作者原程序/所有路线未得 |
| H4 GM算法 | 数学一致Eq21权重、原Algorithm1步序/theta/停止、终态权重角色，真实事件和成本核准 | Eq22印刷歧义作者实际选择及原作者数值后端/容差/协方差配置未确认 |
| H5 终止 | 20步预算/真实CONVERGENCE与usable-limit分类，所有已触发新Ceres事件收敛 | 原3286s numerical cause未在严格新主分支重达，不称已证明修好 |
| 实验与比较 | 9真实身份/三评价/自身+共同支持/原分母/三图/zero online reference/源和二进制身份 | 原论文全部实验复现、同输入求解器排名、全H/O有效解、独立truth及作者时延结论不能宣称 |

可用于论文的命名：**“基于原文选定分支的独立实现与本机器人数据适配，记录原作者模型来源和复现差异”**。OiSAM实际采用作者Earth因子与真实增量算法；Wen实际TC联合目标；GNC实际GM连续化，已经超出旧模块替换路径。但“作者完整原程序/全部实验复现”需取得原作者Oi/Wen/GNC精确程序、相同原始设备/数据和独立参考，核准全部初始化/协方差/原算法歧义，并完成原实验矩阵。缺失原始物理输入不能通过修改warmup、选好support或反复A1消除。

投稿时必须把H0/O55放主结果/coverage表，图表标明不同输入与物理点、有效支持条件/失败原因、shared reference与batch未来信息。原先“H/O近全窗OiSAM厘米级”结论只描述历史重复初始化协议，不能用于新严格分支。新表也不把Wen较差误差归因为原论文本身失效。

## 11. 阅读覆盖与复跑入口

[FGO_FINAL_MANUAL_READ_COVERAGE.csv](G:/LegSA-GINS-project/修复_20261004/FGO_FINAL_MANUAL_READ_COVERAGE.csv)逐路径区分本轮逐行全文、同blob继承全文、局部阅读、仅身份计算/测试执行。核心Oi639、OB桥接101+149、Wen439+327、GNC558、inputs334+364、runner255/Ceres124/评价233本次实际逐块阅读；其中GNC前半为本修复上下文同hash较早已读。旧源码全文阅读不自动覆盖修改后的新blob。没有声称全仓库百万行或所有第三方传递import逐字完审。

复跑命令、ignored roots、外部编排wrapper与测试入口见新docs RUN_REPRODUCE.md。复跑要建立新stage/attempt、重新事前登记最终源/config；不能重用已存在RUN目录、手改源hash绕gate或覆盖本封存结果。外部脚本日志是证据，不是自动运行指令；阅读报告不会启动新的native/evaluator。
