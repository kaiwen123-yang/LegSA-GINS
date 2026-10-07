# 足端信息诊断真实回放：独立结果审查

审查者：research-map 独立代理。结论：在登记的同一工作模型、全相关 Young 上界族及固定加权 trace 目标下，三个原 PAIR 窗口的 2510 个事件全部连续无收益；原有限 epsilon 网格漏解不能解释这次全部 SKIP。没有新的足端导航收益证据。

## 1. 范围与证据链

登记 commit：714934f557607f79588c4e2dfd0b32db4ba373e2。唯一 stage：<SCRATCH_ROOT>/TRUSTED_HEADING_CONTINUATION_20261007/FOOT_INFORMATION_TRIAL_ATTEMPT01。

已独立读取登记计划、三窗小回执、旧/新 native seal、READOUT_COMPLETE、全部 2510 条 EVENT_DIAGNOSTICS 和原事件 CSV；独立完成计数、J/T及门限裕量归并、时间对应、配置字节比较与小元数据 hash 校验。没有调用诊断脚本、readout、native、evaluator、测试或任何科学求解；没有读取原始/参考数据，没有重新 hash 大 NAV/STD/dump。

计划源文件 hash 412ffe58acb980697823e0942f3ef4afe5ea5c1ca714101656cf9900ad5c4160 与登记 commit 的原字节相同。stage 内 REGISTERED_PLAN 是别名展开后的执行副本，其文件 hash 本来不应与源计划相等；实际注册链已核源文件而非误比较展开副本。

新 ALL_NATIVE_SEALED hash 为9e061caab68272f61a9f5246480db3b62b0bc408c47b5bb66f70cb0679d65d7f，与 READOUT_COMPLETE pin 相符；seal 的 plan hash 与 PLAN.json 实际 hash 相符。旧 seal hash 为50f53f871627704c1ceae76d8597e484419a12a6052e21614ea58336f8693397；三个 old NAV/STD/event pin 均直接对应旧 seal.files。新 seal、三 RESULT、旧 pin 中这些 hash 完全一致；新 RESULT 小文件实际 hash 与新 seal 相符。此为对既有封存身份链的独立核对，不冒充再次重算大文件 hash。

三窗配置与原 PAIR 配置逐字节一致。三份回执 returncode=0、native_exec_count=1、access_audit passed，raw/ref opens=0，stage 外写入=0。ledger 恰有3个唯一身份、retry=0；本轮实际3 loader、3 native、0 evaluator、3 offline readout。每份 readout 产物时间晚于全三窗 native seal。

## 2. 全分母核读结果

| 窗口 | 事件数 | J/T 最小值 | J/T 最大值 | J/T 中位数 | 最小网格 score−T |
|---|---:|---:|---:|---:|---:|
| BY2 | 687 | 4.30896042e-10 | 1.55992972e-9 | 9.03326595e-10 | 0.02013256265 |
| BY2H | 666 | 4.51174666e-10 | 1.58178709e-9 | 9.07851499e-10 | 0.02026714157 |
| BY2O | 1157 | 1.82439659e-10 | 1.69084641e-9 | 3.68790284e-10 | 0.01575073875 |

J/T 由每行保存的 J 与 T 独立相除，与保存 ratio 全部相同。全分母条件均为 CONTINUOUS_NO_IMPROVEMENT，未定/连续有益/网格漏解均0。所有 T 正；(T−J)/criterion_margin 的最小值为1.4660155012225e12，远离判据边界，不是舍入造成的临界 SKIP。

所有事件 continuous_omega=0、continuous_score=T、continuous_reduction=0、continuous_beats_original_skip_tie=false；native_applied=false、native_epsilon=0。每条原事件均 PAIR_YOUNG_EXACT_SKIP，prior_weighted_trace=bound_weighted_trace；诊断时间与原事件逐条相等、严格递增，未丢失或重排。三个时间范围为66.313063613–339.507058132、413.307058653–682.5051693480001、3186.909047776–3562.511059492秒。

所有2510条 spectral_full_model_qualified、native_sequence_verified、full_P_grid_action_verified、diagnostic_only_no_state_update 均 true。全五候选共12550个 native score 最大绝对差为7.105427357601002e-15；native T 最大差1.7763568394002505e-15、native J 最大差2.3065931381041177e-21。T/连续score谱一致性误差占各自容差最大9.79679876e-5，J谱误差占容差最大6.54751054e-10。记录中无丢弃的正 P 模态；原生五候选顺序、tie 与最终 action 的资格均通过。这里独立核读的是已封存诊断及审过的算法资格，没有再次执行矩阵求解。

所有事件数值 rank_H=2、rank_P_support=18；这些秩只描述本模型/尺度下的数值结构，不等于物理可观性证明。Gmax 和 fixed_grid_zero_noise_cap_below_first_cost 全部 NA；不能借数值谱截断推导“任意降低 R 也无效”。

## 3. 科学解释与下一步

对固定 P、H、R、W 且满足本次 PSD/PD 条件的 Young/CI 同族目标，f 是凸函数，原点导数是 T−J。此次 J 仅为 T 的约1e-10至1e-9，连续最优点仍是零；加密或连续优化 epsilon 不会把这2510个事件变成有利更新。此结论比仅说五个候选都失败更强，也明确限制在当前工作 covariance 与加权 trace 目标。

它不能证明足端物理观测无信息，不能证明任何更紧相关结构无收益，也不能把 covariance 上界的 trace 不降等同于真实航向不可能改善。当前 SDK 足点代理的来源、时序、body到IMU外参、接触/滑移与噪声上界尚未被独立标定；先凭结果缩小 R 或假定与已有 IMU/SDK 独立会破坏结论前提。

推荐停止本分支的 epsilon 网格调参。下一足端试验应由原始关节/FK、测时与接触证据建立可核验的误差来源/交叉相关或独立误差分量，再登记是否改用更紧模型；独立方向参考应覆盖转动、支撑切换与中断时段。新模型仍需证明它能提供额外方向约束、正确表达不确定性，并在独立参考与固定全窗分母下改善导航。此次被动诊断保持原 NAV/STD/event 身份，没有增加导航效果实验或有效航向观测。

## 4. 作者compact交叉核验

已读foot_information/{RESULTS.md,SEQUENCE_SUMMARY.csv,GRID_SUMMARY.csv,READOUT_RECEIPT.json}。3个输出pin与实际文件hash一致。4行序列表的T/J/JT极值和中位、分母/条件/动作/资格计数，以及20行网格表的相对代价极值和中位，均与从既有2510行字段独立聚合的结果一致；没有导入或调用任何科学函数。文中工作trace、候选代价、数值秩和来源限制与上述结论一致。
