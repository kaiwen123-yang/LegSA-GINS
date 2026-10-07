# 载波同弧差分：921块真实保存模型资格独立复核

结论：本次登记遍历全部921个固定块，860块通过同物理弧差分的代数/保存metadata资格，61块端点模型不可用。731个合格块的末端没有旧singleton，659个合格块的五个原始时槽都没有旧singleton。这证明已有数据中存在未固定整数的差分观测机会；未证明这些机会已形成可信航向，更未证明导航收益或真实载波中断被跨越。

## 1. 审查范围与运行身份

唯一stage：<SCRATCH_ROOT>/TRUSTED_HEADING_CONTINUATION_20261007/ARC_PHASE_SAVED_MODEL_ATTEMPT01。登记/执行commit均为4754bb184cd712290fb37cad4728c6097eccdbf2。实际回执returncode=0；输出COMPLETE状态为COMPLETE_SAVED_MODEL_GEOMETRY_QUALIFICATION_NOT_NAVIGATION。

本审查只读取小计划、完成/访问回执、全部921行OPPORTUNITIES与三份压缩DETAILS，做字段计数、索引/指纹唯一性及hash身份核验。未重跑任何脚本、模型构造、几何/协方差求解、整数求解、测试、native或evaluator；未读原始数据/参考/大ARC_EVENTS历史/大模型PLAN/端点NPZ。下述模型来源资格由已审源码、登记pin、原seal及运行访问审计构成，不冒充第二次处理全部源模型。

最终适配脚本hash为6974da4b477e8e340278fae3d71512547307e995b59269b5594681037341fb9e；内核为3898eb95f2621f483c80ecd0d67b9fd6dcf27135673a755b11f8650a7d66ef12。两个文件实际hash与登记source pin匹配，且字节等于登记commit；计划字节也等于登记commit。相较静态审查，最终路径明确旧prepared/singleton在20261006、新out在CONTINUATION_20261007，固定输出仍不能换目录规避尝试预算。

COMPLETE中的SUMMARY hash c431e00ddb34ac4f62015a07a199161f07b5c8e51e03af217544c8d2d907fb54 已与实际小文件核对；SUMMARY中的OPPORTUNITIES及3个压缩DETAILS hash均与实际文件相等。三份原MODEL_OUTPUT_SEAL实际hash均与登记计划相等，complete_preparation均true；其files中PLAN.json的hash与本轮登记的原计划pin相同。没有重复hash或重新解码巨大科学payload。

## 2. 全分母与端点消费

|序列|原时槽|固定5槽块|合格块|端点不可用|末端无singleton的合格块|全5槽无singleton的合格块|使用/唯一端点数|
|---|---:|---:|---:|---:|---:|---:|---:|
|BY2|1370|274|240|34|209|185|480/480|
|BY2H|1350|270|243|27|176|150|486/486|
|BY2O|1885|377|377|0|346|324|754/754|
|全部|4605|921|860|61|731|659|1720/1720|

逐行block_index完整为0至原块数−1，first_epoch_index=5i，last_epoch_index=5i+4。各块时间严格递增且互不重叠，区间约0.8s。全部4605个时槽各归属一个固定块，没有按旧singleton结果选块、滑移端点或删去61个失败块。所有860合格块的五个模型时槽也均built；输出没有SOURCE_TIME_GRID_GAP或NO_CONTINUOUS_RELATIONS类别。

三份DETAILS行数、块号、状态与CSV一致；每窗所用两个端点的epoch fingerprint全部唯一，其数量等于唯一端点索引数。外部访问审计同样报告1720次成功NPZ打开和1720个唯一NPZ路径。这里的“不重复”仅指本次固定差分的端点消费，不代表不同时块统计独立，也不代表与历史方法或现有导航状态来源独立。

全部860合格块的当前几何G1数值rank为3。两自由基线[-G0,G1]的数值rank分布为849个6、8个5、2个4、1个3；后11个均在BY2O。不能把这个代数rank当两姿态rank或绝对heading可观性，尤其不能从浮点非零奇异值直接推断有用精度或良好条件数。

## 3. 因果、访问与NA边界

全921行的actual_available_time_s、actual_latency_s、joint_covariance_m2、direction_point_ecef、attitude_rank均为空/NA；cross_time_covariance_known、between_block_independence_known、covariance_calibrated、navigation_admitted均false。合格DETAILS统一标为OBSERVATION_ALGEBRA_ONLY_NOT_TRUSTED_HEADING_OR_NAVIGATION。保存的metadata连续资格不能认证没有未检测到的物理slip；缺旧singleton也不等于原始载波丢失，本次同弧差分仍要求连续物理弧的保存证据。

摘要记录读取3份原seal、3份原模型计划、3份arc metadata、3份旧singleton表，1720端点NPZ；仅860次geometry及860次条件bound构造。0整数搜索、0native、0evaluator。两个端点Q仅是旧RAWX工作模型；2(Q0+Q1)只在这些端点矩阵确实上界误差二阶矩时成立，本轮没有建立这个物理前提，更没有处理state/measurement或between-factor cross。

已读取root生成的ACCESS_AUDIT，状态PASS：4646条openat、0未解析，科学打开仅在两个固定旧输入stage及新输出stage，raw观测/导航文件打开列表为空、reference打开0、科学越界写0。该审计的trace hash已独立与保存strace核对为882df20022f8366409ebd5ef4f1f8145bdc2792be0c44dd145ecc60851a95f2d。本审查未再次实现/运行完整路径解析器；访问结论限于已跟踪的openat/execve，不扩大为所有可能系统调用证明。

## 4. 科学判断与后续门

860/921是保存模型中的结构资格比例，不能当可信航向覆盖率；731/659是与旧singleton的机会交叉表，不能当新增有效方向点或导航收益。此次尚未生成可入滤波器的方向测量，也未做输出误差评价。真实slip/fault的拒绝、撤销、重接纳，可信误差上界与实际availability仍是进入导航前的必要工作。

下一步宜先登记有限的相位故障准入/撤销测试及来源明确的不确定性资格，验证短同弧差分如何提供有用的方向变化约束并处理来源相关性；不能从本表直接把全部860块注入导航。独立方向参考与实际转动/支撑变化/遮挡采集仍未完成。
