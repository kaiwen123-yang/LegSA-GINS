# HX-02E 官方 Hartley 相对位姿结果

执行登记提交：`1fc59f6067ddd326b578a7a3a47e62138ae3abe4`。官方代码为 RossHartley/invariant-ekf@ef16e8a1df72f9272111a488880e3fe9d161f59f；库源码未修改。

OFF-LIT 使用登记的论文参数；OFF-DEF 使用官方接触示例的噪声及初始状态协方差。两支的 FK 平移协方差均为 Go2 平台配置 0.010²·I；OFF-DEF 此项已由用户明确裁定，不称其为 Cassie 示例的固定默认值。

每支分别按自身输出在评估窗最初 10 s 做 yaw 和三维平移对齐。位置漂移是水平误差范数对参考累计路程的带截距 OLS 斜率乘 100；航向漂移是连续 NED yaw 误差对分钟的 OLS 斜率。负斜率表示误差在回归意义上下降，不能解释为负误差。参考为 Fixposition 输出，不作独立真值声明。

所有数值来源为 `$HX02E/RUNS/<运行>/RESULT.json:metrics`；原始评估输出及每秒以下网格误差保存在各运行 `eval/OUTPUT/`。完整精度、字段和分母见 HARTLEY_OFFICIAL_TABLE.csv。

| 运行 | 状态 | 评分历元 | 位置漂移 m/100m | 航向漂移 °/min | 水平 RMSE m | 高程 RMSE m | yaw RMSE ° | 最大水平误差 m | 参考路程 m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 OFF-LIT | COMPLETED | 2741 | 33.633600 | 31.042642 | 50.187304 | 4.140141 | 62.173499 | 120.940174 | 328.471311 |
| BY2 OFF-DEF | COMPLETED | 2741 | 21.889076 | 17.423707 | 35.463605 | 8.200648 | 42.276479 | 76.336718 | 328.471311 |
| BY2H OFF-LIT | COMPLETED | 2700 | 47.525517 | 40.766176 | 68.544623 | 3.406695 | 77.484530 | 151.366136 | 325.513916 |
| BY2H OFF-DEF | COMPLETED | 2700 | 34.015027 | 23.239761 | 51.281549 | 7.292197 | 57.617966 | 108.168332 | 325.513916 |
| BY2O OFF-LIT | COMPLETED | 3771 | 28.558852 | 13.987313 | 77.504150 | 2.043761 | 90.896028 | 136.113492 | 337.422047 |
| BY2O OFF-DEF | COMPLETED | 3771 | 11.652023 | 7.502424 | 30.683277 | 9.100259 | 35.655446 | 50.029587 | 337.422047 |

RPE 来源为同一 RESULT.json:metrics.relative_pose_error_yaw_translation；每格为平移 RMSE m / yaw RMSE ° / 配对数。

| 运行 | 1 s | 5 s | 10 s |
| --- | --- | --- | --- |
| BY2 OFF-LIT | 1.612797 / 2.546100 / 2731 | 4.817798 / 7.502526 / 2691 | 7.169306 / 11.416578 / 2641 |
| BY2 OFF-DEF | 0.724179 / 1.278525 / 2731 | 2.181398 / 2.956181 / 2691 | 3.735372 / 4.480051 / 2641 |
| BY2H OFF-LIT | 1.526682 / 2.071074 / 2690 | 4.277866 / 6.001916 / 2650 | 6.340805 / 9.346713 / 2600 |
| BY2H OFF-DEF | 0.734156 / 1.272622 / 2690 | 2.543773 / 3.727419 / 2650 | 4.368607 / 5.921574 / 2600 |
| BY2O OFF-LIT | 2.469612 / 2.851838 / 3761 | 7.967862 / 8.969428 / 3721 | 13.186072 / 14.179047 / 3671 |
| BY2O OFF-DEF | 0.494181 / 1.027665 / 3761 | 1.761952 / 2.762086 / 3721 | 3.067421 / 4.137623 / 3671 |

健全性为报告项，无门槛。yaw 差沿用 HX-02D B2 的原始陀螺 z 积分、不扣零偏、连续 FLU/up-world yaw 差及评分窗口口径；Go2 记录只在控制端核对输入与计算该诊断，不传入姿态/yaw 给原生驱动。路径统一在 10 Hz 支持网格计算。BY2/BY2O 参考分母直接取 HX-02 记录，BY2H 取本次评估结果。来源：RESULT.json:sanity。

| 运行 | yaw−原始 gyro-z °/min | 差值 RMS ° | 原生路程 m | 参考路程 m | 路程比 |
| --- | --- | --- | --- | --- | --- |
| BY2 OFF-LIT | -34.436404 | 69.562305 | 676.171024 | 328.471311 | 2.058539 |
| BY2 OFF-DEF | -21.176888 | 51.953127 | 769.364498 | 328.471311 | 2.342258 |
| BY2H OFF-LIT | -45.699576 | 89.546342 | 668.718744 | 325.513916 | 2.054348 |
| BY2H OFF-DEF | -27.984617 | 74.141239 | 974.012648 | 325.513916 | 2.992230 |
| BY2O OFF-LIT | -16.541701 | 96.852971 | 1116.289570 | 337.422047 | 3.308289 |
| BY2O OFF-DEF | -9.875900 | 43.926631 | 595.564110 | 337.422047 | 1.765042 |

与 HX-02 移植行并列，仅说明，不能把差别单独归因为库代码；初始化和参数语义也有登记差别。旧值来源：`$HX02/90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv`，按 method_id/sequence/metric 定位。

| 序列 | HX-02 移植 | 位置漂移 m/100m | 航向漂移 °/min | 水平 RMSE m | yaw RMSE ° | 失败标记 |
| --- | --- | --- | --- | --- | --- | --- |
| BY2 | Hartley-S | 34.077430 | -101.193364 | 84.155025 | 78.680738 | NONE |
| BY2 | Hartley-LIT | 36.281413 | 31.940420 | 53.399514 | 65.498731 | NONE |
| BY2H | Hartley-S | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED | ABNORMAL_EXIT |
| BY2H | Hartley-LIT | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED | ABNORMAL_EXIT |
| BY2O | Hartley-S | 9.047665 | 495.077120 | 89.675928 | 94.413474 | NONE |
| BY2O | Hartley-LIT | 27.698786 | 13.391928 | 77.552209 | 91.044958 | NONE |

Outcome：无数值门槛，全部运行保留。官方代码 OFF-LIT、OFF-DEF 两配置作为论文“四足状态估计”类别的对比行；HX-02 移植行和 HX-02D 诊断转为补充材料证据。失败行也不删除。本任务不改写 HX-02/HX-02D 原目录或 v3 结果。

执行计数见 00_CONTROL/EXECUTION_COUNTS.json；库前后身份、65 项封存、方法本体、受保护目录及归档清理见 FINAL_INTEGRITY.json。身份门示例和驱动合成检查单独计数，不混入六次真实序列原生运行。

执行附记：首次后台控制器启动在 Python 动态库加载期间中断，未打开执行脚本、无真实原生/评估调用；原因无可用记录。保留 BOOTSTRAP_ATTEMPT_1 日志及 BOOTSTRAP_INCIDENT.json 后，以同一登记代码在独立 tmux 会话完成清单。真实原生/评估均无重复调用。

覆盖说明：BY2H 首条缓存记录晚于合约 413 s，因此 413.0 s 网格点没有估计支持；不外推，评分为 2700 个历元。两支对齐各使用初始窗内的 100 个可用网格历元。出处：各 BY2H RESULT.json:metrics.scored_epochs、unsupported_grid_epochs、alignment.epochs。

并列说明：OFF-LIT 在 BY2/BY2O 的位置漂移为 33.633600/28.558852 m/100 m，旧移植 LIT 为 36.281413/27.698786 m/100 m。官方库仍给出明显漂移；这组并列不单独识别实现、噪声配置或输入模型的因果贡献。出处：本长表与上述 HX-02 表的 position_drift_m_per_100m 行。

完整性闭合：LegSA 解算/评估 0/0，真实原生 6、参考评估 6；每次 trace 成功只读打开 1 次并核 SHA256，控制器及原生参考打开 0。示例 2、合成驱动门 4，另有 1 次脚本尚未打开的后台启动中断；无真实运行重试。出处：00_CONTROL/EXECUTION_AUDIT.json、BOOTSTRAP_INCIDENT.json。

官方原仓库任务前后 status --porcelain 均为空，HEAD 保持 ef16e8a1df72f9272111a488880e3fe9d161f59f；58/58 受版本控制文件及构建副本相同，源码/构建描述 22/22 相同。文件清单摘要 SHA256 为 12eb49db447fd3ed86fb594d147f8d0c2a21df38a0db34a24b91b45bdb2c9cb1。出处：OFFICIAL_SOURCE_START.json、OFFICIAL_SOURCE_FINAL.json，摘要定义见后者 listing_definition。

65 pin 在开始、预注册提交前、结果提交前均为 65/65，CSV 均 59/59；HX-02 12678/12678、HX-02D 82/82、方法本体 423/423、既有未跟踪文件 29/29 保持不变。门检查 4/4 通过，六个运行的误差序列独立重算与指标吻合，96 行长表逐字段核对一致。出处：SEALED_*.json、PROTECTED_TREES_FINAL.json、METHOD_BODY_FINAL.json、INDEPENDENT_VALIDATION.json、LONG_TABLE_VALIDATION.json。最终归档复制与 scratch 清理状态见 FINAL_INTEGRITY.json 和 COPY_VERIFICATION.json；未创建交接包。
