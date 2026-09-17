# H-EXT-03 执行记录

状态：`COMPLETED_H_EXT_03_AGGREGATION`；code freeze `b6aaece1b71737693e39ec72ce0ad0726b188592`。授权与 D7–D12 见 H_EXT_02_CONTINUATION_AUTHORIZATION.md，合约 v1.1。完整 v3/v2 表、遮挡并排、delta、来源、解释与限制见 ../HORIZONTAL_THREE_SEQUENCES.md。

## 实际预算与终态

```json
{
  "native_actual": 0,
  "native_reused": 14,
  "evaluator_actual": 10,
  "reused_evaluations": 16,
  "skipped_algorithm_failure_slots": 2,
  "new_unavailable_evaluation_failed": 0,
  "historical_failed_evaluator_invocations": 1,
  "historical_evaluator_actual": 17,
  "native_budget": 0,
  "evaluator_budget": 11,
  "prereg_identity_native": 0,
  "prereg_identity_evaluator": 0,
  "evaluator_retry_count": 0,
  "total_evaluator_actual_including_h02": 27,
  "total_evaluation_terminal_slots": 28
}
```

本次 10 evaluator 全部通过，trace 子进程各一次，无重试；14 native 复用、不重跑。累计 27 实际 evaluator calls 与 28 科学槽分开：26 成功，2 NOT_RUN_ALGORITHM_FAILURE；旧失败原记录保留。

## 门与来源

- 前置核验 v1 包 1,084,956,510 字节 / 570 成员、511 阶段文件 SHA；均 PASS。
- D8 全 native 14：13 PASS、1 DIVERGED；历史成功评估回溯 16/16 PASS。首个越界事实及全部最大值见 08_AGGREGATE/BOUNDED_OUTPUT_GATE.csv。
- 测试 94 passed；read-only code review PASS；ext05_pavlasek.py/phase5_runner.py 无 diff。
- 26 成功评估的 104 个 scratch/archive error/capture/audit 文件 SHA 对应一致。
- 每序列 PRE/POST raw 22 metadata / 21 nontrace SHA 均通过；trace 由10新 evaluator的唯一句柄核验。
- 原 28 图、RENDER_MANIFEST、旧99与native及失败评估前后身份相同。
- 09 全率 NAV 不在核验过的 v2.1 ZIP/FINALIZE；4 项 UNAVAILABLE。A10为早期校准链，不替代。
- BY2O v2.1 full-rate error series 4 项双重 hash pin、76548 行；exact窗口只读派生，未用ZIP的10Hz展示投影。

## 图与完整交接

FIG02S PNG/PDF/SVG，4182×2938 PNG，自动10项及根代理逐图视觉QA PASS；独立 HEXT_RENDER_MANIFEST，原28图不变。新图manifest由 pending 状态完成视觉复核后登记为 RENDERED_QA_AND_VISUAL_PASS，新增FIG02S_VISUAL_QA.json；不改原28图任何文件。

结果提交为本记录所在提交。两个 H03 commit 与两个 H02 commit 在交接 ZIP 的 GIT_COMMITS.json 中完整登记；结果提交只修改文档。`<HANDOFF_ROOT>/hext_three_sequences_handoff_v2.validation.json` 在结果提交后登记整包SHA/字节数与逐成员SHA/CRC，ext4先写、G:独占复制并回读验证。旧v1包不动。

## 簿记附录

1. D7 重新分类科学槽不抹去原失败进程：v3 历史失败调用仍计一次；v2根本未调用。
2. D9是明确的看到结果后修订，不改native起点身份；论文行字段与原run_matrix拓扑分开。
3. 16旧评估result_reused=true，原scientific code_commit保留；native全部reuse。
4. 精确遮挡窗口与旧冻结分段端点不相同；从核哈希全率误差系列重汇总并标只读派生，不改标签或用10Hz。
5. 09全率NAV缺失按UNAVAILABLE继续，算法发散行按D7继续；本次无新D12评估不可用。
6. 一个合成回归夹具因新增post-evaluator身份门缺虚拟文件，已创建不执行的虚拟评估器并pin其SHA，未弱化真实哈希门；修复后94passed。
7. 包哈希与结果提交避免自引用：commit记录外部receipt位置，包在提交后嵌入完整commit哈希。
8. 执行后的收尾仅做来源/簿记/UI元数据完成，不修改冻结科学代码或参数；所有scratch保留，无外部删除。
