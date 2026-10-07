# NMB1 成功足端因子之后的支撑 episode／SDK 重叠审计

2026-10-07；研究 HEAD 352843e。只读原 episode cache、足端 provider 和已完成 XYZ native 的实际接受事件；不运行 native，不读 reference，不扫描 raw，不改变二进制、测量或调度。

**结论：成功 END 后、两只旧支撑 token 尚未任一关闭的 SDK 接受时刻，只占全窗 59/1182（4.99%），主空窗 21/523（4.02%）。这些 SDK 的源时刻全部已在原两端点足因子区间之外。当前证据不足以把“扩大 SDK 排除到整个旧 episode 结束”列为优先实验，故撤回该候选，不运行它。**

同一 episode 只能说明可能仍有共同来源依赖，不能证明 SDK 重复消费原足端位移；episode 不同也不能证明 SDK 与足端独立。SDK 的内部滤波、惯性和运动学使用没有完整公开依赖图，本审计只量化这一项具体调度假设。

## 1. 输入和身份对应

分析目录：`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/NMB1_SDK_EPISODE_OVERLAP_01/`。

- `readout.py`：从源 episode 和实际接受日志生成以下逐项表。
- `SUMMARY.json`：全部输入 SHA、冻结 tracker 配置、汇总和尾部右删失清单。
- `SUCCESSFUL_END_EPISODE_CLOSURES.csv`：每个实际成功 END 的两足 token、关闭时刻和后续 SDK 数。
- `POST_END_SDK_SAME_EPISODE.csv`：每条满足旧足对尚未关闭的因子—SDK 关联；同一 SDK 可能关联多个早期因子。
- `SDK_RELATIVE_TO_LATEST_SUCCESSFUL_END.csv`：每个 SDK 只关联最近的先行成功 END，报告源时刻与消费 tick 上的 token 状态。
- `UNIQUE_TICK_LAGS.json`：以最近成功 END 为锚的去重时差；避免把长 episode 的多重因子链接当成多个 SDK 更新。

原 cache 是 `CONTINUOUS_HEADING_20261007/TRANSFER_FINAL_BODY_CACHE/NMB1_transfer_body_motion.npz`，SHA-256 `40146653b4b34f6e0bdac200b19116713030a959877476318e48195c347976a4`。原 provider 是 `SUPPORT_POSE_PROVIDER_NMB1_01/SUPPORT_POSE_EVENTS.csv`，SHA-256 `3f669ba88ca8fab1b98a51679496d956e7f09f00d3a986c8035340a4619de734`。实际接受取自 `SUPPORT_POSE_XYZ_NMB1_01/NATIVE/NMB1__REPLACE_SUPPORT_XYZ/` 的 `SUPPORT_POSE_EVENTS.csv` 和 `BODY_VELOCITY_EVENTS.csv`。

两者使用相同 tracker：FR/FL/RR/RL 顺序，force on=[34.2,33.8,30.6,32.0]，off=[24.8,25.2,23.4,24.0]，dwell=0.0120356083 s，最大源间隔=0.05 s。provider 的 opaque token 与 cache 的全局整数 token 通过原 START/END 逐足建立一一对应：3286 个映射点，身份冲突 0，时间差最大 0 ns；未从 NAV 或参考轨迹推定 token。

cache 末端 40972.403804661 s 之后，使用已保存的 `NMB1_SDK_INTERNAL_FRAME_01/NMB1_FULL_SOURCE_MOTION.npz` 足力后缀检查旧 token 是否关闭，不重新扫描 raw。最后 RR/RL 的两个 token 在 native 结束前未见关闭，因此对应 35 个成功 END 的关闭时刻记为右删失，统计窗口终点只作为上界，不能称为实际落足结束。全部实际接受 SDK 的源和状态时刻都在原 cache 范围内，因此这段后缀处理不改变 SDK 重叠计数。

## 2. 精确定义及去重计数

全窗为 [40621.403808498384,40972.56780471802] s，主空窗为 [40749.60018873215,40912.600195646286] s。计数使用已完成 XYZ 臂的实际 accepted=1 日志，不以误差或接受结果选择新片段。

对成功因子 END=t1，其旧足对首次关闭时刻为 min(close_i,close_j)。分别检查 SDK 原始 source_time 与实际 state_time 是否严格落在 (t1,first_close)；之后按 SDK 更新去重。该定义没有把因子自身的 RETIRE 当成真实支撑 episode 关闭。

| 数量 | 全窗 | 主空窗 |
|---|---:|---:|
| 成功足端 END | 476 | 242 |
| 实际接受 SDK 更新 | 1182 | 523 |
| 至少关联一个后续同旧足对 SDK 的 END | 72 | 21 |
| 去重 SDK：源时刻在同旧足对内 | 59 | 21 |
| 去重 SDK：消费 tick 在同旧足对内 | 59 | 21 |
| 源和 tick 均满足 | 59 | 21 |
| 占全部实际接受 SDK | 4.9915% | 4.0153% |
| 源与 tick 的归属判断不同 | 0 | 0 |

同一持续静态 episode 中可以有多个先前成功因子，所以全窗 72 个 END 关联 59 个 SDK，并不矛盾。不能把关联表行数当作独立 SDK 接受数。

以下时差每个 SDK 只用最近成功 END，单位 ms：

| 时差 | min | median | p95 | max |
|---|---:|---:|---:|---:|
| 全窗 source−END，n=59 | 79.971 | 92.012 | 96.177 | 98.011 |
| 全窗 tick−END，n=59 | 83.980 | 97.993 | 102.005 | 102.199 |
| 空窗 source−END，n=21 | 84.694 | 92.012 | 96.008 | 97.686 |
| 空窗 tick−END，n=21 | 88.732 | 96.036 | 100.003 | 101.998 |

去重重叠源时刻全窗从 40668.403794366 到 40972.203807807 s；空窗从 40765.201811717 到 40910.199796744004 s。主空窗成功 END 后旧足对剩余寿命 median=46.965 ms，p95=111.881 ms，max=130.004 ms。全窗有上述长静态末段；`SUMMARY.json` 中基于所有因子—SDK 关联的全窗 source 时差 median=1.694 s 是多重链接统计，不能代替这里每 SDK 去重后的 92.012 ms。

所有被称作重叠的 SDK 源时刻均严格晚于足端 END，未复用足因子的原始 START/END 行，也不在原两端点位移区间内。它们可能有内部历史依赖，但这种依赖不能仅由 episode 身份证明。

## 3. 旧 episode 已结束与新 episode

下面以每个 SDK 的最近先行成功 END 为参照，逐足比较旧 token 与 SDK 源时刻的真实 token。消费 tick 的分类计数完全相同。全窗另有 104 个 SDK 在首个成功 END 前，因此本表全窗分母为 1078；主空窗全部 523 个 SDK 均有先行成功 END。

| 相对旧因子的两只足 | 全窗 SDK | 主空窗 SDK |
|---|---:|---:|
| 两只仍是原 token | 59 | 21 |
| 一只原 token、另一只已 inactive | 4 | 1 |
| 两只都 inactive | 689 | 342 |
| 一只已进入新 token、另一只 inactive | 104 | 43 |
| 两只均进入新 token | 222 | 116 |
| 一只原 token、另一只新 token | 0 | 0 |

主空窗有 159 个 SDK 已有至少一只相关足进入新 episode，342 个对应足均已 inactive。多数 SDK 不属于旧足对的持续共同支撑块，不能把前一因子的共同位移约束无条件延长到这些时刻。

## 4. 为什么此处收口

重叠审计回答了调度机会数量，并没有证明删除这些 SDK 能修正物理均值冲突。同期共同状态读出显示，主空窗足端 END 大多扩大 XYZ 相对匹配 null 的水平速度差，而 SDK 更新大多收缩它；即使来源相关，也不能由此默认扩大 SDK 排除会改善结果。故不运行新的 episode 排除臂。

进一步的源字段审计还发现足端点位移与 SDK 自身 position 增量接近，而 SDK velocity 积分与该 position 有系统差异；foot_speed 与足点导数也存在支撑／摆动相位相关差异。它们均是内部一致性证据，不能作独立真值，但足以阻止把现有冲突直接归因为足端 bias 或真滑移。参见 `NMB1_FOOT_SPEED_SOURCE_DIAGNOSIS.md` 及同期 SDK position 一致性读出。下一步应先完成来源定义／相位覆盖证据，再选唯一因果诊断，不能按导航 H 的改善需求指定错误来源。

## 5. 未选用的共同偏差数学备选

该节只保留数学边界，不是实施决定。设 body0 残差 e_i=u+D(r_i1−l)−(r_i0−l)，D=R0ᵀR1、u=R0ᵀ(p1−p0)。共同／差分为 e_c=(e_i+e_j)/2、e_d=e_i−e_j；共同平移只进入 e_c，e_d 保留足对方向变化。共同世界滑移、机体平移误差和来源共同误差可相互混淆，长度、足力及短时 gyro 本身不能分离它们。

若未来证据支持某一确定来源存在持续 body-fixed 有效运动学速度偏差 b，应使用 e_i−B01 b，其中 B01=integral(R0ᵀR(t))dt；短区间梯形近似为 dt/2·(I+D)。不能在转动时把持续 body 分量直接当成任意 body0 下的 dt·b。B01 对姿态的导数须进入同一 H；差分 e_d 的 b 列为零。它须作为有有限协方差、保留交叉项的持续状态，不能每 100 ms 新放一个无先验自由量，否则消去全部共同位移信息。PVT／receiver velocity 可用期才提供区分机体运动与来源偏差的重要独立锚；失联期不能靠两足共同项单独确认偏差，并与 IMU bias／倾斜／速度存在耦合。

正常联合 EKF 中，SDK 更新即使 H 没有 b 列，也会经 P_bx 改变 b。因此若以后声称 b 只由独立 GNSS 锚校准，必须明确 SDK 的来源策略并维护交叉协方差，不能只写“没有用 SDK−foot 直接拟合”。支撑 token 切换不应自动把持续来源偏差设零；已用于校准 b 的足端证据被撤销时，b 及其后续影响也属于回放依赖，现有短回放窗口不能自动担保任意久的历史校准可撤销。独立 partial carrier 前端仍不因足端依赖而失效，下游共同后验上的创新须重算。

此模型比直接删除 body XY 共同信息保留了未来经独立锚校准后使用共同位移的可能，也引入新的不可辨识和来源归属责任。当前证据尚未支持把偏差放在足端；本备选不实现、不设置噪声、不新增 native。若后来选择它，唯一首要数学验证是：有限偏差先验时保留共同信息，偏差先验趋于无信息时共同信息退化而差分信息不变，加入独立运动锚后可辨识方向按预期恢复；不能用单次短 clone 残差拟合好来宣称模型有效。
