# 同快照创新与权重离线复算

[analyze_innovation.py](analyze_innovation.py) 只读取新观察版事件；使用冻结 ca73 源码的 N6B/clean_v1 公式与 [已登记协议](../MECHANISM_PROTOCOL.md) 容差。先校验原 dz-based NIS、原权重及 R，再计算同一 dz/H/dx/P/base_R 快照上的 `nu=dz-Hdx` 影子值。N16 只取消 HV metadata 中 D 维 999 对 maxStd 的贡献，保持二维 std/R、其他 LSIM 条件、OIM 和 cap。SA 关闭不记为实际权重变化，影子值不进入求解器。

[VALIDATION_RECEIPT.json](VALIDATION_RECEIPT.json) 保存脚本/测试源码 SHA256、实际命令及逐合成日志计数。原先 25 项测试通过；审查后新增“流完整但 SA 失败”和“没有 SA 事件”两项状态门测试，最终 **27/27 通过**。最终代码对既有 11 份纯合成观察日志的 **304/304 个 SA 事件**复算通过。测试没有生成新的 fixture 或调用 native/evaluator，也没有读取真实观察日志、旧 error_series、raw/reference、NAV/STD。历史完整 unit suite 调用次数未有持久逐次日志，记为 unknown；不把测试项数当调用次数。

真实分析由根代理按身份分别执行，例如：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 docs/paper_rebuild/audit_xbpg_20261001/v3_mechanism/analysis/analyze_innovation.py --run-id RUN_00004 --publish-compact
```

此处是使用说明，不是本 worker 已执行真实分析的记录。命令先验证 original/observed 的 REPLAY_RECEIPT、ACCESS_REVIEW、5 份输出字节身份、科学 manifest、退出码与 native 计数；身份未过时不打开事件。解析再核对 BEGIN/END、连续 event_seq、末 END prior_event_count，以及 SA 前后五个矩阵/向量完全同快照。

| 字段 | 含义 |
| --- | --- |
| stream_status=COMPLETE | 事件流及配对完整，单独不代表算术通过 |
| analysis_status=VALIDATED | 完整流中存在 SA 事件，且每条均通过；退出 0 |
| analysis_status=VALIDATION_FAILED | 流不完整，或任一 SA 失败/不可计算；退出 2 |
| analysis_status=NO_SA_EVENTS | 流完整但无 SA 事件，不能声称核实了创新；退出 2 |

终端同时打印失败数和不可计算数。非零分析退出之前保存已读取证据，不改变 native 状态，不重跑或重试。无事件的 HV/RP 配置不补造 SA 行；跨 A04/F04 的不同状态也不作为同状态反事实。

全事件 CSV 与至多 24 份完整关键快照留在 `<MECHANISM_ROOT>/analysis/<run_id>/innovation/`，与同一运行的 `schedule/` 独立共存。关键快照按 source/N12/N16 分类选首条，不按误差大小挑选；原 JSONL 全部原位保留。`--publish-compact` 只在本目录的运行子目录写小型 SUMMARY.json 与 KEY_SNAPSHOT_INDEX.csv，保留原事件序号、文件行和字节位置。innovation 输出目录已存在即拒绝覆盖；只存在同级 schedule 目录不会阻止本项。

`actual_R_mutated=false`、`shadow_decision_applied=false`、`closedloop_not_tested=true` 始终明列。最终 R 的影子变化按已登记的无量纲 scale 容差判定；基准 R 为零的单元要求仍为零，不拿有单位的绝对 R 阈值掩盖细小权重变化。本说明不声称修复后的 RMSE、闭环影响或全 6468 运行的机制结论。
