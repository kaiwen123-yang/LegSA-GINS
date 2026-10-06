# 单工作线程可用时间：独立审查

结论：在已登记的“原记录 C-ILS 服务耗时、单工作线程、其余成本为零”模拟范围内，当前实现未发现阻断性问题。允许父任务在源码冻结后决定执行一次新 provider；本审查没有启动真实模型重放、C-ILS、native 或参考评价。

## 被审查身份与边界

- 被审查实现：scripts/paper_rebuild/carrier_phase/latency_tracking_frontend.py。
- 实现 SHA-256：1a0a48a0839a632cf139a2b08a07191b6b985426bcab6816ac25d54691053929。
- 对照合同：[SERIAL_LATENCY_REPLAY_PLAN.md](SERIAL_LATENCY_REPLAY_PLAN.md)，注册提交 9795895。
- 读取旧 tracking_frontend.py 的原始 receipt 恢复、acquisition_schedule，以及 FixedCandidateTrack.start/observe/missing 的身份与释放约束。
- 本轮必须使用 PARTIAL6 原始封存记录中的 search.certificate.elapsed_s（execution commit 跨 c25a48e→dbf 的同一科学冻结链，后者仅文档变化）；不得把另一个 18-call 性能基准中的新缓存耗时或其中位加速比代入全部 120 个任务。它们不是本模拟的服务时间输入。

## 代码核验

1. RecordedJob 只向服务调度暴露身份、原 selected_at、原五个 validation 时间与 recorded elapsed。SerialService.offer 只按 selected_at 与 busy_until 启动/丢弃；拒绝和未认证搜索仍占用原耗时。记录预读仅为固定模拟输入，valid/status 不影响 launch/drop。
2. busy_until 为 selected_at + elapsed，完成时立即释放服务线程；无需等到原第五个 future 时间。ready == completion 可启动，无排队。结果到达要求当前 raw 时间同时不早于完成时刻与原 validation_end，没有向前容差。
3. 每个 raw slot 独立处理当时的启动机会与满足可用时间的结果；到达结果按 completion、selected_at、case_id 的稳定顺序交给所有权状态机。最后 raw 时刻之后才满足可用性的任务保留 pending，不能截断时间强行发布。
4. incumbent 在历元入口存在时拥有整个历元，包括其失败/释放时刻；所有新到结果被永久抑制。无 owner 时，前一候选追赶死亡允许后续候选尝试；成功获得 owner 后，剩余新到结果抑制且不排队。seen_arrivals 拒绝同一到达复活。
5. 晚到候选恢复原五个模型、原整数对、admission、GLRT、测量及协方差 receipt；FixedCandidateTrack.start 重新核验指纹。之后逐一重放原 validation_end 之后的每个模型；缺测或任一 release 立即永久丢弃。不会只检测当前好历元而跳过历史失败。
6. 历史内部调用旧接口的 availability_time_s 是“逻辑数据时间重放”，不代表过去真实发布。日志明确 INTERNAL_CATCHUP_NOT_EXPORTED、processed_at_simulation_time_s，且区分 original_validation_end 与 scheduler_acquired_at。只有当前历元的 measurement_time == decision_available_time == now 可进入 CSV。
7. 原 acquisition/tracking/prepared PLAN 及各 acquisition case hash 关联得到验证；新 manifest 记录科学源码。配置、N、门和 Q 不随结果改动。各 mode 是独立反事实回放，各自一名 worker，不是 full/partial 同机并行资源模拟。

## 独立测试

tests/test_carrier_latency_review.py 在 Ubuntu 22.04 WSL 中通过 11 项，纯调度与 mock 跟踪：

- 固定种子 884216，200 组、每组 25 个任务；与独立 interval oracle 逐项比较 launch/drop、首个合格 raw 到达时刻、稳定顺序及末尾 pending。随机费用包含零、恰好两秒、两秒加微小量及超过窗口的长耗时。
- 服务完成与 ready 恰好相等可启动；等待原 validation 不占用已经完成的服务线程。
- completion 比 raw slot 晚 1e-12 s 时不得提前输出。
- 追赶经过 missing 时永久死亡，不再访问更晚的“好”模型；幸存只导出当前测量。
- 原结果不可用时不创建 track。
- 多 arrival 中首个追赶死亡可尝试第二个；第二个成功后永久抑制第三个。
- incumbent 失败历元仍抑制有效新到候选。
- NaN、Inf、负 elapsed 拒绝，不能替成零耗时。

实现方另有 16 项专用测试。独立 11 项未替代真实 provider 身份审查或硬件时间验证；纯 mock 测试没有接触 raw/reference，也没有执行搜索、native 或 evaluator。

## 仍然成立的科学限制

这是记录服务时间的理想化模拟，不是实时软件实现或最坏执行时间证书。模型准备、数据加载、验证、GLRT、catchup、tracking、导出、导航、启动和资源争用全部计为零；实际系统会有额外延迟。延迟处理修正发布因果性，不证明整数正确、完整性或测量协方差已校准。

后续导航只能使用本次新 provider，保留全部 1200 raw 历元及无效行，在原完整窗口比较。C0/C1/C2 必须与 PARTIAL6 字节一致；四个 native 全部封存后才允许四个 frozen evaluator。不得为获得更多更新而改门、重排任务、复活被丢弃任务或回填旧测量。
