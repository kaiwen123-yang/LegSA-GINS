# 已固定新增执行合同：3新native +6复用整batch

本页是代码/协议检查点；正式execution pins及绝对stage别名由外部PREREGISTRATION.json在提交后冻结。本页不能当作已完成运行收据。旧8文件和strict结果不改。

## 九个比较身份

三次新Oi native：BY2无重启控制（1块/285节点/正式275）、H分段诊断（全部3块/282原计划节点/正式271）、O分段诊断（全部7块/420节点/正式378）。六次Wen/GNC来自已封存最终PAPER_CONTRACT完整batch；逐RUN、输出、source snapshot和input hash复用，绝不贴上新源身份。比的是GNSS1位置/实际时间支持；传感器信息和batch未来信息不相同。

BY2全部原12列STATES以exact array_equal(equal_nan)比旧strict；status及全部原solver-event字段精确比较，只忽略新block/history字段。不是按参考误差设容差。任一差异阻止offline，先找原因。H/O所有预登记块必须attempt，哪怕前一块数值失败；后块起点由**先有真实gap**决定，不能在块内failure后新初始化。失败块尾部invalid，全部槽位保留。

每块真实A1/位置/速度/std/bias来源及时间记录；暂无合法init就等待且行invalid。H414单节点块attempt并记prior-only，不能称传播/完整增量阶段。PRIMARY_DYNAMIC_ONLY排除每块INITIALIZED行；SECONDARY_ALL_VALID_POSITION单列这些位置prior；两个表同原分母，GNC/Wen不人为在IMUgap停机。

## 物理量及offline

Oi原IMU状态用其**自己**的FRD→当前NED姿态与lever[.03,.03,-.3]m转换GNSS1。Wen/GNC原输出已在GNSS1。参考仍是既定midpoint，使用冻结原yaw转换及半基线偏移到GNSS1；共享GNSS参考独立性继续开放，不叫独立truth。

三方法同一个正式window-start局部N/E/Up锚，frame不随valid support改变；不对方法输出插值。仅GT范围内支撑有效；保留每行reference左右插值时刻和跨度，拒绝GT重复/倒序。自身及共同三方法support分别算，common名义秒±5ms，duplicates拒绝，允许两方法实际差最多10ms并明示。这只是应用数据不同信息下比较，不是同输入solver榜单。

先完整封存全部3新native+6reuse，审核OS-open实际reference0，才可每序列一次读取reference并评价，之后独立复算errors与指标。保存实际anchor LLH、reference min/max/clean count以允许独立坐标复算而不重复打开rawreference。Native/evaluator/process数精确报告3/3和6reuse，旧69不重复累加。本新增14合成边界测试验证新合同，不当论文全复现。

## 3286和资源

O新合法连续块3286处只观察实际是否触发Ceres、窗口/因子family、初终cost/迭代、scaled normal特征值/rank/condition；保持原20步、3/3/15度、30/40窗和噪声。normal条件约等于Jacobian条件平方，仅诊断，绝非准入/score调参门。新状态历史不等于旧3286相同问题；若未实际触发Ceres，明确不能声称再次验证该Ceres失败。

G新stage≤256MiB、E新增≤64MiB，复用existing库/venv，不copy raw、不下载大author材料。G的256KiB分配簇下，整个Python包+FGO C/C++用无损ZIP snapshot，避免872个小文件×3造成约654MiB簇分配；封存逐成员SHA。source identity superset只表示身份覆盖，不假称全部执行。每native记录snapshot/config/protocol/lib/输入/输出和source before/after。全段后native seal发布给root，供其独立offline-only EXT解释诊断绑定；不能由原已封存source漂移否定历史结果。
