# Clone 导航比较器：接口与局部检查

仅派生已封存评价结果，不运行任何 solver/evaluator，不打开参考。与旧控制器/比较器分开命名，不更改它们的 IDS、ARMS 或输出。

入口：

~~~text
python3 scripts/paper_rebuild/carrier_phase/compare_clone_window_navigation.py \
  --stage <SEALED_CLONE_STAGE> --baseline-stage <SEALED_PREVIOUS_SIX_STAGE> \
  --v3-root <ORIGINAL_V3_ROOT> --out <NEW_COMPARISON_DIRECTORY>
~~~

原 V3 lock/facts 固定 SHA，三份旧 error_series 逐个核对原 pin。新六臂和旧六臂终态 metadata 检查各自 PLAN→native seal→evaluation complete 链；真正读取旧结果只需三条 CARRIER_FALLBACK。实际读取的 NAV/STD/error_series/result 必须在相应 seal 中且匹配 SHA。评价器、reference 身份元数据与物理点变换均校验；不存在 error_series 的行不相信残留 summary 数字，指标为 NA。

输出 schema：trusted_heading.clone_navigation_comparison.v1。

- V3_COMPARISONS.csv：12 行，即新六臂的完整冻结评价 / 与原 V3 实际匹配键的精确交集；同原九指标容差，不插值或借共同支持替代完整窗。
- ATTRIBUTION_DIFFERENCES.csv：21 行；每窗 PAIR−NULL、NULL−旧 fallback、PAIR−旧 fallback，各完整与实际精确共同支持，再加同三方共同键的可加性分解。PAIR−NULL 的全部指标同时保留原始差值和零容差非退化布尔量。
- COVERAGE.csv：六行，包括窗口首末、匹配/未匹配、缺少原 V3 实际键、最长实际输出间隔等；不把传播当作绝对航向量测覆盖。
- ZERO_UPDATE_IDENTITY.csv：三行；PAIR 无实际更新时严格检查与 NULL 的 NAV/STD 字节身份；有更新时不预设相等。
- COMPARISON.json：gate、来源 pin、实际键事件、右删失和缺失；事件规则完全复用既有 yaw>2° / H>2m / |Up|>3m 与稳定1s末端确认。

采用口径：原 A 仍要求新 PAIR 三窗九指标/coverage 非退化，且至少两窗 yaw RMSE 相对原 V3 下降5%。建议人工复核还要求这些窗在完整支持和完全相同的 NULL/PAIR error 键上均有严格正的 PAIR−NULL yaw 收益，至少两窗；各窗 matched support 必须完整相同。该项是测量收益归因条件，不增加新的性能改善阈值。零容差九指标非退化单列，不偷换原 V3 工作容差。微小浮点改善会如实列原值，不能据该布尔量声称统计显著。

NULL−旧 fallback 的改善属于 reset/事件分割/后端数值路径，不能写成足测量改善。B 在此没有 raw-fault 恢复场景，保持 NA；整数正确率、false-fix 概率、速度真值指标也为 NA。共享商业 GNSS reference 不是独立真值。没有 main 替换授权。

局部事前登记仅一个纯合成检查：原/旧 fallback yaw10、NULL9、全 SKIP PAIR9 时原 A 可以通过，但足归因建议必须失败；另外独立指定 PAIR8 检查真实额外收益、可加性；缺少实际时键不能给完整支持结论，空序列保持 NA。首轮一次 pytest，1 PASS，0.09 s；失败0、重试0。日志和源码 pin 在 CLONE_COMPARATOR_LOCAL_RECEIPT.json。没有执行真实比较，也没有因真实结果修改阈值。
