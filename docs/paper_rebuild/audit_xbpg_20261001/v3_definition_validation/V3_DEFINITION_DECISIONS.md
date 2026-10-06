# V3 技术定义决策与单因素验证约定

本文件是本轮实施依据，不是论文，也不宣告 V3 全部科学审查通过。起点 `334f5a64a8a1193bde25113ac84a5ddff1211cc7`，正式求解源码 `ca73cb1fb48a020fd2a450d79e520562c34eeb24`，原二进制 recorded SHA256 `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`。既有11身份/22调用、55+55输出字节关系及触发证据复用 [上一阶段最终裁定](../v3_mechanism/FINAL_MECHANISM_FINDINGS.md)，不重新证明一次。

原版源码、二进制、输入、配置和全部结果保留。三个候选各自从正式源的隔离副本实施，不叠加；上一阶段经过无干扰核对的观察 patch 可作为共同观测层继承，新增观测单独测试。当前维护 HEAD 不是原算法或新候选的完整科学身份：候选另登记源 patch、编译选项、binary hash 和原配置 hash。

## 0. 直接继承的冻结期依据（本轮补充约束）

历史设计优先依据 [PROTOCOL_V3_PREREG.md](../../v3/PROTOCOL_V3_PREREG.md) 的“唯一改动与不变项”“航向故障在5Hz表上的时间语义”，以及 [V3_01R_MANUSCRIPT_REPLACEMENT.md](../../v3/V3_01R_MANUSCRIPT_REPLACEMENT.md) 的 Methods / Evaluation。两文件本机内容与交付锚点 `334f5a64a8a1193bde25113ac84a5ddff1211cc7` 一致；最近修改分别为 `1643b9047777ffb8c474321cf8f22e1f66284810`（存储追加）和 `fb39cb8b8bd0ed08ac20ea62f5e4f2ffc483bfef`。另直接读了 `7d43b9af26120ed5dde21f53e515386361072ba6` 中的原预注册，以下科学边界已存在，不是近期审查报告新创设的定义。

|继承项|原约定与本轮处理|
|---|---|
|直接标量heading|仅yaw/yaw_valid换成5Hz raw HPPOSECEF精确iTOW配对、R5 BOTH_FIXED；GNSS2−GNSS1物理变换/wrap-safe残差继承，不再设为决策项。|
|HV输入|所有方法/注入case复用原hash，继续status-heading旋转及原有效性；是明确的既定范围，不是待“统一raw heading”的输入缺陷，本轮不改造。|
|噪声与初始化|2.933193°是继承标记而非重新标定独立5Hz噪声；原初始化、协方差、参数、门控和11配置原样保留。|
|故障与评价|原种子、时窗、1s扰动延拓和std原行暴露继承；商业融合reference仅离线评价、不能升级独立真值。原v3主/v2平行的历史记录不被新候选替换。|
|原V3算法|原二进制、C++及其SA/RP/HV行为是冻结实验身份。原协议用于解释该历史实验，不禁止本轮另行授权、独立身份的候选验证。|
|RP调度要求|两份指定原文及所引用的冻结配置/调用路径没有明确“GNSS全失效仍独立更新RP”要求。原GNSS事件入口行为已确定；N09是增加一种原先没有的更新能力，除非找到明确原要求，不能升格为历史设计违约。|
|N12/N16|原文“weighting/gating frozen”确定旧实验不变，不证明每个计算契约数学自洽。当前P与raw dz不配套的NIS命名/统计矛盾、禁用维参与质量域的新反例仍须如实保留；不靠原PASS或事后改名消除。|

近期审查和本轮事件证据用于检验实现/影响，不取代以上历史设计依据。Claude聊天导出不是前置条件，不查找或要求补传。有限10候选队列、已定容差和原版保持均不变；已经完成的调用不丢弃、不重复。候选结果是否支持采用在最终裁定说明，不能以更低单例RMSE决定定义。保留的问题表只说明现有证据边界，不自动安排下一轮；没有影响V3核心结论的新证据，不追加审查项目。

## 1. 保持的滤波框架、数据角色及顺序

误差状态21维，块顺序为位置、速度、姿态、gyro bias、acc bias、gyro scale、acc scale，各3维。代码反馈为位置/速度减去估计误差，姿态 `C_new=Exp(dx_phi) C_nom`，bias/scale加相应误差估计。对当前名义状态线性化的观测写成 `dz=H δx+v`；`dx`是给定此前顺序观测的误差状态均值，`P=Cov_`是该均值周围的当前协方差。这里的统计解释依赖原误差模型/相关性假设，没有由本轮证明真实数据符合独立高斯条件。

正式 `clean_final_v23_parity_mode` 的有效GNSS事件顺序为 position → scalar yaw → RV → RD → HV → RP →统一stateFeedback；FGO/QM/QA在本队列关闭。实际先行门和源关闭会跳过某项。`EKFUpdate`在同名义状态上累积dx，末尾反馈并清零；原P反馈/reset约定不在这三个候选中改变。

F04/A01=`AB1111`、A04=`AB1011`，AB四位依次RD/SA/RP/HV，RV独立。F03/A02=`AB0000`不进入本轮新候选队列。原始传播输入是已冻结Go2 body IMU；GNSS position、RV、RD为不同观测来源，RP/HV为弱先验，不是真值。正式heading仍为raw HPPOSECEF BOTH_FIXED标量yaw，HV准备旋转继承旧status-heading链；不切B3/FGO/QM，不重新生成provider。

## 2. 三项候选定义（不自动替换原V3）

|项目|原版已实现定义|本轮建议采用并单独检验的定义|
|---|---|---|
|N12|SA以当前P及传入pre-SA R构成S，却以raw dz计算称为NIS的二次型；EKF更新自身使用dz−Hdx。|将OIM统计解释为**当前顺序条件创新**，使用当次同快照的nu=dz−Hdx_before、P_before、H和pre-SA R。候选`N12_ONLY`。|
|N16|horizontal_2d的H/R仅有N/E两维，但metadata.std_xyz的禁用D维999进入三维maxStd/finiteStd。|显式active-axis mask确定std质量域：默认三维，仅实际horizontal_2d为N/E active、D inactive；不改变原std数值、二维H/R及其他LSIM/OIM。候选`N16_ONLY`。|
|N09|GNSS三有效位全失效使事件时间替为−1，因此独立合格RP也不进入原helper。|在已有明确无效GNSS记录的事件时刻，允许合格RP进入原门控；有效GNSS路径保持。无GNSS报文时的完整独立调度另列，未在此实施。候选`N09_RP_ONLY`。|

N12若目标是顺序NIS，原统计量与其使用的当前条件P不配套，属于该计算契约的实现缺陷。所读冻结函数/注释及局部历史推导未提供“统一预测参考均值和统一预测P上的经验评分”的完整冻结设计；这一历史原意**未核实**，不通过改名消除此差异。N16把非观测维的占位值作为真实质量输入，属于active-domain契约缺陷。二者分别判断计算契约、实际实现与候选闭环，不预设候选精度更好或必然合入。N09是已确认的实现范围与本轮希望检验的RP可用性设计之间的差别；**所读原冻结文档没有给出GNSS全失效时RP必须独立更新的要求，因此本轮按可选能力扩展裁定，不称为已证明违反原设计**。已有N09实验原样保留，不能冒充全部异步架构完成。

已复用的局部历史材料为 `../NATIVE_REVIEW.md` §3.5 与 `tests/paper_rebuild/audit_xbpg/native_audit.cpp` 的顺序更新/调度反例思路。其旧测试构建和测试次数不充作本轮测试。没有要求找齐旧聊天；未核实的Claude推导身份不作为正确性依据。

### 2.1 N12的推导与字段角色

同一顺序事件i，给定前序观测：`E[δx|past]=dx_before`、`Cov(δx|past)=P_before`，故

```
nu_i = dz_i - H_i dx_before
S_base_i = H_i P_before H_i^T + R_base_i
nis_i = max(0, nu_i^T inverse(S_base_i) nu_i)
normalized_i = sqrt(nis_i / dof_i)
```

`R_base_i`是当前调用者传入applySourceAwareWeighting的pre-SA R，可能已经包含原yaw scheme的软降权；它不是必然等于provider方差，也不是最终膨胀R。dof、逆矩阵实现、clamp、原归一化和fallback分支保持；fallback的分子也改为`||nu||`，分母仍为原`max(1e-12,trace(R_base)+trace(HPH^T))`的平方根。

raw dz保留用于原先行硬门及最终`EKFUpdate(dz,H,R_effective)`；**不得把nu作为dz传入EKF后再扣一次Hdx**。唯一一次policy evaluate使用conditional innovation；阈值、cap、LSIM规则、SA-off RD硬门、顺序和Joseph协方差更新均保持。源间实际P、状态和后续门控随候选闭环变化，是结果，不是另外调参。

字段明确分开：`metadata.residual_norm=||dz||`仍是raw诊断；`innovation.residual`、`innovation.residual_norm`、NIS/fallback及`result.residual_norm`为conditional量。冻结LSIM不读取该metadata residual_norm，本队列QM关闭。日志必须同时保留raw dz与H/dx/P/baseR，不能让同名norm看似仍表示同一个值。

### 2.2 N16的维度契约

仅当实际观测构造为horizontal_2d时，active mask=`[true,true,false]`；其他实际三维路径及其他源默认`[true,true,true]`。maxStd和std有效性只遍历active维；至少一个active维才有合法质量域。禁用D维的999或其他占位值原样保留用于诊断，不能设成0绕过问题。

该定义包括inactive D为NaN/Inf时不进入二维std质量判别；这比上一阶段仅移除999贡献的有限影子样例更一般，因此必须新增原生测试。active N/E中的非有限、非正值仍走原拒绝/保护规则；三维D仍实际参与检查。其他metadata质量因子保持，已知LSIM可能从2变为1.5而非1；D15的OIM/cap遮蔽是必留负对照。

### 2.3 N09的最窄调度契约

为传入的每条GNSS记录建立独立pending/consumed身份，不能把原`gnss.isvalid`改真。仅针对原explicit validity三位全false、RP enabled且solver_enabled的记录，用**原nearest/tolerance/tie与Go2WeakPriorFactor::isActive**做只读资格探查。探查不推进缓存、不调用SA，不把“事前合格”写成“已经通过创新门”。

到达该GNSS事件机会时：无RP、无匹配或事前不合格者记消费/原因，保持原res0整段传播、无RP/helper调用及无feedback。合格者按原res模板调用原RP helper：res1为RP→一次feedback→`pvapre_=pvacur_`→原传播；res2为原传播→RP→一次feedback；res3为原split→前半传播→RP→一次feedback→`pvapre_=pvacur_`→后半传播。SA/创新后拒绝另记，不能强制接受；这时仍沿已进入分支的一次反馈契约，res3拆传播本身可能有数值差异，须与RP接受影响区分。

不调用`gnssUpdate`，不触发position/RV/yaw/RD/HV，不改变这些输入或调度。正常有效GNSS路径原样，不能再调用一次RP。消费以GNSS输入身份计一次，不顺带重写原provider-row复用规则；实际接受是否重复使用同一row另查。`updateCount`继续表示GNSS更新epoch，不为RP-only加一；新增opportunity/eligible/attempt/accepted/rejected/consumed独立记录。原runtime模块bit计数检查无需放宽。

原测量时刻、GNSS事件时刻、IMU状态时刻分开，真实available/arrival time仍UNKNOWN。此候选不回答完全没有GNSS报文时何时调度，不宣布实时因果性已经证明，也不修A1的HV准备输入使其变可用。

## 3. 源码映射（行号指ca73冻结副本）

|文件（相对cpp/legsa_v23_port_core）|函数/位置|本轮边界|
|---|---|---|
|src/kf_gins/gi_engine.cpp|EKFUpdate:433–452；stateFeedback:455–483；applySourceAwareWeighting:1451–1489|只改N12决策创新；反馈、逆矩阵及Joseph保持|
|src/kf_gins/gi_engine.cpp|HV二维构造:1171–1185；metadata sentinel:1194|N16只给实际维度mask；原值/H/R保持|
|src/source_aware/source_aware_policy.cpp|maxStd/finiteStd:35–41；使用:242/336；OIM fallback:562；result norm:656|N16限制std统计域；N12不改LSIM/门限/cap|
|src/kf_gins/gi_engine.cpp|newImuProcess:485起；addGnssData；RP helper|N09独立pending与RP-only分支，有效GNSS路径保持|
|src/runtime/port_runtime.cpp|无效GNSS仍传入:1467–1478；counter验证:200–246|不改输入生成、循环队列或原counter验证；独立日志补RP-only事件|

观察层继承上轮patch，新加完整P的只读诊断和候选身份/定义字段；不以观察层修补N11、N15、倾斜雅可比、协方差reset或参考问题。

## 4. 固定队列、原生测试与比较判据

[CANDIDATE_QUEUE.csv](CANDIDATE_QUEUE.csv)登记10个组合：N12_ONLY与N16_ONLY各为C00/F04、D15_seed_00/F04；N09_RP_ONLY为C00、D61_20s_seed_00、D62_20s_seed_00各A04/F04。共有7个原基线身份，不是10个独立场景。原66..340全运行范围、初值及provider前置历史保持；A1/A2固定窗`[196.2,216.2)`，不按结果选新窗口。C00/D15无局部中断窗，D15为全序列位置噪声。

每候选先完成本轮新增原生测试并提交；保存失败反例和负对照。N12覆盖dx=0、dz=Hdx、相关S、同快照实际计算、fallback、SA-off；N16覆盖D占位999/普通数/NaN、active维异常、真实三维路径、其他质量因子及cap遮蔽；N09覆盖res1/2/3、匹配边界/等距选择、消费一次、正常路径不重复、无RP/不合格RP不产生零观测、接受与拒绝以及一次统一反馈。原有测试数量不转录为本轮结果。

计划真实candidate native调用10次，复用旧可信baseline，不预定新增baseline调用。技术重试需具体登记且保留失败；科学发散不自动重试、不改参数。完整NAV/STD/新事件留新隔离根，不继承旧释放政策。所有新输入读取限定为同一冻结provider和原配置，逐对象检查旧已核资格/文件元数据，不重复全盘hash。

N12同快照独立数值核对固定`abs 1e-9 + rel 1e-8×abs(recorded)`；倍率/R传播核对`abs 1e-10 + rel 1e-10×abs(recorded)`。计数精确。N09 C00/A2为科学路径未改变的负对照，首先核五输出字节；如不等，保留差异并解释，不能直接作正常通过。候选有意变化的对象不套观察版“输出不变”门，也不以RMSE降低作为代码正确性判据。

候选实际事件按稳定的GNSS输入身份/来源/原测量时刻对照基线，不用已因插入事件变化的event_seq硬拼。报告首个实际权重/更新差异及delta、首个可对照状态分叉；N09首次新增的中间更新没有同一时刻原事件时，明确基线缺该状态、记录拆传播与更新增量及随后首个共同IMU/输出时刻差异，不捏造基线插值状态。

## 5. 完整P诊断（不改滤波器）

候选每次有效newImuProcess结束、原checkCov前检查完整21×21 P。全部441项有限、正对角单列；否则不归一化。正对角下`Cij=Pij/sqrt(Pii)/sqrt(Pjj)`，检查C有限；对称门固定`max|C-C^T| <= 1e-10*max(1,max|Cij|)`。仅对通过对称门的**诊断副本**`Cs=(C+C^T)/2`做Cholesky，无jitter/裁剪/主元修正，原P不写回。

记录每个pivot：全部>1e-12为通过本数值正定诊断；落在[-1e-12,1e-12]为近奇异/数值未决；小于−1e-12为分解失败/正定性风险，不凭浮点结果宣称严格不定。失败不改原停止规则。保存分项状态、覆盖次数、首异常、最大非对称及最小pivot。原生测试覆盖跨量纲SPD、非对角NaN、非对称、正对角不定和秩亏。

基线只核已有EKF_BEFORE/AFTER完整P快照，明确不是逐IMU末连续覆盖；不为补齐诊断再跑baseline。旧checkCov只检查对角不是本新诊断，其原通过状态不升级。

## 6. 离线评价与原口径复现

采用同一冻结v3评价链：`protocol_v3/evaluation_process.py::evaluate`安全单例，不实例化Context/controller。外部evaluator SHA256为`aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`。参考仅由离线子进程读取并核同句柄hash `ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c`，不得进入solver。baseline7次、candidate最多10次v3评价分别登记，不重复计native；本轮不新做v2视图。

评价从KF_GINS_Navresult.nav出发，用冻结transform生成新EVAL_NAV_V3.nav，仅转换位置到`p_POI=p_IMU+C_b^n[0.03,-0.148095745932992,-0.30]^T`；不能拿原native EVAL_NAV.csv当作已经转换，也不能重复转换。base_time1772784000，原窗[66,340]，yaw_truth_mode=enu，consistency_policy=canonical_v2_wgs84_full_support。STD不传播至POI，保持UNTRANSPORTED_STD_DIAGNOSTIC_ONLY；reference仍为商业融合解，不提升为独立真值。关闭旧export_matched_truth，避免继承其real_clean展示标签。

先核baseline新评价点NAV hash与原记录，再核同名指标/支持字段。指标容差预先固定为`abs 1e-10 + rel 1e-10×abs(old)`，时间abs1e-9、计数精确；这不是D12的0.01m/deg门。不同口径/支持无法闭合时不直接相减，保留该对象评价限制，继续其他对象的技术结果。

各对象给全窗H/up/yaw及roll/pitch误差、输出/匹配/共同支持、完整状态和有限性。A1/A2另从新error_series计算固定半开故障窗及前后段，标为本轮派生，不能叫终点误差。不加冻结evaluator的outage参数来冒充所需窗RMSE。无参考速度字段，因此速度只做NAV自身诊断，不伪造速度RMSE。保留新失败在10计划组合分母中。

不bootstrap、不作新显著性结论、不搜参数/时移/安装角。少量说明图仅用真实新NAV/误差与权重，标新派生版本；没有算法位置就不画伪轨迹。最终逐候选裁定实现/闭环/范围/是否建议进入共同版本验证；N11、N15、倾斜几何/雅可比、生成链、评价点、P reset/完整传播及参考相关性继续独立登记，不能因三候选完成自动PASS。
