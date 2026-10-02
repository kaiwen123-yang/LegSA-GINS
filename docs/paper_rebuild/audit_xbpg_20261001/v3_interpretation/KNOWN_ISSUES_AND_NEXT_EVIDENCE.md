# 把既有问题连到结果，不预判实际影响

本轮保留原 `FINDINGS.csv`、`FORMAL_CONTROL_REVIEW.md`、`PYTHON_INPUT_REVIEW.md`、`PYTHON_EVALUATION_REVIEW.md` 及覆盖表，未修复或重做其合成诊断。`ISSUE_RESULT_MAP.csv` 将正式适用性、可暴露方法/工况、已有证据、缺失变量与受影响表图分列。

正式 native 源为 `ca73cb1fb48a020fd2a450d79e520562c34eeb24`；原审查 FINDINGS 行引用 `eb3cbed314693358c7c38442b6fbbb7afcf0342e` 的行号，并已记录 non-B3 实现与正式源相同。这个源码关联支持适用性，不证明正式运行实际触发。runner、evaluator、RUN_MANIFEST 的 source_commit 字段按方法说明书分别保存，不能拼成一个通用版本号。B3 和旧 N03/N25 的候选分支不升级为正式 F04 主结果。

## 优先对象一：调度、支持与 A1/A2

N09 的静态路径把 RD/HV/RP 尝试放在有效 GNSS 事件内，nearest 复用/可用时刻仍须核对。正式可暴露方法为 F04、A03–A08；F01/F02/F03/A09 没有这些辅助通道，不能一并声称触发同一问题。

A1/CORE D06/D57 适合界定调度边界；A2 保留有效 heading 的历元可继续进入事件，不能把 A1 的静态条件直接套到 A2。已读时序支持“何时误差变大”的描述，也保留了全窗和中断窗不同的数值；仍缺 GNSS 三有效位、辅助 row_id/available_time/consumed、具体更新分支与接受时间。因此状态为 **APPLICABLE_BUT_TRIGGER_UNVERIFIED**，不是已证明所有 A1 误差由 N09 造成。

最小后续对象是一个已注册 A1 case 加同 seed 的 A2 对照，先查是否存在同身份调度/接受日志；不存在时，只有另行授权的专门机制测试才能回答触发次数。不在本轮重跑或恢复矩阵。

## 优先对象二：SA 创新与尾部

N12 在存在前序更新时使用 dz 而非 dz−Hdx 的 NIS 路径，适用 SA 开启的 F04/A03/A05/A06/A07/A09。F04−A04、A09−F03 是相应配置开关入口。已有 D15/位置 std/混合故障的 yaw 尾部改善与部分 H 升高并存，只是结果现象；source_aware_touch_count 不能还原每步创新。

最小缺失证据为同一事件的 dz、H、dx、P、R、NIS、scale/reject 和更新次序。先选 D15_seed_00 的 F04/A04 和自然 C00 的相同对照，避免事后只选收益样本。现有保留误差复算一致，不证明这些内部量符合数学定义。原问题仍待定向核查，不修改标签或正式源。

N16 的 HV std_D=999 与 SA 交互只覆盖 SA+HV 的 F04/A03/A05；A04 关闭 SA、A06 关闭 HV。需要实际 2D/vertical-disabled 处理、effective R、maxStd/caps 的前后值，才能知道哨兵是否影响横向缩放。开关回显不是触发证据。

## 其他源级风险与证据界限

- N11 异步杆臂速度路径适用 RV/RD 方法，F02 不调用二者。要有 IMU bias/scale/dt、杆臂、res 分支及观测时刻，才可统计实际影响；旧 toy 的约 0.152882 m/s 不是正式 V3 的实测偏差。
- N15 的缺失数值默认零风险涉及 RP/RD provider，覆盖 F04/A03–A08，需先读取同身份 provider 的 active/有效位及原字段质量。正文 error_series 有限不能证明输入没有坏字段，也不能由缺测断言加载为有效零。本轮未全扫 provider payload。
- N01/N02 的基线投影转 yaw 与标量 H 倾斜近似覆盖持续标量航向方法（除 F01）；F01 的公共初始化双天线链另列。需实际 roll/pitch、天线向量、P 交叉项与接受记录。保留的 roll_err/pitch_err 是误差，不是实际姿态，不能拿它们代替倾角验证。
- P-PROV-01 的“新 raw 主航向、HV 仍用旧 status 航向”是已确认 lineage 事实；依赖相关性和支持差异已解释，误差影响大小尚未识别。

## 控制与评价身份不能从数字一致性推出来

CTL-03/09 的恢复身份门、CTL-08 的 bookkeeping、CTL-04 的实际子进程计数、CTL-10 的访问证据均保留。旧控制审查部分针对 clean6 v2.1 路由，必须先确认正式 V3 使用哪条路径；不能将旧模块的夹具反例直接判成 V3 每个 run 的实际身份错误。此前 6,468/12,936 总账关联减少某些缺行疑问，但不是每个恢复分支证明。

CTL-01/P-EVAL-04 提醒“有限、单调、位于窗口内”不等于全窗覆盖。本轮保存实际 time_start/end、dt 分布及 matched 支持；matched/output 的 coverage 仍不是期望窗口覆盖。对已释放 NAV 的运行，本轮不能从 error_series 推断未导出的 output/failed-match 历元。

P-EVAL-02 的 reference 重复时标和无最大 gap 插值门属于静态定义风险。本轮未读取原始 reference，不知道实际 reference 是否触发；误差时标无重复不能替代输入参考审查。P-EVAL-05 则已确认 v3 位置物理点变换不同时传播 STD 的杆臂/姿态协方差，故 3σ 只能沿旧诊断定义，不能称为已校准 POI 置信区间。

`CLAIM_EVIDENCE_MATRIX.csv` 将真实手稿文字、完整精度原值、反例和缺失量对应。它区分作者已经写出的限制、展示文字确有差异以及未验证机制；没有把旧问题当作全部既有结果错误的证明。

本轮结束后可以先修正解释文字或补齐分母；进一步只读输入/评价源核对、机制测试、独立版本重跑属于不同授权层次。此处只列最小对象，不调参数、不插桩、不恢复 solver/provider/evaluator。
