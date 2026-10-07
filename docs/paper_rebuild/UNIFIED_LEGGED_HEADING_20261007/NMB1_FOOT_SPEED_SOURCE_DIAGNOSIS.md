# NMB1 足速／足点导数与支撑阶段：源内诊断收口

2026-10-07。新增脚本 `nmb1_foot_internal_kinematics.py`、`nmb1_foot_speed_semantics.py`，位于 `scripts/paper_rebuild/unified_legged_heading_20261007/`。只读完整 motion cache 和既有 provider；raw/NAV/reference/native 均为 0，没有时间搜索、拟合补偿、校准采用或新资格门。

**约 7.5% 的前向共同差不能直接归为足点误差或真实回滑。记录 foot_speed 与足点有限差分具有相同整体符号、近似幅值，却在支撑与摆动阶段出现反向均值差；foot_speed 更贴近 SDK velocity 不能成为替换原足点观测的依据。**

## 已有 481／242 END 的运动学分解

记 q=记录 foot_speed_body_frd，r_dot_FD=(r[k+1]−r[k])/dt。原零杆臂假设下，两种足端推算体速为 `−q−omega×r` 与 `−r_dot_FD−omega×r`。两者使用同一源 gyro、因果左 ZOH、完整 SDK XYZ，旋回各 START body frame 积分。有限差分用于离线诊断，含下一源样本，不作为新的因果在线输入。

| 来源／共同前向 foot−SDK 均值 | 全 481 END | 空窗 242 END |
|---|---:|---:|
| 原两时刻足点端点 | −6.594 mm | −7.260 mm |
| 足点有限差分运动学积分 | −6.596 mm | −7.262 mm |
| 记录 foot_speed 运动学积分 | −1.941 mm | −2.031 mm |

空窗足速积分相对端点增加 5.228 mm，约为原负均值的 72.02%。FD 与端点只差 −0.00248 mm，说明端点旋转符号及离散积分误差不足以解释前向主差。此 72% 是两个源模型的均值分解，不是物理原因或误差来源占比认证。

按两只足的 body 坐标分别核对，`integral(q)−(r1−r0)` 空窗 x 均值 −5.232 mm、abs p95 9.521 mm；使用相邻端点 q 平均后仍为 −5.467 mm。因此不能归咎于左矩形积分采样方式。y/z 均值仅 +0.083/+0.243 mm；主要问题在前向。

空窗记录足速推出体速与 SDK 的时间均值差 x/y/z 为 −0.01968/−0.00866/−0.04282 m/s，FD 版本为 −0.07086/−0.00785/−0.04044 m/s。改善主要在 x，q 没有同时解除垂向来源冲突。

481 END 的 962 个足区间保持同一 frozen support token；provider 端点与 cache 最大差为 0。重放同一 SupportArcTracker 后，与旧 cache 在首个使用 START 之后的支撑资格及转移时刻差异均为 0。因此本结果不是改变触地规则或拼错足端来源造成。

## 整体符号、幅值与阶段

全窗全部源段 q 与 FD 的 x/y/z 相关为 0.900/0.837/0.892，时间加权 RMS 比为 0.988/0.998/0.992；未发现单位倍数、整体反号或全局 7.5% 尺度差。相关不等于导数完全一致，源级 FD 对不均匀日志时间和快速变化敏感。

| 空窗确认状态 | 源足段数 | FD−q 前向时间均值 | x/y/z 相关 |
|---|---:|---:|---:|
| 支撑：两端同一 token | 62,754 | +0.06271 m/s | 0.518/0.780/0.818 |
| 摆动：两端 SWING | 80,055 | −0.06844 m/s | 0.850/0.872/0.890 |
| 转换／其余，完整保留 | 9,219 | +0.08723 m/s | 0.775/0.786/0.794 |

支撑与摆动反向差说明它不是简单恒定比例，更符合阶段相关的信号生成／滤波／采样差异这一工作解释；现有字段不能确认滤波器、命令值或关节运动学来源，也未搜索延迟。

在实际 242 END 内，以确认支撑到首次 token 失效的归一化阶段分四组，FD 体速−SDK 的 x 均值为 −0.0519/−0.0859/−0.0975/+0.0458 m/s；q 版本为 +0.0057/−0.0261/−0.0539/+0.0886。末阶段转正，不支持“整段始终同向持续滑动”的简单解释。归一化阶段使用了离线未来退役时间，只做描述，未进入资格判断。

区间最年轻足的已确认支撑年龄 median 42.879 ms；END 到首次 token 退役仍有 median 46.965 ms。按平均足力四分位，端点 common x 均值 −7.699/−8.110/−8.466/−4.799 mm，不单调；成熟度及末端剩余时间也未给出可把冲突局限于接触瞬间的简单规律。足力仍是未标定 SDK 单位，不能转成摩擦／真接触认证。

特别注意符号：若把 SDK velocity 暂当真实体速，表观足端地面速度在 body 系为 `v_sdk+omega×r+r_dot=−(v_foot−v_sdk)`。本次负前向差对应表观**向前**足端运动，不能直接命名为向后回滑；SDK 不是已知真值，所以连这一表观运动也不是滑移证据。

## 是否只是 SDK velocity 的构造恒等式

逐样本 `q+omega×r+v_sdk` 不为零：空窗 stance 模中位 0.09966 m/s，swing 2.35318 m/s，精确零样本 0。两只及以上同时支撑足的平均体速与 SDK 差也不恒等：空窗模中位 0.08027 m/s、p95 0.27641 m/s。可排除记录 q 在所有时刻仅由 `−v_sdk−omega×r` 原样复制的严格恒等式。

这**不能证明独立来源**。SDK velocity 仍可能使用部分足速、加权／滤波／偏置模型；q 也可能是内部运动估计或命令量。全部共支撑的 117.062 s 中，足速平均体速−SDK 的前向均值仅 +0.000842 m/s，而固定 END 覆盖内为 −0.01968 m/s，说明选中的支撑阶段会影响均值。无 SDK 实现与独立关节／外部测量，无法从相关或残差大小反推出依赖图。

## 与第三条同源位移证据合并

独立保存的 `NMB1_SOURCE_POINT_TIME_AUDIT_01/THREE_SOURCE_METRICS.csv` 使用 SDK RPY 将同 242 区间统一到 SDK world 后投回 START body：foot−SDK position 前向 mean/RMS=−0.406/2.172 mm；SDK velocity 积分−SDK position=+7.234/8.125 mm。三维足点在这条内部位移关系上更自洽；SDK position 仍不是独立真值，不能据此缩放 velocity。

因此当前可执行结论是：保留原始三维足点的物理观测定义，foot_speed 作为来源语义诊断，**不因更贴 SDK 而换因子、不拟合 7.5% 补偿、不把共同差阈值变成滑移 REVOKE**。如果下一步研究同支撑 episode 的信息消费关联，应明示其处理的是可能共享来源及重复消费，不宣称已经确认或修正滑移。当前字段已足够排除若干粗错，但不足以认证 q/velocity/position 的内部独立性。

## 产物

Scratch 基目录 `/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/`：

- `NMB1_FOOT_INTERNAL_KINEMATICS_01/`：PLAN/SUMMARY、PAIR_INTERVALS、FOOT_INTERVALS、SOURCE_SEGMENTS、STRATA、SUPPORT_EPISODES。
- `NMB1_FOOT_SPEED_SEMANTICS_01/`：PLAN/SUMMARY、STATE_FOOT_CLOSURE。

每个 PLAN 固定输入与执行脚本 SHA-256；所有阶段与异常分母保留。没有修改 C++、旧 provider、native 输出或上一轮读出。
