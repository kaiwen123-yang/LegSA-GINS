# 完整P诊断的适用性与零方差scale

本轮完整21×21检查的 `NONPOSITIVE_DIAGONAL` 原样保留。所选七个原配置的 `gsstd/asstd/initsgstd/initsastd` 均为 `[0,0,0]`，逐字段见 [P_CONFIG_DOMAIN.csv](P_CONFIG_DOMAIN.csv)。这些是原初始化与过程模型输入，不是候选引入，也没有为诊断而修改。

冻结源码 `ca73cb1fb48a020fd2a450d79e520562c34eeb24` 的映射（均相对 `cpp/legsa_v23_port_core`）：

- `include/legsa_v23_port_core/types.hpp:49–50`：SG从15、SA从18开始，共六维。
- `src/config/port_config_loader.cpp:569–583`：上述scale标准差乘1e−6；零保持零。
- `src/kf_gins/gi_engine.cpp:33–35,53–56,768–769`：初始化std平方，scale的fallback floor也为零，所以scale初始P为零。
- 同文件`:781–782`：scale过程噪声与std平方成比例，为零；原`:522–528` 的对角检查允许零。

原P的这一建模方式与已观察到的15..20零对角相符。完整21维严格正定不是这里可以无条件要求的属性。固定诊断仍报告 `NONPOSITIVE_DIAGONAL`；归一化对称性与Cholesky均为 **NOT_TESTED**。不得事后把零改为小正数、降维后补一个全P PASS，或把这个状态直接解释为发散、候选破坏P。这里也没有由零scale模型证明其他15维或完整P半正定，原reset/交叉协方差模型的正确性仍未因此确立。

为完成有限的实际对称性说明，另用 [covariance_snapshot_supplement.py](covariance_snapshot_supplement.py) 读取分析缓存中已经按“首来源/首异常”保存的 `KEY_SNAPSHOTS.jsonl`，只计算其中确有完整P的逐元素 `P−Pᵀ` 绝对差，保留最大差的索引、441项有限数及六个scale行/列是否精确全零。此项不重扫事件，不调用solver/evaluator，不降维、不分解、不加新的通过容差。

这是事后标明目的的新增验证算术，覆盖仅限缓存的小型首见快照。它不能替代原版所有EKF快照或候选所有IMU历元的对称性核对。不同协方差块单位不同，带索引的全局最大绝对差只是描述值，不能称为共同物理量纲的误差。实际已读取17个缓存中的211个完整关键P，结果见 [covariance_supplement/](covariance_supplement/README.md)。

此补注只闭合本轮诊断解释，不自动增加滤波重构、reset修补或下一轮审查。
