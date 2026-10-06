# AR 小试与 TIM 测量论证（2026-10-06）

**决定：V3 照常成稿；AR 有值得继续检验的信号，尚未形成新的方法贡献。** 本轮实际执行了有限原始载波试验、已知整数检查和测量误差传播验证，全部在 E 盘 Ubuntu-22.04 WSL；原 V3、生产源码、历史结果和现有稿件保持原身份。

先读 [给作者的决定](01_AUTHOR_DECISION.md)，它回答“值不值得继续 AR、怎样解决新颖性、TIM 怎样补、如何不耽误成稿”。

## 三项关键结果

- **真实载波前端有改善信号。** 12 个预选 BY2 历元全部记账，3 个支持不足。A 标准长度约束与 B 附加倾角弱先验在共同 9 点上，对共享商业参考的近似航向一致性 RMSE 为 60.18°／2.44°。A 是本次 RAW 前端，V3 未参加这组比较。真实整数正确性仍为 NA。
- **已知整数试验显示收益与失效同时存在。** 4 个固定噪声实例中，A 有 3 个整数正确，正确 RP 的 B 有 4 个；正负严重 RP 故障的 8 个配对条件中，B 出现 5 个错误候选。简单一致性 C 拦下它们，却也拒掉正确 RP 纠正 A 错误的实例。不能据此估计真实风险率。
- **TIM 的模型可以具体补。** 已完成投影角、相关位置误差、时标/安装灵敏度及错方向长度门反例的合成验证。0.35 m 水平基线仅横向差分误差这一项要控制在 1°／0.5° 标准不确定度，对应约 6.109／3.054 mm。尚未完成设备校准与独立测量覆盖验证。

## 阅读与复核

| 需要了解 | 文件 |
|---|---|
| 作者决定与成稿安排 | [01_AUTHOR_DECISION](01_AUTHOR_DECISION.md) |
| 最近似论文、哪些不能再称创新、两刊定位 | [02_NOVELTY_AND_VENUE](02_NOVELTY_AND_VENUE.md) |
| 原始载波 12 点小试、完整支持与结果 | [03_AR_QUALIFICATION](03_AR_QUALIFICATION.md) |
| 可入稿的测量公式、源码身份、合成检验及最小实测 | [04_MEASUREMENT_AND_VALIDATION](04_MEASUREMENT_AND_VALIDATION.md) |
| 独立检查、调用数、残差/角度重算及后续合成复核 | [05_INDEPENDENT_REVIEW](05_INDEPENDENT_REVIEW.md) |
| 一致性否决门为何不能同时增加正确可用率 | [06_MINIMAL_PROPOSAL_AND_STOP_RULES](06_MINIMAL_PROPOSAL_AND_STOP_RULES.md) |
| 带真整数的配对噪声/故障试验 | [SYNTHETIC2_RESULTS](SYNTHETIC2_RESULTS.md) |

原始载波试验协议和全部选择/pin 在 [AR_CONTRACT](AR_CONTRACT.md)、[AR_PREREGISTRATION](AR_PREREGISTRATION.json)；后续合成单独登记在 [SYNTHETIC2_CONTRACT](SYNTHETIC2_CONTRACT.md)、[SYNTHETIC2_PREREGISTRATION](SYNTHETIC2_PREREGISTRATION.json)。后者是在第一阶段结果后设计并冻结的机制探索，不冒称盲测。

## 完成边界

完成：12 次真实 cold SPP，18 次真实 C-ILS；初始已知整数检查 16 次 C-ILS；后续机制检查 16 次 C-ILS；合计 50 次 C-ILS。原始载波在线参考读取 0、封存后离线参考读取 1；后续合成不读取 raw/reference。测量传播单独运行 1 个合成进程。无导航滤波重跑、无原 V3 改动；各冻结试验内均无按结果追加历元/seed/调参。

没有完成：新 AR 验收理论、正式错误固定风险校准、真实整数真值、连续恢复试验、独立外测标定或期刊新颖性保证。倾角辅助、坏先验退出和错误固定恢复已有近作；本轮结果证明值得讨论的现象，没有证明方法首创。

后续仅在能写出超出现有机制的具体决策时再扩大研究；否则保留 V3，补现有测量证据。源码脚本与全部小表随研究分支提交，WSL scratch 留存完整 payload 与调用账本。
