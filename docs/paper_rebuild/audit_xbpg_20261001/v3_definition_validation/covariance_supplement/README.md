# 已保留关键P快照的有限对称性补充

17个已完成事件缓存中的首来源/首异常快照按原event_seq与P字段去重，实际读取211个完整21×21 P。211个均441项有限，六个scale行/列均精确为零。没有再次打开原events，没有solver/evaluator/reference调用。

逐元素最大绝对反对称差为1.1102230246251565e-16；全量211条见KEY_P_SYMMETRY.csv，来源指针、快照行号、P_before/P_after均保留。这只是已有首见快照的描述，未新增通过阈值，不能证明全部时间序列对称或完整P半正定。全部时间支撑的冻结诊断仍先遇NONPOSITIVE_DIAGONAL；归一化对称/Cholesky未执行，不用这个补充改写该状态。

最大差所在键：`BASELINE/ADD_RUN_00103, event=270, /data/snapshot/P_before, indices=[3,0]`。不同块单位不同，最大绝对差不能用作统一物理误差指标。

方法、零scale配置/源码和未改变判据的边界见[共同说明](../P_MODEL_BOUNDARY.md)；纯合成算术测试及输入/预期见[测试脚本](../test_covariance_snapshot_supplement.py)。回执同时保留测试时源码pin和随后仅添加数据角色标签的版本说明，不将计数当科学正确性证据。
