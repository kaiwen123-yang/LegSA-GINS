# SDK与计量证据入口（2026-10-05）

先读 [官方接口与作者事实](OFFICIAL_INTERFACE_AND_AUTHOR_FACTS.md)，再读 [TIM测量链和clock模型](TIM_MEASUREMENT_CHAIN_AND_CLOCK_MODEL.md)。两块均为文档证据，不是已完成校准，也不替换原V3或诊断实验身份。

- [23项输入不确定度预算台账](INPUT_UNCERTAINTY_BUDGET.csv)：未知量保留NOT_ESTIMATED，实际新八包POI/VRTK配置与旧序列分列。
- [最小验证协议](MINIMAL_VALIDATION_PROTOCOL.md)：可识别性和接受标准，尚未执行。
- [Methods英文与中文解释](METHODS_INSERT_EN_AND_ZH.md)：当前事实与未来验证分别写。
- [官方计量来源及阅读范围](OFFICIAL_METROLOGY_SOURCE_MAP.csv)；[首块公开源码pins](OFFICIAL_SOURCE_PINS.csv)；[首块阅读覆盖](READ_COVERAGE_BLOCK01.csv)；[本块阅读覆盖](READ_COVERAGE_BLOCK02.csv)。

事件匹配只证明有归属的起点选择方法；一次事件不能分离clock offset/drift/latency。共享GNSS商业reference下的RMSE是agreement指标，不能直接作为标准不确定度。当前submission_ready=false。

本轮不绘图、不执行新的native/provider/evaluator，不改科学数据或封存收据。GPS Solutions相关定位将在独立文档追加，TIM预算不等于AR新方法。
