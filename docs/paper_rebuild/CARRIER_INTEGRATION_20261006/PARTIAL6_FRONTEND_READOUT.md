# 六整数上限：获取与连续跟踪结果

固定选择上限六维；其余整数仍是原问题中的整数干扰参数。完整 120 个搜索窗均执行一次，仍使用 100000 节点 / 30 秒、原协方差和验收门限。默认八维实现及 V3 未替换。

16/120 个窗口生成工程上合格的初始测量，原八维为 6/120。单所有者控制器启动 15 个来源，抑制 1 个重叠合格来源；产生 70/1200 条测量（15 初始 + 55 连续），最后全部释放。七次相位诊断失败、六次选中弧改变、两次长度检验失败。

搜索结果全部保留：

| 结果 | 数量 |
|---|---:|
| UNRESOLVED_ACTIVE_ARC_CHANGED | 50 |
| EXPERIMENTAL_FIXED_CANDIDATE | 16 |
| REJECTED_RESIDUAL | 13 |
| UNAVAILABLE:partial freeze requires the exact certified selected-class search | 8 |
| REJECTED_PHASE_FAULT_DIAGNOSTIC | 18 |
| REJECTED_LENGTH | 11 |
| UNRESOLVED_COMPETITION | 1 |
| REJECTED_RESIDUAL_AND_LENGTH | 3 |

逐来源寿命见 PARTIAL6_TRACKING_RESULTS.csv。70 条连续测量来自 15 个获取来源，滚动窗口重叠；既没有真实整数标签，也不能把通过工作模型检验等同于正确固定概率。

本试验是同一开发序列上的可用性比较；当前回放时间戳尚未计入搜索墙钟耗时。导航输出和完整 H/V/yaw 指标单独见 PARTIAL6_NAVIGATION_READOUT.md；数量增加本身不证明精度改善。
