# 候选敏感性：R5W、R5SIGMA、B3 的原身份

这些材料来自 `<CLEAN_ROOT>/stages/CLEAN7_T5BC_V3_CANDIDATE_PILOT/07_AGGREGATE/`，由 V3_REPORT_SOURCE_INDEX 的 sensitivity_pilot/subset/summary 明确引用。正式 Protocol V3 的持续航向使用冻结 R5 规则，native 身份独立；F01 不启用持续航向，F04 是双 fixed raw HPPOSECEF 标量航向；本节候选不是正式 F04 的替换版本。

## 表的组成与失败

PILOT_TABLE_V3/V2 各 36 行：9 个 frozen v2.1、6 个 T5A R5、15 个候选、6 个 LC 引用；34 COMPLETED、2 AVAILABLE_GEOMETRIC_AUDIT_FAIL。SUBSET61_TABLE_V3/V2 各 305 行（FROZEN_V21、R5、R5W、R5SIGMA、B3 ×61），292 COMPLETED、12 NOT_RUN_ALGORITHM_FAILURE、1 NOT_APPLICABLE。

最终展示提取的 T5BCR_REFERENCE_THREE_SEQUENCES 每版 15 行：B3 的 F02/A04/F04×三序列九行，R5W/R5SIGMA 各三行；REFERENCE_SUBSET61 每版 183 行为三个候选×61，TAIL_SUMMARY 六行是三个候选×H/yaw。每候选有限 58/61。W/σ 的 D27/D60 DIVERGED，D57 NO_VALID_HEADING_INPUT；B3 的 D57 是 NOT_APPLICABLE，不能改成成功或普通失败。

候选 paired frozen 只有 57 个共同有限 case。RUN_00004 这样的 run_id 在不同候选根复用，必须用 stage+variant+case+root 才有完整物理身份，不能只用短 run_id 拼接。T5bc 历史执行/续作的 code freeze 分别为 `b0a9230f0711c7b81af9d868a98d0eb537ad6eb9` / `e54df899db74ff8c11e37e09803c296965bfafba`，它们不是正式 V3 或统一 v2.1 的 source 身份；旧 HARD_STOP 与后续 PASS_T5BCR_COMPLETE 均保留；旧 261 native、494 实际评价进程、518 槽不加入 A 层正式计数。

## 实际候选定义

来源 `<CODE_ROOT>/configs/paper_rebuild/hext/T5BC_CONTRACT_V1.yaml` 的 D2/D3：

- R5 固定 std 标记 2.933193°。
- R5SIGMA 采用 BY2 1 s 滞后差分残差定义 sigma=sqrt(Var(residual)/2) 得到的常量 std 2.026119195812087°，不是各 case 调优。
- R5W 使用 degrees(0.40311929221090503 × sqrt(pAcc1²+pAcc2²) / 0.35)。
- B3 的 z=p2−p1，预测 Cnb[0,−0.35,0]（FRD），协方差为 k_b²(pAcc1²+pAcc2²)I3，k_b=0.4350071485556226；标量 yaw 关闭。

这些量使用 BY2 标定后应用三序列，原 HV 仍沿旧 1 Hz 支持。D1 原 yaw/A1 故障列由 D2 替换，不能以名称相同就说每个候选保留了所有原 yaw 故障。B3 是结构不同的候选，不能靠敏感性表宣称它已经修复正式版本的倾斜近似。

## 原数字与取舍

|候选 F04|BY2 yaw RMSE (°)|BY2H|BY2O|
|---|---:|---:|---:|
|R5W|1.8972596973175209|1.961058509301035|2.2467811457943987|
|R5SIGMA|1.8570683472786316|1.9758522094858635|2.3112956895809607|
|B3|1.928668136706766|1.8285574481592226|2.517171899391886|

原预注册选择记录给出的三序列和：R5=6.2538569227651107、σ=6.1442162463454558、W=6.1050993524129546；原改善量分别 0.1096406764196549 / 0.1487575703521561，小于当时 0.3 的标准。这里转录原选择值，没有本轮重新优化或按序列挑不同版本。

|候选，SUBSET61 有限 58|yaw median (°)|yaw P95 (°)|worst 5% mean (°)|max (°)|
|---|---:|---:|---:|---:|
|R5W|1.8972003167290268|1.9225082543066605|1.942347539049934|1.9443388858516877|
|R5SIGMA|1.857001327687724|1.8834986136087621|1.9790286071852863|2.011632624619754|
|B3|1.9285758869857743|1.9519367281582527|10.168424074685419|14.314418781235302|

worst 5% 取 ceil(0.05×58)=3 个有限 case 的均值，与 P95 阈值不同。B3 的 P95 看似靠近另两者，最坏三个均值明显更大，说明不能只看单个分位数。H median 对 W/σ/B3 为 0.09795279057859552 / 0.09807938016398715 / 0.0979785453676891 m，均值约 0.410 m 仍受尾部影响；失败不能当零误差补入。

逐单元格来源见 `secondary/SENSITIVITY_SOURCE_CELLS.csv`，输入读取记录保留原路径、版本和行数。这些是最终展示引用的层 B 敏感性材料，不是额外三序列独立实验，也不是本轮新结果或已完成文献复现。
