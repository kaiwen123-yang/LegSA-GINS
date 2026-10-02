# 保留时序：实际读完的范围和不能复算的部分

最终逐文件表为 [RETAINED_SERIES_CHECKS.csv](RETAINED_SERIES_CHECKS.csv)，2309 行中 2308 是 error_series，1 是 matched trajectory。`series_checks/GROUP_READ_SUMMARY.csv` 给出十六批回执；机器合计在 `series_checks/FULL_READ_SUMMARY.json`。这些合计仅读取已生成 CSV/JSON，没有再次打开 gzip。

## 完整性与本轮验证计算

全部 2308 个 error_series 主扫描各一次，读至 gzip EOF 并通过 CRC，合计 131,210,304 数据行；唯一 matched trajectory 56,642 行也读至 EOF。总计 131,266,946 行、13,314,046,312 个压缩字节，同一主扫描计算的未压缩 SHA256 全部匹配原 recorded hash。新验证 hash 与 recorded hash 分列，未把旧 pin 填成新计算。

全部导出字段内非有限单元格、重复时标、逆序时标均为零；这描述保留文件正文，不证明原始 reference 无重复或全 NAV 没有缺失。时间间隔、首末时刻、正间隔中位数、最大 gap、固定阈值 gap 计数和时间向量 hash 逐文件保留。三序列自然 C00 的最大 gap 分别约 0.091676/0.176012/0.379999 s；起止包络不能替代连续覆盖证明。

每份 error_series 都有可复算字段并已核对，总计：

|状态|检查单元格数|含义|
|---|---:|---|
|MATCH|381,501|原记录和本轮独立验证在预先冻结的定义、支持和容差内一致；含 matched 导出的可核对项|
|MATCH_NULL|332|双方按同一定义均不可得；不是误差为零|
|NOT_RECOMPUTABLE_FROM_RETAINED_FIELDS|20,777|保留字段不足或超出冻结扫描的定义范围；详见下面逐类清单|
|超容差差异|0|不表示原算法、参考或所有评价字段均已验证|

本轮**执行了新的 validation calculation**：保留误差上的指标复算、固定窗口统计、计数及逐 case 配对算术。历史 collection 的 `new_performance_statistics=0` 回执未改写。每个 METRIC_CHECKS 行保存 recorded_value、check_value、原源 JSON pointer/行键、denominator、差值、容差和源精度。浮点容差在首次载荷读取前固定为 abs 1e-10 + rel 1e-10×abs(recorded)，计数精确、时间 abs 1e-9；没有根据结果放宽。

error_series 的十三字段、单位、物理点、坐标、signed/absolute/squared 关系、STD 诊断与 mask 限制已经在 `SCHEMA_AND_TOLERANCE.md` 冻结。只有导出的匹配历元，没有原始有效 mask 的完整集合。逐分量 RMSE、人口 SD、分位数、wrap、原 trapz gap 处理等严格沿原定义核对；这不把该定义本身判为科学正确。

## 为什么不是 2308 次独立 native

v3/v2 各 1154 个 error_series，对应 **1154 个完成的物理 native**。计划保留 1188 native 中的另 34 个失败没有误差输出，不能补成零。唯一 matched 属于其中一个 native，不再增加一次运行。自然三序列的不同配置来自同一条录制；CORE 保留选择主要为固定 seed00，A1/A2 为已指定种子，保留集合不是随机抽样。

此前总账记载另外 10,062 份 error_series 按策略释放、566 评价槽未生成；全采样 NAV/STD 各 6,378 份释放、90 失败未生成。这些是上一轮保留对账，本轮没有重做全盘库存，也没有为其重跑。不从 1154 个保留成功 native 外推全矩阵正确率。

## 具体不可复算项

`UNSUPPORTED_METRICS.csv` 为完整分项：每个 error_series 有九项，合计 20,772 项。

- output_epoch_count、unmatched_epoch_count、reference_epoch_count：只导出匹配误差，无法知道原 NAV/参考全体支持。
- coverage_ratio、finite_output、finite_ratio：需要未导出的输出/匹配前有效性分母；不能由现存文件全有限就填 1。
- evaluation_runtime_seconds：正文不编码原进程用时。
- meta/base_time、meta/yaw_truth_mode：绝对时间原点、参考航向构造不在误差字段中。

唯一 matched 导出缺 roll/pitch/error 投影列，冻结扫描没有进行另一套地理投影；H、3D、up、roll、pitch 五项未作同定义复算。时间、共同支持及由保留 yaw 字段支持的检查已完成。这里的“未作投影”是本次冻结核对范围，不是声称用户禁止一切独立坐标算术。该 matched 不能代替已经释放的完整 NAV/STD。

所以“2308 份可复核”表示每份的**保留字段所支持的指标**，不是 2308 份评价所有字段均重现。需要原始参考资格、匹配前支持、真实在线状态或新求解的信息仍未知。

## 已知局部窗口遗漏与旧窗口差别

冻结窗口收集器只接受数值 pair，未提取两个 bundle 中 dict 形式的 intervals；`WINDOW_LIMITATIONS.csv` 保留原 JSON pointer：

|case|影响保留文件|实际窗口|本轮状态|
|---|---:|---|---|
|D22_seed_00|22（11×2）|[348.205852,352.205852)，在原评价全窗 66–340 s 之外|正文和原全窗指标已核对；局部窗口未新算|
|D39_seed_00|22（11×2）|[82.204517,84.204517)、[182.204872,184.204872)、[349.204539,352.204539)|前两段在窗内、末段在窗外；正文/全窗已核对，三个局部窗口未新算|

这是本轮收集器的明确缺口，不是原算法错误证据，未用第二遍主扫描补算。D22 的原配置窗口确实在全窗外；其 seed00 error 的未压缩 hash 与相应 C00 相同，证明这批保留误差相同，不证明从输入重得同一 NAV。D22 的“行数/秒数”描述与实际实现单位差异见 `core/position_value/README.md`。

其他 `WINDOW_SUMMARY.csv` 同时保留 evaluator_event 和 registered_fault 的边界。部分旧 event 帮助字段与真实 provider centered interval 不同；不拿一个替换另一个。post 通常延伸到全窗末端，不是测得的恢复时长。所有新固定窗口统计标为 validation derived，不冒充原报告已发布的故障窗成绩。

四个不同结论必须分开：转录/汇总一致；保留误差与原统计一致；从原输入复现同一 NAV；算法数学与参考独立性可靠。本轮完成前两者的明确范围，后两者没有执行。solver、provider generator、原 evaluator、aggregate/controller、bootstrap、raw/reference/NAV/STD payload 新调用均为零，原文件没有写回。
