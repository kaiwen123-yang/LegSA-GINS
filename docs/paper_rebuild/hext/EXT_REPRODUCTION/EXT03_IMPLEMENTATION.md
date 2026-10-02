# EXT03 新版本：单历史适配与合成验证

本文件保留实现/运行前依据及该测试小项的历史计数；当前三序列执行状态和真实结果见[最终比较](FINAL_COMPARISON.md)。

接口在 [`reproduction_ext03.py`](../../../../src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_ext03.py)：

```python
engine = ReproductionEXT03Engine(provider, lambda_library)
record = engine.step(receiver1_rawx_epoch, receiver2_rawx_epoch)
```

一个对象对应一个序列的一条连续历史，参数固定为 `GPS_BDS_DUAL_FREQUENCY / CONSTRAINED / sigma_s=0.010 m`。不建十模式网格，不引入 GPS-only fallback，不在对象之间共享历史。调用者负责输入 pin、provider 生命周期、冻结动态库身份、真实/合成数据角色和输出落盘；构造引擎不打开原始数据或参考，也不启动旧 phase3 生命周期。

## 数学核心与输入变化的边界

旧 [`ext03_yang2024.py`](../../../../src/legsa_gins/paper_rebuild/horizontal_literature/ext03_yang2024.py) 保持原样，新对象直接调用其 `process_epoch`。顺序为 DD 更新、带噪声长度行、MLAMBDA 两候选及 ratio 检验。`build_dd_observation`、`reconcile_ambiguity_state`、`detect_cycle_slips`、`constraint_update`、`mlambda_resolve` 仍是同一旧核心。

新共用输入层为 [`reproduction_backend.py`](../../../../src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_backend.py) 的 `build_dual_frequency_blocks`：两接收机分别使用自己的 RAWX `(T,P)` 得到广播卫星时刻，GPS/BDS 分星座 pivot，保留双频及共享 pivot 协方差。公式和保留近似见 [REPRODUCTION_NOTES.md](REPRODUCTION_NOTES.md)。本项不重复实现这层几何，也不使用历史 phase-bias 数值纠正当前观测。

SPP 使用原始 epoch。`common_signal_epochs` 在双方相同精确 `SignalIdentity(gnss_id,sv_id,sig_id,freq_id)` 中，以较小一侧 C/N0 最大、再以 identity 排序的固定规则选择每频每星一个信号；筛后的同一组 epoch 同时送 DD 和 GF/MW。每个记录保留 `signal_selection_audit`。此前成功 KF 历史中的同星同频 raw identity 变化，通过旧 `actual_carrier_lli_tracking_discontinuities` 接口重置对应 DD，包括 pivot 影响；不把新 sig_id 的相位静默继承到旧 ambiguity。

信号选择记忆只在 KF 更新成功后推进；更新失败时尚待处理的 signal switch 会在下一次仍被报告。筛选只含 integer-compatible 观测，因此本轮另行明确补齐原始追踪适配：每个原始 epoch 在 SPP 前读取 carrier valid、locktime、half-cycle/subhalf 和 receiver-clock 标志，使用旧事件条件，按 `(receiver, exact raw identity)` 积累 pending 原因。GF/MW/先验 DD 调用旧 helper 时使用临时 raw memory，不能消费 live history。成功 KF 后，仅消费本次实际 block 的卫星或 pivot 对应 selected raw identity；失败及未入模型的信号保留 pending。未选中的另一个 sig_id 的 invalid 不能重置当前正常成分。

这项原始标志保存和 pending 生命周期是本轮输入适配修正，防止共同有效信号筛选丢掉 invalid→valid 证据；不是声称论文唯一指定了这种调度。没有改旧核心的 slip 门限、Q、R 或 ratio 规则。逐历元新增 raw 事件、pending 前/应用/后的 audit。

## 递推和失败规则

复用旧 `phase3_runner.run_variant_sequence` 的 SPP 和 KF 更新规则，而不调用其 runner；原始 tracking 的读取位置按上述明确修正：

- 接收机 1 SPP 成功后立即保存其下一历元种子，随后才求接收机 2；第二接收机失败不撤销第一接收机的新种子。
- 每历元以原始 `SPP2−SPP1` 重置 baseline 先验及 baseline 交叉项，方差 `900 m²`；ambiguity 继续递推/重映射，并采用原 cycle-domain 过程噪声。
- 原始 tracking 记忆在 SPP 前更新；SPP、DD、数值或整数搜索失败时，raw history/pending 保留，KF state 保持上次成功状态。相对旧循环的变化仅是原始标志可见性和 pending 消费时机，不在失败行伪造新姿态。
- 首次没有成功 fixed 时，长度行方向采用原始 SPP baseline；若有上次成功 ratio-fixed baseline，则先用它。旧核心没有 fixed 过期参数，新对象不补一个新阈值。
- 当前 float 历元仍输出当前 float，`fixed_baseline_ned_m=null`。保留在 state 内的 `previous_fixed_baseline_ned_m` 只解释约束方向，不冒充当前 fixed 输出。
- SPP/DD/KF 失败生成 `solution_state=invalid`、原 `failure_code`、`state_updated=false`。当前 baseline/yaw/length/covariance 字段均为 `null`；单独的 `state` 可保留以前成功状态，必须连同其 `epoch_time_s` 阅读。
- 配对必须同 GPS week、同 TOW 且有限；同一对象严格 TOW 递增。乱序/配对错误在 SPP 或状态改变前抛出异常；不推断跨周转换。

## 字段和单位

|字段|含义|
|---|---|
|`solution_state`, `paper_ratio_fixed`|`float` / `paper_ratio_fixed` / `invalid`；ratio-fixed 是论文接受规则，不是整数正确真值|
|`baseline_ned_m`, `body_yaw_deg`, `baseline_length_m`|本历元选中 fixed 或 float 的 baseline、项目物理转换后的 body yaw、长度；baseline heading 另外保留|
|`float_baseline_ned_m`, `fixed_baseline_ned_m`, 两个 attitude|两条结果分别保存；baseline pitch 不等于完整三轴机体姿态|
|`state`|完整原 `EXT03State`：历元、`[b_N,b_E,b_D,N_DD...]`、协方差、ambiguity identities、上次成功 fixed 和 tracking memory|
|`ambiguities`, `covariance`|float cycles、最佳/次佳整数、精确身份及完整混合单位协方差；不是仅取对角线|
|`ratio`, `ratio_is_infinite`, `mlambda`|次佳/最佳 ambiguity 目标；最佳为零时沿用 `ratio=null` 和独立无限标志，不输出非法 JSON Infinity|
|`slip`, `state_diagnostics`|旧核心全部周跳类别/受影响身份/初始化标志及新增、移除、重置、pivot 计数|
|`spp_audit`, `dd_audit`|两个 code-only SPP 原字段；全部 block、H/R/z、行域、ambiguity 顺序及每信号几何项|
|`signal_selection_audit`, `signal_switches`|双方精确信号选择，以及切换前后 raw identity 和对应旧核心信号身份|
|`raw_tracking_audit`, `tracking_pending_before/applied/after`|未经过有效观测筛选的四类原事件；pending 保留 receiver+raw identity，送核心时才映射其频率身份；失败后仍可核查|
|`stage_evidence`|分别记录两个 SPP 的 attempted/returned/accepted、`DD_MODEL_BUILT`、`CORE_PROCESS_CALLED`，以及 float/MLAMBDA/两个候选的阶段证据；不能用 `state_updated` 代替|

`ambiguity_correctness_known=false`；输出不读取参考。`_jsonable` 保留双精度数值和完整矩阵，非有限诊断值以字符串 `NaN/+Infinity/-Infinity` 保留，不改成零；缺失仍是 `null`。矩阵和逐历元记录应由调用者保留在本机运行根，不能作为巨量 Git 源表。

阶段证据使用三值语义。SPP/DD 前失败且未调用 core 时，`float_solution_returned`、`mlambda_attempted`、`mlambda_completed`、`mlambda_result_returned`、`two_candidates_returned` 可明确为 `false`。一旦进入旧 `process_epoch` 而它抛错，可能已完成 KF 或整数搜索；旧 core 不暴露中间回执，所以这些内部字段均为 `null`，`internal_stage_status=UNKNOWN_CORE_CALL_NOT_RETURNED`，附未知原因和原异常 token。不能仅凭 `state_updated=false`、`solution_state=invalid` 或错误名字把阶段次数补成零。

core 正常返回后 `float_solution_returned=true`；本对象始终传入 MLAMBDA 库，因此 `mlambda_attempted=true`，并从实际 `MLAMBDAResult.candidate_returned/best_integer/second_integer/failure_code` 登记两候选和完成状态。`mlambda_result_returned` 表示核心获得诊断对象；`mlambda_completed` 要求无 failure code 且两候选确实返回。ratio 不足 3 的 float 行也可能已经完整执行 MLAMBDA；它的这些字段仍为 true。旧 `MLAMBDAResult` 没有 `status` 字段，原结果不被臆造字段代替。

## 参数来源

新 `parameter_registry()` 只给这一套 primary 参数，排除旧 sensitivity grid 与明确 inactive 的 RTKLIB 默认。仅修改新 registry 的出处标注，不改旧封存表：

|参数|本次值|来源|
|---|---:|---|
|baseline length|0.350 m|`PROJECT_PHYSICAL_CONTRACT`；原文不是该数值|
|初始 baseline 方差|900 m²|论文明确|
|初始 ambiguity 方差|900 cycle²|论文明确|
|ratio 阈值|3.0|论文明确，次佳/最佳目标比|
|长度 sigma|0.010 m|既有工程值，不称论文给定|
|moving-base 先验重置、ambiguity Q、GF/MW/prior-DD 阈值、SPP/DD noise|原已登记值|`ENGINEERING_INHERITED_NOT_PAPER_DISCLOSED`，保留 `inherited_source` 原出处|

`inherited_source` 中出现旧 `paper-disclosed` 仅记录旧 baseline 行的错误标注；新 `source` 和 `paper_disclosed_value=false` 才是当前裁定。原文未充分给出的 Q/F/R、首次均值及 fixed staleness 不能据此称已精确复现作者唯一实现。

## 本轮测试

最终 `EXT03_TEST_ATTEMPT_03`：**57 passed，0 failed，0 skipped**，其中新文件 24 项、旧 EXT03 核心文件重新执行 33 项。第一版 `EXT03_TEST_ATTEMPT_01` 的 50 PASS（17 新 + 33 旧）及 raw tracking 补齐后的 `EXT03_TEST_ATTEMPT_02` 的 55 PASS（22 新 + 33 旧）均保留。第三次新增阶段证据并验证 SPP 前失败与 core 内进度未知、ratio 拒绝但搜索完成的区别。合计本轮三个 pytest 进程、162 次测试项执行，最终不同测试项 57。机器日志/JUnit/逐次回执在 `<EXT_REPRO_ROOT>/tests/EXT03_TEST_ATTEMPT_0{1,2,3}.*`；公开小回执为 [TEST_RECEIPT.json](TEST_RECEIPT.json)。这不是沿用旧测试数量，前两次日志没有覆盖。

新测试包含：同一个 b0、同一个 prior P 下 DD→pseudo、pseudo→DD 和堆叠观测与独立信息形式解的一致性；真实 `process_epoch` 的 DD→pseudo→MLAMBDA 顺序；pivot 对 Qba 和跨频协方差的完整变换；周跳重置的受影响行/列；ratio 恰好 3 与相邻下浮点数；首次没有 fixed、后续保留 fixed 方向但当前 float 不冒充 fixed；SPP2 失败、tracking 后失败、exact-signal 切换后数值失败的历史处理；严格配对/乱序与 JSON/新参数出处。

后加 5 项分别验证 carrier-invalid→valid、half-cycle-invalid→valid 在 locktime 不下降时仍保留原事件；SPP2 失败期间原始 invalid 不被吞掉；未入模型的另一 exact component 的 pending 既不丢失、也不误施加到当前有效 component；正常连续流没有额外 raw reset。所有失败/边界输入都是明确构造的负对照，没有真实数据重放。

原生库测试每次仅用构造的二维 float ambiguity 和相关 Q，调用已 pin 的 RTKLIB MLAMBDA 返回两个候选，与独立小整数穷举目标逐项核对（三次 pytest 各 1 个原生库合成请求，合计 3）。SPP 由纯合成 fake 提供；真实 RAWX/provider、参考、评价器、科学运行均未调用。合成测试通过仅说明这些公式和状态规则，尚不是三序列实测结论。

第 3 次定向测试的两条完整合成失败记录另存 `<EXT_REPRO_ROOT>/tests/EXT03_TEST_ATTEMPT_03_evidence/EXT03_STAGE_FAILURE_EXAMPLES.json`，含明确合成标志、原失败 token、SPP/DD/core 各阶段值和 UNKNOWN 原因，可直接检验失败状态没有被换算成未调用。
