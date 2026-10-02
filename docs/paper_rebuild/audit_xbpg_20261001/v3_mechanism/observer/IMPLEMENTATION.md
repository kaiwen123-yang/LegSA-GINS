# I01 观察版实现与合成验证

仅修改 `<MECHANISM_BUILD_ROOT>/source_observed/cpp`。原 ca73cb1fb48a020fd2a450d79e520562c34eeb24 源快照的 154 个成员全部与 SOURCE_MEMBERS.csv recorded pin 核对一致；正式 worktree `cpp` 相对 HEAD 无 tracked diff。隔离观察树修改四个旧文件，新增两个日志文件；逐路径 hash 见 PATCH_FILES.csv，补丁为 observer.patch。正式科学源、source_frozen、provider 和 V3 结果没有写入。

`READY.json` 给出最终 binary/patch hash 及合成门，`BUILD_RECEIPT.json` 保存实际构建命令、输出日志入口/hash、flags 和计数。观察 binary：`<MECHANISM_BUILD_ROOT>/build_observed/legsa_v23_port_core_demo`。GCC 11.4.0、CMake 3.22.1、Unix Makefiles、C++17、Release `-O3 -DNDEBUG`；原 link 无外部依赖。首次观察构建通过；随后仅加入离线核算需要的原 readiness 配置字段和 QA/FGO 开关后增量构建，再执行最终合成测试。两次观察构建、一次冻结 fixture 库构建、两次 fixture 编译全部成功；这是封存前正常增量构建，技术失败与重试均为 0。

观察为独立环境变量开关。所有新增 GIEngine 状态是日志序号/context/cache；实际滤波变量、measurement vector 和原计数不被观察方法写入。日志复制已计算的 EKF 的 S/K/Hdx/delta；SourceAwarePolicy 中仅给额外观察字段复制实际最终 alpha、实际 moderate/strong 分支 multiplier 和原 scale_value，不重新求值策略。未添加 shadow NIS/LSIM、未改 R、未调整 helper 次序或 rolling history。影子公式的适用性/算术由独立离线代码判定。

每次新 GNSS 输入最多做一遍每源观察匹配；每个 IMU 只引用同一 GNSS 输入序号的候选快照。缓存不替代原 helper 的匹配。真实选中行从原指针偏移记录，辅助接受后重复的 `(source,row_id)` 可以离线计数。GNSS 传入 GIEngine 不带原文件行号，因此保留 unknown，不冒充 original row_id。`available_time=UNKNOWN` 同样不补造。

完整接口及早返回语义见 SCHEMA.md。SA 被配置关闭仍可能进入原 applySourceAwareWeighting，日志标 source_enabled=false；源级 sourceaware 关闭而绕过 applySA 时，保留实际 EKF 事件，没有虚构 SA 调用。GNSS 全失效期间仍有 IMU_OPPORTUNITY 与各源候选行，不以缺少辅助函数调用认定输入不存在。FGO、QA 记录配置但本队列不启用；本插桩不扩大这些机制的诊断范围。

## 合成门的实际证据

`synthetic_fixture.cpp` 不读取任何 config/provider/raw/reference 文件，以 public GIEngine API 构造 11 种小输入：all_active_sa、disabled_aux、no_rows、no_match、source_off、sa_off、prior_sa_off、quality_reject、no_eligible_hv、rd_residual_gate、policy_reject。冻结库、观察库关闭日志、观察库开启日志各执行一个 fixture 进程。因此 **native_fixture_processes=3，fixture_subscenarios=33，real_native_processes=0**。没有调用旧 toy controller、原 evaluator 或 provider generator。

每个场景写 15 行完整科学状态：位置/速度/姿态/quaternion/Cbn/bias/scale、完整 Cov、原更新/拒绝/cov-health/SA 统计；并写原 SOURCE_AWARE_WEIGHT_TRACE（适用时）。冻结条件有 19 个科学 CSV（11 状态 + 8 原 SA trace）；观察 off/on 各 19/19 字节相同，共 38 项。rolling 字段也随原 trace 比较，没有为匹配而重舍入。观察关闭不创建事件日志。

观察开启共 4,291 JSONL 事件、3,903 个完整矩阵，304 SA 调用、294 EKF 更新，其中 206 更新的实际 Hdx 非零（阈值 1e-12）；这些是测试覆盖计数，不能作为真实数据机制结论。检查包括 res 四分支、全失效/未到时/已消费输入、invalid GNSS 入口、相等时间最后一行、实际选择与缓存一致、重复消费可见、所有测量 return/gate 类别、HV 二维 R 与 metadata 999、禁用 SA 与直接 prior EKF、SA 同快照、effective R 真正传入 EKF、完整序号及 END footer。288/288 检查通过，详情见 SYNTHETIC_CHECKS.csv。

小型脚本 `run_synthetic_fixture.py` 只构建并运行上述 fixture，拒绝已有输出目录，不自动重试。`validate_synthetic_fixture.py` 仅读该隔离 fixture 产物并写小回执，不调用 native。原始合成事件与科学输出保留 `<MECHANISM_BUILD_ROOT>/synthetic_fixture_v1/`，不推送大事件载荷；SYNTHETIC_FILES.csv 留下精确入口与 hash。

该合成门只说明上述覆盖内的无干扰。真实 11 对象仍逐个核对原版对历史 pin、观察版对原版字节，以及科学 counter/config 一致；不能以合成 PASS 代替真实身份门。真实调用由根代理在协议/插桩审查并提交后执行，本 worker 不执行。READY 的 independent_review_status 在此交付时为 PENDING_SUPERVISOR_REVIEW；独立审查由根代理另记。
