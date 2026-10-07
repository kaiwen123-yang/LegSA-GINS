# 两端未固定相位：信息增量资格与独立 ARC clone 方案

状态：数学/源码方案及局部源码已准备，合成数值与测试尚未执行。先完成有限合成资格；真实 native 预算尚未登记，本文件不授权真实执行。

## 问题与已有证据

已封存 921 个不重叠五历元块，860 块具有连续物理弧的合法消 N 对比；61 块端点模型缺失。固定块首/块末约相隔 0.8 s。旧几何读出不含姿态、joint attitude P、跨时 Q01、state/noise cross，也没有真实 arrival/model-ready 时间。860 个合法对比仅为观测代数资格。

本轮最小问题是：在显式两端姿态和同一条件信息集下，当前相位对比对已有联合姿态不确定性增加多少**工作模型信息**？独立假设下的条件收益、给定 cross 下的条件收益和未知 cross 的鲁棒工作界必须分列。不求方向点、不固定整数、不反馈导航，也不把 prior 补足的秩归因于相位。

## 1. 局部模型与 gauge

取 ECEF 左扰动 e=[δθ0;δθ1]，以 true-minus-working-nominal 为误差符号。两端必须绑定同一 `conditioning_information_id`；给定 C 的协方差支路明确假设该信息集下 e/n 中心化零均值。未知 cross 支路改用围绕 nominal 的二阶矩上界，必须覆盖偏置。完整 P6=[[P00,P01],[P10,P11]]。不给 P01 的接口应拒绝，不能用两个边缘自动拼成独立 prior。给定同一 body frame 的固定物理基线 l，bi=Ci l，

    h = G1 b1 − G0 b0,
    H = [ G0 [b0]×, −G1 [b1]× ],
    residual = z − h = H e + n.

H 沿用 arc_phase_difference.py:397–416 的 prediction Jacobian 符号；测量误差约定与 attitude_clone.update_measurement 相同。真实基线安装误差、同步、anchor/LOS 误差不是此六维姿态模型已经解释的量，须进完整误差模型或明确留为未资格。

对任意 G0/G1，两端各绕自身基线旋转不可由单根基线观测：N 至少包含 [b0/|b0|;0] 和 [0;b1/|b1|]，H N=0。H 的姿态秩至多 4，不能沿用自由两端基线的 rank6 宣称两端姿态全可观。静态 b0=b1、G0=G1 时，公共旋转 [v;v] 也被抵消。微弱几何改变产生的小奇异值须报告实际工作信息强度，不能用机器阈值的 rank 跳变宣布绝对 yaw 已解。

保留完整 6 维矩阵；不给 gauge 加虚构观测、jitter 或独立姿态先验。H 的明确几何零空间与 supplied P 的数值零空间分列。有限 P 是已有 proper 工作 prior；若真正先验在某 gauge 上不适定/无界，不能用 P=0 或 pseudoinverse 把它伪装成确定，返回前提未满足。

## 2. 两层相关性不得混同

第一层是测量两端噪声：R=Q0'+Q1'−Q01'−Q10'。已封存 Q0'/Q1' 不给出 Q01'。条件界 Rbar=2(Q0'+Q1') 对任意端点 cross 的二阶矩成立，前提是 Q0'/Q1' 确实上界端点误差二阶矩；目前 RAWX 工作 Q 的该前提没有实测校准。

第二层是当前两端 prior 与这次对比噪声的 C=E[e nᵀ]。即使第一层 R 已知，C 仍可能由于复用 GNSS/PVT/相位、共同 anchor/安装/IMU 来源而非零。端点不重叠不证明块间独立，更不证明 C=0。native P 日志不能凭空提供 C。

接口强制选择以下模式，并保留 source_id、qualification_note、covariance_kind：

1. **WORKING_ZERO_CROSS_ASSUMPTION**：显式 C=0 假设、R 为 supplied working covariance。输出条件改善，不标物理独立。
2. **SUPPLIED_CROSS**：显式完整 6×m C，检查 [[P,C],[Cᵀ,R]] PSD；协方差/观测一致且 S 正定后，才给条件结果。
3. **UNKNOWN_CROSS_BOUND**：P、Rbar 为 supplied 二阶矩上界；不给 C、不执行独立 Kalman 结果；只报告完整 Young 上界与其工作资格。物理二阶矩前提不成立时，结果仍只能称条件工作模型诊断。

不同模式不能把同一个 unknown 当成 zero；Rbar 不能自动改名为已校准协方差。缺测量时域 cross、state/noise cross、真实可用时标的事实必须原样进入输出。

## 3. 最小信息读出

给定 C 的条件模型用

    S=HPHᵀ+HC+CᵀHᵀ+R,
    K=(PHᵀ+C) S⁻¹,
    Ppost=P−(PHᵀ+C) S⁻¹(HP+Cᵀ).

这是给定二阶矩下的线性估计误差协方差；要解释成观测后的完整条件分布还需 joint Gaussian 等前提，本工具不声明该分布。给定 C 的 joint PSD 只核代数一致性，不证明真实来源 cross 已资格。

同时复核完整相关 Joseph 式：F P Fᵀ+K R Kᵀ−F C Kᵀ−K Cᵀ Fᵀ。现有 attitude_clone.py:206–259 作为独立 oracle，在合成测试中将六维状态嵌入原 21 维；不修改其源码，不在真实数据上伪造时间触发更新。

输出完整 P/Ppost/ΔP、当前端 trace（Wcur=diag(0,0,0,1,1,1)）、两端总 trace（Wjoint=I6）、公共/相对 ECEF 扰动投影 trace，以及用户显式提供且预先固定的 PSD W。投影协方差下降可以来自 prior/cross 相关性传递，不等于相位直接观察该 gauge。直接测量几何 HN 和在 C=0 假设下 HᵀR⁻¹H 单列；已知 C 结果不能冒充纯几何信息。

未知 C 用完整原 Young 族：

    Kε=PHᵀ(HPHᵀ+Rbar/ε)⁻¹,
    Bε=(1+ε)[(I−KεH)P(I−KεH)ᵀ+KεRbarKεᵀ/ε].

只检查固定 ε={1/64,1/16,1/4,1,4} 和连续存在性条件 T=tr(WP)、J=tr(WPHᵀRbar⁻¹HP)。T>0 时 J>T 当且仅当连续族存在严格 trace 改善；另列原浮点 tie。此最小内核不实现连续 optimizer，不把“存在改善”写成已找到最优更新。T=0 不计算 J/T。两种 W 的结论可不同，全部保留。

实际最小实现采用测量空间完整谱 `Rbar^(-1/2) H P Hᵀ Rbar^(-1/2)`，无须求 P 的伪逆或支持重构。R/Rbar 必须正定才能完成本次白化，否则 UNRESOLVED；不添加 loading。保留所有正谱贡献；数值 rank 仅诊断。不从 mixed-unit 全矩阵阈值截去小正特征值，不给 S/R 加 loading；分尺度检查 T、J、完整目标。如果谱重构或 PSD 资格不能可靠成立，报告 UNRESOLVED、相关推断 NA。可用直接完整 P 公式计算目标时不依赖谱截断；不认证 Gmax/零噪声极限。

## 4. 当前 native 不能直接声称被动 clone

源码证据：

- gnss_file_loader.cpp:224–298 按精确 double 时间合并 PVT 与 carrier；invalid carrier 仍在输入事件表。
- gi_engine.cpp:678–690 对无 PVT 且本次不使用 carrier 的行直接 continue，不构成传播边界；“输入存在”不等于已处理的精确姿态时点。
- gi_engine.cpp:692–709 插入新时点会切分 IMU 增量/测量 dt；不能把最近 IMU 姿态当 RAWX 端点，也不能预称插入事件不改变原轨迹。
- gi_engine_attitude_clone.cpp:108–134 的现有 foot 接口要求足端身份/接触 episode 和 0.1–0.15 s；不得把 0.8 s 相位块伪装为足事件。
- gi_engine.cpp:526–532 在 active clone 时换为 24 维 Cholesky 普通更新；:569–597 在 clone mode 非 off 时启用完整 covariance reset。直接启用旧 NULL_CLONE 与旧 PVT_CONTROL 的矩阵计算路线不同。

因此真实后续应使用**独立 ARC 事件/clone 身份**，复用 clone 代数但不复用 foot 输入字段。先固定三窗同一 ARC 时间表，ARC_NULL 与 ARC_TELEMETRY 两臂均做相同增广、24 维普通更新、完整 reset 和边缘删除；唯一差异是输出只读诊断。每窗 NAV、STD 及已有状态事件必须逐字节一致，未通过不得解释 P。旧 PVT_CONTROL 单列历史身份，不能当 matched NULL；与旧轨迹若不等也不得重新命名成一致。

可以另做真正旁路 observer，但它必须复用原实际 K/Phi/reset 约定，还要解释旧 mode=off 缺少完整 covariance reset 的近似。当前不选择此较大实现。准确排查旧端点实际覆盖率需要专门的已封存调度元数据对齐；本次只读代码，不宣称 860 块原先已有精确姿态时点。

## 5. 独立 ARC_SOURCE_EVENTS 格式与固定时序

后续 event schema 与 phase 观测数值分离，建议 JSONL：

    schema, sequence_id, block_id, endpoint_id, role(START/END),
    source_time_s, source_time_scale_id, time_mapping_source_id,
    replay_execution_time_s, actual_available_time_s(null),
    availability_mode(SOURCE_TIME_REPLAY_ASSUMPTION),
    schedule_source_id, saved_block_status, endpoint_model_fingerprint(null allowed).

source_time_s 是封存 RAWX 标签映射的精确端点时刻；replay_execution_time_s=source_time_s 仅为历史 source-time replay 假设。实际 arrival/model-ready 缺失仍为 null，绝不能把 replay 字段当真实 available。native 只读时刻/身份，不读 z、G、Q、整数、参考或误差。

时间表保留原 921 块、每块 START/END，非重叠，唯一 block/endpoint ID；61 模型缺失块仍保留调度与结果，不能事后按可改善程度选块。开始在该时点原普通更新完成并 full feedback 后建立确定性 ECEF clone；区间内普通观测对 clone 做联合条件更新和 reset。结束同样在原普通更新/feedback 后、任何新相位消费前记录联合状态，然后只取当前边缘退休。遇到初始 IMU 支持不足/缺失、时间冲突或不完整块，记录未覆盖，不造历史姿态。两臂事件优先次序一致且事先固定。

不重叠使单个 clone slot 足够；但没有建立跨块相位噪声独立。本轮真实方案不消费相位，不存在将 860 个候选结果连乘的信息累计。

## 6. 为 860 块补的必要日志（仍非充分物理资格）

每个 END 至少保存：

- block/两端/clone ID、端点模型指纹、exact START/END 和实际 state timestamp、事件处理顺序、原 source IDs 及登记 config/binary/source hashes。
- END 当前21+clone3 的完整 P24、dx24、state ordering/单位/误差符号；START 的 P21 与增广 J0 供审计。不能只保存姿态方差或 P00/P11。
- START 原 C0 和 END 时经区间普通观测修正的 clone C0_given_end、END C1、各自姿态 frame/reset 定义。信息线性化必须使用与 END P24 同条件信息集的 C0_given_end；不能配上未更新的 START nominal。
- END 当前 cbn、BLH、ECEF C1 和 J1=[−NED_frame_connection at position, cne at attitude]。从 P24 构造 P6 的映射为 B=[[0,Iclone],[J1,0]]，P6=B P24 Bᵀ；ECEF 姿态含位置相关 frame 误差，不能仅抽 PHI 两块。
- 已消费测量身份/来源 ledger（或可重建清单）和时间区间内普通更新/完整 reset 次数，识别同源 phase/PVT/anchor 已使用的可能性。仅来源名称不等于已知数值 C；C 未知仍未知。
- 固定物理基线向量/坐标系/安装来源，以及 actual availability 的 unknown 标记。Q0'/Q1'/G0/G1/z 留在已封存模型，native 不读；全部原生输出封存后才允许离线按精确身份对齐。

这些日志足以形成**条件工作 P** 的两端诊断；不会自动证明 P 上界真实误差、R 实测覆盖、C=0、相位故障可信或在线可用。默认真实读出只能使用 UNKNOWN_CROSS_BOUND 条件模式。独立假设若列出必须标反事实工作敏感性，不能作准入。

## 7. 局部预登记预算

新文件仅 `src/legsa_gins/paper_rebuild/carrier_phase/arc_phase_information.py` 和 `tests/paper_rebuild/test_arc_phase_information.py`，不改已封存 arc/foot 更新源码。一次 pytest 进程，12 个固定合成 test items，单线程，60 s 上限，0 native/evaluator/CILS/raw/reference/真实诊断，0 参数扫描，0 自动重试。原始 stdout/stderr/JUnit/源 pin 和首个失败必须保留。技术修复后只允许根代理重新登记受影响项目；不得擦除首次记录。

1. SO(3) 有限差分符号及两端 baseline-spin gauge。
2. 静态公共旋转 gauge、相对扰动有信息，完整 gauge 保留。
3. 弱几何变化可改变数值 rank 而信息增量仍可任意小。
4. 完整 P01 与丢弃 P01 的不同结果；接口不默认独立端点。
5. C=0 条件后验，对照标量解析解及原 attitude_clone oracle。
6. 合法 dense C 的联合条件式、相关 Joseph 式和原 oracle 一致。
7. C=−PHᵀ、R=HPHᵀ+I 抵消反例：有 H 但 K=0，无新增信息。
8. 未知 cross 的 Young 条件及完整 PSD 上界，对照固定 seed=20261007 的 16 个合法 latent cross；这不是随机覆盖证明。
9. 奇异 P 的确定性 clone/gauge，以及奇异 S 必须未解析/拒绝，零 loading。
10. 小正方差配大 W 的足诊断反例，保留分数质量，ω=0 精确 T。
11. 旋转及单位坐标变换下完整公式/目标一致，W 必须协变。
12. 来源/模式/维度/非PSD/nonfinite 及 finite-input 中间 overflow 拒绝，真实 availability 缺失保持 NA、不准入。

新内核不需要真实姿态或相位，测试不读 saved DETAILS。新源码已实现，测试源含 12 个固定 test functions；仅完成 AST 静态语法/数量检查，未 import 新内核、未 pytest、未执行任何合成数值。源码及精确测试参数将随冻结登记，测试执行仍待根代理。后续真实预算仅为提案：最多三窗×(ARC_NULL,ARC_TELEMETRY)=6 native、0 eval；C++实现、source-time replay合同和身份门仍须另行登记，当前不启动。
