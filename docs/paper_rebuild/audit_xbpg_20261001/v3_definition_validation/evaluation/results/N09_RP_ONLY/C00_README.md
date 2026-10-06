# N09_RP_ONLY：C00 两个负对照

C00/A04 与 C00/F04 的候选评价均为 `COMPLETED_CANDIDATE_COMPARABLE`。每个对象与已闭合基线的 142 个全窗对照字段全部相同，所有数值差值为零；既有原生回执同时记录 5/5 输出 `BYTE_IDENTICAL`。本项没有精度改善或退化。

| 对象 | H RMSE (m) | Up RMSE (m) | yaw RMSE (deg) | roll RMSE (deg) | pitch RMSE (deg) |
|---|---:|---:|---:|---:|---:|
| [RUN_00006 / A04](RUN_00006/CANDIDATE_BASELINE_FIELDS.csv) | 0.09691990156944293 | 0.05001891586618585 | 1.886000833151237 | 2.067087299693141 | 2.141149184458976 |
| [RUN_00004 / F04](RUN_00004/CANDIDATE_BASELINE_FIELDS.csv) | 0.09790607774950152 | 0.04899590433188947 | 1.8862718548526467 | 2.254340402339318 | 2.265490744005314 |

表中数值直接转录各对象 `FULL_METRICS.json`，基线值相同；完整差值和来源见各对象 `CANDIDATE_BASELINE_FIELDS.csv`。两个基线各已完成 143/143 原有字段核对，本项复用这些结果，没有再运行 baseline evaluator。

双方 output/matched/精确时间交集均为 56,642 历元，时间数组完全相同；实际范围 `66.005054..339.997056`，注册评价窗 `[66,340]`，coverage 1。参考窗计数 5,480、清洗后参考计数 6,040。各 17/17 evaluator 门通过，NAV/STD 全 33 列有限，无插值或删历元。

## 字节身份来源

两份来源为 `<VALIDATION_ROOT>/candidates/N09_RP_ONLY/<run_id>/CANDIDATE_RECEIPT.json#/output_hashes`，原回执用当次候选新 hash 对照基线已记录 hash，标明 `old_payload_read=false`。其五项为 EVAL_NAV.csv、KF_GINS_Navresult.nav、KF_GINS_STD.txt、LegSA_PORT_NAV.nav、LegSA_PORT_STD.csv。本评价对所用 NAV/STD 重新核其当前 hash；其余三项沿用该小回执，未新增读取这些正文。

新转换的 POI NAV 同样与对应旧 evaluator NAV pin 相同：

- `RUN_00006`：`497f66ef84d42998f46753eaac90fb83f21d09ae5f7d0247d57b636b9ee38d3c`，见[评价回执](RUN_00006/EVALUATION_RECEIPT.json)。
- `RUN_00004`：`375663491799b93d5c69251f7cad0edc21bc8ac8732a59600fede2a67b0fb8db`，见[评价回执](RUN_00004/EVALUATION_RECEIPT.json)。

## 次数与解释范围

准备提交 `88f2042cef57f0b151117e3bc122ea7025454c5e`。本项 evaluator 子进程 2 次、参考子进程读取 2 次；parent 参考正文读取 0、native 0、重试 0、Git 0。评价账本累计各 13 次，其余 4 个 N09 A1/A2 评价仍未调用。新大载荷在 `<VALIDATION_ROOT>/evaluations/N09_RP_ONLY/<run_id>/`。两对象均 real_clean、synthetic=false、semisynthetic=false。

这仅支持本候选在两个 C00 负对照上保留原输出与评价结果，不替代其事件分支核查或 A1/A2 的实测结果。N09 按当前定义为可选 RP 入口扩展，不从本负对照推导原设计必须独立更新或历史违约。参考仍非独立真值，STD 未传播至 POI；无参考速度，不计算速度 RMSE。
