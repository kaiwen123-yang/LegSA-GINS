# 已记录生成依赖策略：局部资格与全输入准备

登记 `07637339a3cc531d042397c4ff154c4eeca53d30`；初始源码登记 `fa7ccec`。初始计划的 identity 调用计数在任何执行前修正，源码未变；没有运行失败或重试。总进程耗时约12.03秒。

8个Python合成用例、8组native固定用例首次全部通过；一次configure、一次build、一次harness compile。覆盖真实loader与setter身份错误、缺项/unsupported不消费、双时钟及后一ULP、原容差过期、先资格筛选再latest/tie、同时间水位、provider/SA拒绝消费、generation/feedback，以及真实GNSS/ARC/res1调度。旧两策略附加metadata的同二进制输出相同；历史三窗输出兼容尚需下一阶段核对。

|序列|完整HV行|有插值支持|无支持且ready空|helper调用|
|---|---:|---:|---:|---:|
|BY2|63278|60867|2411|8|
|BY2H|63221|61669|1552|8|
|BY2O|95860|87091|8769|12|
|合计|222359|209627|12732|28|

六份固定科学输入各一次有界读取，共67,191,365字节，读取的缓存各核一次SHA。没有原始关节/NPZ/参考读取，没有速度重算。固定8192行分块，所有旧字段的原字节、行顺序和换行保留；`a1_heading_valid==support`，`valid==update_flag==(go2_source_valid && support)`逐行通过。此三窗恰好supported等于原valid，代码没有把二者预设等同。

新增五列绑定schema、完整provider向量索引、HV时间bits、支持标志和ready。supported的ready取HV行时间与最新非零历史GNSS18端点原始行时间的最大值；unsupported的ready留空。三份新增CSV共79,640,482字节，原CSV未改。

新策略`causal_recorded_dependencies_unique_latest`只在research NED horizontal模式可用。依赖未就绪不消费，仍须满足原0.08秒source-age；合格后先选最新，再消费整个timestamp，质量拒绝不退款、不在同次调用回退。新模式输出尾部计数表示候选扫描次数，不能称独立观测数。

资格二进制SHA `9bde21f71a7035341a7830586e4ff80ed9cc80a8f92c427e1f11b1a03b659d2d`，1,266,440字节。真实native/evaluator调用均为0。本结果不能证明物理arrival、上游原始采样或SDK/状态独立性，也不能计作航向/导航收益。

下一步固定六次真实回放：候选二进制旧causal三窗与封存15文件/窗比较，全部通过后执行新策略三窗；不得由旧4598次中删除3683次来预测新的更新数。详情机器记录[HV_DEPENDENCY_QUALIFICATION_RESULTS.json](HV_DEPENDENCY_QUALIFICATION_RESULTS.json)及事前计划[HV_DEPENDENCY_QUALIFICATION_PLAN.json](HV_DEPENDENCY_QUALIFICATION_PLAN.json)。

独立复核：heading_evidence只读COMPLETE、JUnit、各进程回执及选定合成输出，确认顺序/计数和边界。旧causal CSV保持20列，新策略27列；未重读原科学输入或完整派生CSV，原字段保真结论依赖准备门及manifest，不扩大为全文件系统访问审计。
