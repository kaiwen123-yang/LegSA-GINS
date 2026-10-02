# N09_RP_ONLY：隔离实现与本轮原生合成验证

按已提交的 [V3 定义 §2.3](../../V3_DEFINITION_DECISIONS.md) 实施，科学源为正式 ca73 + 上轮无干扰观察层的 `<OBSERVED_SOURCE>`。先逐文件核对后复制到 `<VALIDATION_BUILD_ROOT>/source_N09_RP_ONLY`：156/156 文件字节一致，无符号链接；本轮结束原观察源 156 文件仍保持相同 hash。正式 cpp、原观察源、输入和原结果均未写入。

**科学改动仅三个文件。** [scientific.patch](scientific.patch) 为相对 `<OBSERVED_SOURCE>` 的零上下文 diff，[SCIENTIFIC_PATCH_FILES.csv](SCIENTIFIC_PATCH_FILES.csv) 保存安装公共层前的 hash。`gi_engine.hpp` 增加独立 pending 身份、资格缓存与计数；`gi_engine.cpp` 增加 RP-only 调度分支；新 `gi_rp_only.cpp` 实施资格和独立事件。原 RP helper、SA policy、EKF、反馈函数、匹配算法、runtime 队列与原 module counter 验证都没有改写。

每次 `addGnssData` 分配独立递增 `input_id`，与 observer 是否开启无关。只有 `validity_explicit=true` 且原三个有效位全 false 的输入进入候选资格域；不把 `isvalid` 改真。RP enabled、provider/solver 已启用后，只读探查一次原 vector：`dt<=best_dt`，故容差包含边界、等距选择最后一行，且**先选最近行，再按原 `Go2WeakPriorFactor::isActive` 判定**，不跳过最近的 inactive 行去找较远 active 行。缓存不推进 loader/cursor，不调用 SA；原 helper 在实际调用时仍使用原 matcher 和原门。直接输入在该运行中固定，候选未引入运行中替换 provider 的机制。

到达该输入的原 GNSS 时间机会时，资格不足者消费一次并保持原 res0 整段传播，没有 helper、零观测或反馈。资格满足者分别执行：

|res|实际顺序|
|---|---|
|1|原 RP helper → 一次 feedback → `pvapre_=pvacur_` → 原传播|
|2|原传播 → 原 RP helper → 一次 feedback|
|3|原 split → 前半传播 → 原 RP helper → 一次 feedback → `pvapre_=pvacur_` → 后半传播|

helper 的接受和 SA 拒绝均保留；进入分支后即使拒绝也按定义执行一次 feedback。候选不调用 `gnssUpdate`，不触发 position/yaw/RV/RD/HV，不增加 `updateCount`。正常有效 GNSS 的原 res 模板保持，RP 不追加调用。一个输入身份只消费一次；新输入即使时间相同仍是新身份，原 provider-row 复用规则不重写。新输入覆盖尚 pending 的输入时，旧身份另记 `SUPERSEDED_BY_NEW_GNSS_INPUT`，不伪造其获得过调度机会；这项仅作身份完整性记录，不改变原覆盖行为。

**独立日志与计数。** 沿用 `LEGSA_V3_OBSERVER_DIR` 的 `events.jsonl`，新增 `RP_ONLY_INPUT / OPPORTUNITY / SKIPPED / ATTEMPT / RESULT / FEEDBACK / CONSUMED`；开启日志与关闭日志的候选科学结果在全部 31 场景字节相同。原 `IMU_OPPORTUNITY` 保留原 GNSS 调度视角，不能将其 `GNSS_ALL_FLAGS_FALSE` 单独解读为新 RP-only 分支没有执行，必须同时读新事件。

每条新事件的 `data.snapshot` 保留 `candidate=N09_RP_ONLY`、定义 ID、`input_id`、pending、显式全失效位、GNSS 事件时间、候选 RP 原 row_id/time/abs_dt、原容差、enabled/solver/loaded 数、资格原因、本事件原因、当前完整状态及 dx、独立累积 counters。没有候选时 time/dt 为 `UNKNOWN`，不是零。GNSS 事件时间与 RP 行时间分开；真实 `available_time` 仍为 `UNKNOWN`。

`input_records/consumed_records/superseded_records` 包括正常有效 GNSS；`invalid_records` 仅计显式三位失效记录；`opportunity_count/eligible_count/attempt_count/accepted_count/rejected_count/skipped_count/feedback_count/rp_only_consumed_count` 只计新增 RP-only 链。机会按输入身份计，不按每 IMU 循环重复计。`RP_ONLY_RESULT` 的 context 已带实际 `measurement_attempt_seq`，可关联原 `MEASUREMENT_SELECTED / SA_EVALUATION / MEASUREMENT_DECISION` 的精确返回原因；`RP_ONLY_ATTEMPT` 位于原 helper 入口之前，其 context 中旧的 attempt 序号不能当本次完成的 helper ID。接受通过原 RP update counter 的实际增量登记，不从“资格通过”推定。

**公共只读观察层单列。** 保存科学 patch 后安装 [common/install_observation.py](../../common/install_observation.py)。公共层新增 `covariance_diagnostics.hpp`，在 `gi_engine.cpp` 原 checkCov 前调用只读 P 诊断，并在 `gi_observer.cpp` 加候选身份和原 innovation residual_vector。三个目标都在本候选副本内，无符号链接；记录见 [COMMON_INSTALL_RECEIPT.json](COMMON_INSTALL_RECEIPT.json)。公共层没有混入 scientific.patch；最终合成源码逐文件 pin 见 [FINAL_SOURCE_FILES.csv](FINAL_SOURCE_FILES.csv)。

**本轮新测试，不沿用旧 PASS。** [native_fixture.cpp](native_fixture.cpp) 分别链接旧观察库与本候选库，运行 baseline、candidate-off、candidate-on 三个新进程。每进程 31 个场景，共 93 次场景执行；每进程另有 13 个纯合成参考 engine，共 39 个参考实例。进程数仍为 3，不把场景或 engine 实例称真实 native 调用。没有真实 config/provider/reference 读取，`data_mode=synthetic_fixture_only`、`synthetic_data_used=true`、`semisynthetic_data_used=false`。

31 场景覆盖 res1/2/3 接受及 SA 拒绝、有效三位及 yaw-only 正常路径、legacy implicit-validity、RP 关闭/solver 关闭/无行/无匹配、inactive/非正/NaN std、容差恰等与略超、等距最后一行、最近 inactive 不绕过、SA-off、没有 GNSS、未来 pending、消费一次、同时间新身份、被替换 pending。拒绝 fixture 的 `reject_extreme=true` 仅用于合成门测试，不改任何正式配置或真实候选参数。

参考 engine 通过**原有效 GNSS res 模板**触发原 RP helper：纯合成 carrier 仅 yaw 位有效，但 yaw 更新与其他辅助源关闭。因此参考只做 RP、原 feedback 与原 `pvapre` reset；该 carrier 与开关安排只在 fixture，未进入候选源码。比较三步完整导航状态及 441 项 P，故能检验 res1/res3 的 feedback 后传播基点语义；参考的 GNSS 计数有意不同，不用它要求 RP-only 增加 GNSS 计数。

[FIXTURE_RECEIPT.json](FIXTURE_RECEIPT.json) 为 **592/592 检查 PASS**；[FIXTURE_CHECKS.csv](FIXTURE_CHECKS.csv) 保留逐项判断。18 个正常路径/无合格 RP/无 GNSS 负对照与旧观察库保持完整状态、P 和原科学计数字节一致；13 个新增分支场景与原模板参考三步状态/P 字节一致；31 场景观察开启/关闭状态和计数字节一致。93 个有效 IMU 末诊断均覆盖完整 21×21 P，均通过固定数值正定诊断，未写回矩阵。本数值范围不替代真实候选的逐对象检验。

必须保留的拒绝负对照：`rejected_res3` 的 RP `accepted=0,rejected=1,feedback=1`，但因拆分传播，其第一步 latitude 为 `0.5000000005095275 rad`，原整段传播 baseline 为 `0.5000000005096151 rad`，差 `-8.759659664292485e-14 rad`；候选与拆分模板参考仍字节相同。这个新合成差异不能归为接受 RP 的闭环效果，亦非真实场景精度结论。完整逐场景计数与首差见 [FIXTURE_SCENARIOS.csv](FIXTURE_SCENARIOS.csv)。

fixture 的 `STATE.csv` 无表头，字段依次为 step、engine timestamp、state.time、BLH 三值、NED velocity 三值、rpy 三值、qbn(wxyz)、Cbn 九个行优先值、gyro/acc bias 与 gyro/acc scale 各三值、P 的 441 个行优先值；末尾为空分隔项。每行 478 个实值，三行。原文件及日志均留 `<VALIDATION_BUILD_ROOT>/N09_RP_ONLY_fixture_v1`，共享 [FIXTURE_FILES.csv](FIXTURE_FILES.csv) 给完整成员/hash，不上传大构建或日志。

[run_fixture.py](run_fixture.py) 的两个显式 phase 保存每条命令开始、退出值及日志位置，拒绝自动重跑已有 phase。[COMMANDS.json](COMMANDS.json) 记录 4 条成功构建命令、3 个成功新合成进程，失败/重试均 0；真实 candidate native 与 evaluator 均 0。编译为 GCC 11.4.0、Release `-O3 -DNDEBUG -std=c++17`、CMake Unix Makefiles、`-j2`，见 [BUILD_RECEIPT.json](BUILD_RECEIPT.json)。本候选仅达到合成验证与独立审查入口，真实对象由主管另行逐槽控制；不从此处启动真实运行，不合并其他候选。
