# Jan5 原始数据、FIX/FLOAT 与初始化准入审查

审查日期 2026-10-06；全部新读取、哈希、解码与统计在 Ubuntu-22.04 WSL。导航求解器 0 次、评价器 0 次；未读取商用融合参考轨迹、未提取 ZIP、未做观测重采样、时差拟合、AR 或参数选择。只为原始可用性与后续试验资格作判断。

## 结论先行

用户再次列出的 1 个 ZIP 和 8 个 body 与 R5 使用的数据**路径和完整字节哈希一致**。这是同一批原始数据，不是新增 8 条验证。ZIP 虽以 11:16:59 命名，内部包含 8 个不同时间的 receiver session 文件夹，共 176 个成员。

但“仓库数据全都只有一天”也不准确：主 BY2/BY2H/BY2O 窗口来自 **2026-03-06**；NMB1–4/XB1–4 来自 **2026-01-05**。已具两个采集日期的原始材料，本次没有增加日期。Jan5 的 8 段同日非重叠录制可以用作重复试验、输入状态分层和失效边界，不能计为 8 个独立采集日或自动称为未见测试集。

四 XB 的双接收机各自 FIX 都为零，但 FLOAT、其他有效定位与 RAWX 大量存在。旧 F03/F04 的 8 个 NO_INIT 是 **4 个 session × 2 个方法**；共同双 FIX 航向初始化规则不满足，并不是八次算法发散，也不是原始 GNSS 记录全缺。此次逐历元重解码验证了这个事实。

**不能只删 FIX 条件。** XB 双 FLOAT 的独立位置差长度中位数为 10.02、17.73、15.10、44.57 m，均无一对落在原 0.2–0.6 m 容许区间。RELPOSNED 中的有效 heading 也不能直接接入：全部 isMoving=0，所述矢量长约 2.5–2.94 km，指向固定参考站关系，并不是 0.35 m 双天线。

## 身份去重与复现入口

- [9 个原始文件的当前 SHA256](raw_audit/FILE_IDENTITY.csv)：8 个 body 与旧 profile/R5 plan 双重匹配；ZIP SHA256=`a12c5f05e1c89739f3c5cf3ab89e07a0b1d0a17858f1b119862d314ea46e3e39`，大小 198,406,698 bytes。
- [16 个 GNSS raw ZIP 成员身份](raw_audit/RAW_MEMBER_IDENTITIES.json)：本轮读取全部成员字节并核 SHA，全部与 20261005 原始审计一致。只解码 PVT、HPPOSECEF、RELPOSNED、RAWX，其他消息仅计数；每条被解码 UBX 核长度、class/id、checksum。
- [审查范围与源记录哈希](raw_audit/AUDIT_SCOPE.json)、[body 完整字段旧审计](../TIM_EVIDENCE_20261005/data_and_selection/BODY_FILE_PROFILE_PUBLIC.json)、[R5 输入身份](../EXISTING_DATA_R5_20261005/new_data/RUN_PLAN_T03.json)。Body 已重新核完整字节哈希后复用旧全流字段/时间统计，避免再次解析约 10 亿字节文本；不是声称本轮逐行人工重读。
- 复现脚本：[audit_raw_inputs.py](../../../scripts/paper_rebuild/heading_reassessment_20261006/audit_raw_inputs.py)、[group_dates.py](../../../scripts/paper_rebuild/heading_reassessment_20261006/group_dates.py)。参数 `--raw` 指 Jan5 原始目录，`--prior` 指 TIM 的 data_and_selection，`--r5-plan` 指上述 R5 plan，`--out` 必须为新的空输出目录。日期脚本接收 `--main-scope`、`--body-summary`、`--out`。不存在自动运行 solver 的分支。

## 日期、session 与 body 内容

全部时间为消息内 Unix/PVT 对应的 UTC；不能把文件名时间和完整测量首时刻混用。下表为完整 body 文件时间，非 GNSS 交集、非 R5 求解器实际启动窗口。完整时间精度与两类有效长度见 [BODY_AND_SESSION.csv](raw_audit/BODY_AND_SESSION.csv)。

| body | 首时刻 UTC（2026-01-05） | 末时刻 UTC | 跨度 s | 完整字段帧/全部帧 | >0.1 s 间隔数 |
|---|---|---|---:|---:|---:|
| nmb1.txt | 11:16:05 | 11:22:53 | 408.246 | 93266/93267 | 0 |
| nmb2.txt | 11:25:05 | 11:31:08 | 363.176 | 81811/81811 | 0 |
| nmb3.txt | 11:32:45 | 11:38:50 | 365.132 | 81950/81951 | 0 |
| nmb4.txt | 11:39:51 | 11:45:39 | 347.740 | 78609/78610 | 0 |
| xb1.txt | 12:25:15 | 12:31:51 | 395.640 | 91752/91753 | 1 |
| xb2.txt | 12:33:39 | 12:39:38 | 358.663 | 84435/84436 | 1 |
| xb3.txt | 12:40:55 | 12:46:42 | 346.436 | 80305/80306 | 2 |
| xb4.txt | 12:49:28 | 12:55:29 | 360.692 | 79737/79738 | 0 |

“连续支持时长”只是在跨度中减去 >0.1 s 相邻样本间隔总和，尚不是算法可用时长，更不是独立样本数。XB1/2/3 的最大间隔分别约 0.198/0.168/0.222 s；所有 body 时间戳单调、无重复。除 NMB2 外各有 1 个不完整末帧，不能补零伪装完整。所读旧完整字段统计的非有限值计数为零。

字段包括 quaternion(4)、gyro(3)、accelerometer(3)、rpy(3)、position(3)、velocity(3)、foot_force(4)、foot_position_body(12)、foot_speed_body(12) 等。足端字段/SDK velocity 可支持进一步的接触与滑移诊断；它们是 SDK 报告量，不能自动当作独立真实足端速度、独立接触标签或已完成的编码器/FK 里程计。本文未用 SDK position 或融合参考给航向/时间调参。

[DATE_SESSION_GROUPS.csv](raw_audit/DATE_SESSION_GROUPS.csv) 把主三窗口与 Jan5 分开：BY2O 为 3 月 6 日 07:53:06–07:59:23，BY2 为 08:01:06–08:05:40，BY2H 为 08:06:53–08:11:23 UTC。主窗口时长不能与 Jan5 完整文件长度不加区分地相加。8 个 body 与 8 个 receiver 文件夹按现有时间覆盖配对，相邻录制并无时间重叠；“不同文件/时间段”不是统计独立性证明。

接收机 PVT 自身的 FLOAT 位置包围盒显示 NMB 大致位于纬度 39.9785–39.9795、经度 116.3454–116.3464；XB 大致位于纬度 39.9835–39.9842、经度 116.3391–116.3404。两组原始位置有不同空间簇的观察，但 FLOAT 本身有误差，也不能由包围盒确定具体路线、八条独立路线、安装变化或“完全未参与开发”。[逐状态位置包围盒与 hAcc](raw_audit/RECEIVER_ACCURACY_BY_STATE.csv) 保留原值；没有读取 reference 画路线后选择 session。

## GNSS 原始分母与状态

状态来自 PVT：3D fixType 与 gnssFixOK 同时满足才算有效；carrier=2 为 FIX，=1 为 FLOAT，=0 为 OTHER_VALID，否则 INVALID。这个状态划分与“只有 FIX 才能用”不是同一件事。u-blox 的 PVT carrier 标志区分浮点与固定解；RELPOSNED 的 isMoving 表示移动基站模式，其相对矢量原点是参考站。[F9P 集成手册](https://content.u-blox.com/sites/default/files/ZED-F9P_IntegrationManual_UBX-18010802.pdf)，[UBX RELPOSNED 字段说明，第 131–132 页](https://content.u-blox.com/sites/default/files/u-blox_ZED-F9H_InterfaceDescription_(UBX-19030118).pdf)。这里借用相同 UBX 消息布局说明，不据此把设备型号认定为 F9H。

下表为 **整个 receiver session** 的 PVT 历元；每格依次 FIX / FLOAT / OTHER_VALID / INVALID。完整原始首末时间、丢帧和有效位置间隔见 [GNSS_RECEIVER_STATES.csv](raw_audit/GNSS_RECEIVER_STATES.csv)。

| session | GNSS1（FIX/FLOAT/其他有效/无效） | GNSS2（FIX/FLOAT/其他有效/无效） | 精确 iTOW 配对 | 双 FIX | 双 FLOAT |
|---|---:|---:|---:|---:|---:|
| NMB1 | 803 / 171 / 42 / 814 | 771 / 189 / 53 / 817 | 1830 | 771 | 143 |
| NMB2 | 760 / 182 / 39 / 825 | 792 / 138 / 44 / 831 | 1805 | 750 | 124 |
| NMB3 | 915 / 130 / 45 / 826 | 905 / 124 / 68 / 819 | 1916 | 904 | 109 |
| NMB4 | 724 / 153 / 41 / 862 | 698 / 179 / 50 / 853 | 1780 | 697 | 140 |
| XB1 | 0 / 746 / 1044 / 237 | 0 / 908 / 943 / 166 | 2017 | 0 | 617 |
| XB2 | 0 / 640 / 1051 / 191 | 0 / 915 / 885 / 82 | 1882 | 0 | 590 |
| XB3 | 0 / 596 / 995 / 166 | 0 / 938 / 685 / 128 | 1747 | 0 | 562 |
| XB4 | 0 / 638 / 975 / 168 | 0 / 946 / 771 / 64 | 1781 | 0 | 604 |

表中两个接收机的非 FIX 有效定位都计入原始统计；原 R5 provider 的主位置/速度来自 GNSS1，GNSS2 用于构成差分航向，不能把 GNSS2 的统计列当作它被单独融合的次数。原 R5 `gnss_inputs` 的 position_valid 是 `PVT ok && UTC valid && HP exists/valid`，**不要求 carrier FIX**；只有航向要求两机 FIX、精确同 iTOW、HP有效及长度 0.2–0.6 m。receiver velocity 同样按 PVT ok，不要求 FIX。相关代码：[run_new_sequences.py](../EXISTING_DATA_R5_20261005/new_data/run_new_sequences.py)。因此“先把所有 GNSS 的 FIX 限制放开”不是对现状的准确描述。

NMB 的 PVT 数据文件近乎连续 5 Hz，但相邻**有效位置**间隔最大达 163–173 s，双 FIX 航向间隔达 202.6–216.8 s。这主要是有记录而无效，不是同等长度文件缺行。真实记录缺行另列：GNSS2 在 NMB2/XB1/XB3 有 1/10/6 个 0.4 s 相邻 PVT 间隔；其余统计范围内约 0.2 s。`HP flags=0` 本身不能推翻 PVT invalid。

[HEADING_SUPPORT.csv](raw_audit/HEADING_SUPPORT.csv) 同时列 FULL_SESSION、BODY_RECORDED、BODY_MINUS_1p1 三种分母。原 body 支持内，NMB 双 FIX 分别 703/724/814/656；不应把完整 session 的 771/750/904/697 当作相同窗口计数。后者等于历史总数，验证本次重解码与原来源一致。-1.1 s 仅复现 R5 已登记时间支持，没有重新拟合。

## 为什么 XB 不能靠移除 FIX 门得到航向

原 R5 prepare 对 xb 名字分支直接登记 NO_INIT，依赖此前原始审计；不是各启动一次 solver 后失败。本次重新解码全部 XB 双 raw 后确认两机都没有任何 FIX，且全部有效状态下的独立 HP 位置差都不在 0.2–0.6 m。保留 NO_INIT 是原已声明初始化合同下的正确结果；新假设必须有新的 heading 初始化/不确定度合同，不能把旧记录改成完成。

| session | 双 FLOAT 配对数 | 差分基线 p50 m | p95 m | 最大 m | 长度落 0.2–0.6 m 的历元 |
|---|---:|---:|---:|---:|---:|
| NMB1 | 143 | 2.497 | 5.681 | 53.455 | 45 |
| NMB2 | 124 | 1.040 | 50.015 | 61.658 | 44 |
| NMB3 | 109 | 0.592 | 25.485 | 34.436 | 57 |
| NMB4 | 140 | 1.695 | 27.166 | 27.489 | 26 |
| XB1 | 617 | 10.024 | 38.616 | 56.562 | 0 |
| XB2 | 590 | 17.727 | 42.881 | 73.775 | 0 |
| XB3 | 562 | 15.099 | 95.516 | 110.150 | 0 |
| XB4 | 604 | 44.569 | 62.567 | 64.856 | 0 |

这里是两个绝对位置的差，尚未用共同载波观测做移动短基线估计。XB 两接收机 FLOAT hAcc 中位约 0.458–0.751 m，而预期基线仅 0.35 m；NMB FLOAT hAcc 中位约 0.131–0.226 m，也存在数米尾部。hAcc 是接收机报告的精度字段，不是由真值验证的实际误差。基线长度通过也不能证明方向正确，更不能按这个诊断表挑选最优门限。NMB 的少量长度合理 FLOAT 历元可以进入预注册诊断，不能自动作为可靠初始航向。

新解码的 [RELPOSNED_SUPPORT.csv](raw_audit/RELPOSNED_SUPPORT.csv) 显示所有 16 个成员 isMoving=0；许多 heading_valid=1，但 relPosLength 中位 NMB 约 2,515–2,529 m、XB 约 2,925–2,943 m，refStationId 为 0/391。它描述接收机相对固定参考站的矢量，不能冒充两天线的体轴方向。不能仅搜到 relPosHeadingValid 就解锁 XB 初始化。

## 非 FIX 下真正可执行的原始观测机会

[RAWX_PAIR_OPPORTUNITIES.csv](raw_audit/RAWX_PAIR_OPPORTUNITIES.csv) 给出不求解的准入计数。两个接收机 RAWX 的 week/rcvTow 精确二进制键没有交集，但存在约 -8 ms（后段 -7 ms）的接收机局部测量时差。按固定 ≤0.1 s 半个 5 Hz 周期的近邻诊断，匹配是一对一；没有移动观测时刻或拟合 offset。精确键为零不等于没有可配对的原始观测。

| session | 近邻唯一 RAWX 对 | 共同有效载波且半周有效、≥4 颗不同卫星的历元 | 其中 GPS 自身≥4星 |
|---|---:|---:|---:|
| NMB1 | 1830 | 972 | 796 |
| NMB2 | 1804 | 935 | 735 |
| NMB3 | 1917 | 1051 | 849 |
| NMB4 | 1779 | 885 | 690 |
| XB1 | 2027 | 872 | 0 |
| XB2 | 1882 | 825 | 12 |
| XB3 | 1758 | 793 | 39 |
| XB4 | 1781 | 961 | 30 |

卫星按 (gnssId,svId) 去重，不把同卫星双频当两颗。载波标准差低四位为 15 的无效项排除，并要求双方 cpValid、finite 及 half-cycle-valid；这比简单“RAWX 文件存在”更具体，但**仍不是 AR 成功率/航向可用率**。混合星座总数≥4不能替代每星座参考卫星、实际几何、星历、共同频率、周跳和时钟处理。特别 XB1 的 GPS≥4为零，不应按 GPS-only 路径承诺恢复；多星座可能性需独立合同。没有解算星历，没有计算 DOP，没有尝试整数固定。

建议顺序：先把 NMB 的 FIX↔FLOAT 转换和缺测作为可审计自然条件，固定时间与坐标合同，验证 raw 两接收机差分链；如需 XB，再预声明无可靠初始航向时的处理与冷启动状态。优先证明原始因果输入与观测协方差正确，不先靠参考航向或后验拟合把轨迹跑通。它们可支持跨录制日的失败边界与有限参数转用研究；要声称跨路线、未见场景、独立泛化，还需明确采集/开发使用史和新的留出设计，当前结果不能代替。
