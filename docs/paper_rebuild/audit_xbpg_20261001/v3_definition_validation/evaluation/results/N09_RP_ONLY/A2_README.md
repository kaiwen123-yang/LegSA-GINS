# N09_RP_ONLY：A2 两个负对照与评价账闭合

ADD_RUN_00402/A04 与 ADD_RUN_00400/F04 均为 `COMPLETED_CANDIDATE_COMPARABLE`。每对象全窗 142 项对照字段全部相同；before、fault、after 各段的 142 项统计/支持字段也分别全部相同。既有原生回执各记录 5/5 输出 BYTE_IDENTICAL。本项没有精度改善或退化。

下表是本轮候选值，也是对应本轮基线值，差值均为零。完整全窗值直接来自各对象 FULL_METRICS.json/字段对照；分段是本轮固定窗 validation calculation，不能叫旧表原值或终点误差。

| 对象 | H RMSE (m) | Up RMSE (m) | yaw RMSE (deg) | roll RMSE (deg) | pitch RMSE (deg) |
|---|---:|---:|---:|---:|---:|
| [ADD_RUN_00402 / A04](ADD_RUN_00402/CANDIDATE_BASELINE_FIELDS.csv) | 0.20755841962690857 | 1.8276537479128219 | 1.8829301879186475 | 2.066872257850443 | 2.1409171425744247 |
| [ADD_RUN_00400 / F04](ADD_RUN_00400/CANDIDATE_BASELINE_FIELDS.csv) | 0.20006768091577798 | 1.8233615017572633 | 1.8832103492119665 | 2.2545567956422405 | 2.2652675864170067 |

## 固定分段

段内基线与候选值相同，以下只列一份值；全量五轴及其他统计见各对象 FIXED_WINDOW_METRICS.json。半开窗未改变，分段 reference count 均为 null（未知），未新增参考读取补分母。

| 对象 | 固定段 | 双方匹配/输出数 | H RMSE (m) | Up RMSE (m) | yaw RMSE (deg) |
|---|---|---:|---:|---:|---:|
| [A04](ADD_RUN_00402/FIXED_WINDOW_METRICS.json) | before [66,196.2) | 27387 | 0.044417121423498476 | 0.04082263564429652 | 1.5593278174938967 |
| [A04](ADD_RUN_00402/FIXED_WINDOW_METRICS.json) | fault [196.2,216.2) | 3678 | 0.7210799731569756 | 7.169678185537965 | 2.1747913034552093 |
| [A04](ADD_RUN_00402/FIXED_WINDOW_METRICS.json) | after [216.2,340] | 25577 | 0.13609522319929737 | 0.05987807875966778 | 2.137258819134434 |
| [F04](ADD_RUN_00400/FIXED_WINDOW_METRICS.json) | before [66,196.2) | 27387 | 0.04506805951189013 | 0.04068262321805115 | 1.5579994848704155 |
| [F04](ADD_RUN_00400/FIXED_WINDOW_METRICS.json) | fault [196.2,216.2) | 3678 | 0.6856569039114336 | 7.15293292164543 | 2.1742666004235476 |
| [F04](ADD_RUN_00400/FIXED_WINDOW_METRICS.json) | after [216.2,340] | 25577 | 0.13734363364021365 | 0.05815193341220015 | 2.1389188718425625 |

## 支持、身份和范围

两个对象的全窗基线/候选 output、matched、精确共同时间交集均为 56,642，时间数组相同，coverage 1，实际范围 66.005054..339.997056，全窗 [66,340]。reference window count 为 5,480，cleaned reference count 为 6,040。各 17/17 evaluator 门通过，NAV/STD 全 33 列有限，无插值或删历元。

原生字节身份来自 `<VALIDATION_ROOT>/candidates/N09_RP_ONLY/<run_id>/CANDIDATE_RECEIPT.json#/output_hashes`，其五项为 EVAL_NAV.csv、KF_GINS_Navresult.nav、KF_GINS_STD.txt、LegSA_PORT_NAV.nav、LegSA_PORT_STD.csv；原回执以候选新 hash 对照已记录基线 hash，标 old_payload_read=false。本评价另核其实际使用的 NAV/STD 当前 hash；其余三项只读取小回执。新转换 POI NAV hash 也与对应基线相同，详见两份 EVALUATION_RECEIPT.json。

该结果支持两个保留 yaw 的 A2 对象作为本可选 RP 入口扩展的负对照；不单凭相同 RMSE 推断每个调度分支，分支/接受事实留给独立事件核查，不宣告原设计历史违约。两对象均 semisynthetic、synthetic=false、semisynthetic=true。参考非独立真值，STD 未传播至 POI；没有速度真值，不计算速度 RMSE。

## 17 槽实际调用闭合

本项使用准备提交 `5460eb7817fcda1a6ba63d13873639f730366d49`，新增 evaluator child 2、reference child open 2。全部 17 槽现在为 7 个 COMPLETED_BASELINE_GATE_PASS 和 10 个 COMPLETED_CANDIDATE_COMPARABLE；调用 attempts、实际 evaluator child、参考 child open 均为 17，无失败、未启动、未知计数或重试。七基线共 1,001/1,001 项原有字段核对通过，10 个候选均有与相应基线完全相同的时间支撑。

评价工作本身 parent 参考正文读取 0、native 0、Git 0；此前候选 native 是其他回执的独立计数，没有混入 evaluator 数。详见 [最终计数回执](../../EVALUATION_FINAL_COUNTS.json) 和 [逐槽账本](../../EVAL_MANIFEST.csv)。原性能记录保留，新大载荷在 `<VALIDATION_ROOT>/evaluations/<variant>/<run_id>/`。评价账闭合不等于数学、机制或参考可靠性审查完成。
