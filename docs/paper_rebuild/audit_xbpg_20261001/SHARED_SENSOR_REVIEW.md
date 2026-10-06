# frames / time_alignment 及直接 IMU 语义依赖审查

已完整语义审查 `frames/` **6 文件227行**、`time_alignment/` **3文件438行**。请求中的 `src/legsa_gins/go2/` 在实际worktree不存在，未搜索或读取同名旧结果。为解释事件检测实际计算，额外完整阅读直接依赖 `datasets/by2/unitree_imu_semantics.py` **1文件146行**。本交付共 **10文件811行**；逐文件身份/调用者/深度见 `SHARED_SENSOR_COVERAGE.csv`。源码锚点 `e24d4735dd51724560f030275179d7e5efc19763`，上述原模块无本地差异、无修改。

最重要的结论：正常输入的FLU↔FRD、ENU↔NED、Hamilton wxyz旋转和数学yaw↔heading公式成立；这些变换只是坐标表达，不能证明XBPG的物理安装已知。发现7组已确认边界缺陷、3组条件风险，详见 `SHARED_SENSOR_FINDINGS.csv`。主要反例是：非有限时间能进入归一化CSV；“共同窗口”仅看各自最大时刻而可接受无时交数据；合法纬度0被当missing；GPST tow fallback被标成Unix；所有四元数证据缺失的IMU汇总仍为passed。尚未修复这些源函数，未改变正式协议。

新增真实函数反例 `tests/paper_rebuild/audit_xbpg/test_shared_sensor_findings.py`。本轮选择7份既有unit测试（event文件只执行事件检测那个测试，不执行历史IMU转换trial）加新增文件，结果 **18 passed / 10 strict-xfailed，exit 0**；新增文件4 pass/10 xfail。xfail是明确旧代码未满足的边界，不表示修复完成或整体实现全绿。测试只有合成CSV/向量，没有raw重扫、真实参考性能评价或历史runner调用。命令与输出保留 `<AUDIT_ROOT>/data_audit/shared_sensor_review/{TEST_RECEIPT.json,pytest.log}`。

```bash
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python3 -m pytest -q tests/paper_rebuild/audit_xbpg/test_shared_sensor_findings.py -rx
```

## 实际调用边界

`frames/` 的仓库显式调用者目前只有本包与unit tests；当前正式IMU/provider并不由 `Go2FrameAdapter` 自动保护。不能看到这个类就宣称正式链已经防住双重FLU转换，也不能把本包的数值边界缺陷自动归因当前C++姿态输出。

`time_alignment.event_normalization.make_event_normalization_report` 由历史 `scripts/experiments/run_by2_filter_core_trial.py:326`、`run_by2_measurement_floor_sanity.py:86` 使用；其他motion函数在历史BY3 generalization脚本中调用。本轮只搜索调用代码，未运行旧脚本或读其结果。

一个确实触达清洁正式链的例外是 `detect_go2_kick_event`：`paper_rebuild/kick_alignment.py:26,119–128,224–231` 运行它作为maintained candidate交叉检查。旧检测器的 `zscore_threshold` 默认6在 `score>=min_score(3) or score>=zscore_threshold` 下实际只需score≥3，而且score不是z-score。实函数fixture `gyro_x=12 rad/s`产生score4，在threshold6和1e6两次均detected（SS-08）。**正式kick最终时刻没有直接取该候选：** `kick_alignment.py:205–222`另用acc/gyro jerk robust MAD分数，严格比较6，`:250–265`最终存其selected timestamp，并把旧candidate的时间/分数作为单独metadata。所以本项影响maintained gate含义，不能直接宣称正式kick时刻错误。旧完整event归零链也没有在当前formal中替代这套frozen算法。

`unitree_imu_semantics` 的norm函数被上述两套检测器共享；`kick_alignment.py:145–158`先做逐字段finite检查，因此旧norm把missing当0的路径在这处受到额外保护。本报告只检查这些调用边界，**没有把518行kick_alignment整个模块计为完成审查**；其余函数和完整现场同步依据仍属总审查范围。

## 逐文件、函数/关键语句组

### `src/legsa_gins/frames/__init__.py`（4行）

1–4只有约定说明，无函数或状态。文字列出ECEF/BLH不代表包里存在完整地理坐标变换；本包实际只实现轴交换/符号变换与四元数操作。

### `src/legsa_gins/frames/conventions.py`（34行）

10–19 `FrameName`枚举Go2 FLU、FRD-compatible、NED、ENU、ECEF、BLH、BODY/ODOM/MAP。它是名称约定，没有实测frame graph、单位或安装关系。

22–26 `FrameTaggedVector`是frozen dataclass，三元tuple只是type hint；不在runtime检查维度、有限性或frame是否属于enum。29–34定义Go2 FLU与final_v23 FRD-compatible文字假定，没有按接收机/采集SDK/录制绑定。不得直接据此给新XB四段安装矩阵；这是SS-10的角色/证据边界。

### `src/legsa_gins/frames/transforms.py`（42行）

7–10 `_triple`只检查len=3；不转换dtype或拒绝NaN/Inf。13–22 `flu_to_frd/frd_to_flu`均为`diag(1,-1,-1)`，绕x旋转π，det=+1，保持矢量范数和手性，自逆；向量原来是什么物理量和单位会保留。25–34 `enu_to_ned/ned_to_enu`采用`[[0,1,0],[1,0,0],[0,0,-1]]`，也是det=+1、自逆。二者不是安装角校准，也不是绝对姿态/杆臂转换。

37–42 `wrap_angle_deg`映射[-180,180)，`wrap_heading_deg`映射[0,360)。有限常规值及跨界测试通过；实现取模不会像while循环卡住Inf，但Inf结果NaN，极大有限float的小角精度已不可恢复。这里是degree函数，不能直接替代C++ rad函数；未用该包宣称C++角度边界通过。

### `src/legsa_gins/frames/go2_adapter.py`（73行）

12–18 `FrameAdaptResult`记录原/目标frame、是否操作与说明；21–35 adapter目标固定FRD-compatible并标准化frame枚举/字符串。37–41 `already_frd_compatible && FLU`明确抛ValueError；43–50 FLU分支调用一次轴变换。52–59 FRD分支原样返回，**没有调用 `_triple`**，长度2的输入被接受（SS-02实函数反例）。61–67其它声明/不支持frame fail closed；70–73 `_frame_value`接受任意str再交由上层比对。guard只约束调用者声明，不能检测已经错误标成FLU但实际FRD的数值；没有来源绑定、安装矩阵或finite gate。正常“一次变换/保留FRD/冲突拒绝”3个既有unit通过。

### `src/legsa_gins/frames/quaternion.py`（52行）

9–10声明wxyz与Vector3类型。13–18 `quat_normalize`直接平方求和开根，只有exact zero抛ValueError；对有限非零`(1e200,0,0,0)`得到全0，对`1e-200`因平方下溢而误抛zero，对NaN返回NaN（SS-01）。不是常规unit quaternion误差，但公开helper的数值边界已确认。

21–23 conjugate保留w、取负虚部；26–34 Hamilton乘法四项符号与主动旋转一致，q1*q2表示先q2后q1。37–43 inverse=q*/||q||²，对非unit正常有效，仍有norm overflow/underflow与finite漏洞。46–52 `quat_rotate_vector`先normalize，做q*(0,v)*q⁻¹，返回三虚部；q的frame方向由caller决定，包不会区分qbn/qnb/qeb，也没验证v完整三维（多余维可忽略，短向量IndexError）。正常+90°z旋转x→y和逆乘单位元通过；不能把它当作内置Go2四元数frame身份证据。

### `src/legsa_gins/frames/yaw.py`（22行）

1–9明确math yaw为ENU从East逆时针、heading为North顺时针，且real final_v23约定尚待oracle。15–22两函数均`90°−angle`再wrap到相应域。普通水平轴向定义数学正确、inverse按圆周相等，东西北向样例通过。它不是“横向双天线方位+90°在联合倾斜下等于Euler yaw”的证明；未定义baseline/body安装向量，不能直接用于解除当前双航向几何阻塞。

### `src/legsa_gins/time_alignment/__init__.py`（5行）

1–5说明本包只生成诊断和algo_time_sec、不声明硬件同步。这个边界应保留，但若其他runner将算法时间轴上的重合当物理同步，声明不能消除实际数据流的问题（SS-09）。

### `src/legsa_gins/time_alignment/time_domain_audit.py`（126行）

14–18四种启发式标签；21–27 `_as_float`缺失→None、坏数ValueError→None，但Inf/NaN仍返回，TypeError未捕获。30–37CSV字段完整读成list，无valid/reject计数。40–41 `_monotonic`允许重复，空表all=true，不过empty分支另设置false。

44–72 `infer_time_domain`只排None，中位数>1e9称Unix-like，0..604800称GPS-TOW-like，其余<1e7且单调称relative。这只描述量级：boot time=1000也会标GPS-like、负值也可relative，缺GPS week/leap/epoch不能做时钟判定。Inf会标Unix-like（SS-03）；NaN污染median/min/max且不能作为有效支持。75–80 `_reasonable_overlap`仅min/max，要求正长度，不检查实际间隙、唯一性/到达时间还是测量时间。

83–105 `audit_by2_time_domains`字段名固定Go2 timestamp/GNSS time_unix/trace timestamp，不适合直接读原始XB ROS stamp或trace.time；双方Unix-like且范围交叉就direct_comparison_allowed，不要求monotonic或时钟证据。106–126返回clock_sync=false、physical_offset=false，这些是正确的claim ceiling；trace只参与自身domain摘要，不参与direct_allowed计算，`trace_used_for_alignment=false`在此函数数据流可静态核对。`event_normalized_time_axis=true`在这里只是政策标签，尚未实际归零。缺任意源count则evidence_missing；坏finite值使count不可信。

### `src/legsa_gins/time_alignment/event_normalization.py`（307行）

13–19导入BY2 norm与time audit。22–54 `_as_float`缺失回退，但坏串直接ValueError、NaN/Inf不拒绝；`_as_bool`支持1/true/t/yes/y；CSV全表读写；`_percentile`nearest rounded index，无finite过滤，空输入返0。它们无逐行reject ledger，无法充当本轮原始终端完整解析器。

57–89 `detect_go2_kick_event`：前max(5,min(40,n/10))行acc norm中位数；全段foot force delta P95至少1作scale。对每行取gyro norm、|acc−初始中位|、yaw rate、foot speed除同一max(min_score,1)，与force/scale作最大。不同物理单位共用无单位min_score，不是统计z-score；最早最大值胜出，因为只用`>`替换。status为score≥min_score **或** ≥zscore_threshold，等价≥两阈值较小者，因此默认zscore6不生效（SS-08，fixture两次调用输出一致）。分数与rowtime有限性无显式保障。当前frozen caller只在初始event段调用并另做robust jerk选点，影响边界详前节。

92–146 `detect_go2_formal_motion_start`：跳过kick以前/同刻；后续每个row取固定**样本数**sustained_window=5，非5秒，未检查dt或跨缺口。速度≥.02m/s、gyro/yaw≥.05rad/s、foot speed≥.05m/s三类需要all(window)；foot-force只看当前一下变化、mode/gait用any变化，也可以在无持续位移时选起点。按dict顺序先找到通过特征即return，不是多个传感器共同确认。尾窗口不足break；失败fallback第一行，并给evidence_missing。窗口为0/负数、阈值NaN无参数验证，可能vacuous all或索引异常。kick_used_as_search_anchor硬编码true，即使kick_time缺失。

149–155 `_horizontal_m`为半径6378137的局部球面水平近似，lat/lon degree→m，cos(lat0)，没有WGS84曲率差和反经线wrap；小范围事件定位可作为近似，不能当绝对高精度评价器。

158–190 `detect_gnss_formal_motion_start`：先保留has_position，第一位置作基点；从第二历元开始每min_consecutive=3个样本，以全部距离≥.2m **或** 全部heading_valid选起点。静止且heading有效也detected（实函数观察，SS-09），因此名称motion不构成真实运动证据。174行`_as_float(...,lat0) or lat0`把合法纬度/经度0替换为基值（SS-05）；缺失time_unix时退到tow，180/186真实值来自tow但181/187仍写type=time_unix（SS-06）。无检测则第一has_position weak_candidate；缺有限性/时间递增/唯一性检查。

193–194 `normalize_time_axis`是单纯相减，不求时钟映射。197–227 `add_algo_time_to_csv`保留raw_time、追加algo_time，丢弃missing、负algo和指定end之后的行；NaN使所有比较为false，仍写出（SS-03）。全表保内存、无drop counters/排序/去重，输出路径由caller给定，可能覆盖同名派生文件。230–250 `compute_common_algorithm_window`只取各自最大algo time减margin，start固定0，不看双方最小支持或gap；Go2=[100,110]、GNSS=[0,10]仍common_window_ready且window[0,10]（SS-04）。

253–307 `make_event_normalization_report`读time域、检测kick、**分别**检测Go2/GNSS formal start，然后分别减自己的起点。检测失败的None又被`or0.0`代替；输出固定在各输入CSV的相邻目录，未提供统一受控输出root；不要向raw目录上的输入调用它。计算event_pair_delta时标注明not_clock_offset，这个差值也不送入同步；但两源独立起点归零本身能把不同物理事件强行画在同一algo time（SS-09），仅可作已说明的诊断gauge，不能证明观测融合时间成立。最终evidence_status仅取commonwindow，不传递kick/起点的weak或missing作为整体失败；reference仅用于time域摘要，没有参与起点选取。未调用此函数生成XBPG输入。

### `src/legsa_gins/datasets/by2/unitree_imu_semantics.py`（146行；直接依赖）

12–15 `_as_float`将missing/空白变0，但非数字抛异常、非finite保留。18–33 `quaternion_wxyz_to_rpy`为Hamilton wxyz的ZYX roll/pitch/yaw，rad；pitch超±1截±π/2，无自身归一化。36–40 wrap到[-π,π)，等π的后判在常规模结果下不可达，无while卡死。43–69 `check_quaternion_rpy_consistency`接受quat_wxyz或0..3键，归一化后与rpy分别作圆周差，max<.05rad为passed；零q给evidence_missing。缺rpy却被0替代，identity q可假pass；奇异姿态的不同Euler表示也可能给大差，不等于旋转不一致。

72–91 `accel_norm`（m/s²）、`gyro_norm`（rad/s）、12维四足速度的整体欧氏norm（m/s）；foot norm不是某一足端实际速度阈值，足数/维数变化会改变总norm。94–106 `foot_force_delta`四项差norm，prevNone给0，没除dt，不等于力变化率；单位取决设备字段契约，代码不验证。missing分量默认为0，可能造成虚假变化或压低运动分数。

109–145 `make_unitree_imu_semantics_report`逐row检查后只数suspicious，**不数evidence_missing**；只要rows非空且suspicious=0，all-missing quaternion也总体passed（SS-07）。输出单位/wxyz/FLU/accel_contains_gravity均为静态标签，不是从数据推导设备物理关系；velocity frame明确evidence_missing边界合理。汇总max/初始acc、gyro无需全部finite、初始静止或校准质量；position/velocity非truth、foot不是独立FK的false标记不保证其它caller没误用。当前formal的norm调用先做finite gate，但这个语义报告仍可达标准化/诊断路径，需分开影响判断。

## 修正与未审范围

建议作为独立候选：统一finite/维度与时间schema拒收、用缩放范数防四元数overflow/underflow、保留source timestamp integer sec/ns、真实timescale标签和valid-mask；共同窗口至少从有效样本范围交集建立并记录gap/匹配分母；用显式None区分缺失与零坐标；语义汇总区分passed/suspicious/missing；把旧kick的量纲化score和robust z-score分开命名与gate。不要为了通过新XB数据去改冻结阈值或用参考校时。

本交付内10文件没有未读段。`go2/`不存在；`go2_state/`、`go2_prior/`、`datasets/by2/`其他文件及完整`paper_rebuild/kick_alignment.py`不在这里计入完成（仅inspect caller函数片段）；这些模块是否已由其他审查覆盖由总覆盖表决定。未改raw或冻结provider，未修改当前正式算法，未调用旧结果评估，也没有执行三篇文献复现。
