# 全部既有横向比较：实际做了什么，以及成绩可以说明什么

本块以正式读者名称 **LegSA-GINS** 讲述比较；F04、AB1111、LC01 等内部ID只用于定位证据。原V3的6,468次运行、11种配置、588个案例、两套评价合同及128个标量指标全部沿前三块保留，本块没有执行估计器、生成器或评价器，没有更改原结果。比较资料按各自执行时点和源码身份解读，不能把早期占位、后来的真实补齐、进一步诊断混成一次实验。

[30项方法/配置身份总表](EXTERNAL_METHOD_STORY.csv)逐项保留原23项注册，增加RTKLIB三种条件、三篇FGO选定链及SDK dead-reckoning诊断。23项不是23篇完成复现的论文；S条件、单接收机诊断及RTKLIB条件也不是新论文。[33项资产索引](COMPARISON_SOURCE_ASSET_INDEX.csv)给出实际路径、前后SHA、行数和时间身份；20个小型结果/登记/封存文件按原字节复制在[COMPARISON_SOURCES](COMPARISON_SOURCES/)。完整机器字段读取和选段人工语义阅读分别登记于[阅读范围](READ_COVERAGE_04.csv)。

## 原V3里的横向比较首先是怎样形成的

原冻结 `CLEAN8_PROTOCOL_V3/07_AGGREGATE/MAIN_TABLE_V3.csv` 有52行：15行LegSA-GINS及内部基础/消融配置，37行外部条目；全表26行COMPLETED、4行AVAILABLE_GEOMETRIC_AUDIT_FAIL、1行NOT_RUN_ALGORITHM_FAILURE、21行UNAVAILABLE。4行几何失败是BY2H的LC01与LC01-S、FILE_START与CONTRACT_START组合；算法失败是EXT05C-S的BY2H FILE_START。外部21行是当时组装主表的历史不可用/占位，不能据此否认后来EXT、RTKLIB、GINav、Hartley已有实际运行。相反，也不能将后来的成绩回填原冻结主表后假称原实验同期已有这些结果。

原字节[V3主表](COMPARISON_SOURCES/ORIGINAL_V3_MAIN_TABLE_V3.csv)和[V2主表](COMPARISON_SOURCES/ORIGINAL_V3_MAIN_TABLE_V2.csv)并列留存。原V3评价位置是声明的双天线中点；V2是另一位置合同，不能交叉取更好的数字。跨程序都有商业融合参考并不自动证明同一实体物理点或独立真值，覆盖率也须读原分母与实际输出节拍。

随后CLEAN9的HX02/HX05把原始观测航向法、RTKLIB、松耦合IEKF、单接收机诊断、官方GINav与官方InEKF分层运行，HX03检查既有provider层退化，HX07R检查RTKLIB多条件。2026-10-04又完成EXT V2新身份、严格FGO及另立身份的FGO分段诊断。上述结果都是追加历史，不重跑或覆盖原LegSA-GINS全矩阵。

## 输入中的双位置基线与原始观测动基线分别承担什么角色

LegSA-GINS的A1航向由双接收机已解算HP位置差和质量/长度门形成，在线姿态中使用该航向及GNSS1位置/RV，另有真实RAWX Doppler派生速度与Go2 RP/HV信息。它不是在滤波器内部执行逐卫星载波整周模糊度求解，也不能将RTKLIB moving-base的完整原始观测链当作同一种输入。原V3仅替换预定yaw与yaw_valid字段，其他信息与冻结初始化按前三块保持；共同初始化即使对无在线双航向配置也含双接收机信息。

官方RTKLIB moving-base和EXT01/02/03则从两个接收机原始码/相位或重建RINEX估计相对基线/模糊度，输出投影航向，不使用Go2 RP/HV或LegSA的整套松耦合输入。该输入层差异解释比较目的：评估本数据/适配条件下完整应用路线的成绩，而非将高层RTK与raw-code算法当作同输入求解器排名。

## RTKLIB四个条件：同一官方程序，不是四篇基线

官方版本为RTKLIB 2.4.3_b34，冻结commit `180043ee24b6d2b168f98b64be15f69d50046b1a`。HX07R完整历史控制复现V0；V0E仅改广播星历，V1在其上扩展星座条件，V2在V1上使用fix-and-hold。原config的navsys值分别33、33、57、57；共同L1/L2、moving-base与项目0.350m长度/0.010m约束及ratio3条件均有原config/COMMAND记录。它们没有IMU、SDK姿态或A1作为在线估计输入。

|条件|BY2原生有效/1370；航向RMSE°|BY2H原生有效/1350；RMSE°|BY2O原生有效/1885；RMSE°|解释|
|---|---:|---:|---:|---|
|V0|153；14.566166|179；27.011169|112；23.138950|原冻结条件|
|V0E|194；20.646991|217；31.263814|231；20.402911|只改星历条件|
|V1|154；14.611254|186；12.732971|117；21.781901|更多星座条件|
|V2|60；4.511761|149；10.622992|93；19.205502|fix-and-hold条件|

小误差伴随较低支持，不能只摘V2的BY2 RMSE。原生、fixed/float以及held支持分别保存；V0 held RMSE58.241052/55.117993/129.988223°，BY2O曾有301.4s旧值年龄，held不能写成当时新的有效解，Q1也不证明真实整数正确。HX07早期窗口转换得到157而完整历史目标153（预定±2门）因此硬停止，exit0是控制不一致，不是程序无崩溃即成功；HX07R采用完整历史并重现153/179/112。旧157条件留supplement，不能替代原控制。源表[主表2行](COMPARISON_SOURCES/RTKLIB_HX07R_MANUSCRIPT_ROWS.csv)与[补充12行](COMPARISON_SOURCES/RTKLIB_HX07R_SUPPLEMENT_ROWS.csv)各自说明native/fixed/hold及条件。

## LC01、LC01-S、EXT05C：估计器真实运行与信息边界

LC01是Pavlasek、Walsh和Forbes（ICRA 2021）两位置接收机SE₂(3) IEKF主算法的独立实现，估计九维R/v/p，不估计IMU bias。两HP位置及pAcc构成相关测量，保存的联合协方差为 `[[R1,-R1],[-R1,R1+R2]]`；Van Loan离散化、Joseph更新和群注入均有源码/测试映射。它没有LegSA的RV、RD、SDK RP/HV辅助，Appendix MEKF并未实现。初始yaw使用双接收机位置差；IMU轴/尺度、过程噪声和起点遵循其实际配置，不是假装无双天线信息的单天线启动。

LIT与S是同一算法的参数条件。LIT自然序列V3合同的H RMSE为0.097548/0.074606/0.054304m，yaw为2.994827/2.208612/2.453697°；S补充yaw为1.539239/1.943003/4.015602°。S使用本项目BY2有效标定模型，开发数据重叠须披露。LIT主条件的选择也留有 `amended_after_results_seen=true`，不能写成与结果无关的纯事前选择。

LC01和LC01-S在BY2H两个起点共4行发生几何审计FAIL：估计基线水平长度≤0.1m的后段风险没有被COMPLETED数值掩盖，行状态为AVAILABLE_GEOMETRIC_AUDIT_FAIL。数值仍可用于描述该特定运行，却不能当几何合同合格的优势证据。H的FILE_START与CONTRACT_START另保留，不能选一个起点就删除另一失败记录。

EXT05C是同九维滤波器的**单接收机在线位置更新诊断**，初始yaw仍用了GNSS2，因此正式读者不能称全流程纯单天线。LIT yaw为12.048642/20.108223/5.845502°（H为CONTRACT_START）；H FILE_START55.609934°另存。EXT05C-S同理是项目参数诊断，H FILE_START在418.6s速度51.1987m/s真实发散，保持UNAVAILABLE；CONTRACT_START的8.114756°不替它擦除失败。

LC01-M、LC01-S-M、LC01-2D修改草案已取消执行；EXT05B未实现且有人类豁免。不能把库文件或测试存在写成已获得论文比较成绩。[历史HX05主/补表](COMPARISON_SOURCES/HX05_HISTORICAL_MANUSCRIPT.csv)和[补充](COMPARISON_SOURCES/HX05_HISTORICAL_SUPPLEMENT.csv)保留这些路线的实际层次，旧EXT数字按其旧时点解读。

## GINav与Hartley：官方数学核心并不消除传感器差别

GINav使用Chen、Chang、Chen（GPS Solutions 2021）官方 `bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666` 的SPP/INS松耦合路线：GNSS1 RAWX/SFRBX→RINEX→SPP，Go2 IMU和官方TDCP速度对准；没有GNSS2 A1或SDK姿态先验。旧BY2的113.002s长对准后仅77/275窗键，H/3D RMSE130.818726/219.883711m、yaw69.753332°。后来HX02的BY2/BY2O有D8速度门真实失败，BY2H仅2/271；2/2自身匹配不是271个原槽位全覆盖。旧BLOCKED文字与后来实际执行区别保留，失败不形成可排名的虚构完整成绩。

Hartley使用官方contact-aided InEKF `ef16e8a…` 的Propagate/CorrectKinematics数学核心，OFF-LIT/OFF-DEF三序列共6次实际完成，估计R/v/p、bias和接触状态。观测是Go2 `foot_position_body` 高层运动学代理及力阈值滞回，而非原作者关节编码器、接触检测和安装标定链；噪声、力门、轴、首1s初始化属于项目适配。无GNSS的xyz/yaw四自由度本来缺绝对可观测性，因此先10s单次xyz+yaw对齐后的相对轨迹不能与绝对GNSS物理点直接排位。

OFF-LIT对齐H RMSE50.187304/68.544623/77.504150m，yaw62.173499/77.484530/90.896028°，真实大漂移全部保留；旧移植BY2H静止初始化失败也没有被新官方驱动的成功覆盖。SDK-attitude dead-reckoning对照的H6.209/9.178/6.322m使用供应姿态，属于条件输入诊断，不能证明InEKF数学算法错误。GINav/Hartley可称已命名官方求解路线或官方滤波核心实际运行，不能称原论文传感器实验完整复现。

## EXT01–03后来升级成哪些真实原始观测核心

三条路线早期受适配/后端合同限制，最新V2已实际执行两个接收机raw码/相位链，不是把通用滤波器改标签。EXT01实现Teunissen C-LAMBDA整周/长度约束基线核心及严格球面搜索；EXT02实现Liu等TIM 2022单基线CWLS Algorithm1/2；EXT03实现Yang等TIM 2024双频GPS/BDS DD-KF、长度伪观测、MLAMBDA与ratio。工程实例仍应逐条声明：EXT01预算/接受检验缺口；EXT02全唯一候选池、任一未完成整历元拒绝；EXT03未完全取得的F/Q/R与每步SPP基线重设。EXT02多天线三轴完整分支未做，EXT03项目0.350m基线也不是作者原1.23m/7.99m实验。

V2修正接收机分别计算发送时刻及SPP几何flight-time地球旋转delay，原始伪距仍传卫星provider、卫星坐标只旋一次；新输入/缓存/source pins单列。旧结果、空间暂停的BY2O EXT01 1,250历元/955有效partial全部保留，后来TECH_RETRY_2九组合从epoch0开始，未将暂停前后wall拼接成正常时延。原生在线reference成功读取0，全九封存后才3次离线评价；原15669记录=9100valid+6569invalid，未输出及边界均保留1370/1350/1885分母。

|方法|BY2有效；投影航向相对Euler参考RMSE°|BY2H有效；RMSE°|BY2O有效；RMSE°|
|---|---:|---:|---:|
|C-LAMBDA|980；85.015472|1059；89.127388|1173；81.273465|
|CWLS|961；85.179795|1029；89.192923|1210；81.486071|
|长度约束DD-KF|541；79.931845|467；63.994556|269；103.754200|

EXT01/02没有整数接受检验，ratio-fixed为NOT_APPLICABLE，不是0正确率；EXT03 ratio支持78/70/5，整数真值正确性未知。三法共同键506/451/227，ALL7（含四RTKLIB条件）仅6/39/55，同key依然不消除频率/星座/噪声/状态/质量门差别。全部[63行](COMPARISON_SOURCES/EXT_V2_COMPARISON_TABLE.csv)、[450行共同支持](COMPARISON_SOURCES/EXT_V2_COMMON_SUPPORT_ALL.csv)、[27行V1/V2同法共同支持](COMPARISON_SOURCES/EXT_V1_V2_SAME_METHOD_COMMON_SUPPORT.csv)保留。物理修复后的EXT01/02共同支持RMSE变化绝对值<5.3e−6°，EXT03相同；真实大误差没有消失，不能靠修复声明把结果写好看。

三法输出是body−y侧向基线的水平投影方位+90°；商业融合参考提供Euler yaw。若R=Rz(ψ)Ry(θ)Rx(φ)，量差是 `atan2(−sinθ sinφ, cosφ)`，水平投影必须非零。后来已执行的[名义量定义检查](../EXT_MEASURAND_20261004/README.md)保留全部7689正式有效键、原13815槽位；量差RMS0.031092–0.043577°、max0.454407°，9个RMSE改变最大0.004278°，不足以解释64–104°误差。没有拟合旋转/符号/安装角或挑样本；安装天线次序、真实机体轴和实体测量仍未独立核定，商业融合参考也不是独立truth。

结果后又加入竖直/近竖直投影无量纲比例门 `ρ²=(bN²+bE²)/‖b‖²>1e−12` 及转换失败valid=false/yaw=null；此门拒绝数学奇异，不是已标定的实用准确率或噪声门。19边界测试、75相关测试、独立19测试通过。全部9100旧有效保存基线均不触发：min水平范数0.0198182443m，min水平/全长0.0566235552。旧9次是guardless源码执行，guard是独立后结果身份，**未用新源码重贴旧9/135 pins、未重跑或改数值**。V2 README早期正文里的“待guard”句与后补banner分时点理解，完成收据为 `G:/LegSA-GINS-project/修复_20261004/EXT_HEADING_POST_RESULT_REPAIR_RECEIPT.json` 及同目录 `EXT_HEADING_POST_RESULT_INDEPENDENT_PEER_REVIEW.json`。

这些负结果支持“指定实现、输入、工程策略及声明几何下表现不足”；在安装、作者参数及独立参考未闭合之前，不能无条件写原方法普遍不适用或LegSA-GINS同输入求解器胜出。不能为改善成绩改变EXT02整池策略、基线符号、物理量或epoch选择。

## 三篇FGO：严格主身份与新分段诊断分开

选定链现已包括真实完整估计过程：OiSAM的15维INS/GNSS、Earth预积分桥、结构Givens、增量缓存、30/40 A-JSWR与Ceres；Wen的原始伪距、body加速度bias/AHRS运动联系与联合LM；GNC的原始码+Doppler联系、GM连续化和状态/权重交替。但作者Oi完整程序、Wen原Xsens AHRS动态/校准、GNC作者数值设置/Eq21与Eq22歧义均未全部取得，不能称三篇全部作者程序/全部原场地实验复现。逐项45链映射在[原文符合性矩阵](../FGO_COMPLETE_AUDIT_20261004/COMPLIANCE_MATRIX.csv)。

严格9身份的OiSAM只允许一次A1初始化、不重启，BY2 275/275，BY2H 0/271，BY2O55/378。H408s缺IMU时只有6个节点尚未进入30节点增量阶段，O3241s缺IMU后停止；H无输出不是误差0，O前缀0.056376m的3D RMSE不能称全窗成功。Wen/GNC三序列完整batch分别274/270/377；Wen没有自行估计的姿态，GNC没有姿态状态。严格[27行METRICS](COMPARISON_SOURCES/FGO_STRICT_METRICS.csv)及[100行应用表](COMPARISON_SOURCES/FGO_STRICT_COMPARISON_TABLE.csv)保留；应用表复用的EXT数值仍是其旧generation，不静默替成EXT V2。

最新另立身份 `FGO_SEGMENTED_DIAGNOSTIC_20261004T100449Z` 已封存完成**3个新OiSAM native＋复用原6个Wen/GNC native**，封存后3次offline；不是9次fresh运行。按照真实IMU缺口事前分1/3/7块，每块再用一次A1 gauge初始化，新增信息逐次记账；没有按收敛好坏重启/删块。所有方法统一到GNSS1物理点，新Oi位置使用自身姿态和声明杆臂转换，未插值/hold输出。仅这一新FGO比较内部的GNSS1点统一闭合，不自动证明其与原LegSA中点评价同点。

|新诊断主动态支持|BY2|BY2H|BY2O|
|---|---:|---:|---:|
|OiSAM自身有效/原分母|275/275|267/271|370/378|
|OiSAM H / 3D RMSE(m)|0.097867 / 0.107594|0.064957 / 0.077222|0.052046 / 0.064826|
|OiSAM自行估计yaw RMSE(°)|4.652921|2.534907|3.971789|
|三方法共同主动态key|274|267|369|

主表PRIMARY_DYNAMIC_ONLY排除所有prior-only初始化行；SECONDARY_ALL_VALID_POSITION另保留OiSAM275/269/376，不借初始化输出填主支持。B控制与严格相同无重启；H/O新初始化改变状态历史和输入信息，不能抹掉旧严格H0/O55。O3286s usable NO_CONVERGENCE的20次更新仍保留有效记录，O3484s bodyrate stale无效并等3485s；坏事件没有被宣称消失。原分母275/271/378继续保留，Wen/GNC没有yaw成绩。各序列[BY2](COMPARISON_SOURCES/FGO_SEGMENTED_BY2_METRICS.csv)、[BY2H](COMPARISON_SOURCES/FGO_SEGMENTED_BY2H_METRICS.csv)、[BY2O](COMPARISON_SOURCES/FGO_SEGMENTED_BY2O_METRICS.csv)各12行，合计36行及native/offline三份原字节seal按本块数据接收时点冻结；接收后，FGO独立包[最终36行与三序列图](../FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/README.md)已完成并推送25e437b；本块未新作图或声称自己重新视觉复核，历史接收copy和seals不回改。

Oi使用高层RTK位置+IMU+初始化；Wen使用原始码+外部AHRS/线加速度；GNC使用码+Doppler。即使新GNSS1点和共同时间键明确，也不能称同输入求解器排名，更不能用跨方法误差单独证明RD/RP/HV的因果必要性；其因果讨论应回到原LegSA单变量消融和第三块的方向/失败全账本。

## 仍没有合法成绩的候选，以及只做了模块的内容

原23项中的12项没有合法独立性能条目：D01_DIRECT_GEOMETRIC_BASELINE、EXT05B、LC01-M、LC01-S-M、LC01-2D、LC02_YIN2023_RAEKF、LC02_CHANG2021_FSTCKF、LC02A_JIANG2021_ADAPTIVE_FADING_CKF、LC02B_TAGHIZADEH2023_AHINF_CKF、EXT06_HAO2018_TWO_ANTENNA_LC_EKF、D02_SINGLE_RECEIVER_IEKF、EXT06 Luo候选。身份/材料不足、未实现、取消或原源码身份不闭合的具体原因保留总表，不用通用robust EKF或CKF换标签代替作者算法。Luo候选文献身份仅历史中等置信登记且未全文/实现，不形成当前比较结论。

EXT04是Wu TIM 2025的FAR/PAR航向/ambiguity模块，不是完整GNSS/INS与misalignment估计器，三序列0接受保留；它未升级到本批EXT V2后端。QA/QM内研究诊断中的Huber、Cauchy、Tukey、IGG3、Barron、DCS、switchable等形状在冻结政策源码437–552行只是OIM等效R倍率，不含作者factor状态、switch状态或优化体系。正式LegSA采用conservative分支，并非把这些全部跑进主算法；[7项scope](INTERNAL_ROBUST_ANALOGUE_SCOPE.csv)明确不能计成7篇完整复现。

HX03既有provider退化也不是RAWX层同一故障。修正评价观察器后的HX03R2实际396逻辑格，360有限/36native发散，旧观察器投影造成的缺测假警另保留，不改原native轨迹；LC01-BR附加18个条件也未改善H中位数。D57不同方法暴露于position或heading的故障不同，不能借相同D编号证明同一输入扰动。完整退化主张仍依赖对应provider、字段mask、初始化和故障窗，而不是只看方法名。

## 论文中如何据此组织比较

主文首先说明LegSA-GINS的六类输入、冻结标定/初始化、15活动+6固定状态和原矩阵中的单变量配置，再用完整成功/失败和原分母报告效果。外部比较按输入层和物理量分组：原始观测投影航向、两位置/单位置更新IEKF、raw-SPP/INS、接触代理相对里程计、selected FGO估计链。LC01几何FAIL、GINav长对准/失败、RTKLIB低支持、Oi严格缺口、EXT大误差都保留，避免只比各自最佳支持。

[公平性合同表](COMPARISON_FAIRNESS_CONTRACTS.csv)列出每组已闭合和未闭合的输入、初始化、状态、物理点、航向量、时间支持与参考边界。适合的表述是“本传感器/适配条件下的应用结果及工程适用边界”。原矩阵消融可以提出同一pipeline内的条件证据；跨输入高低层差异、无独立安装测量、商业融合共享参考和相对gauge对齐不能被差成绩自动消除。本块无需为追求指标补做新旧全矩阵，也没有启动任何追加科学任务。

全部126项最新EXT/严格FGO/分段FGO字段索引见[FROZEN_EXTERNAL_METRICS_OVERVIEW](FROZEN_EXTERNAL_METRICS_OVERVIEW.csv)。它保留原decimal字符串、status、物理量和支持角色，不把NA转0、不归一成共同排名；RTKLIB、LC01/Hartley/GINav另保留其历史原字节表和完整路径索引。
