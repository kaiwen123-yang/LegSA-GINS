# LegSA-GINS：原V3全量故事的当前阅读入口

这是一套面向论文写作的完整任务、配置、指标、选型和比较账本。正式方法名称是 **LegSA-GINS**；F04/AB1111只作内部证据映射。原科学冻结commit `7d43b9af26120ed5dde21f53e515386361072ba6`、原binary `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`、原evaluator `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da` 的身份保持，本故事没有纠错、更改或重跑原V3。

按以下顺序读即可从项目选择走到论文论证，不需要先读全部历史日志：

1. [全部任务与指标账本](01_FULL_TASK_LEDGER.md)：CORE5951＋ADD495＋H/O22＝6468实际native配置；588案例×11方法，12370完成评价＋566未运行槽位；128指标逐项解释入口、完整失败/NA及源身份。
2. [源码→方法→配置→指标](02_METHOD_CONFIG_METRIC_STORY.md)：原冻结C++滤波/机械编排/测量更新、15活动＋6固定状态、position/RV/yaw/RD/RP/HV各角色及六信息源、33非运输模型、单变量配置、评价物理点与128量纲。
3. [为什么最后选这些，以及完整矩阵实际结果](03_SELECTION_HISTORY_AND_FULL_MATRIX_RESULTS.md)：BY2标定及选择历史、全部55组成功/失败、原17汇总的138600算术字段核对、56项单模块方向和全部588案例组；小问题是适用边界与历史选择披露，不启动V3纠错。
4. [所有外部比较及公平边界](04_COMPARISON_INVENTORY_AND_FAIRNESS_STORY.md)：23原注册＋补充条件共30读者身份、7模块analogue；RTKLIB四条件/双位置基线、LC01/S、单接收机更新IEKF、官方GINav/Hartley、raw EXT核心、严格FGO和新增分段FGO分别说明。

自然序列LegSA-GINS的原V3 H/V/3D RMSE(m)为BY2 0.097906/0.048996/0.109481，BY2H 0.068362/0.045352/0.082038，BY2O 0.054543/0.045859/0.071260；yaw RMSE为1.886272/1.933770/2.433815°。这些是被冻结评价合同下相对商业融合参考的成绩，参考不是已经证明的独立truth，也不是可任意跨物理点的通用排行榜。canonical来源为[NATURAL_METHOD_RESULTS.csv](NATURAL_METHOD_RESULTS.csv)中 `internal_method_id=F04`、`evaluator_contract=evaluator_contract_v3` 的三行，字段 `yaw_rmse_deg` 原token依次 `1.8862718548526467`、`1.93377013508875`、`2.433814932823714`；注册原表CORE_541_TABLE_V3.csv第5行与SEQUENCE_TABLE_V3.csv第12/23行（含表头）对应，同字段V2/V3相同。更多自然配置也在该表，原token保留。

大账本使用确定性gzip无损保存原CSV字节，避免Git重复存放80MB的重复绝对路径。检查行数/hash或提取全字段可用此目录的[reader](read_ledger.py)：

```sh
python3 read_ledger.py --help
python3 read_ledger.py tasks --verify
python3 read_ledger.py metrics --verify
python3 read_ledger.py actions --verify
```

具体CLI以 `--help` 为准；第一块[打包回执](LOSSLESS_LEDGER_PACKING_RECEIPT.json)绑定gzip与解压后原字节，plain本机副本只是忽略文件，科学源数据没有删除。[TASK_LEDGER.csv.gz](TASK_LEDGER.csv.gz)、[METRIC_LEDGER.csv.gz](METRIC_LEDGER.csv.gz)、[NATIVE_ACTION_LEDGER.csv.gz](NATIVE_ACTION_LEDGER.csv.gz)分别含6468、12936、6468行。两套metric合同分开，未输出/发散/NOT_RUN保留，不把NA改成零。

原实验根：`<G_PROJECT>/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/`；原注册在 `<PROTOCOL_V3_SCRATCH>/00_PREREGISTRATION/REGISTRY.json`，scratch为 `/home/kaiwen/research/LegSA-GINS-SCRATCH/CLEAN8_PROTOCOL_V3`。各run具体路径、源hash、输出hash及历史留存/释放状态在任务/action账本中。部分全量native/error大payload按原已授权保留策略释放，原输出索引、标量、hash、失败记录和留存1188native/2376评价payload仍有证据；不能把已释放payload称仍可逐项重新读，也不能把释放说成未执行实验。

本入口为第四个追加块，前三块各自README/收据及原字节不可变。第一块18文件提交baf4e915，第二块11文件db4d1064，第三块27文件62f2f09e；第四块[READY回执](FOURTH_BLOCK_READY_RECEIPT.json)封存新增文件并确认前56文件不变，不将当前新增诊断源码当成原V3执行源码。

横向比较最新时点：EXT V2九新身份及名义投影解释检查已经完成；严格OiSAM B275/H0/O55保留，新分段诊断另立身份、3个新Oi＋6个旧Wen/GNC复用，主动态Oi支持275/267/370，排除prior-only行；本块接收的是全部native/offline seal及36原指标行。随后FGO独立包[SEGMENTED_RESULTS](../FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/README.md)的36行全表、三序列图及独立验收已完成并推送25e437b；本块历史接收seal及copy不回改，本块不冒称自己重新视觉审核。当前入口不把历史UNAVAILABLE占位当最新状态，不把新分段成绩回贴严格表，不新增V3运行。

阅读诚实边界：全量注册/配置/聚合指标使用完整机器字段核对和身份封存；关键方法、选择及结果解释按[四份coverage](READ_COVERAGE.csv)、[02](READ_COVERAGE_02.csv)、[03](READ_COVERAGE_03.csv)、[04](READ_COVERAGE_04.csv)记录人工全文/选段/同blob继承范围。这是可追溯的全量任务与指标故事，不声称全仓数百万行日志、大raw/trace或所有文献每字已人工审核。
