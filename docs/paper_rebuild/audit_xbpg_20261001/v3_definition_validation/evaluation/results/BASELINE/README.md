# 七个原基线：新 v3 评价口径核对

七个已登记原基线均为 `COMPLETED_BASELINE_GATE_PASS`。每个转换后的 POI NAV hash 与原记录一致；每个 143 项原有字段核对通过，七份共 1,001 项，所有有数值差值的项均为零。此结论是同一冻结评价口径的复现，不是对参考独立性、算法数学或总体实验可靠性的证明。

本次仅调用最后五个尚未评价的基线；先前完成的 RUN_00004、RUN_01401 没有重跑。各对象完整原值/新值、容差、来源 JSON pointer 在 `BASELINE_FIELD_CHECKS.csv`，全指标在 `FULL_METRICS.json`。下表直接转录本轮全精度值；H/Up 单位 m，yaw 单位 deg。

| 原身份 | 方法 | H RMSE | Up RMSE | yaw RMSE | 旧新核对 |
|---|---|---:|---:|---:|---:|
| [RUN_00004](RUN_00004/BASELINE_FIELD_CHECKS.csv)：C00_clean_normal | F04 | 0.09790607774950152 | 0.04899590433188947 | 1.8862718548526467 | 143/143 |
| [RUN_01401](RUN_01401/BASELINE_FIELD_CHECKS.csv)：D15_seed_00 | F04 | 3.5569029035745645 | 3.9238010989307734 | 2.698608937739373 | 143/143 |
| [RUN_00006](RUN_00006/BASELINE_FIELD_CHECKS.csv)：C00_clean_normal | A04 | 0.09691990156944293 | 0.05001891586618585 | 1.886000833151237 | 143/143 |
| [ADD_RUN_00105](ADD_RUN_00105/BASELINE_FIELD_CHECKS.csv)：D61_20s_seed_00 | A04 | 14.37239919313786 | 1.3398986219328846 | 1.9928866823595006 | 143/143 |
| [ADD_RUN_00103](ADD_RUN_00103/BASELINE_FIELD_CHECKS.csv)：D61_20s_seed_00 | F04 | 14.8962849820269 | 1.3038156320506586 | 1.9940410608763517 | 143/143 |
| [ADD_RUN_00402](ADD_RUN_00402/BASELINE_FIELD_CHECKS.csv)：D62_20s_seed_00 | A04 | 0.20755841962690857 | 1.8276537479128219 | 1.8829301879186475 | 143/143 |
| [ADD_RUN_00400](ADD_RUN_00400/BASELINE_FIELD_CHECKS.csv)：D62_20s_seed_00 | F04 | 0.20006768091577798 | 1.8233615017572633 | 1.8832103492119665 | 143/143 |

## 转换后 NAV 身份

| run_id | 本轮 evaluator NAV SHA256（等于旧记录） |
|---|---|
| [RUN_00004](RUN_00004/EVALUATION_RECEIPT.json) | `375663491799b93d5c69251f7cad0edc21bc8ac8732a59600fede2a67b0fb8db` |
| [RUN_01401](RUN_01401/EVALUATION_RECEIPT.json) | `d1fef028cfec0d4c58089dd4817225c87abebb5d6283bacba58963a894457e2a` |
| [RUN_00006](RUN_00006/EVALUATION_RECEIPT.json) | `497f66ef84d42998f46753eaac90fb83f21d09ae5f7d0247d57b636b9ee38d3c` |
| [ADD_RUN_00105](ADD_RUN_00105/EVALUATION_RECEIPT.json) | `52be3f73790e5681fa0c72e781bf9cc78bfcc5658f8a76b0a0971a5dbebf2e06` |
| [ADD_RUN_00103](ADD_RUN_00103/EVALUATION_RECEIPT.json) | `cf40e6114e7ffd1c49d0a0391f872fd8e8feecc42bd552c62bd2a15fa907571c` |
| [ADD_RUN_00402](ADD_RUN_00402/EVALUATION_RECEIPT.json) | `cb4b6c6e6473eb77659e1e8da6c8a380ad88f673a4d73cb456a8a5810bded92e` |
| [ADD_RUN_00400](ADD_RUN_00400/EVALUATION_RECEIPT.json) | `9c8bdd220b71873ce14c23366b798da05541e65e43a05d5d8f4abf3a5a334cc7` |

## 支持、派生窗及调用账

七份均有 56,642 个原输出和匹配历元，coverage 1，匹配范围 `66.005054..339.997056`，评价窗 `[66,340]`。每份 reference window count 为 5,480、cleaned reference count 为 6,040；二者不是 NAV 匹配数。每份 17/17 evaluator 门通过，NAV/STD 全 33 列有限，缺失没有填零，未删历元。

A1/A2 的四份 `FIXED_WINDOW_METRICS.json` 另外保存本轮新派生的前段 `[66,196.2)`、中断 `[196.2,216.2)`、后段 `[216.2,340]`。各段明确保留 output/matched 支持，分段参考历元数为 unknown（null），没有为补参考分母再读 trace。这 12 个分段结果不计入 1,001 个旧字段复现项，也不当作旧表原有数字或终点误差。

七个基线分别一次 evaluator child、一次参考 child open，合计各 7；本小项新增各 5 次。连同先前四个 N12/N16 候选，本轮账本 evaluator/reference 累计各 11 次；其余 6 个 N09 候选评价仍未调用。parent 参考正文读取、native、自动重试、Git 操作均为 0。每份 STARTED/BEFORE_EVALUATOR_CALL/终态回执均保留；未出现失败或计数未知槽。

前两基线准备提交 `af74931169deb1f94576277f35df2b976a4286dc`；本次五份使用 `291c6c6f87990430a07ad44882b92ed62337df12`，科学入口与阈值/容差未改。源 reference 为原融合解；STD 未传播至 POI，仍为 `UNTRANSPORTED_STD_DIAGNOSTIC_ONLY`，不计算没有参考支持的速度 RMSE。

两份 C00 为 real_clean、synthetic=false、semisynthetic=false；D15/A1/A2 五份为 semisynthetic、synthetic=false、semisynthetic=true。新载荷保留在 `<VALIDATION_ROOT>/evaluations/BASELINE/<run_id>/`，只引用 `<MECHANISM_ROOT>/replays/<run_id>/original/` 的已完成原生输出，旧 V3 性能源未改写。
