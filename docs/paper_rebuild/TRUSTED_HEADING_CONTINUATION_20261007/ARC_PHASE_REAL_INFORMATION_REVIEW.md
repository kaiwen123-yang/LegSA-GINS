# 真实工作prior的相位信息读出：静态科学复核

状态：PASS_STATIC_SCIENTIFIC_REVIEW_WITH_LOCAL3_GATE。该review只读提案、信息内核、saved producer、坐标映射和adapter/plan；未读取实际prior/DETAILS数值或执行数学。本agent另按根代理要求编写3项合成适配器测试但未执行；根代理已登记并执行，结果见末节。

## 1. 固定问题与调用预算

实际已有完整分母921块、918个native prior、原860合法相位模型，固定交集857。读出仅问四个冻结目标在同一END工作信息集、固定二阶矩假设及固定Young族下是否可改善。857不能称可信相位/航向覆盖，918也不是相位准入。61缺模型和3终端未覆盖仍在921主表。

现有arc_phase_information.diagnose的UNKNOWN分支只返回joint/current/declared三个完整目标（src/legsa_gins/paper_rebuild/carrier_phase/arc_phase_information.py:277–283）；prior_projected_traces虽然有四项，但只是prior trace，不提供四目标全部J及grid选择。严格复用已测试public API时，固定declared=relative/common的两次调用是合理接口预算：最多857次geometry、1714次diagnose。其内部有5142次Young目标计算、25710个既有epsilon候选；joint/current重复结果应一致、最终各报告一次。没有新数学族、连续优化器或收益挑选。

一次调用后以J_joint−J_relative拼common会引入取消误差及新的边界/选择资格；本轮不据此优化。直接调用私有helper虽可少重复，但属于另一个适配接口决定，未获本review自动授权。

## 2. saved几何与噪声映射

arc_phase_saved_model_qualification.py:239–249说明known-SD几何修正已在保存y中扣除。384–397序列化G0/G1、端点Q贡献、条件界、relations和PhaseEpoch指纹。arc_phase_difference.py:291–312明确：

- G0=F0*原epoch0 geometry，G1=F1*原epoch1 geometry；
- z=F1*phase1−F0*phase0；
- Q0′=F0*Q0*F0转置，Q1′=F1*Q1*F1转置。

因此本次直接取已映射G/Q；不能再次F映射、二次known-SD修正或重建模型。relations维度/顺序、两端指纹、block/epoch和exact bits必须一致。指纹是PhaseEpoch头+数组内容摘要，不是NPZ文件hash。gzip JSON解码会接触z/F/旧谱，但本轮不可拿z算残差或以旧rank选块。

两端噪声cross未知时Rbar=2(Q0′+Q1′)；它是条件于端点有效二阶矩界的Young界，不是已标定covariance。矩阵为m×m，应保持全部关系cross，不准只取对角。

## 3. H符号、P映射与四目标

native误差为从nominal到truth的正左姿态扰动。Ci_true≈(I+[δθi]×)Ci，使bi_true≈bi−[bi]×δθi。由h=G1b1−G0b0得到H=[G0[b0]×,−G1[b1]×]；与既有information.linearize_geometry及原phase_difference的prediction Jacobian一致。不可混用对nominal扰动的残差导数−H。

END线性化应使用clone_C0_given_end和current_C1，与END P24/P6配套；START旧nominal仅审计。current姿态到ECEF误差要含BLH位置frame项：
J1=[−nedFrameConnection,零velocity,cne at PHI,其余零]；
B6上半为clone选择、下半为J1；P6=B6 P24 B6转置。
重算须沿用Earth::cne/DRi与attitude_clone.cpp:144–161的正负号、WGS84常数和BLH单位，不能只截PHI/clone子块。

current W=diag(0,0,0,1,1,1)、joint W=I6；relative/common分别用[−I,I]/sqrt(2)与[I,I]/sqrt(2)构成W=L转置L。它们都是同一ECEF坐标下的固定投影trace，不是单独绝对yaw目标。两端各自baseline-spin gauge至少2维，H沿其为零。proper prior或cross传递带来的投影变化不可称相位直接观察gauge。

固定工作基线仅[0,−0.35,0]m，engine-frame假设，不是新物理安装证据；不要再次自行roll旋转。

## 4. 条件信息集、非线性余项和未知cross

所有矩条件必须相对于同一I_END，并在本次phase残差之前冻结。native P只是继承的离线执行前缀工作矩阵，已有NED择近未来报告时刻政策，不能称全源在线因果。P01只给state-state关系，不提供state/phase C_en；本轮仅UNKNOWN_CROSS，C_en=None，不做ZERO/SUPPLIED分支，也不把actual availability补成端点时间。

科学措辞必要补强：H是一阶姿态线性化，z−h=He+n仅在线性工作替代模型中作精确方程。若要将Young界用于实际非线性误差，n必须包含且Rbar必须界住全部有效误差——相位噪声、bias/anchor/安装/同步及非线性余项。目前原Q′不具备这些物理资格。仅“P/Q在I_END下上界各自原噪声”不足以自动覆盖遗漏余项。

本轮应显式标LINEARIZED_WORKING_SURROGATE_ONLY、nonlinear_remainder_qualified=false、physical_second_moment_bounds_qualified=false；条件数值结论是固定线性替代模型下的工作界。不能加未登记噪声、假设物理余项为零或把术语BOUND当实测保证。该补强无需新增数学计算。

## 5. 数值资格与未解析结果

全部918已有prior先做身份/完整P24→P6映射及数值资格，不按相位收益选择。正对角自然尺度比较保留微小方差，零对角对应整行/列须精确零；沿用冻结symmetry/PSD和SO(3)容差，不jitter、截谱、删cross、normalize rotation或修复矩阵。Rbar须SPD，否则UNKNOWN诊断未解析。数值PSD门通过不是物理PSD/可信度校准。

映射误差、P24/P6数值PSD、Rbar SPD及finite中间运算错误按预登记资格输出NA/原因，保留921主表；不放宽门或换参数。文件/身份/hash/重复键属全局技术失败，与数学未解析分开。必须防仅输入finite但归一化/HPHT/solve/trace中间overflow错误放行。

既有五点grid及epsilon=0 skip顺序、tie、T/J/J_over_T/continuous boundary全部原样。continuous existence不等于五点grid选中非零，也不等于找到最优更新；Young族无改善不证明所有未知相关算法不可能改善。各目标不择优包装总成功，无跨块累加信息。

## 6. 最终源码、计划和局部资格

完整静读481行adapter，冻结SHA-256为55822aae95d650bdccfb169bd703f065f100b0384c05d22122ca081c2d3c227e；科学计划检查版本SHA-256为0a0bd6af80766bbe614015251f290619c91f5963930de64ced992f1b690b8efa。后续根代理仅补入局部资格回执pin/登记状态，不改变数学范围。预算918个已有prior资格、857固定交集、1714次diagnose、921主表和四目标上限3428行相符；phase/prior/ledger输入单次读取并在解码前核SHA。没有原provider/NPZ/raw/reference/NAV读入，没有新残差或导航更新。

初稿中发现的start_dispatch_ordinal与conditioning ledger ordinal混淆已修复。最终join按唯一ARC_START+block检索真实ledger entry并核source bits/U/R；END绑定其前缀并与life/prior/phase身份一致。完整prefix与within-clone-interval来源标志分列，不把区间计数0当prior在线因果证明。Rbar核对已按原提案固定自然尺度2e−10，exact-zero行要求不变，不按失败修矩阵。

所有918 prior先数值资格，模型不齐61也不跳过此门；仅合法交集进入两次UNKNOWN诊断。非有限/PSD/SPD/映射数值失败保留块和NA；身份/hash/文件错误全局停止。qualification明确LINEARIZED_WORKING_SURROGATE_ONLY、非线性余项及物理矩界未资格，未来源计数只报告不门控。4目标、原epsilon网格/tie、重复joint/current一致性均沿用已测试core。既有core登记0cd9772的12项合成资格保持，不重跑。

新增 tests/paper_rebuild/test_arc_phase_real_information_adapter.py 有3个固定pytest items，SHA-256为36eabb44dbcaa83bcf9688abc4e61ec1e71149bd9da23368e0b7449a40fe7778：

1. 独立赤道解析Cne/J1与含position-attitude/clone cross的合成P24，按显式误差分量核P6；END corrected C0和C1匹配，证明丢位置项会改变该fixture。
2. 缺J位置项、缺B位置项、错误C1、非PSD完整P24均返回UNRESOLVED且原输入不变。
3. 合法join特意使用START source dispatch=1但ledger ordinal=3，防两个计数混用；错误schema、相邻binary64端点及错误SHA必须拒绝，SHA门早于JSON解码。

固定包含5次qualify_prior、1次显式frame_jacobian、3次join及小型合成metadata hash；没有diagnose或真实输入调用。根代理已于a33851c登记后首次执行3项，全部通过，pytest报告0.47 s；没有修源码后重跑。本agent没有执行这些测试，局部结果事实来自根代理登记执行回执。

最终结论：没有剩余阻断科学问题，可由根代理完成最终pin/登记后进入这一次条件线性工作信息读出。此资格不是读取结果本身，更不是相位准入、物理误差界、连续可信航向或导航收益。任何参数、目标、R处理或读取范围变化需另登记，不能执行后放宽。
