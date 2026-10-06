# 六条单历史姿态 clone 导航：事前登记

状态：REGISTERED_READY。native e361e35 已完成一次构建与16项局部合成验证；比较器已完成1项事前登记合成验证。控制器经独立只读复核，无阻断问题。新 binary、静态库、局部回执和比较器身份已冻结；提交此登记后才执行真实 prepare/native/evaluate。到本登记写入时，新增真实调用仍为0。

## 固定对照与输入

三窗固定 BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]。每窗仅 NULL_CLONE、PAIR_YOUNG 两臂，共 6 native / 最多 6 evaluator。此前三窗 PVT_CONTROL/CARRIER_FALLBACK 共 6 条只复用，不重跑；本轮累计 native 12。

配置逐行克隆已封存 FULL_WINDOW_NAVIGATION_ATTEMPT01 的 CARRIER_FALLBACK 配置，继续校验其 PLAN→原 V3 lock 身份链。五 provider、原 7 列 500 Hz IMU、初始化、euler_yaw、PVT-priority fallback、已封存 CARRIER.csv 均不变。旧 HV 仍依赖 GNSS heading；不能把本试验说成全部速度/姿态来源独立。足输入只用已完成 FOOT_PAIR_PROVIDER_ATTEMPT01 的三份 EVENTS.csv，不重读 body 或重建支撑。

两臂共享 exact-source 足事件、同一安装映射、完整 24 维交叉协方差、所有旧观测的 joint gain、正左反馈与 full reset、相同 clone 建立和边缘删除。NULL 不用足残差反馈；PAIR 在固定工作质量门后，按既定五 epsilon 与初始化固定 W 选择 Young 上界或精确 SKIP。因此 PAIR−NULL 才用于归因足相对方向；NULL−旧 CARRIER_FALLBACK 单列 reset/传播分割效应。

## 冻结工作假设

复用 0.2 s 机会、首实际 source START、0.1–0.15 s END、canonical pair 和不可复用 endpoint。sigma 每点每轴 0.01 m 是工程上界假设，不是标定。任意四点 cross 的 Sigma6 上界为 0.0008 I，残差上界为 0.0016 I。SDK 位置是否含 GNSS 输入未知，IMU 统计独立未证实，body-FRD→engine-body 单位阵为显式软件假设。不得从结果减小噪声或改脚对增加更新。

Young epsilon 固定 [1/64,1/16,1/4,1,4]；W 从初始化 current21 分块方差确定后冻结。safe innovation 阈值 16.26623619623813。门是工作模型诊断，不是无滑移真值或完整性保证。未来过程和原观测的未知相关性没有因该上界自动解决。

终态 RETIRE 超出最后 IMU 时，只在实际终态删除 clone并登记未消费事件，不能延长 NAV。开始/结束超 IMU 支持也保留缺失，不回填或调整窗口。

## 执行与封存

控制器为 scripts/paper_rebuild/carrier_phase/clone_window_navigation.py。直接 import 旧 full_window_navigation 的 check/clone/launch/native_access/emit/seal_files 等纯辅助函数，不改旧 IDS/ARMS 或脚本。六次 reservation 使用新独立 ledger，重复或超预算即拒绝。

~~~text
python3 scripts/paper_rebuild/carrier_phase/clone_window_navigation.py prepare \
  --registration-commit <REGISTERED_COMMIT> --stage <NEW_STAGE> \
  --baseline-stage <SEALED_PREVIOUS_SIX> --foot-provider <SEALED_FOOT_PROVIDER>
python3 scripts/paper_rebuild/carrier_phase/clone_window_navigation.py native \
  --registration-commit <REGISTERED_COMMIT> --stage <NEW_STAGE>
python3 scripts/paper_rebuild/carrier_phase/clone_window_navigation.py evaluate \
  --registration-commit <REGISTERED_COMMIT> --stage <NEW_STAGE>
~~~

prepare：小型身份/事件/配置审计，1 次 checker 编译、6 次 loader-only 调用；不运行传播、搜索或参考评价。native：每次最多 1200 s，独立进程组限制，passive openat/execve 审计明确五旧 provider、carrier 与 foot 输入，禁止参考和原始数据。六条终态全部封存前，evaluate 入口不可进入参考读取阶段。失败不自动重试；有限发散保留为算法失败且该条评价 NA。技术失败保留并停止，不能拿旧输出替代。

两臂必须输出相同实际 IMU time keys，NAV/STD 相互时键一致，STD 至少 10 列。若 PAIR 实际更新为零，要求 NAV 与 STD 均逐字节等于 NULL；这不是所有 BY2/H 都预设相等。若发生更新，差异保留供比较，不能由差异本身断定收益。

## 交付字段和评价

每 native RESULT 保留旧 run_id / sequence_id / arm / status / nav / std / output_rows / time_keys_sha256 / bound / heading_counts，并添加 clone_counts 与 foot_diagnostics（全部事件动作、实际更新、固定 W、终态缺失）。新 arm 始终为 NULL_CLONE / PAIR_YOUNG，不映射成 PVT_CONTROL / CARRIER_FALLBACK。

所有六输出封存后，使用原 frozen evaluator、每序列锁定基线中位数与 lever 物理点变换，仅改 NAV 位置 2/3/4 列，STD 不变换。reference 是共享商业 GNSS 参考，不是独立真值。成功 EVALUATION_RESULT 保留原 row/audit/capture/transform/output_support/error_series pin，失败行不伪造零误差。

后续独立比较器复用既有纯指标/事件函数：分别报告新 6 条完整支持、各旧/新实际 time 键交集；原 V3 非退化门仍适用。收益要同时呈现 PAIR 相对 NULL，不能借 reset 的数值变化归因足测量。无 raw-fault 恢复场景时 B 仍不能由这些窗判断；速度误差、整数真值等不支持指标为 NA。比较器属于后续独立交付，本控制器不提前读取 reference 或计算采用结论。
