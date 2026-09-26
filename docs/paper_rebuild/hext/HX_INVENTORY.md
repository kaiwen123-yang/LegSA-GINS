# HX-INV 外部方法只读盘点

终态：`PASS_HX_INV_READONLY_INVENTORY`（未触发任何硬停条件）。任务开始 2026-09-23T12:24:24Z，第二次封存表比对 2026-09-23T13:31:58Z。

任务 HX-INV 为只读盘点：解算调用 0 次、评估调用 0 次；未改任何封存文件、配置或参数；
参考轨迹数据文件（trace CSV / bag / fpl）没有任何进程打开。另有 1 起导入事故
（`hext/matched.py` 被部分导入，第 15 行即中止）和 5 项子代理规则偏差（涉及 4 个子代理），均不属于硬停条件，
逐项见 §9，不并入解算/评估计数。

本文中的 CLEAN4 与 H-EXT 旧数值只作盘点，不进任何手稿表。评估器版本或评估点与 v3 不同的旧结果在
§3 各方法的"现存结果"与 §4.2 逐条标出。

路径别名：`$W` = `/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair`；
`$V3` = `<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3`；`$STAGES` = `<CLEAN_ROOT>/stages`；
`$CLEAN4` = `$STAGES/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON`；
`$HEXT` = `$STAGES/CLEAN7_HEXT_EXTERNAL_SEQUENCES`；`<CLEAN_ROOT>` = `/mnt/g/LegSA-GINS-project/clean_rebuild_202607`
（由 gitignored 的 `$W/configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml` 解析，只读）；
`$EXTERNAL` = `/home/kaiwen/research/LegSA-GINS-EXTERNAL`。

## 0. 概要

| 项 | 结果 |
| --- | --- |
| 起点 | 分支 `stage/clean3-math-repair`；`git pull --rebase` 返回 up to date；HEAD `4d932c9cbf5258d14fa2cc65991a5fe3df5ab11c`；`git merge-base --is-ancestor` 对 4d932c9、fb39cb8、7d43b9a 均为真。本地领先 origin 4 个 FC-01 提交（4b9d734、8443c57、cce42f7、4d932c9），随本次 push 一并推送 |
| 任务开始 | 2026-09-23T12:24:24Z（北京时间 20:24:24，会话首个工具调用） |
| 身份检查 | PASS（§1.2） |
| 封存表 sha256 比对 | 一致：65/65 登记文件（59 CSV）一致，未登记 0、缺失 0；两次比对见 §1.3 |
| 解算调用 / 评估调用 | 0 / 0 |
| 导入事故（单列，不计入上行） | 1 起：`hext/matched.py` 部分导入（§9.1） |
| 子代理规则偏差 | 5 项（4 个子代理），均未写文件、未调用二进制或评估器、未打开 trace/bag/fpl 参考轨迹数据（§9.2） |
| 方法行数 | CSV 23 行：dual_antenna_ambiguity_heading 6、legged_state_estimation 1、loosely_coupled_gnss_ins 12、single_antenna_gnss_ins 4、other 0（§2） |
| A1/A2 工况 | A1 27 + A2 18 = 45，与预期一致（§5） |
| 18 型候选 | 18 型，覆盖 11 族中的 9 族；"航向偏差"与"IMU"两族在 D01–D60 中无对应型（§6） |
| 产出 | 本文件、`HX_INVENTORY.csv`、`$W/AGENTS.md` 一行记录；E: 未存任何文件，G: 未新建目录，未开 scratch，未打包 |

## 1. 身份检查与哈希比对

### 1.1 身份检查（只读 `$V3/07_AGGREGATE/MAIN_TABLE_V3.csv`，行号含表头）

| 项 | 所在行 | 表中值（全精度） | 按期望位数舍入 | 期望 | 结果 |
| --- | --- | --- | --- | --- | --- |
| LC01 文献配置 BY2 C00 yaw RMSE | 第 17 行（BY2, LC01, LIT, FILE_START） | 2.9948274600591076 | 2.994827460 | 2.994827460 | 一致 |
| EXT05C BY2 C00 yaw RMSE | 第 18 行（BY2, EXT05C, LIT, FILE_START） | 12.048641737808111 | 12.048642 | 12.048642 | 一致 |
| F04 BY2 yaw RMSE | 第 4 行（PROTOCOL_V3）；`07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv` 第 27 行（C00_clean_normal） | 1.8862718548526467 | 1.886272 | 1.886272 | 一致 |
| F04 BY2H yaw RMSE | 第 9 行；FULL_ABLATION 第 12 行 | 1.93377013508875 | 1.933770 | 1.933770 | 一致 |
| F04 BY2O yaw RMSE | 第 13 行；FULL_ABLATION 第 23 行 | 2.433814932823714 | 2.433815 | 2.433815 | 一致 |

两张表的当前 sha256 与登记值相同：MAIN_TABLE_V3.csv `cd734338cf89518679d78179f410a79ecad3060535d3b80e43a62545cee9b21c`，
FULL_ABLATION_TABLE_V3.csv `44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1`
（`docs/paper_rebuild/v3/V3_01R_FINAL_REPORT.md:314,375`）。

### 1.2 封存表哈希比对

登记清单的定位链：
- fb39cb8 提交内的 `docs/paper_rebuild/v3/V3_01R_FINAL_REPORT.md` §7A 登记了
  `00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/BASELINE.json`（`7830a1a596077558d0f2289c066dbd81b1f53e6c25adc8ec0c8833ee055a503b`）与
  `MACHINE_QA_AND_TABLE_IDENTITY.json`（`6a0d2914df1ac20ef48b1fcfe2a35e7a10bcae53f56b73e18ba5f5e53918114f`），
  §7B 登记了 `09_HANDOFF/PACKAGE_DISPOSITION.json`（`1e698d64…`）与 `09_HANDOFF/FINAL_ACCEPTANCE.json`（`50b1f09d…`），§7A 登记 `00_CONTROL/DONE.json`（`2020dce5…`）。
  这五个文件的当前 sha256 与登记值逐字相同。
- `BASELINE.json` 的 `files_sha256` 即 V3-01-R 收尾核过的 65 项身份（59 CSV + 6 个 json/md），
  status `PASS_REVIEWED_TABLE_BASELINE`，csv_count 59；`MACHINE_QA_AND_TABLE_IDENTITY.json` 的 `files_sha256` 与其逐项相同。
  只读验收器 `scripts/paper_rebuild/v3r_delivery_verify.py:62-75` 按同一清单核验（65 项、59 CSV）。
- 4d932c9（FC-01）提交只改 `FC01_UNIFIED_FAILURE.md`，没有新的表哈希清单。

比对范围：`$V3/07_AGGREGATE/` 与 `$V3/07C_FAILURE_FAMILY_CONFIG/` 下全部文件（58 个 CSV），另加清单同样覆盖的
`07D_CLASSIFICATION_PROVENANCE/`（1 个 CSV）。磁盘上三目录共 65 个文件，与清单 65 项一一对应。

| 比对 | 时间（UTC） | 结果 |
| --- | --- | --- |
| 第一次（导入事故之前） | 2026-09-23T12:26:10Z | 65/65 一致；不一致 0；未登记 0；登记但缺失 0 |
| 第二次（导入事故之后、两份产出写完之后） | 2026-09-23T13:31:58Z – 2026-09-23T13:31:59Z | 65/65 一致（其中 CSV 59）；不一致 0；未登记 0；登记但缺失 0；BASELINE.json 与 MACHINE_QA 回执哈希仍与仓库登记值相同，二者 files_sha256 逐项相同 |

逐文件清单（第二次比对时的当前值；"登记"列为 BASELINE.json 中的值是否相同）：

| # | 文件（相对 `$V3`） | 字节 | 当前 sha256 | 与 BASELINE.json 登记 |
| ---: | --- | ---: | --- | --- |
| 1 | `07C_FAILURE_FAMILY_CONFIG/CORE_541_V21_COMPARISON_V2.csv` | 2868853 | `ed49b04064b40ab531cae56fb339a35926b30fe864b12e0045c92402a07a0cd5` | 一致 |
| 2 | `07C_FAILURE_FAMILY_CONFIG/CORE_541_V21_COMPARISON_V3.csv` | 2880848 | `e0bcac20f368c49e2be9cf96656a6710d34e5b39850380d8421da95099ce764d` | 一致 |
| 3 | `07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv` | 53015 | `d374c4370952dc54c328bf868548848059d398801851e021fb664b349773cb50` | 一致 |
| 4 | `07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V2.csv` | 321944 | `8ca53668a12a0a0db3d9765277fcbbeb6be91184addf97b784f02c6ccf42c76f` | 一致 |
| 5 | `07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv` | 323074 | `44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1` | 一致 |
| 6 | `07C_FAILURE_FAMILY_CONFIG/MANIFEST.json` | 1921 | `a2b83104c14b497eda6af3ef93bf092606bc12e95b4bb0803136f16621fc63c6` | 一致 |
| 7 | `07C_FAILURE_FAMILY_CONFIG/MANUSCRIPT_FULL_ABLATION_AND_FAILURES.md` | 2507 | `d37f091e6ef6d39792af47528237ebd70477192d83b9da453b8e86c10cfd46f6` | 一致 |
| 8 | `07C_FAILURE_FAMILY_CONFIG/SUBSET61_V21_COMPARISON_V2.csv` | 325018 | `6bfb6c0fb0b3b62c77e8a694cbaac4b81a503685dc93b55a9cb7fed120ffdadb` | 一致 |
| 9 | `07C_FAILURE_FAMILY_CONFIG/SUBSET61_V21_COMPARISON_V3.csv` | 326418 | `732583a54c07300f7d1774d950721854072e07b8614b1991e6880d9963e5040a` | 一致 |
| 10 | `07D_CLASSIFICATION_PROVENANCE/F01_IDENTICAL_NAV_CLASSIFICATION.csv` | 6625 | `c309991a31a07afbcdd54a2934f06513e9d557b2de42384bededd66d2219026c` | 一致 |
| 11 | `07D_CLASSIFICATION_PROVENANCE/MANIFEST.json` | 1116 | `000a6797920e9b7e1faec876a1badeba24242d9a762bf5e13baa08d5bf38e7ff` | 一致 |
| 12 | `07_AGGREGATE/ABLATION_TABLE_V2.csv` | 11812 | `d2ec61913fa3953b2cea189cc553eed8479d3bd8464502b6bae843392800b1d0` | 一致 |
| 13 | `07_AGGREGATE/ABLATION_TABLE_V3.csv` | 11877 | `8c5fed7e2ef022e94e19b095e2e3b7b68dae94a3676e16afc5b6e0cb4bb30a75` | 一致 |
| 14 | `07_AGGREGATE/ADDENDUM_FAMILY_SUMMARY_V2.csv` | 20879 | `e46266ecd093a4a4effb128935c60829246567f76306f5c19857ad51a7d697dc` | 一致 |
| 15 | `07_AGGREGATE/ADDENDUM_FAMILY_SUMMARY_V3.csv` | 20876 | `0b0c1306cf063e3943d21be6169d3795d73ff87952cf199c3333b22426f5752f` | 一致 |
| 16 | `07_AGGREGATE/ADDENDUM_SUMMARY_V2.csv` | 10259 | `d8e78de4ad19a929e27e29eceb46cea741a4a177b164e68b85aada384ddda70e` | 一致 |
| 17 | `07_AGGREGATE/ADDENDUM_SUMMARY_V3.csv` | 10280 | `ab88f5703eb0d9441915984e69ab7fa45fb587a1592dcf00ff54c3d65efdf890` | 一致 |
| 18 | `07_AGGREGATE/ADDENDUM_TABLE_V2.csv` | 4913748 | `13c3a9c790ecab766694d7fca79eaef08f41b9a00c066c376ccb881d12dcb86a` | 一致 |
| 19 | `07_AGGREGATE/ADDENDUM_TABLE_V3.csv` | 4924232 | `82aaef841c4e62d13ce4c4a2625b063ec3ac02ffc379db835cf1452486c978bb` | 一致 |
| 20 | `07_AGGREGATE/ADDENDUM_V21_COMPARISON_V2.csv` | 236842 | `599ba72d06bd8684e62d1f7e471d93896ce9dc62b49cfa9e6168e43deeaa72b5` | 一致 |
| 21 | `07_AGGREGATE/ADDENDUM_V21_COMPARISON_V3.csv` | 237022 | `2882956ac280bb4f7df06326e2dd0e6d856e048dbae1272c11f9e820080a7c3d` | 一致 |
| 22 | `07_AGGREGATE/AGGREGATE_MANIFEST.json` | 4070741 | `11b6779460ef4ade860b034cba88abe5f89fa6bb7eb125ee4b7d7bccb9f0464a` | 一致 |
| 23 | `07_AGGREGATE/BY2O_SEGMENT_TABLE.csv` | 67539 | `13a2c4e8de7638fa8672bb49d6556f531061a3924fe7dbf6911adfcf53779876` | 一致 |
| 24 | `07_AGGREGATE/CORE_541_DISTRIBUTION_V2.csv` | 3217786 | `ec76e858f0535792fc1e449208db5b7121b66490ec203c54ea79942fb0709009` | 一致 |
| 25 | `07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv` | 3223434 | `301cec24cb454781138aa39dd3b86a4b37b7855773e6d28e891b7231047d4c39` | 一致 |
| 26 | `07_AGGREGATE/CORE_541_FAMILY_SUMMARY_V2.csv` | 105360 | `05de983ccc2fb13d67dbcbbc28dd121040fd98cfd8e6f44d0300299c018452c3` | 一致 |
| 27 | `07_AGGREGATE/CORE_541_FAMILY_SUMMARY_V3.csv` | 105743 | `1f630c70679896c82855769b7580dc2921e9b5cc78add46b3be41f37bd17429d` | 一致 |
| 28 | `07_AGGREGATE/CORE_541_SUMMARY_V2.csv` | 11841 | `bea055fce46c0869f883cf28667b5ab9a6e23c55c1383e74e0939064091b1fc4` | 一致 |
| 29 | `07_AGGREGATE/CORE_541_SUMMARY_V3.csv` | 11863 | `1e0181936e4cf40de57bd1e6f0724acdf1644bb7616aaff0121bbd8a54febd35` | 一致 |
| 30 | `07_AGGREGATE/CORE_541_TABLE_V2.csv` | 57283589 | `fd3fd890b9b9239d83885b8d01378ab7bb5f79842d94e61f69acde5f1fa0ca81` | 一致 |
| 31 | `07_AGGREGATE/CORE_541_TABLE_V3.csv` | 57448961 | `dbe3c6cd3de0f04acdb555dcaedfd3fc913d30fefd94ae3bed2dc85acf6fb50d` | 一致 |
| 32 | `07_AGGREGATE/CORE_541_TYPE_SUMMARY_V2.csv` | 629592 | `b0ef6a21ceddfeaa4c90e9d4fad42f2bd86bc03db832a86f0fdb8f60b8fd8fde` | 一致 |
| 33 | `07_AGGREGATE/CORE_541_TYPE_SUMMARY_V3.csv` | 632820 | `dda9093a2258a4c41cc26a932fe526a9168a57933fe569e81dc8922eaf0d6266` | 一致 |
| 34 | `07_AGGREGATE/CORE_541_V21_COMPARISON_V2.csv` | 2863543 | `98d338d8c192864cc4905993f0c60787f44219087a8b3ef247b3e6537c74b25a` | 一致 |
| 35 | `07_AGGREGATE/CORE_541_V21_COMPARISON_V3.csv` | 2875538 | `51b90d5834fe1347aea5467fb7253812a44708287d5871823d71efa0953e2b5c` | 一致 |
| 36 | `07_AGGREGATE/ERROR_SERIES_INDEX.csv` | 735589 | `affc8caae6231dec61d8c10e76624b4aaf8ec4e9791b17f47bf3691032a89142` | 一致 |
| 37 | `07_AGGREGATE/FAILURE_COMPARISON.csv` | 9453 | `4d5a19abbc40228a3c98f8dfb7f32ce616f3af5cbd6ac65fec8eea66460b536f` | 一致 |
| 38 | `07_AGGREGATE/HORIZONTAL_REPLACEMENT_AUDIT.csv` | 5901 | `9b20741c137d42e98617808478a264634a849ef64fe7349094b8833ab57e00c9` | 一致 |
| 39 | `07_AGGREGATE/MAIN_TABLE_V2.csv` | 52185 | `965b558280119a5e256872f488794f2d1bdb731326d891bc56c475e9a2e9bd3e` | 一致 |
| 40 | `07_AGGREGATE/MAIN_TABLE_V3.csv` | 51910 | `cd734338cf89518679d78179f410a79ecad3060535d3b80e43a62545cee9b21c` | 一致 |
| 41 | `07_AGGREGATE/MANUSCRIPT_REPLACEMENT_TEXT.md` | 2917 | `47cacf1bea39848e01732ec87823729c4a73cf0d143d8783b4f203119eafef5b` | 一致 |
| 42 | `07_AGGREGATE/PAIRWISE_CASE_LEVEL_V2.csv` | 3017912 | `68a29577b441583519a3cd630dcade0c40fb67f58065cd23238feb9889ac1324` | 一致 |
| 43 | `07_AGGREGATE/PAIRWISE_CASE_LEVEL_V3.csv` | 3030539 | `9131dc0f3905f5339cc105919354349031a78657a02ddfb63fe4c193861abcff` | 一致 |
| 44 | `07_AGGREGATE/PAIRWISE_SUMMARY_V2.csv` | 255910 | `3b681c1f34fd813841bce4ac42465cd1c753d73da967e66761f57bbfc0c7a70d` | 一致 |
| 45 | `07_AGGREGATE/PAIRWISE_SUMMARY_V3.csv` | 256292 | `0587815641ff0b9fe94506e51f47672ad6a94cbc0411e2d9dc852c233f86b89a` | 一致 |
| 46 | `07_AGGREGATE/REPORT_SOURCE_INDEX.json` | 4185 | `43dbdade50172e191b394dfc5b64815ddc0c6c5b7f73cbda41762d32acbc4704` | 一致 |
| 47 | `07_AGGREGATE/SEQUENCE_FAMILY_SUMMARY_V2.csv` | 22165 | `f8d0bd8b04a1a0f69abe38bd74ecbcd86379804ce1d24f02a454a276ab1cf096` | 一致 |
| 48 | `07_AGGREGATE/SEQUENCE_FAMILY_SUMMARY_V3.csv` | 22291 | `065356028ce32c5a6bba73adc7b1b913f6b16566c73adaf305fee5cca0362288` | 一致 |
| 49 | `07_AGGREGATE/SEQUENCE_SUMMARY_V2.csv` | 10284 | `b14ae9b08df15434bbeb8dccb71ea4f11e9fe35e53f3b0ea49c960e8a0bf6841` | 一致 |
| 50 | `07_AGGREGATE/SEQUENCE_SUMMARY_V3.csv` | 10355 | `9d33e393c69e25490f761b5c5e2510f289f9989c3e2cc2010547176105fab2ee` | 一致 |
| 51 | `07_AGGREGATE/SEQUENCE_TABLE_V2.csv` | 321944 | `8ca53668a12a0a0db3d9765277fcbbeb6be91184addf97b784f02c6ccf42c76f` | 一致 |
| 52 | `07_AGGREGATE/SEQUENCE_TABLE_V3.csv` | 323074 | `44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1` | 一致 |
| 53 | `07_AGGREGATE/SEQUENCE_V21_COMPARISON_V2.csv` | 16780 | `1048772e2ca1f75d029dedb6ff210c2b3e34387962eb49dcba10cfed4aeefa30` | 一致 |
| 54 | `07_AGGREGATE/SEQUENCE_V21_COMPARISON_V3.csv` | 16928 | `57778389cd9d107c77c1fbcd5438eaa378c98bef6f364cd97daf735dfb42db40` | 一致 |
| 55 | `07_AGGREGATE/SUBSET61_SUMMARY_V2.csv` | 11505 | `be54762dacc8ff345eff43d140d84b18b63683b62d28cafce545b0f91a00fb24` | 一致 |
| 56 | `07_AGGREGATE/SUBSET61_SUMMARY_V3.csv` | 11536 | `8c4f55d32ebe2f9c124db70fef3eccfffd5467251f6adfa5809480b0798f20e6` | 一致 |
| 57 | `07_AGGREGATE/SUBSET61_TABLE_V2.csv` | 6452406 | `391737b611ad79d8c0fe1e6cb5f412dbe8ada9be84b8df6d3e18bb15c241ab06` | 一致 |
| 58 | `07_AGGREGATE/SUBSET61_TABLE_V3.csv` | 6471105 | `f88d4a82e81fc881cba46db9ab1b511164dbcc2508842259a54a37947c4d0519` | 一致 |
| 59 | `07_AGGREGATE/SUBSET61_V21_COMPARISON_V2.csv` | 324688 | `b87087c543a42260353d517284c6a680b47ab910ca4f8bf4ef2111042d0f018c` | 一致 |
| 60 | `07_AGGREGATE/SUBSET61_V21_COMPARISON_V3.csv` | 326088 | `f4a05c889f374b37d9452c37531b6e93351d6e9d30f1f71ebe70348ffaccf2b9` | 一致 |
| 61 | `07_AGGREGATE/T5BCR_REFERENCE_SUBSET61_TAIL_SUMMARY.csv` | 3648 | `a4aa65e0552ec4480e92da344ef5bdf410c01232204aa452738eb4149d02d35e` | 一致 |
| 62 | `07_AGGREGATE/T5BCR_REFERENCE_SUBSET61_V2.csv` | 3174581 | `bf8c68c1f3b25c957d1d8c378817cd36073185f7c09e33fe6bc2e69ae5050d54` | 一致 |
| 63 | `07_AGGREGATE/T5BCR_REFERENCE_SUBSET61_V3.csv` | 3185332 | `92f0d5c874591ff48c978436e7a4a5fd1f3c21a53670ae5a0592cd4d25cf9ef5` | 一致 |
| 64 | `07_AGGREGATE/T5BCR_REFERENCE_THREE_SEQUENCES_V2.csv` | 22879 | `9c59de133c20918f7412f1540168f11c569f2c52e49bd9e00a4eb5eb7c394282` | 一致 |
| 65 | `07_AGGREGATE/T5BCR_REFERENCE_THREE_SEQUENCES_V3.csv` | 23060 | `eedb79e24acdc9da064118e84be0960d1c755daf83d9e9acb0e16f34bf5f677e` | 一致 |

### 1.3 冻结二进制与冻结评估器（抄自 v3 封存记录）

| 角色 | 路径 | 完整 sha256 | 记录出处 | 本次字节复核 |
| --- | --- | --- | --- | --- |
| 冻结二进制 | `<CODE_ROOT>/build/p13_v21_cpp/legsa_v23_port_core_demo`（`$W/build/p13_v21_cpp/legsa_v23_port_core_demo`，759,456 B） | `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c` | `configs/paper_rebuild/v3/PROTOCOL_V3_CONTRACT.yaml:21-23`；`docs/paper_rebuild/v3/V3_01_PREREQUISITES.json:42-45, 201-206`；`docs/paper_rebuild/v3/PROTOCOL_V3_PREREG.md:14-15` | 一致（只计算哈希，未执行） |
| 冻结评估器 | `<CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py`（18,195 B） | `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da` | `PROTOCOL_V3_CONTRACT.yaml:24-26`；`V3_01_PREREQUISITES.json:48-51, 209-214`；`PROTOCOL_V3_PREREG.md:16-17` | 一致（该文件是源码，按规则可读；只计算哈希，未执行、未导入） |

## 2. 五类归属一览表

归类规则：按信息结构。载波/基线航向求解归 dual_antenna_ambiguity_heading；腿式本体感知估计归 legged_state_estimation；CLEAN4 登记为 Layer B solution-level LC（含 LC02 槽位全部候选）与双位置接收机 IEKF 归 loosely_coupled_gnss_ins；更新只用单接收机位置的变体与单天线 InEKF 设计归 single_antenna_gnss_ins。LC02_GINAV 只用单接收机 SPP，按记录归 LC，若按天线数划分可改入 single_antenna_gnss_ins；EXT06 若视腿里程计为主可改入 legged_state_estimation（均在 §3 各行注明）。完整性复核子代理未发现 23 行之外的新外部方法 id，只补充了变体、别名与血缘（已并入相应行）。

| 类别 | 方法（CSV 行） | 行数 | 该类是否有可运行实现 |
| --- | --- | ---: | --- |
| dual_antenna_ambiguity_heading（双天线模糊度/基线航向） | EXT01、EXT02、EXT03、EXT04、RTKLIB_UNMODIFIED_MOVING_BASE、D01_DIRECT_GEOMETRIC_BASELINE | 6 | 有：EXT01–EXT04 为已跟踪 Python 实现（BY2 硬编码，入口 help_ok），RTKLIB 动基线为外部二进制诊断；D01_DIRECT_GEOMETRIC_BASELINE 代码不在仓库（HORIZONTAL18_V2 诊断流） |
| legged_state_estimation（四足状态估计） | Hartley | 1 | 有：Hartley（C++ hartley_h5_runner + Python 包装，入口 help_ok；二进制未运行） |
| loosely_coupled_gnss_ins（松耦合 GNSS/INS） | LC01、LC01-S、EXT05B、LC01-M、LC01-S-M、LC01-2D、LC02_GINAV、LC02_YIN2023_RAEKF、LC02_CHANG2021_FSTCKF、LC02A_JIANG2021_ADAPTIVE_FADING_CKF、LC02B_TAGHIZADEH2023_AHINF_CKF、EXT06_HAO2018_TWO_ANTENNA_LC_EKF | 12 | 有：LC01、LC01-S（Python，入口 help_ok；H-EXT 路径受合约门控）；LC02_GINAV 需 Windows MATLAB（不在 WSL PATH）。无实现：EXT05B（附录方程不一致，人工豁免）；LC02_YIN2023_RAEKF（NO_GO，未授权实现）；LC02_CHANG2021_FSTCKF（NO_GO，无实现目录）；LC02A_JIANG2021、LC02B_TAGHIZADEH2023（NO_GO，全文未得、未生成代码）；EXT06_HAO2018（已废弃）；LC01-M/LC01-S-M/LC01-2D（H-EXT-04 执行取消，库 NOT_AUTHORIZED_FOR_EXECUTION） |
| single_antenna_gnss_ins（单天线 GNSS/INS） | EXT05C、EXT05C-S、D02_SINGLE_RECEIVER_IEKF、EXT06 | 4 | 有：EXT05C、EXT05C-S（Python，入口 help_ok；初始化用双天线基线，非纯单天线）。无实现：EXT06（Luo，pending）；D02_SINGLE_RECEIVER_IEKF 代码不在仓库（HORIZONTAL18_V2 诊断流） |
| other（其他） | — | 0 | 该类无实现：CLEAN4 与 H-EXT 记录中没有归入 other 的外部方法（遗留 DA 目录项、u-blox 接收机相对解代理、HORIZONTAL18_V2 内部方法与 Go2 板载估计器均不计为外部方法或已按信息结构归类，见 §3.24） |
| 合计 | | 23 | |

runnable_check 统计（按 CSV 行，一行可含多种检查）：含 help_ok 的行 13；含 import_ok 的行 10；含 static_only 的行 19，其中只有 static_only 的行 10。help_ok/import_ok 只表示入口检查跑完，不表示方法可用或可复现。

## 3. 方法逐条

字段与 `HX_INVENTORY.csv` 一一对应（CSV 列名：method_id, category, reference, code_path, entry_command, runnable_check, param_source, inputs, output_type, by2_c00_existing_result, unavailable_reason_verbatim, by2h_by2o_existing, proposed_metric, evaluator_subprocess, notes）。

### 3.1 EXT01

| 字段 | 内容 |
| --- | --- |
| category | dual_antenna_ambiguity_heading |
| reference | P. J. G. Teunissen (2006) 'The LAMBDA method for the GNSS compass', Artificial Satellites 41(3):89-103; P. J. G. Teunissen (2010) 'Integer least-squares theory for the GNSS compass', Journal of Geodesy 84:433-447; P. J. G. Teunissen, G. Giorgi, P. J. Buist (2011) 'Testing of a new single-frequency GNSS carrier phase attitude determination method', GPS Solutions 15:15-28（configs/paper_rebuild/horizontal_literature/EXTERNAL_METHOD_CONTRACTS_V1.yaml:32-58） |
| code_path | src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py；shared_raw_backend.py；phase1r_runner.py；phase1_runner.py；scripts/paper_rebuild/run_horizontal_literature_phase1r.py；合约 configs/paper_rebuild/horizontal_literature/PHASE1R_VALIDATION_CONTRACT_V2.yaml；外部 $EXTERNAL/RTKLIB（2.4.3_b34 @180043ee，convbin）与 $EXTERNAL/rtklib_bridge/lib/liblegsa_rtklib_bridge.so、librtklib_legsa.so |
| entry_command | python3 scripts/paper_rebuild/run_horizontal_literature_phase1r.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --method-id EXT01_CLAMBDA --case-id C00_VALIDATED --trace-mode post-native-descriptive --workers 16（$CLEAN4/11_REPORT/PHASE1R_R2_EXT01_C00_VALIDITY_REPORT.md:59-64） |
| runnable_check | help_ok（scripts/paper_rebuild/run_horizontal_literature_phase1r.py --help）；import_ok（horizontal_literature.ext01_clambda）；static_only（RTKLIB/bridge 外部二进制）。仅表示入口检查跑完，不表示方法可用或可复现：HEAD 的 shared_raw_backend.py 与 R2 记录不同（d72548fb… 对 1abcb79d…），磁盘上 liblegsa_rtklib_bridge.so 现为 6df66600…（R2 记录 6cc83e59…，现为 EXT03/EXT04 构建） |
| param_source | EXTERNAL_METHOD_CONTRACTS_V1.yaml:9 基线 0.350 m、:73-84 随机模型下限（伪距 0.50 m、载波 0.004 周、多普勒 0.02 Hz）；PHASE1R_VALIDATION_CONTRACT_V2.yaml:35、:64-66 σ 公式、:74 lambda_seed_count 8、:77 node_budget 1000000、:80-81 无模糊度接受检验（ratio_threshold null）；只有 0.350 m 为物理/文献模型值 |
| inputs | 两台接收机 UBX RXM-RAWX GPS L1 C/A 伪距+载波（gnss1-raw.csv/gnss2-raw.csv），SFRBX→convbin→RTKLIB 广播星历，接收机位置由原始码 SPP；不用 status 流、IMU、腿、接触、单天线位置解；航向来自自身载波双差定长 GNSS2-GNSS1 基线（body yaw = 基线航向 + 90°） |
| output_type | heading_only |
| by2_c00_existing_result | CLEAN4 PHASE1R R2（$CLEAN4/02_EXT01_CLAMBDA/C00_VALIDATED_R2；$CLEAN4/11_REPORT/PHASE1R_R2_STATUS.json:292-301）：配对历元 1509，返回整数解 1077，无效 432，integer_solution_availability 0.7137176938369781，无模糊度接受检验；native_freeze_sha256 6da2b5a05b9f784d35e288b64398182e77c235605d9aa90375bac9b166106493；终态 UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION。原生后诊断【评估器与评估点均与 v3 不同：phase1r_runner.py:1577-1649 自带航向比较器，非冻结评估器，无 66-340 s 窗】：对 HPPOSECEF 基线代理 yaw RMSE 120.73505854071854 deg；对参考 yaw RMSE 120.5700062447263 deg（1077 历元）。v3 MAIN_TABLE_V3.csv:20 未评估（evaluation_status UNAVAILABLE，evaluator_contract_v3 仅为标签，hext/aggregate.py:364-377 生成） |
| unavailable_reason_verbatim | MAIN_TABLE_V3.csv:20 failure_classification "UNAVAILABLE_NO_IMU_POINT_NAV"；notes {"availability": "UNAVAILABLE_NO_IMU_POINT_NAV", "frozen_failure": "", "original_evaluation_status": "UNAVAILABLE", "scope": "BY2_FROZEN_REGISTRY_REASON; NO_NEW_H_OR_O_EXECUTION", "source_line": 8, "source_table": "<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/HORIZONTAL_TABLE_V3.csv", "source_table_sha256": "d91f53aaf855efc8c533a6f15a9c6c933e87bafb2bcc9bd169ba862163c82c01"}；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION/FINAL_METHOD_REGISTRY.csv:2 "UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION"；AGENTS.md:954-957 "1077 / 1509 globally certified integer solutions; no ambiguity acceptance test; do not call them successful or correct fixes; unresolved fractional-DD phase-bias applicability boundary." |
| by2h_by2o_existing | 未运行。MAIN_TABLE_V3.csv:27（BY2H）、:34（BY2O）为 NOT_EXECUTED/UNAVAILABLE，scope "BY2_FROZEN_REGISTRY_REASON; NO_NEW_H_OR_O_EXECUTION"；代码 BY2 硬编码（phase1r_runner.py:85 EXPECTED_PAIR_COUNT = 1509） |
| proposed_metric | heading_only：固定率/可用率 = 有效航向历元 / 评估窗内 GNSS 历元；有效历元航向 RMSE（wrap-safe，参考 yaw = wrap360(90 - interp(unwrap(yaw_ENU)))，要求前后括住、不外推）；保持上一有效值的全窗航向 RMSE（首个有效值之前的历元单独计数为无航向历元，不记零）；最大绝对误差（有效序列与保持序列各报一次）。评估点不适用（无位置/IMU 点输出）是换指标的理由，不是没有结果 |
| evaluator_subprocess | NEW：航向评估子进程——strace 下只打开 trace 1 次并核哈希（经 evaluator_capture 钩子或调用冻结评估器的 load_trace）、支持各序列 base_time 与窗、与冻结评估器相同的 yaw 语义、以方法原生历元表构造 GNSS 历元分母、实现保持上一有效值；统计复用 horizontal_literature/phase2_runner.py _wrapsafe_error_metrics（:1491 起）/ _continuity_metrics（:1461 起）/ _circular_statistics_deg（:1442 起），审计模式复用 hext/external_evaluation._evaluate_process（:129-205）；H-EXT-04 库 hext/heading_provider.py 的 baseline_heading / angular_difference_statistics / extract_epoch_set 可作参考，但标记 NOT_AUTHORIZED_FOR_EXECUTION，登记授权前不得使用。phase2_runner 现有实现在父进程读 trace（:3507）且 BY2 硬编码（:3541-3542），不能直接作为进程复用 |
| notes | 早期尝试：PHASE1（$CLEAN4/02_EXT01_CLAMBDA/C00，994/515，已被取代，AGENTS.md:956 禁止称为 fix）、PHASE1R R1（C00_VALIDATED，BLOCKED_PHASE1R_SEARCH_OBJECTIVE_CROSSCHECK_FAILED）；0.350 m 硬约束不是精度证据（AGENTS.md:977）；遗留目录 DA01_TEUNISSEN_CLAMBDA_COMPASS 不属 CLEAN4 |

### 3.2 EXT02

| 字段 | 内容 |
| --- | --- |
| category | dual_antenna_ambiguity_heading |
| reference | Xing Liu, Tarig Ballal, Hui Chen, Tareq Y. Al-Naffouri (2022) 'Constrained Wrapped Least Squares: A Tool for High-Accuracy GNSS Attitude Determination', IEEE TIM 71, 8005315, doi 10.1109/TIM.2022.3193412（configs/paper_rebuild/horizontal_literature/PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:9-20） |
| code_path | horizontal_literature/ext02_cwls.py；phase2_runner.py；shared_raw_backend.py；scripts/paper_rebuild/run_horizontal_literature_phase2.py；合约 PHASE2_EXT02_CWLS_CONTRACT_V1.yaml；外部 rtklib_bridge .so、convbin |
| entry_command | python3 scripts/paper_rebuild/run_horizontal_literature_phase2.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --method-id EXT02_CWLS --case-id C00 --trace-mode disabled --workers 16；原生后：同脚本加 --mode post-native-diagnostics --post-recovery-id PROXY_TIME_ASSOCIATION_R1（$CLEAN4/11_REPORT/PHASE2_EXT02_C00_REPORT_PROXY_TIME_ASSOCIATION_R1.md:1300-1301） |
| runnable_check | help_ok（run_horizontal_literature_phase2.py）；import_ok（horizontal_literature.ext02_cwls）；static_only（外部 bridge/convbin）。仅表示入口检查跑完，不表示方法可用或可复现：HEAD 的 phase2_runner.py、运行脚本、合约、shared_raw_backend.py 与原生记录不同，bridge .so 已变 |
| param_source | PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:48 K_policy ALL_UNIQUE_CANDIDATES、:50 delta_Delta 0.05（论文值）、:53 基线 0.350、:55-56 细化容差 1.0e-10 / 20 次、:87 高度角 10.0、:124-128 σ（码 max(0.50, 0.01*2^prStdev)、载波 max(0.004, 0.004*cpStdev)）；ext02_cwls.py:44-46 |
| inputs | 两台接收机 RAWX GPS L1 C/A，精确配对 1509；接收机位置原始码 SPP；status 基线、HPPOSECEF、RTKLIB 位置均不作解算输入；无 IMU、腿、接触、单天线位置；航向来自自身 C-WLS 基线方向（body yaw = heading + 90°） |
| output_type | heading_only |
| by2_c00_existing_result | CLEAN4（$CLEAN4/03_EXT02_CWLS/C00）：配对 1509，accepted wrapped 1057（0.7004638833664678），失败 452，模糊度正确性未知；native_freeze_sha256 c1d8260df693ed213c004ae90f3446e546e88f599b662ec40879711b8b3f060d。原生后【评估器与评估点均与 v3 不同：phase2_runner.py:3542-3559 自带比较器，在父进程读 trace】：对 HPPOSECEF 代理 RMSE 120.98227411490542 deg（1057）；对参考 yaw（66-340 s）匹配 964、valid_coverage 0.7036496350364964（分母 1370）、RMSE 120.52876042302128 deg；终态 PASS_PHASE2_EXT02_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT。v3 MAIN_TABLE_V3.csv:21 未评估 |
| unavailable_reason_verbatim | MAIN_TABLE_V3.csv:21 "UNAVAILABLE_NO_IMU_POINT_NAV"（notes 同 EXT01，source_line 9）；FINAL_METHOD_REGISTRY.csv:3 "452 invalid; […] heading accuracy poor; not full-attitude/full-NAV comparator"（原文此处一词按本文用词规则以 […] 代替）；AGENTS.md:959-962 "1057 / 1509 accepted wrapped solutions; ambiguity correctness unknown; poor physical heading applicability on BY2." |
| by2h_by2o_existing | 未运行（MAIN_TABLE_V3.csv:28、:35 NOT_EXECUTED；phase2_runner.py:82 EXPECTED_PAIR_COUNT = 1509） |
| proposed_metric | heading_only：固定率/可用率 = 有效航向历元 / 评估窗内 GNSS 历元；有效历元航向 RMSE（wrap-safe，参考 yaw = wrap360(90 - interp(unwrap(yaw_ENU)))，要求前后括住、不外推）；保持上一有效值的全窗航向 RMSE（首个有效值之前的历元单独计数为无航向历元，不记零）；最大绝对误差（有效序列与保持序列各报一次）。评估点不适用（无位置/IMU 点输出）是换指标的理由，不是没有结果 |
| evaluator_subprocess | NEW：航向评估子进程——strace 下只打开 trace 1 次并核哈希（经 evaluator_capture 钩子或调用冻结评估器的 load_trace）、支持各序列 base_time 与窗、与冻结评估器相同的 yaw 语义、以方法原生历元表构造 GNSS 历元分母、实现保持上一有效值；统计复用 horizontal_literature/phase2_runner.py _wrapsafe_error_metrics（:1491 起）/ _continuity_metrics（:1461 起）/ _circular_statistics_deg（:1442 起），审计模式复用 hext/external_evaluation._evaluate_process（:129-205）；H-EXT-04 库 hext/heading_provider.py 的 baseline_heading / angular_difference_statistics / extract_epoch_set 可作参考，但标记 NOT_AUTHORIZED_FOR_EXECUTION，登记授权前不得使用。phase2_runner 现有实现在父进程读 trace（:3507）且 BY2 硬编码（:3541-3542），不能直接作为进程复用 |
| notes | 代理关联为 UNIQUE_NEAREST_COMMON_EPOCH（PHASE2 合约 :259-267），实测 1509/1509 均 +2 ms；accepted wrapped solution 不等于模糊度正确（RAW_METHOD_APPLICABILITY_BOUNDARY.md:7） |

### 3.3 EXT03

| 字段 | 内容 |
| --- | --- |
| category | dual_antenna_ambiguity_heading |
| reference | Hongli Yang, Yuanming Shu, Rongxin Fang, Lulu Qiao, Dong Ding, Guangxue Li (2024) 'GPS/BDS Dual-Antenna Attitude Determination With Baseline-Length Constrained Ambiguity Resolution: Method and Performance Evaluation', IEEE TIM 73, 1003414, doi 10.1109/TIM.2024.3374423（configs/paper_rebuild/horizontal_literature/PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml:10-27） |
| code_path | horizontal_literature/ext03_yang2024.py；phase3_runner.py；phase3_signal_inventory.py；phase2_runner.py；ext01_clambda.py；shared_raw_backend.py；scripts/paper_rebuild/run_horizontal_literature_phase3.py；外部 librtklib_legsa.so（MLAMBDA）、liblegsa_rtklib_bridge.so（pntpos）、EXT03_PNTPOS_BRIDGE.patch（PHASE3 合约 :259-262） |
| entry_command | python3 scripts/paper_rebuild/run_horizontal_literature_phase3.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --method-id EXT03_YANG2024 --case-id C00 --trace-mode disabled --workers 16（$CLEAN4/11_REPORT/PHASE3_EXT03_C00_REPORT.md:200-209）；恢复：加 --mode post-native-diagnostics --post-recovery-id RTKLIB_TIME_ASSOCIATION_R1（:215-222） |
| runnable_check | help_ok（run_horizontal_literature_phase3.py）；import_ok（horizontal_literature.ext03_yang2024）；static_only（外部 MLAMBDA/pntpos 库）。仅表示入口检查跑完，不表示方法可用或可复现：HEAD 的 phase3_runner.py 与原生记录不同（记录为仅报告层改动，原生 runner 重建于 11_REPORT/PHASE3_EXT03_C00_NATIVE_SOURCE_PROVENANCE_R2） |
| param_source | PHASE3 合约 :40 基线 0.350、:44 ratio_threshold 3.0（论文披露）、:46-47 初始基线协方差 900.0 m² 与初始模糊度协方差 900.0 cycle²（论文披露）、:48 primary_baseline_sigma_m 0.010（声明的工程值）、:49 敏感性 [0.001, 0.005, 0.010, 0.020, 0.050]、:115-116 高度角 15.0（RTKLIB 默认）、:161-178 论文未给的量测/过程噪声取固定 RTKLIB 默认；ext03_yang2024.py:34-37、:55-61 |
| inputs | 两台接收机 GPS L1/L2 + BDS B1/B2 RAWX，5 Hz 精确配对 1509；RTKLIB pntpos 原始码 SPP 初始化；无 IMU、腿、接触、status 基线、HPPOSECEF；航向来自自身 DD-KF 基线状态（body yaw = 基线航向 + 90°） |
| output_type | heading_only |
| by2_c00_existing_result | 主模式 GPS_BDS_DUAL_FREQUENCY/CONSTRAINED/σ=0.01（$CLEAN4/11_REPORT/PHASE3_STATUS.json:66-78）：有效 609，论文 ratio-fixed 105（0.06958250497017893），无效 900，101/105 ratio-fixed 与代理不一致；【评估器与评估点均与 v3 不同：phase3/phase2 自带比较器】对参考全有效 RMSE 84.34382296702495 deg（覆盖 0.3948905109489051），ratio-fixed RMSE 40.63084624232342 deg；十个模式共 15090 行（7122 有效）；native_freeze_sha256 e172100ad64a2c20ee6772f9b7cb1e212cfb940fde8c3ac94c970b101671b3f0；终态 PASS_PHASE3_EXT03_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT。v3 MAIN_TABLE_V3.csv:22 未评估 |
| unavailable_reason_verbatim | MAIN_TABLE_V3.csv:22 "UNAVAILABLE_NO_IMU_POINT_NAV"（notes 同 EXT01，source_line 10）；FINAL_METHOD_REGISTRY.csv:4 "101/105 ratio-fixed proxy-inconsistent; not a formal solution comparator"；AGENTS.md:964-968 "609 / 1509 valid; 105 paper-ratio-fixed; 900 invalid; 101 / 105 ratio-fixed rows are proxy-inconsistent." |
| by2h_by2o_existing | 未运行（MAIN_TABLE_V3.csv:29、:36；phase3_runner.py:80 EXPECTED_PAIR_COUNT = 1509） |
| proposed_metric | heading_only：固定率/可用率 = 有效航向历元 / 评估窗内 GNSS 历元；有效历元航向 RMSE（wrap-safe，参考 yaw = wrap360(90 - interp(unwrap(yaw_ENU)))，要求前后括住、不外推）；保持上一有效值的全窗航向 RMSE（首个有效值之前的历元单独计数为无航向历元，不记零）；最大绝对误差（有效序列与保持序列各报一次）。评估点不适用（无位置/IMU 点输出）是换指标的理由，不是没有结果 |
| evaluator_subprocess | NEW：航向评估子进程——strace 下只打开 trace 1 次并核哈希（经 evaluator_capture 钩子或调用冻结评估器的 load_trace）、支持各序列 base_time 与窗、与冻结评估器相同的 yaw 语义、以方法原生历元表构造 GNSS 历元分母、实现保持上一有效值；统计复用 horizontal_literature/phase2_runner.py _wrapsafe_error_metrics（:1491 起）/ _continuity_metrics（:1461 起）/ _circular_statistics_deg（:1442 起），审计模式复用 hext/external_evaluation._evaluate_process（:129-205）；H-EXT-04 库 hext/heading_provider.py 的 baseline_heading / angular_difference_statistics / extract_epoch_set 可作参考，但标记 NOT_AUTHORIZED_FOR_EXECUTION，登记授权前不得使用。phase2_runner 现有实现在父进程读 trace（:3507）且 BY2 硬编码（:3541-3542），不能直接作为进程复用 |
| notes | 十个模式（GPS/BDS/GPS+BDS × 约束 σ）是同一方法 id 的模式；原生内含未改 RTKLIB 动基线诊断（见 RTKLIB_UNMODIFIED_MOVING_BASE 行）；FIG03 范围 EXT01-EXT03 |

### 3.4 EXT04

| 字段 | 内容 |
| --- | --- |
| category | dual_antenna_ambiguity_heading |
| reference | Jiaji Wu, Jinguang Jiang, Yuying Li, Tianci Tang, Jianghua Liu, Jingnan Liu (2025) 'Robust Dual-Antenna GNSS/INS Attitude Determination via Constrained Ambiguity Resolution and Misalignment Compensation', IEEE TIM 74, 9539914, doi 10.1109/TIM.2025.3626898（configs/paper_rebuild/horizontal_literature/PHASE4_EXT04_WU2025_CONTRACT_V1.yaml:13-29）；仅实现 Section II-A 航向模块 |
| code_path | horizontal_literature/ext04_wu2025.py；phase4_runner.py；ext01_clambda.py；phase2_runner.py；phase3_signal_inventory.py；shared_raw_backend.py；scripts/paper_rebuild/run_horizontal_literature_phase4.py；外部 rtklib_bridge .so |
| entry_command | python3 scripts/paper_rebuild/run_horizontal_literature_phase4.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --artifact-root <REPRO_ROOT> --execution-lock $CLEAN4/11_REPORT/PHASE4_EXT04_EXECUTION_LOCK_R2F.json --execution-lock-sha256 cf88cc4ded1d042458d5f9f1acd3221d6d161fed0ce0b302f8376f7065330fae --preexisting-manifest $CLEAN4/05_EXT04_WU2025_MODULE/C00/EXT04_PREEXISTING_STAGE_HASH_MANIFEST.sha256 --preexisting-manifest-sha256 470629e9c0e2f973d3b5e78dde574a5222698018d52a38a8df9ee9ce14c9519c --method-id EXT04_WU2025 --case-id C00 --trace-mode disabled --workers 16 --mode native-only --resume（$CLEAN4/11_REPORT/PHASE4_STATUS.json exact_reproduction_commands） |
| runnable_check | help_ok（run_horizontal_literature_phase4.py；numpy 导入期 lscpu 被拦截、未执行）；import_ok（horizontal_literature.ext04_wu2025）；static_only（外部 bridge）。仅表示入口检查跑完，不表示方法可用或可复现：HEAD 的 phase4_runner.py、运行脚本、合约、tests/paper_rebuild/test_horizontal_phase4_c00.py 与原生记录不同 |
| param_source | PHASE4 合约 :74 基线 0.350、:158-163 ratio 3.0（PAPER_EXPERIMENTAL_VALUE）、:164-168 基线容差 0.050 m（论文基线参数改作声明容差）、:169-173 后验卡方 α 0.01（声明策略，论文未给）、:174-177 ADOP 0.12 周（声明策略，论文未给）、:178-185 单因素敏感性、:113-137 高度角 10.0 与 CN0 20；ext04_wu2025.py:39-44、:695-733 |
| inputs | 两台接收机 GPS L1/L2 + BDS B1/B2 RAWX，精确配对 1509，pntpos SPP 初始化；不用 IMU（论文为 GNSS/INS，但 INS 部分被模块边界排除）、腿、接触、status、HPPOSECEF；航向来自 FAR/PAR 接受的约束整数基线——BY2 C00 接受数为 0 |
| output_type | heading_only |
| by2_c00_existing_result | $CLEAN4/11_REPORT/PHASE4_STATUS.json：全部 27 个策略×模式行 accepted_count 0；FAR_and_primary_PAR_accepted_count 0；航向行 40743；聚合 FAR rejected 187、PAR exhausted 4368、invalid 36188；代理与参考比较行数 0，无任何误差数值；native_freeze_sha256 5f74a0928939c7e630bf8540d1259aeb51c86cf3fc07440fa43503ffc2d2bd46；终态 PASS_PHASE4_EXT04_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT。v3 MAIN_TABLE_V3.csv:23 未评估 |
| unavailable_reason_verbatim | MAIN_TABLE_V3.csv:23 "UNAVAILABLE_NO_IMU_POINT_NAV_ZERO_ACCEPTED_EPOCHS"（notes 同 EXT01，source_line 11）；FINAL_METHOD_REGISTRY.csv:5 "no FAR or primary PAR acceptance on clean BY2 C00"；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/00_METHOD_REGISTRY/FINAL_METHOD_REGISTRY_V2.csv:5 "PAPER_EXACT_PAR_POLICY_NOT_IMPLEMENTED_UNDER_SPECIFIED"；AGENTS.md:970-974 "module-only diagnostic; exact PAR policy not closed; all declared policy/mode accepted counts are zero; not a fourth complete raw method." |
| by2h_by2o_existing | 未运行（MAIN_TABLE_V3.csv:30、:37；phase4_runner.py:156 EXPECTED_PAIR_COUNT = 1509） |
| proposed_metric | heading_only：固定率/可用率 = 有效航向历元 / 评估窗内 GNSS 历元；有效历元航向 RMSE（wrap-safe，参考 yaw = wrap360(90 - interp(unwrap(yaw_ENU)))，要求前后括住、不外推）；保持上一有效值的全窗航向 RMSE（首个有效值之前的历元单独计数为无航向历元，不记零）；最大绝对误差（有效序列与保持序列各报一次）。评估点不适用（无位置/IMU 点输出）是换指标的理由，不是没有结果。当前接受数为 0：可用率报告为 0，其余指标无有效历元，数值空缺并注明原因（不是零误差） |
| evaluator_subprocess | NEW：航向评估子进程——strace 下只打开 trace 1 次并核哈希（经 evaluator_capture 钩子或调用冻结评估器的 load_trace）、支持各序列 base_time 与窗、与冻结评估器相同的 yaw 语义、以方法原生历元表构造 GNSS 历元分母、实现保持上一有效值；统计复用 horizontal_literature/phase2_runner.py _wrapsafe_error_metrics（:1491 起）/ _continuity_metrics（:1461 起）/ _circular_statistics_deg（:1442 起），审计模式复用 hext/external_evaluation._evaluate_process（:129-205）；H-EXT-04 库 hext/heading_provider.py 的 baseline_heading / angular_difference_statistics / extract_epoch_set 可作参考，但标记 NOT_AUTHORIZED_FOR_EXECUTION，登记授权前不得使用。phase2_runner 现有实现在父进程读 trace（:3507）且 BY2 硬编码（:3541-3542），不能直接作为进程复用 |
| notes | R1-R6 为同一原生运行的报告/收尾版本；Galileo 子模式不支持（无 Galileo 广播星历）；论文 Eqs. 5-24（加计调平、GNSS/INS 滤波、失准校正、Go2 IMU）按模块边界排除；策略×模式网格为 3 个系统模式（GPS_DUAL_FREQUENCY / BDS_DUAL_FREQUENCY / GPS_BDS_DUAL_FREQUENCY）× 9 个策略身份 = 27 个分支，全部接受数 0（$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/02_RAW_DUAL_ANTENNA/EXT04_SUPPLEMENTARY_DIAGNOSTIC_SUMMARY.csv 第 2-28 行；13_/11_REPORT/HORIZONTAL_CROSS_LAYER_INTEGRATED_REPORT.md:26）；论文精确 PAR 策略 EXT04_PAR_PAPER_EXACT 为 NOT_IMPLEMENTED_UNDER_SPECIFIED（$CLEAN4/11_REPORT/PHASE4_EXT04_C00_R1_REPORT.md:67） |

### 3.5 RTKLIB_UNMODIFIED_MOVING_BASE

| 字段 | 内容 |
| --- | --- |
| category | dual_antenna_ambiguity_heading |
| reference | RTKLIB 开源软件 2.4.3_b34，commit 180043ee24b6d2b168f98b64be15f69d50046b1a，BSD-2-Clause（$CLEAN4/00_CONTRACTS/EXTERNAL_METHOD_CONTRACTS_V1.yaml:64-72）；记录中无论文 |
| code_path | horizontal_literature/phase3_runner.py:409-416、:1471-1542（角色 POST_NATIVE_DIAGNOSTIC_ONLY）；外部二进制 $EXTERNAL/RTKLIB/app/consapp/rnx2rtkp/gcc/rnx2rtkp；另见 phase1r_runner.py:1652-1805、phase4_runner.py:3109 |
| entry_command | ["$EXTERNAL/RTKLIB/app/consapp/rnx2rtkp/gcc/rnx2rtkp", "-k", ".../RTKLIB_UNMODIFIED_MOVING_BASE.conf", "-o", ".../RTKLIB_UNMODIFIED_MOVING_BASE.pos", gnss2.obs, gnss1.obs, gnss1.nav, gnss2.nav]（$CLEAN4/04_EXT03_YANG2024/C00/POST_NATIVE/EXT03_C00_RTKLIB_DIAGNOSTIC.json:4-14），由 phase3 流程启动 |
| runnable_check | help_ok（包装入口 run_horizontal_literature_phase3.py）；static_only（rnx2rtkp 二进制未运行）。仅表示入口检查跑完，不表示方法可用或可复现 |
| param_source | RTKLIB_UNMODIFIED_MOVING_BASE.conf：pos1-posmode=movingbase、pos1-frequency=l1+l2、pos2-armode=continuous、pos2-arthres=3、pos2-baselen=0.350；config sha256 97f0fe4157ce31909538e696184a7faadad059c3099ab912cbe2e97b0fc9e14f（EXT03_C00_RTKLIB_DIAGNOSTIC.json:15）；rnx2rtkp sha256 3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda（PHASE3_EXT03_C00_REPORT.md:31）；工程设置，非文献值 |
| inputs | 两台接收机重建 RINEX（gnss2 流动站、gnss1 基站、导航文件）；无 IMU、status、腿、接触；航向可由动基线向量得出 |
| output_type | other |
| by2_c00_existing_result | 仅诊断（$CLEAN4/04_EXT03_YANG2024/C00/POST_NATIVE）：660 行（177 fixed、483 float），baseline_norm_mean_m 0.7901123316657044（EXT03_C00_RTKLIB_DIAGNOSTIC.json:3）；与 EXT03 原生状态对比 608 个有限比较，方向角差均值/中位/最大 75.777/69.436/169.581 deg（PHASE3_EXT03_C00_REPORT.md:132-134）；从未与参考比较，无评估器、无评估点。另两处同类诊断：EXT01 phase 1R（$CLEAN4/02_EXT01_CLAMBDA/C00_VALIDATED{,_R2}/RTKLIB_DIAGNOSTIC_GPS_L1.*；R2 摘要 output_row_count 564、quality_counts {"1": 130, "2": 434}，role INDEPENDENT_RAW_DATA_SANITY_CHECK_NOT_EXT01）；EXT04（$CLEAN4/05_EXT04_WU2025_MODULE/C00/EXT04_C00_RTKLIB_DIAGNOSTIC.json 与 POST_NATIVE_R1_RTKLIB_FIXED_ASSOCIATION/EXT04_C00_R1_RTKLIB_DIAGNOSTIC.json；output_row_count 653、quality_counts {"1": 136, "2": 517}，role UNMODIFIED_RTKLIB_RELATIVE_DIAGNOSTIC_ONLY） |
| unavailable_reason_verbatim | "Stock RTKLIB chooses pivots differently, so this remains diagnostic-only."（$CLEAN4/11_REPORT/PHASE3_EXT03_C00_REPORT.md:134）；phase3_runner.py:1610 "diagnostic-only and never solver input" |
| by2h_by2o_existing | 无 |
| proposed_metric | 若作为方法登记：heading_only：固定率/可用率 = 有效航向历元 / 评估窗内 GNSS 历元；有效历元航向 RMSE（wrap-safe，参考 yaw = wrap360(90 - interp(unwrap(yaw_ENU)))，要求前后括住、不外推）；保持上一有效值的全窗航向 RMSE（首个有效值之前的历元单独计数为无航向历元，不记零）；最大绝对误差（有效序列与保持序列各报一次）。评估点不适用（无位置/IMU 点输出）是换指标的理由，不是没有结果；动基线向量转 body yaw = 航向 + 90°，可用率以 fixed 历元计 |
| evaluator_subprocess | NEW：航向评估子进程——strace 下只打开 trace 1 次并核哈希（经 evaluator_capture 钩子或调用冻结评估器的 load_trace）、支持各序列 base_time 与窗、与冻结评估器相同的 yaw 语义、以方法原生历元表构造 GNSS 历元分母、实现保持上一有效值；统计复用 horizontal_literature/phase2_runner.py _wrapsafe_error_metrics（:1491 起）/ _continuity_metrics（:1461 起）/ _circular_statistics_deg（:1442 起），审计模式复用 hext/external_evaluation._evaluate_process（:129-205）；H-EXT-04 库 hext/heading_provider.py 的 baseline_heading / angular_difference_statistics / extract_epoch_set 可作参考，但标记 NOT_AUTHORIZED_FOR_EXECUTION，登记授权前不得使用。phase2_runner 现有实现在父进程读 trace（:3507）且 BY2 硬编码（:3541-3542），不能直接作为进程复用 |
| notes | 不在任何 CLEAN4 方法登记表中，作为 EXT03 阶段的子诊断出现；RTKLIB 同时是 EXT01/EXT03 的固定依赖（那不是独立方法）；遗留材料把 'RTKLIB moving-base equals Teunissen/Yang/Liu/Wu reproduction' 列为禁止表述 |

### 3.6 D01_DIRECT_GEOMETRIC_BASELINE

| 字段 | 内容 |
| --- | --- |
| category | dual_antenna_ambiguity_heading |
| reference | HORIZONTAL18_V2 记录中无文献身份 |
| code_path | 运行时代码 configs/paper_rebuild/horizontal_literature/HORIZONTAL18_V2.yaml、scripts/paper_rebuild/run_horizontal18_v2.py、src/legsa_gins/paper_rebuild/horizontal_literature/horizontal18_v2.py、horizontal18_v2_runner.py（哈希见 $CLEAN4/07_HORIZONTAL18_V2_CANARY_R3_SERIALIZATION_FAILURE_E7AC202C/HORIZONTAL18_V2_PREPARATION.json:33-52）——均不在 HEAD，也不在 git 历史中 |
| entry_command | 无记录（源阶段 07_HORIZONTAL18_V2 已不存在，只剩 canary 与 prep 归档） |
| runnable_check | static_only（代码不在仓库，无法做 --help/导入检查） |
| param_source | 未找到 |
| inputs | BY2 双接收机位置（real_by2_raw）；无 IMU、腿、接触；输出列为 provider_epoch_index、absolute_time_unix_seconds、time_seconds、body_yaw_ned_deg、yaw_variance_rad2、yaw_std_deg、valid、baseline_length_m（heading_only 已由表头核实） |
| output_type | heading_only |
| by2_c00_existing_result | HC00_CLEAN 仅原生：NATIVE_COMPLETE，GEOMETRIC_BASELINE.csv 1472 行（row_count/valid_count 取自 RUN_SUMMARY.json）（sha256 0141892ea42c0d76fc2d7b67362de9e5351cf47a73c6897e92e1ac8c9296b19f）；未评估（CANARY_R3_ARCHIVE_LEDGER.json:266 evaluation_created false） |
| unavailable_reason_verbatim | "HORIZONTAL18_V2,DENIED_ACTIVE_PERFORMANCE_EVIDENCE,ALL,HORIZONTAL18_V2/** (identity only; performance not read),false,false,Old ranking mixes identities/support and is forbidden as active evidence."（$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/01_EVIDENCE_INDEX/INACTIVE_OR_LEGACY_EVIDENCE.csv:2）；archive_reason "GNSS_FORMAL_VALIDITY_FLAGS_SERIALIZED_AS_FLOAT_TOKENS_REJECTED_AT_LINE_1"（CANARY_R3_ARCHIVE_LEDGER.json:3） |
| by2h_by2o_existing | 无 |
| proposed_metric | 若恢复：heading_only：固定率/可用率 = 有效航向历元 / 评估窗内 GNSS 历元；有效历元航向 RMSE（wrap-safe，参考 yaw = wrap360(90 - interp(unwrap(yaw_ENU)))，要求前后括住、不外推）；保持上一有效值的全窗航向 RMSE（首个有效值之前的历元单独计数为无航向历元，不记零）；最大绝对误差（有效序列与保持序列各报一次）。评估点不适用（无位置/IMU 点输出）是换指标的理由，不是没有结果 |
| evaluator_subprocess | NEW：航向评估子进程——strace 下只打开 trace 1 次并核哈希（经 evaluator_capture 钩子或调用冻结评估器的 load_trace）、支持各序列 base_time 与窗、与冻结评估器相同的 yaw 语义、以方法原生历元表构造 GNSS 历元分母、实现保持上一有效值；统计复用 horizontal_literature/phase2_runner.py _wrapsafe_error_metrics（:1491 起）/ _continuity_metrics（:1461 起）/ _circular_statistics_deg（:1442 起），审计模式复用 hext/external_evaluation._evaluate_process（:129-205）；H-EXT-04 库 hext/heading_provider.py 的 baseline_heading / angular_difference_statistics / extract_epoch_set 可作参考，但标记 NOT_AUTHORIZED_FOR_EXECUTION，登记授权前不得使用。phase2_runner 现有实现在父进程读 trace（:3507）且 BY2 硬编码（:3541-3542），不能直接作为进程复用 |
| notes | HORIZONTAL18_V2 已停用；同一 canary 中 M01_EXT05_PAVLASEK_IEKF 是 LC01 的另一身份（并入 LC01 行），M02-M04 为内部方法；HORIZONTAL18_V2 中 D01/D02 是诊断流而非必选方法（HORIZONTAL18_V2_PREPARATION.json:28 diagnostic_stream_count 36、:30 mandatory_method_count 4），记录把 HORIZONTAL18_V2 整体归为 NOT_AN_EXTERNAL_METHOD_IDENTITY（docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload/00_ACTIVE_METHOD_REGISTRY/INACTIVE_OR_LEGACY_RESULT_REGISTRY.csv:3）；为不遗漏仍列一行，不建议作为外部对比方法 |

### 3.7 LC01

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Natalia Pavlasek, Alex Walsh, James Richard Forbes (2021) 'Invariant Extended Kalman Filtering Using Two Position Receivers for Extended Pose Estimation', ICRA 2021, pp. 5582-5588, doi 10.1109/ICRA48506.2021.9561150, arXiv 2104.14711（configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml:5-15）；别名 EXT05A / EXT05A_PAVLASEK_TWO_RECEIVER_IEKF / LC01_EXT05A；活动登记 id LC01_PAVLASEK2021_TWO_RECEIVER_IEKF（docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload/00_ACTIVE_METHOD_REGISTRY/ACTIVE_SOLUTION_LEVEL_LC_REGISTRY.csv:2；configs/.../lc02_final_candidate_triage/stage_payload/00_REGISTRY/LC02_FINAL_CANDIDATE_REGISTRY.csv:2，status COMPLETED_ACTIVE_METHOD）；HORIZONTAL18_V2 身份 M01_EXT05_PAVLASEK_IEKF |
| code_path | horizontal_literature/ext05_pavlasek.py（PavlasekIEKF :294-417）；ext05_provider.py；phase5_runner.py；scripts/paper_rebuild/run_horizontal_literature_phase5.py；H-EXT：hext/ext05_sequence_runner.py、parameters.py、execution.py、continuation.py、external_evaluation.py；scripts/paper_rebuild/hext_native.py、hext02_native.py、hext02_execute.py、hext03_execute.py |
| entry_command | CLEAN4：python scripts/paper_rebuild/run_horizontal_literature_phase5.py --mode native --workers 16 --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml，随后 --mode geometric-audit 与 --mode trace-evaluation（$CLEAN4/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/EXT05A_C00_NATIVE_SUMMARY.json execution.argv）；H-EXT：python scripts/paper_rebuild/hext02_native.py --sequence <SEQ> --mode run --cache-relative H_EXT_02/03_PROVIDER_CACHE/<SEQ> --output-relative H_EXT_02/04_NATIVE_RUNS/<SEQ>/LC01/<START> --configuration LC01 --start-mode <START>（hext/execution.py:269-270、:297-312） |
| runnable_check | help_ok（run_horizontal_literature_phase5.py、hext02_native.py、hext_native.py）；import_ok（horizontal_literature.ext05_pavlasek、ext05_provider、hext.ext05_sequence_runner）。仅表示入口检查跑完，不表示方法可用或可复现：H-EXT-02 路径受代码门控（ext05_sequence_runner.py:663-664 要求 execution_authorized true，合约为 false，H_EXT_CONTRACT_V1.yaml:4）；HEAD 的 phase5_runner.py、ext05_provider.py、运行脚本与 CLEAN4 原生时代码快照不同，仅 ext05_pavlasek.py（89d5496a…）与合约相同 |
| param_source | PHASE5 合约 :120-122 过程 PSD（论文实验值）gyro [0.0004, 0.0004, 0.000324] rad²/s、accel [0.0289, 0.0225, 0.0576] m²/s³；:115-118 初始协方差（姿态 (π/3)²、速度 0.1²、位置 0.1²）；:60-62 杠杆 imu_to_gnss1_frd_m [0.03, 0.03, -0.30]、gnss2_minus_gnss1_frd_m [0.0, -0.350, 0.0]；:80-87 R1 = pAcc1² I3、R2 = pAcc2² I3、堆叠 [[R1, -R1], [-R1, R1+R2]]；合约 sha256 a9476f909ed65c9b4760ac19dc3cde3d625fa3d390b2f133cae79182e2293392；phase5_runner.py:451-463 硬编码同值；H-EXT 经 hext/parameters.py:39-46 读取 |
| inputs | 两台接收机 UBX-NAV-HPPOSECEF 位置 + pAcc（RAWX 只用于历元时间线核对）；Go2 body IMU（仅陀螺/加计，FLU→FRD 再安装角 -1°）；不用 status 流、接收机 IMU、腿、接触、速度、多普勒；航向来自每次更新中的 p2-p1 相对向量与首个有效基线给出的初始 yaw |
| output_type | imu_point_nav |
| by2_c00_existing_result | (1) v3 封存行 MAIN_TABLE_V3.csv:17（evaluator_contract_v3，aa049248，v3 点）：h 0.0975479714305497 m、up 0.05066431825806066 m、yaw 2.9948274600591076 deg、3D 0.10992033421878504、58014/58014，evaluator_nav_sha256 0bea5169d8500015dff472f96ecfd02992b0d7208ad5baeaa5378273ee9056d1，source_nav ccd25c2e…；来源 P07 <CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/HORIZONTAL_TABLE_V3.csv 第 5 行（sha256 d91f53aaf855efc8c533a6f15a9c6c933e87bafb2bcc9bd169ba862163c82c01），变换经 clean5_degradation/evaluation.py:166（b_med 0.356191491865984）。(2) CLEAN4 C00（$CLEAN4/06_EXT05_PAVLASEK_TWO_RECEIVER/C00；FINAL_C00_NATIVE_FORMAL_RESULTS.csv 第 3 行）【同一评估器字节 aa049248，但评估点不同：IMU 点、无杠杆平移，即 v2 点；无捕获哈希与一致性门】H 0.1691391165921043 m、3D 0.3790089605253968 m、yaw 2.9948274600591076 deg；AGENTS.md:986-990 的锚点即此值；native freeze 9af78f4e4af3606317b817902d0d52c3320e3197f0bc1a009842baf7a181a516。(3) MAIN_TABLE_V2.csv:17（evaluator_contract_v2，IMU 点，h 0.16913911659210426）自 CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json 复用（sha256 7ad4294999bdb7b3668bb7cd59869f49a42fb0d840f76b83c94b0704aee64d75）。(4) CLEAN4 77 历元共同支撑诊断 h 0.1833817467510378（仅诊断） |
| unavailable_reason_verbatim | BY2 不适用（COMPLETED）。BY2H 行 evaluation_status AVAILABLE_GEOMETRIC_AUDIT_FAIL，审计错误 "geometric audit baseline has inadequate horizontal length"（$HEXT/08_AGGREGATE/GEOMETRIC_AUDIT.csv）；docs/paper_rebuild/hext/H_EXT_02_EXECUTION_RECORD.md:77 "BY2H 双接收机四行均因水平基线 ≤0.1 m 前置条件失败，median/P95 不可得，原始 UNAVAILABLE/error 保留；属于 D6 几何审计失败，不是指标零值。" |
| by2h_by2o_existing | 有（H-EXT，均 evaluator_contract_v3）：BY2H FILE_START MAIN_TABLE_V3.csv:42 h 0.09745269819180266、up 0.055628473363064763、yaw 2.1739364356142343（AVAILABLE_GEOMETRIC_AUDIT_FAIL）；BY2H CONTRACT_START :43（手稿行）h 0.0746064486934978、up 0.04480400773175869、yaw 2.208612313835051（AVAILABLE_GEOMETRIC_AUDIT_FAIL）；BY2O FILE_START :50 h 0.05430420090026619、up 0.04475161716620303、yaw 2.4536970334279924（COMPLETED，几何审计 PASS）；原生 $HEXT/04_NATIVE_RUNS/<SEQ>/LC01/<START>，评估 $HEXT/07_OFFLINE_EVALUATION/v3/<run>/EVALUATION_RESULT.json |
| proposed_metric | imu_point_nav：冻结评估器 aa049248，v3 评估点（NAV 按 FRD 杠杆 [0.03, 0.03-0.5*b_med, -0.30] m 平移到 POI，b_med 取各序列冻结值 BY2 0.356191491865984 / BY2H 0.35418777593777223 / BY2O 0.35013463864843675），各序列闭区间评估窗（BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]）；主指标 yaw/水平/高程 RMSE，另报 3D、yaw P95、roll/pitch、输出/匹配历元数与覆盖率，并行给 v2（IMU 点）。解算失败时：失败率（带分母）、失败时段（D8 界首次越界至窗尾）、失败前截断 NAV 的同口径指标（标 PRE_FAILURE，不并入有限样本分布） |
| evaluator_subprocess | 现有即可：hext/external_evaluation.py（H-EXT 已用它评估全部 LC01/EXT05C 行）；BY2 LIT 行走 P07 路径 clean5_parity/evaluation._external_evaluate；分段 hext/aggregate.segment_rows；失败 hext/t5a_runtime.bounded_lla_native。NEW：HX-03 注入所需的 provider/cache 层（缓存受哈希与身份绑定）；A2 基线保留变体的相对量测更新（§6.5） |
| notes | 手稿采用文献配置（BY2/BY2O FILE_START，BY2H CONTRACT_START），S 完整进补充（AGENTS.md:895）；BY2H 几何审计失败是因瞬态后任一历元水平基线 ≤0.1 m（phase5_runner.py:877-907）；HORIZONTAL18_V2 的 M01_EXT05_PAVLASEK_IEKF 为同一方法另一身份（仅原生、未评估、已停用）；遗留目录 DA06_PAVLASEK_TWO_RECEIVER_IEKF 无实现；v3 参考点：CLEAN5_PARITY_PLAN.md:55、:254 曾记为未证明，2026-09-09 人工声明（CLEAN5_PARITY_CONTRACT.yaml:164-167）确立 POI 变换；H-EXT H02 行（BY2H、BY2 S）经 hext/execution.py:354-356 评估，用默认 HARD_STOP 一致性策略，H03 行（BY2O）经 hext/continuation.py:407-411 用 D12；CLEAN4 原生运行时 EXT05 源码尚未跟踪（提交 32a0664 下，EXT05A_C00_NATIVE_SUMMARY.json code_snapshot） |

### 3.8 LC01-S

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | 同 LC01（Pavlasek, Walsh, Forbes 2021）的滤波器，配项目标定的 IMU 参数（S 值无文献来源） |
| code_path | hext/parameters.py（:49-78、:81-90、:103-120）；hext/ext05_sequence_runner.py（:897-1054、:1057-1146）；滤波器 ext05_pavlasek.py 不变 |
| entry_command | python scripts/paper_rebuild/hext02_native.py --sequence <SEQ> --mode run --cache-relative H_EXT_02/03_PROVIDER_CACHE/<SEQ> --output-relative H_EXT_02/04_NATIVE_RUNS/<SEQ>/LC01-S/<START> --configuration LC01-S --start-mode <START>（hext/execution.py:269-270、:311-312）；评估 hext02_execute.py / hext03_execute.py evaluate |
| runnable_check | help_ok（hext02_native.py）；import_ok（hext.ext05_sequence_runner）。仅表示入口检查跑完，不表示方法可用或可复现：H-EXT 路径受代码门控（同 LC01） |
| param_source | 非文献值：configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml（sha256 4ce6ca6c544c2ba39988ea0b0631a60207a4cea36987c3a2139052fedd3a4871）：frozen_arw 0.985（:482-485）→ gyro PSD 8.209651003126647e-08 rad²/s；accel PSD [0.024955479759623252, 0.026591815116529294, 0.01618043453873932]（:183-186）；加计比例 s 1.0308398903907543（:176）；缺口策略 DROP_DT_GT_0P1_AND_CONTINUE；初始协方差、R、杠杆、标定判据与 LC01 相同 |
| inputs | 同 LC01（加计按 s 缩放） |
| output_type | imu_point_nav |
| by2_c00_existing_result | H-EXT-02 BY2 FILE_START，MAIN_TABLE_V3.csv:40（v3）：h 0.10352490362681992、up 0.045250085330977255、yaw 1.5392385536245534、roll 4.243477935993363、pitch 2.990040090051533，几何审计 PASS，evaluator_nav_sha256 821c3f08c699080f808ef35355da6f3e78b5b8c7d6c153a10dfdefe4d9950c9b，来源 $HEXT/07_OFFLINE_EVALUATION/v3/BY2__LC01-S__FILE_START/EVALUATION_RESULT.json；v2 行（IMU 点，评估点与 v3 不同）h 0.17652071574947822。CLEAN4 无此配置 |
| unavailable_reason_verbatim | BY2/BY2O 无。BY2H 行（:46、:47）AVAILABLE_GEOMETRIC_AUDIT_FAIL，审计错误 "geometric audit baseline has inadequate horizontal length"（$HEXT/08_AGGREGATE/GEOMETRIC_AUDIT.csv） |
| by2h_by2o_existing | 有：BY2H FILE_START MAIN_TABLE_V3.csv:46 h 0.10670864118045774、up 0.040725576553664294、yaw 1.7940541340876093；BY2H CONTRACT_START :47 h 0.08373314985151889、up 0.0403641769018664、yaw 1.9430028350481119（均 AVAILABLE_GEOMETRIC_AUDIT_FAIL）；BY2O FILE_START :52 h 0.06046245535470896、up 0.03993000337367851、yaw 4.015602467888004（COMPLETED，PASS） |
| proposed_metric | imu_point_nav：冻结评估器 aa049248，v3 评估点（NAV 按 FRD 杠杆 [0.03, 0.03-0.5*b_med, -0.30] m 平移到 POI，b_med 取各序列冻结值 BY2 0.356191491865984 / BY2H 0.35418777593777223 / BY2O 0.35013463864843675），各序列闭区间评估窗（BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]）；主指标 yaw/水平/高程 RMSE，另报 3D、yaw P95、roll/pitch、输出/匹配历元数与覆盖率，并行给 v2（IMU 点）。解算失败时：失败率（带分母）、失败时段（D8 界首次越界至窗尾）、失败前截断 NAV 的同口径指标（标 PRE_FAILURE，不并入有限样本分布） |
| evaluator_subprocess | 同 LC01：hext/external_evaluation.py 现有即可 |
| notes | 补充行（H_EXT_CONTRACT_V1.yaml:315）；S 参数以 BY2 标定（CLEAN5_CALIBRATED_SENSOR_MODEL.yaml:177-182），BY2 行对 IMU 模型为样本内；D10 曾按 BY2 v3 航向选 S，H-EXT-04L 把手稿行改回 LIT（amended_after_results_seen true，H_EXT_CONTRACT_V1.yaml:316），第 40 行自身标志为 false |

### 3.9 EXT05B

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Pavlasek, Walsh, Forbes (2021) ICRA 2021 的 Appendix A MEKF，Eqs. (45)-(50)（PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml:5-13、:19-28）；别名 EXT05B_PAVLASEK_TWO_RECEIVER_MEKF_APPENDIX_EXACT |
| code_path | 无实现；仅标识符（ext05_pavlasek.py:26、:28）与豁免记录写出（phase5_runner.py:759-778） |
| entry_command | 无（豁免 JSON 由 CLEAN4 LC01 原生运行附带写出） |
| runnable_check | static_only（无实现、无入口） |
| param_source | 无参数；状态与缺陷列表 PHASE5 合约 :19-28 |
| inputs | 无（未实现；按定义与 LC01 相同：两台 HPPOSECEF 位置 + Go2 body IMU） |
| output_type | other |
| by2_c00_existing_result | 无结果：$CLEAN4/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/EXT05B_C00_MEKF_NOT_IMPLEMENTED.json（status NOT_IMPLEMENTED_DUE_TO_INTERNAL_APPENDIX_INCONSISTENCY，human_waiver true）；P07 HORIZONTAL_TABLE_V3.csv 第 13 行 UNAVAILABLE_NOT_IMPLEMENTED；v3 MAIN_TABLE_V3.csv:25 全部 UNAVAILABLE，从未评估 |
| unavailable_reason_verbatim | PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml:20-28 "status: NOT_IMPLEMENTED_DUE_TO_INTERNAL_APPENDIX_INCONSISTENCY"、"human_waiver: true"，defects "EQ45_LEFT_NAVIGATION_ERROR_CONFLICTS_WITH_EQ46_RIGHT_BODY_JACOBIAN"、"EQ47_RELATIVE_NOISE_PLUS_CONFLICTS_WITH_EQ21_DIFFERENCE"、"EQ48_INNOVATION_AND_EQ50_ATTITUDE_SIGN_CONFLICT"、"NO_CORRECTION_INJECTION_RESET_EQUATION"、"STACKED_ABSOLUTE_RELATIVE_MEASUREMENT_CROSS_COVARIANCE_OMITTED"；$CLEAN4/11_REPORT/EXT05A_C00_VALIDITY_REPORT.md:12 "MEKF appendix baseline: `NOT_IMPLEMENTED_DUE_TO_INTERNAL_APPENDIX_INCONSISTENCY` (human-waived; no synthetic or repaired MEKF result)."；MAIN_TABLE_V3.csv:25/32/39 failure_classification "UNAVAILABLE_NOT_IMPLEMENTED"，notes availability "UNAVAILABLE_NOT_IMPLEMENTED"、scope "BY2_FROZEN_REGISTRY_REASON; NO_NEW_H_OR_O_EXECUTION"、source_line 13 |
| by2h_by2o_existing | 否；MAIN_TABLE_V3.csv:32、:39 只是 UNAVAILABLE 占位 |
| proposed_metric | 若实现：按 imu_point_nav 口径（同 LC01）；当前无输出，登记为未实现（不是指标零值） |
| evaluator_subprocess | 若实现同 LC01（hext/external_evaluation.py）；NEW：MEKF 本身（需先解决附录方程不一致） |
| notes | 不在 $CLEAN4/12_FINAL_EVIDENCE_INTEGRATION/FINAL_METHOD_REGISTRY.csv；豁免明确不是独立论文主张（separate_paper_claim false） |

### 3.10 LC01-M

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Pavlasek 等（2021）滤波器；H-EXT-04 草案 D2（未跟踪 configs/paper_rebuild/hext/H_EXT_04_CONTRACT_V1.yaml:17-18） |
| code_path | src/legsa_gins/paper_rebuild/hext/matched.py（relative_projection :35-52、relative_measurement_system :67-95、update_relative_components :98-137、MatchedEpochUpdate :149-212），标记 NOT_AUTHORIZED_FOR_EXECUTION（:6、:22）；执行包装只在未跟踪草稿（scripts/paper_rebuild/hext04_execute.py、src/.../hext/matched_execution.py 等） |
| entry_command | 无（执行部分已取消，<HEXT_SCRATCH> 下无 H_EXT_04 运行目录） |
| runnable_check | static_only（NOT_AUTHORIZED_FOR_EXECUTION；未跑 --help、未按计划导入——matched.py 的意外部分导入见 HX_INVENTORY.md §9.1） |
| param_source | LIT（同 LC01） |
| inputs | 同 LC01，另以冻结 v2.1 A1 yaw_valid 历元集作更新调度（匹配 1 Hz 历元做双接收机更新，其余做 p1-only 更新） |
| output_type | imu_point_nav |
| by2_c00_existing_result | 无（从未执行） |
| unavailable_reason_verbatim | docs/paper_rebuild/hext/H_EXT_04L_RECORD.md:61 "H-EXT-04 LC01-M/LC01-2D/S5 执行部分取消。仅 heading_provider.py、matched.py 中 D4 变换/调度/2D 投影及纯库测试纳入，NOT_AUTHORIZED_FOR_EXECUTION；删除的是拟提交库文件中的执行包装部分，其完整原稿已复制到 `<HEXT_SCRATCH>/H_EXT_04L/DRAFT_PRESERVATION`，未物理删除草案。"；AGENTS.md:896 "H-EXT-04 执行部分取消；仅库代码 NOT_AUTHORIZED_FOR_EXECUTION，T5 待[…]；额外身份验证预算问题作废。"（原文此处一词按本文用词规则以 […] 代替） |
| by2h_by2o_existing | 否（仅在未跟踪草案合约中计划） |
| proposed_metric | 若将来登记并授权：按 imu_point_nav 口径（同 LC01）；当前无输出 |
| evaluator_subprocess | 若将来运行同 LC01（hext/external_evaluation.py） |
| notes | 草案身份，未进入任何封存表 |

### 3.11 LC01-S-M

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Pavlasek 等（2021）滤波器；H-EXT-04 草案 D2（同上） |
| code_path | src/legsa_gins/paper_rebuild/hext/matched.py（relative_projection :35-52、relative_measurement_system :67-95、update_relative_components :98-137、MatchedEpochUpdate :149-212），标记 NOT_AUTHORIZED_FOR_EXECUTION（:6、:22）；执行包装只在未跟踪草稿（scripts/paper_rebuild/hext04_execute.py、src/.../hext/matched_execution.py 等） |
| entry_command | 无（执行部分已取消，<HEXT_SCRATCH> 下无 H_EXT_04 运行目录） |
| runnable_check | static_only（NOT_AUTHORIZED_FOR_EXECUTION；未跑 --help、未按计划导入——matched.py 的意外部分导入见 HX_INVENTORY.md §9.1） |
| param_source | S（同 LC01-S） |
| inputs | 同 LC01-M，S 参数 |
| output_type | imu_point_nav |
| by2_c00_existing_result | 无（从未执行） |
| unavailable_reason_verbatim | docs/paper_rebuild/hext/H_EXT_04L_RECORD.md:61 "H-EXT-04 LC01-M/LC01-2D/S5 执行部分取消。仅 heading_provider.py、matched.py 中 D4 变换/调度/2D 投影及纯库测试纳入，NOT_AUTHORIZED_FOR_EXECUTION；删除的是拟提交库文件中的执行包装部分，其完整原稿已复制到 `<HEXT_SCRATCH>/H_EXT_04L/DRAFT_PRESERVATION`，未物理删除草案。"；AGENTS.md:896 "H-EXT-04 执行部分取消；仅库代码 NOT_AUTHORIZED_FOR_EXECUTION，T5 待[…]；额外身份验证预算问题作废。"（原文此处一词按本文用词规则以 […] 代替） |
| by2h_by2o_existing | 否（仅在未跟踪草案合约中计划） |
| proposed_metric | 若将来登记并授权：按 imu_point_nav 口径（同 LC01）；当前无输出 |
| evaluator_subprocess | 若将来运行同 LC01（hext/external_evaluation.py） |
| notes | 草案身份，未进入任何封存表 |

### 3.12 LC01-2D

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Pavlasek 等（2021）滤波器；H-EXT-04 草案 D3（H_EXT_04_CONTRACT_V1.yaml:19-20） |
| code_path | src/legsa_gins/paper_rebuild/hext/matched.py（relative_projection :35-52、relative_measurement_system :67-95、update_relative_components :98-137、MatchedEpochUpdate :149-212），标记 NOT_AUTHORIZED_FOR_EXECUTION（:6、:22）；执行包装只在未跟踪草稿（scripts/paper_rebuild/hext04_execute.py、src/.../hext/matched_execution.py 等） |
| entry_command | 无（执行部分已取消，<HEXT_SCRATCH> 下无 H_EXT_04 运行目录） |
| runnable_check | static_only（NOT_AUTHORIZED_FOR_EXECUTION；未跑 --help、未按计划导入——matched.py 的意外部分导入见 HX_INVENTORY.md §9.1） |
| param_source | S（草案 D3） |
| inputs | 同 LC01；相对块投影到固定 NED 的 N/E（P = blockdiag(I3, S_NE*C_nb)，matched.py:47-52），绝对 p1 行保留 |
| output_type | imu_point_nav |
| by2_c00_existing_result | 无（从未执行） |
| unavailable_reason_verbatim | docs/paper_rebuild/hext/H_EXT_04L_RECORD.md:61 "H-EXT-04 LC01-M/LC01-2D/S5 执行部分取消。仅 heading_provider.py、matched.py 中 D4 变换/调度/2D 投影及纯库测试纳入，NOT_AUTHORIZED_FOR_EXECUTION；删除的是拟提交库文件中的执行包装部分，其完整原稿已复制到 `<HEXT_SCRATCH>/H_EXT_04L/DRAFT_PRESERVATION`，未物理删除草案。"；AGENTS.md:896 "H-EXT-04 执行部分取消；仅库代码 NOT_AUTHORIZED_FOR_EXECUTION，T5 待[…]；额外身份验证预算问题作废。"（原文此处一词按本文用词规则以 […] 代替） |
| by2h_by2o_existing | 否（仅在未跟踪草案合约中计划） |
| proposed_metric | 若将来登记并授权：按 imu_point_nav 口径（同 LC01）；当前无输出 |
| evaluator_subprocess | 若将来运行同 LC01（hext/external_evaluation.py） |
| notes | 草案身份，未进入任何封存表；LC01-2D 保留绝对 p1 行（matched.py:50），不是仅基线更新 |

### 3.13 LC02_GINAV

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Chen, Chang, Chen (2021) 'GINav: a MATLAB-based software for the data processing and analysis of a GNSS/INS integrated navigation system', GPS Solutions 25, 108, doi 10.1007/s10291-021-01144-9；官方软件 github.com/kaichen686/GINav @ bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666（BSD-2-Clause，configs/paper_rebuild/horizontal_literature/ginav2021/GINAV2021_RUNTIME_CONTRACT.yaml:9-15）；别名 LC02C_GINAV2021_OFFICIAL_SPP_INS_LC、GINAV |
| code_path | scripts/paper_rebuild/run_lc02_ginav2021.py；src/legsa_gins/paper_rebuild/horizontal_literature/ginav2021/*.py；configs/paper_rebuild/horizontal_literature/ginav2021/GINAV2021_RUNTIME_CONTRACT.yaml；$EXTERNAL/GINav（项目包装不调用 GINavExe.m，而是在断言 global_variable/decode_cfg/read_infile/readimu/exepos 后直接调用 exepos(opt, file)，ginav2021/matlab.py:153、:257；静态闭合行列出的官方函数为 src/ins/ins_align.m、tdcp2vel.m、ins_time_updata.m、src/main_func/gi_Loose.m、gi_processor.m、gnss_solver.m、src/gnss_ins_lc/gnss_ins_lc.m）；未跟踪 scripts/paper_rebuild/LC02_GINAV2021_RESUME_20260826.py（sha256 06dd11dc…，与 r4 归档驱动相同） |
| entry_command | 文档化：python3 scripts/paper_rebuild/run_lc02_ginav2021.py execute --ginav-root <GINAV_ROOT> --matlab-executable <MATLAB_EXECUTABLE> --libarchive-path <PINNED_RESOLVED_LIBARCHIVE_FILE> --scratch-root <FRESH_EXT4_SCRATCH> --stage-root <EXACT_STAGE_ROOT> --paper-root <PAPER_ROOT> --legacy-freeze-root <LEGACY_FREEZE_ROOT>（docs/paper_rebuild/horizontal_literature/ginav2021/README.md:11-16）；实际链 attempt1-4 → resume_20260826 / continuation_* / r4 → r4b/r4c/r4d 子命令；只有 r4 所用驱动与仓库中未跟踪副本逐字节相同（sha256 06dd11dc75c65569e1b4a3475fe68bc41ba623c3d8ce15f2e47ec26c52e89967），更早的根目录各自归档了同名但不同版本的驱动；MATLAB 为 Windows 版经 WSL 调用 /mnt/f/MATLAB2025b/bin/matlab.exe（R2025b，sha256 6dc32276086121e44edf4846f033066ba5b0fae9bad002d8917a411e0a59afa9） |
| runnable_check | help_ok（run_lc02_ginav2021.py）；import_ok（horizontal_literature.ginav2021.matlab）；static_only（GINav MATLAB 本体：MATLAB 不在 WSL PATH，合约禁止 PATH 回退，未运行）。仅表示入口检查跑完，不表示方法可用或可复现：HEAD 代码为 r4d 身份，与产生 G4 原生输出的 r4c 代码不同 |
| param_source | 官方配置 conf/LC/GINav_SPP_LC_CPT.ini（sha256 6250830f6785d62e323b51b6852fc15d982ee1768f5a90f9dd031760c98c2196）；BY2 派生配置 config_hash 688ea8acaa910971b9cc3a37861328d6be1b678e82f8a409a1385207ebc66975，逐项差异 $CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/runtime/r4b/s/g3c/BY2_GINAV_CONFIG_DIFF.csv（navsys C→GRCJ、sample_rate 100→500、lever 0,0,0→0.03,0.03,0.30、PSD 改为 GO2_IMU_ALLAN_90MIN_RECOVERED_V1 映射；SPP 选项与初始不确定度不变）；合约 GINAV2021_RUNTIME_CONTRACT.yaml:135-146、:164-167；无论文表格参数，文献值即官方软件配置 |
| inputs | GNSS1 RAWX/SFRBX → RTKLIB convbin RINEX 3.04 + 广播星历（GINav 内部 SPP）；NAV-PVT 仅用于因果时间关联；Go2 body IMU（陀螺/加计，63277 条前缀）；不用 GNSS2、双天线航向、Go2 姿态/PVT、腿、接触；航向来自官方 TDCP 速度对准，之后 INS 递推 + SPP LC 位置/速度更新 |
| output_type | imu_point_nav |
| by2_c00_existing_result | CLEAN4 coverage-aware C00（$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/coverage_aware_c00/；FINAL_C00_NATIVE_FORMAL_RESULTS.csv 第 2 行）【评估点与 v3 不同：GINav IMU 点无平移；评估器只记 'exact evaluator'、10 次调用、未记 sha256，无一致性门、无封存】窗 66-340 s，275 个整数历元、77 有效行，行覆盖 0.28，时间跨度覆盖 0.6204270072992701，最大缺口 11.0 s，38 段；H 130.8187259110151 m、3D 219.88371098234956 m、up 176.73513319764166 m、yaw 69.75333248293973 deg、roll 14.936207000465183、pitch 14.107014661009151（AGENTS.md:992-1005 的锚点即此）。v3 重评估（<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/LC02_GINAV/，aa049248，v3 点）：一致性门 horizontal_max_m 0.32877265945943457 > 0.01 未通过 → FAILED_EVALUATOR，无指标入表 |
| unavailable_reason_verbatim | MAIN_TABLE_V3.csv:19（:26、:33 相同）notes {"availability": "UNAVAILABLE_EVALUATION_FAILED", "frozen_failure": "External evaluator audit failed: ", "original_evaluation_status": "FAILED_EVALUATOR", "scope": "BY2_FROZEN_REGISTRY_REASON; NO_NEW_H_OR_O_EXECUTION", "source_line": 7, "source_table": "<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/HORIZONTAL_TABLE_V3.csv", "source_table_sha256": "d91f53aaf855efc8c533a6f15a9c6c933e87bafb2bcc9bd169ba862163c82c01"}（冒号后为空因评估器 stderr 为 0 字节）；docs/paper_rebuild/CLEAN5_DEGRADATION_SUBSET_RESULTS.md:1326 "GINav 的评估器实际调用 1 次、exit_code=0；capture matched_epoch_count=77。capture.consistency：horizontal_max_m=0.328772659 m > 0.01 m，up_max_m=0.00397204515 m，yaw_max_deg=1.70530257e−13 deg，passed=false。因此横向外层 evaluation_status=`FAILED_EVALUATOR`，availability=`UNAVAILABLE_EVALUATION_FAILED`；没有重试，正式 H/3D/Up/yaw/体坐标指标均为空。exit 0 不替代 wrapper 的一致性门。"；AGENTS.md:1111 "GINav horizontal v3 remains `UNAVAILABLE_EVALUATION_FAILED`." |
| by2h_by2o_existing | 从未运行（不在 H-EXT 方法表 H_EXT_CONTRACT_V1.yaml:234-250；v3 BY2H/BY2O 行 :26、:33 只复制 BY2 理由）；AGENTS.md:1473 默认不重跑 GINav |
| proposed_metric | imu_point_nav：冻结评估器 aa049248，v3 评估点（NAV 按 FRD 杠杆 [0.03, 0.03-0.5*b_med, -0.30] m 平移到 POI，b_med 取各序列冻结值 BY2 0.356191491865984 / BY2H 0.35418777593777223 / BY2O 0.35013463864843675），各序列闭区间评估窗（BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]）；主指标 yaw/水平/高程 RMSE，另报 3D、yaw P95、roll/pitch、输出/匹配历元数与覆盖率，并行给 v2（IMU 点）。解算失败时：失败率（带分母）、失败时段（D8 界首次越界至窗尾）、失败前截断 NAV 的同口径指标（标 PRE_FAILURE，不并入有限样本分布）。GINav 为稀疏输出（77/275），另报行覆盖、时间跨度覆盖、最大缺口与段数（覆盖感知分母，不外推）；一致性门失败时按 D12 规则单列为评估失败类别（不记零、不删历元） |
| evaluator_subprocess | 现有：clean5_parity/evaluation._external_evaluate（P07，已用于 GINav v3 尝试）或 hext/external_evaluation.evaluate（含 D12 策略）；.pos→11 列 NAV 适配器先例 clean5_degradation/evaluation.ginav_nav（:109-114）与 GINAV_OUTPUT_CONVERSION_CONTRACT.md。NEW：CLEAN4 coverage-aware 评估代码不在仓库，需要时按 v3 口径重写覆盖感知统计；稀疏 NAV 一致性门失败的处理须事先写入合约 |
| notes | 类别说明：记录定为 Layer B solution-level LC（AGENTS.md:928-930），只用 GNSS1 单接收机 SPP，若按天线数划分可改入 single_antenna_gnss_ins；已跟踪的 docs/paper_rebuild/horizontal_literature/ginav2021/LC02_GINAV2021_FINAL_TERMINAL_REPORT.md 仍写 attempt4 的 BLOCKED/VACANT，未更新到 r4d（PASS_LC02_GINAV2021_EXACT_ROUTE_AND_BY2_C00_VALIDATED，formal_lc02_slot FILLED）；两个标准 NAV 哈希不同（r4c 99f3b09e… 与 coverage_aware 85902928…，后者被 CLEAN4 与 v3 评估）；FIG02 中为 Not comparable；FIG02 保留 GINav 为 Not comparable 的原因是"no compatible completed v3 C00 evaluation is available"（src/legsa_gins/paper_rebuild/publication/protocol_v2_figures.py:726），不是缺少 IMU 点输出；coverage_aware_c00.zip 存在但评估状态记 "zip_created": false（GINAV_C00_EVALUATION_STATUS.json:97），说明该 zip 在评估事务外生成；绘图消费者 $CLEAN4/14_HORIZONTAL_FULL_PLOTTING/08_LC02_GINAV；CLEAN4 阶段内还有 11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.frozen_attempt2_9adb15c9fd3ee38e 与 .frozen_attempt3_f56190fef675b387（RELOCATION_LEDGER.json 记 formal_lc02_slot VACANT、G4_BY2_C00_runs 0）与 .partial（attempt 1）；结果范围区分 full_duration_c00（全输入处理，官方有限原生输出）与 coverage_aware_c00（正式窗评估），INS-only 行单列（13_/03_SOLUTION_LEVEL_LC/SOLUTION_LEVEL_LC_AVAILABILITY_SUMMARY.csv:3-5） |

### 3.14 LC02_YIN2023_RAEKF

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Yin, Yang, Ma, Wang, Chai, Cui (2023) 'A Robust Adaptive Extended Kalman Filter Based on an Improved Measurement Noise Covariance Matrix for the Monitoring and Isolation of Abnormal Disturbances in GNSS/INS Vehicle Navigation', Remote Sensing 15:4125, doi 10.3390/rs15174125（docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload/00_ACTIVE_METHOD_REGISTRY/ACTIVE_SOLUTION_LEVEL_LC_REGISTRY.csv:3）；旧别名 EXT06_YIN2023_RAEKF_LC |
| code_path | 仅审计代码，无解算器：horizontal_literature/lc02_y0_y3_audit.py、lc02_y4a_reproducibility_closure.py；scripts/paper_rebuild/audit_lc02_yin2023_y0_y3.py、audit_lc02_yin2023_y4a.py；合约 configs/paper_rebuild/horizontal_literature/lc02_yin2023/** |
| entry_command | 无审计 CLI 调用记录（只有 pytest 命令，configs/.../lc02_yin2023/y4a/stage_payload/11_REPORT/LC02_Y4A_STATUS.json:132、:140、:148） |
| runnable_check | help_ok（audit_lc02_yin2023_y0_y3.py、audit_lc02_yin2023_y4a.py——审计入口，不是解算器）；方法本身 static_only（无实现）。仅表示入口检查跑完，不表示方法可用或可复现 |
| param_source | docs/.../lc02_yin2023/stage_payload/02_PAPER_REVIEW/LC02_TABLE_AND_PARAMETER_REGISTRY.csv：Table 1 Q1-Q6（:2-7）；Table 2 陀螺偏置 0.25 deg/h、加计偏置 0.025（印刷单位 deg/h）、陀螺随机噪声 0.04 deg/√h、加计随机噪声 0.03 m/s/√h（:8-11）；Table 3 方法 4 PDOP²·Q·r²（:15）；IGGIII k0 1.15、k1 4.45（:27-28）；ω 0.85/0.15（:30-31）；LC02_PROCESS_NOISE_CONTRACT.yaml:12-13 论文未印 IMU 噪声数值 |
| inputs | GNSS1 UBX-NAV-PVT + NAV-COV（1510 次精确 iTOW 连接，5 Hz），GNSS 速度不在线使用；Go2 body IMU；GNSS2/基线/yaw 禁止；无腿、接触；航向仅 INS 递推 |
| output_type | other |
| by2_c00_existing_result | 无（C00_run 0、Yin_solver_run 0、trace_open 0：$CLEAN4/08_LC02_YIN2023_RAEKF/11_REPORT/LC02_Y0_Y3_STATUS.json:25-33）；合约定义的 INS 名义点 Go2_body_IMU_mechanization_origin（LC02_FRAME_AND_LEVER_ARM_CONTRACT.yaml:13-18，numerical_value_authorized_now false）从未产生输出 |
| unavailable_reason_verbatim | "Terminal: `NO_GO_LC02_YIN2023_RAEKF_AS_FORMAL_PRIMARY`." 与 "Formal RAEKF admission fails because the full online mapping is not unique:"（docs/paper_rebuild/horizontal_literature/lc02_yin2023/y4a/stage_payload/07_Y4A_REPRODUCIBILITY_CLOSURE/06_ADMISSION_DECISION/LC02_YIN2023_NO_GO_REASON.md:3、:7）；"The formal-primary rubric requires all ten hard gates plus `FAITHFUL_ALGORITHM_REPRODUCTION` for RKF and RAEKF. Only four gates pass, and the required branch levels are not met."（.../11_REPORT/LC02_FORMAL_ADMISSION_DECISION.md:9） |
| by2h_by2o_existing | 否 |
| proposed_metric | 若实现：按 imu_point_nav 口径；当前无输出，登记为未实现（不是指标零值） |
| evaluator_subprocess | 若实现：hext/external_evaluation.py；NEW：解算器本身（需先闭合 6 个硬门） |
| notes | 旧别名 EXT06_YIN2023_RAEKF_LC 与新 EXT06（Luo）冲突；EKF/AKF/RKF/RAEKF 分支视为一族一个正式外部主方法；停用的遗留别名 QA11G_YIN2023_IMPROVED_R_RAKF_EKF 的代码在 src/legsa_gins/reporting/by2_algorithm_runner.py:52（该文件被 docs/paper_rebuild/LEGACY_DENYLIST.md:23 拒绝），不是本方法的实现 |

### 3.15 LC02_CHANG2021_FSTCKF

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Yuanzhi Chang, Yongqing Wang, Yuyao Shen, Chunguo Ji (2021) 'A new fuzzy strong tracking cubature Kalman filter for INS/GNSS', GPS Solutions, doi 10.1007/s10291-021-01148-5（configs/paper_rebuild/horizontal_literature/lc02_chang2021/01_SOURCE_REGISTRY/LC02_CHANG_SOURCE_REGISTRY.csv:2） |
| code_path | 仅审计：horizontal_literature/lc02_chang2021_audit.py；scripts/paper_rebuild/audit_lc02_chang2021_r0_r4.py；无滤波实现 |
| entry_command | PYTHONPATH=src python3 scripts/paper_rebuild/audit_lc02_chang2021_r0_r4.py --validate-only（configs/.../lc02_chang2021/11_REPORT/LC02_CHANG_R0_R4_STATUS.json:123） |
| runnable_check | help_ok（审计入口 audit_lc02_chang2021_r0_r4.py）；方法本身 static_only（无实现）。仅表示入口检查跑完，不表示方法可用或可复现 |
| param_source | configs/.../lc02_chang2021/02_FULL_PAPER_REVIEW/LC02_CHANG_PARAMETER_REGISTRY.csv：n 15、m 6、ρ 0.95、N 40、α̂1 22、α̂2 13、T11 10 / T12 30 / T21 10 / T22 20、STCKF_FB β 4.5 等；Q/R 初始协方差 CURRENTLY_UNKNOWN（:33） |
| inputs | GNSS1 NAV-PVT + NAV-COV（位置、NED 速度及协方差，1510 次 5 Hz 连接）；Go2 IMU；禁用 GNSS2、基线、yaw、RAWX；无腿、接触；航向仅 INS 递推 |
| output_type | other |
| by2_c00_existing_result | 无（"All filter, C00, representative-case, comparison, LC01, Hartley, EXT01–04, HORIZONTAL18, and Canonical-541 run counts are zero."，docs/.../lc02_chang2021/11_REPORT/LC02_CHANG_R0_R4_FULL_REPORT.md:47） |
| unavailable_reason_verbatim | "Decision: `NO_GO_LC02_CHANG2021_FSTCKF_AS_FORMAL_PRIMARY`."（docs/.../lc02_chang2021/11_REPORT/LC02_CHANG_FORMAL_ADMISSION_DECISION.md:3）；"No implementation or synthetic-validation directory exists."（同文件 :7）；"The formal primary is rejected for source semantics, not for observed performance."（05_NON_DUPLICATION_AUDIT/LC02_CHANG2021_NO_GO_REASON.md:3） |
| by2h_by2o_existing | 否 |
| proposed_metric | 若实现：按 imu_point_nav 口径（输出点须先在合约中定义，当前为 CURRENTLY_UNKNOWN）；当前无输出 |
| evaluator_subprocess | 若实现：hext/external_evaluation.py；NEW：解算器本身 |
| notes | 5 门通过、7 门失败；BY2 单位/点兼容性 FAIL（CHANG2021_MEASUREMENT_CONTRACT.yaml:28-29） |

### 3.16 LC02A_JIANG2021_ADAPTIVE_FADING_CKF

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Jiang, Zhang, Li, Li (2021) 'Performance evaluation of the filters with adaptive factor and fading factor for GNSS/INS integrated systems', GPS Solutions 25, 130, doi 10.1007/s10291-021-01165-4 |
| code_path | 无（candidate_code_generated 0：configs/.../lc02_final_candidate_triage/stage_payload/11_REPORT/ZERO_EXECUTION_AUDIT.json:28） |
| entry_command | 无 |
| runnable_check | static_only（无实现） |
| param_source | 无（全文未取得，source registry 记 NOT_CAPTURED） |
| inputs | 未闭合；仅三角共同边界：Go2 body IMU + 依候选而定的 GNSS1 解 PVT/协方差（LC02_FINAL_CANDIDATE_TRIAGE_FULL_REPORT.md:23）；无腿、接触；航向未定义 |
| output_type | other |
| by2_c00_existing_result | 无（navigation_filter_run 0、BY2_C00_run 0） |
| unavailable_reason_verbatim | "LC02A,LC02A_JIANG2021_ADAPTIVE_FADING_CKF,Jiang et al. GPS Solutions 2021 DOI 10.1007/s10291-021-01165-4,NO_GO_SOURCE_UNAVAILABLE,NOT_EVALUATED_SOURCE_UNAVAILABLE,false,false,MANDATORY_GATES_NOT_ALL_PASS"（$CLEAN4/10_LC02_FINAL_CANDIDATE_TRIAGE/00_REGISTRY/LC02_FINAL_CANDIDATE_REGISTRY.csv:6）；"The mandatory-gate result is `NO_GO`; Jiang 2021 is neither an exact nor faithful reproduction candidate in the current source pack."（docs/.../lc02_final_candidate_triage/stage_payload/02_JIANG2021/JIANG2021_SOURCE_CLOSURE_AND_DECISION.md:9）；decision_reason "MANDATORY_FORMAL_REPRODUCTION_GATES_NOT_ALL_PASS" |
| by2h_by2o_existing | 否 |
| proposed_metric | 若实现：按 imu_point_nav 口径（接口未闭合，暂定）；当前无输出 |
| evaluator_subprocess | 若实现：hext/external_evaluation.py；NEW：解算器本身 |
| notes | 仅静态三角，排名 NOT_RANKED_MANDATORY_GATES_FAIL |

### 3.17 LC02B_TAGHIZADEH2023_AHINF_CKF

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | Taghizadeh, Safabakhsh (2023) 'Low-cost integrated INS/GNSS using adaptive H-infinity Cubature Kalman Filter', The Journal of Navigation 76(1):1-19, doi 10.1017/S0373463322000583 |
| code_path | 无（candidate_code_generated 0：configs/.../lc02_final_candidate_triage/stage_payload/11_REPORT/ZERO_EXECUTION_AUDIT.json:28） |
| entry_command | 无 |
| runnable_check | static_only（无实现） |
| param_source | 无（全文未取得，source registry 记 NOT_CAPTURED） |
| inputs | 未闭合；仅三角共同边界：Go2 body IMU + 依候选而定的 GNSS1 解 PVT/协方差（LC02_FINAL_CANDIDATE_TRIAGE_FULL_REPORT.md:23）；无腿、接触；航向未定义 |
| output_type | other |
| by2_c00_existing_result | 无（navigation_filter_run 0、BY2_C00_run 0） |
| unavailable_reason_verbatim | "LC02B,LC02B_TAGHIZADEH2023_AHINF_CKF,Taghizadeh-Safabakhsh Journal of Navigation 2023 DOI 10.1017/S0373463322000583,NO_GO_SOURCE_UNAVAILABLE,NOT_EVALUATED_SOURCE_UNAVAILABLE,false,false,MANDATORY_GATES_NOT_ALL_PASS"（$CLEAN4/10_LC02_FINAL_CANDIDATE_TRIAGE/00_REGISTRY/LC02_FINAL_CANDIDATE_REGISTRY.csv:7）；"The mandatory-gate result is `NO_GO`; Taghizadeh 2023 is neither an exact nor faithful reproduction candidate in the current source pack."（docs/.../03_TAGHIZADEH2023/TAGHIZADEH2023_SOURCE_CLOSURE_AND_DECISION.md:9）；decision_reason "MANDATORY_FORMAL_REPRODUCTION_GATES_NOT_ALL_PASS" |
| by2h_by2o_existing | 否 |
| proposed_metric | 若实现：按 imu_point_nav 口径（接口未闭合，暂定）；当前无输出 |
| evaluator_subprocess | 若实现：hext/external_evaluation.py；NEW：解算器本身 |
| notes | 仅静态三角，排名 NOT_RANKED_MANDATORY_GATES_FAIL |

### 3.18 EXT06_HAO2018_TWO_ANTENNA_LC_EKF

| 字段 | 内容 |
| --- | --- |
| category | loosely_coupled_gnss_ins |
| reference | 仅身份 token 'HAO2018'，记录中无作者、题名、出处 |
| code_path | 无 |
| entry_command | 无 |
| runnable_check | static_only（无实现） |
| param_source | 无 |
| inputs | 未记录（身份名指两天线 LC EKF） |
| output_type | other |
| by2_c00_existing_result | 无 |
| unavailable_reason_verbatim | "The abandoned `EXT06_HAO2018_TWO_ANTENNA_LC_EKF` identity is forbidden and obsolete."（$CLEAN4/08_LC02_YIN2023_RAEKF/00_ACTIVE_METHOD_REGISTRY/ACTIVE_EXTERNAL_METHOD_BOUNDARY.md:12；仓库副本 docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload/00_ACTIVE_METHOD_REGISTRY/ACTIVE_EXTERNAL_METHOD_BOUNDARY.md:12） |
| by2h_by2o_existing | 否 |
| proposed_metric | 已废弃身份，不建议评估；若恢复则按 imu_point_nav 口径 |
| evaluator_subprocess | 若恢复：hext/external_evaluation.py |
| notes | 与新 EXT06（Luo）ID 冲突；类别仅凭身份名（也可理解为双天线航向辅助 LC） |

### 3.19 EXT05C

| 字段 | 内容 |
| --- | --- |
| category | single_antenna_gnss_ins |
| reference | Pavlasek, Walsh, Forbes (2021) ICRA 2021 滤波器的单接收机诊断变体（PHASE5 合约 :29 'diagnostic: EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF'）；无单独论文 |
| code_path | 同 LC01（two_receiver=False）：ext05_pavlasek.py；phase5_runner.py；hext/ext05_sequence_runner.py（H02_CONFIGURATIONS 'EXT05C' :597-600） |
| entry_command | CLEAN4：与 LC01 同一原生运行（run_horizontal_literature_phase5.py --mode native ...）；H-EXT：python scripts/paper_rebuild/hext02_native.py --sequence <SEQ> --mode run --cache-relative H_EXT_02/03_PROVIDER_CACHE/<SEQ> --output-relative H_EXT_02/04_NATIVE_RUNS/<SEQ>/EXT05C/<START> --configuration EXT05C --start-mode <START> |
| runnable_check | help_ok（run_horizontal_literature_phase5.py、hext02_native.py）；import_ok（horizontal_literature.ext05_pavlasek）。仅表示入口检查跑完，不表示方法可用或可复现：H-EXT 路径受代码门控（同 LC01） |
| param_source | 同 LC01 文献值（PHASE5 合约 :120-122、:115-118、:60-62），只用 R1 = pAcc1² I3（:81） |
| inputs | GNSS1 HPPOSECEF + pAcc1 用于更新；GNSS2 只在初始化（基线 yaw）；Go2 body IMU（陀螺/加计）；无 status、腿、接触、速度、多普勒；航向：初始 yaw 来自双天线基线，之后仅靠 IMU 递推与 p1 更新的杠杆耦合 |
| output_type | imu_point_nav |
| by2_c00_existing_result | v3 MAIN_TABLE_V3.csv:18：h 0.0877508129138417、up 0.05646995229568549、yaw 12.048641737808111、yaw_p95 16.868495836757056、58014/58014，evaluator_nav_sha256 5bdb0c4d8fa8959354f3e05e5d0418d9b31607dec5cad37945dd47ddfbb29695，source_nav 915192d6…，P07 第 6 行（availability AVAILABLE_DIAGNOSTIC_DUAL_RX_INITIALIZATION）。CLEAN4（$CLEAN4/11_REPORT/EXT05A_C00_VALIDITY_REPORT.md:10）【评估点不同：IMU 点】H 0.171008 m、3D 0.381820 m、yaw 12.048642 deg；v2 行 h 0.17100769332496332 |
| unavailable_reason_verbatim | BY2 不适用（COMPLETED）；非主表/手稿行：role SINGLE_RECEIVER_DIAGNOSTIC（H_EXT_CONTRACT_V1.yaml:239-242）；P07 availability "AVAILABLE_DIAGNOSTIC_DUAL_RX_INITIALIZATION"（HORIZONTAL_TABLE_V3.csv 第 6 行）；docs/paper_rebuild/CLEAN5_DEGRADATION_SUBSET_RESULTS.md:1349 "EXT05C 保留诊断身份；无 IMU 点 NAV 的行保持 UNAVAILABLE。" |
| by2h_by2o_existing | 有（v3）：BY2H FILE_START MAIN_TABLE_V3.csv:44 h 0.1972843996333379、up 0.07873541819872971、yaw 55.609933584769315；BY2H CONTRACT_START :45 h 0.06918972281588827、up 0.05064624712585625、yaw 20.108223061254332；BY2O FILE_START :51 h 0.05195371361637804、up 0.0489029709338383、yaw 5.845502312798482（均 COMPLETED）；原生 $HEXT/04_NATIVE_RUNS/<SEQ>/EXT05C/<START> |
| proposed_metric | imu_point_nav：冻结评估器 aa049248，v3 评估点（NAV 按 FRD 杠杆 [0.03, 0.03-0.5*b_med, -0.30] m 平移到 POI，b_med 取各序列冻结值 BY2 0.356191491865984 / BY2H 0.35418777593777223 / BY2O 0.35013463864843675），各序列闭区间评估窗（BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]）；主指标 yaw/水平/高程 RMSE，另报 3D、yaw P95、roll/pitch、输出/匹配历元数与覆盖率，并行给 v2（IMU 点）。解算失败时：失败率（带分母）、失败时段（D8 界首次越界至窗尾）、失败前截断 NAV 的同口径指标（标 PRE_FAILURE，不并入有限样本分布） |
| evaluator_subprocess | 同 LC01：hext/external_evaluation.py 现有即可 |
| notes | 初始化用 GNSS2，不是纯单天线（约定 single_antenna_dual_yaw_initialization_only: true，CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml:394、:459）；航向对起点敏感；无几何审计（NOT_APPLICABLE_SINGLE_RECEIVER）；不在 FINAL_METHOD_REGISTRY.csv |

### 3.20 EXT05C-S

| 字段 | 内容 |
| --- | --- |
| category | single_antenna_gnss_ins |
| reference | EXT05C 的 S 参数版（项目标定 IMU 参数，无文献来源） |
| code_path | hext/parameters.py（:49-78、:81-90、:103-120）；hext/ext05_sequence_runner.py；滤波器不变 |
| entry_command | python scripts/paper_rebuild/hext02_native.py --sequence <SEQ> --mode run --cache-relative H_EXT_02/03_PROVIDER_CACHE/<SEQ> --output-relative H_EXT_02/04_NATIVE_RUNS/<SEQ>/EXT05C-S/<START> --configuration EXT05C-S --start-mode <START> |
| runnable_check | help_ok（hext02_native.py）；import_ok（hext.ext05_sequence_runner）。仅表示入口检查跑完，不表示方法可用或可复现：H-EXT 路径受代码门控 |
| param_source | 同 LC01-S（CLEAN5_CALIBRATED_SENSOR_MODEL.yaml :146-149、:176、:183-186、:482-485），非文献值 |
| inputs | 同 EXT05C（加计按 s 缩放） |
| output_type | imu_point_nav |
| by2_c00_existing_result | BY2 FILE_START MAIN_TABLE_V3.csv:41（v3）：h 0.11422779709467196、up 0.04699794989782003、yaw 9.7220981511841、yaw_p95 12.493120088559007，evaluator_nav_sha256 10daedc05be27fbe57eb2510af9a9f89bf0ba79610bea456cb4d2b2857aedf82；v2 行（IMU 点）h 0.17673171338322227。CLEAN4 无此配置 |
| unavailable_reason_verbatim | BY2H FILE_START（MAIN_TABLE_V3.csv:48）failure_classification ALGORITHM_FAILURE_DIVERGED，evaluation_status NOT_RUN_ALGORITHM_FAILURE，notes historical_evaluation_status "FAILED_EVALUATOR_CONSISTENCY"；docs/paper_rebuild/hext/H_EXT_02_CONTINUATION_AUTHORIZATION.md:44 "First D8 crossing: data row 2,446 / CSV line 2,447, relative time `418.59999990463257 s`, absolute `1772784418.6 s`; speed `51.19872445663034 m/s`, displacement `23.01454294544155 m`, relative height `9.62322100024769 m`. Maximum displacement `4.164517139545904e18 m`, maximum speed `4.2392617981840067e18 m/s`, maximum absolute relative height `3.7731674202350495e18 m`." |
| by2h_by2o_existing | BY2H FILE_START 发散（UNAVAILABLE）；BY2H CONTRACT_START MAIN_TABLE_V3.csv:49 h 0.08541883542514975、up 0.043320959381852174、yaw 8.114756205259614；BY2O FILE_START :53 h 0.07507995368164405、up 0.0397668290891221、yaw 8.266805432879499 |
| proposed_metric | imu_point_nav：冻结评估器 aa049248，v3 评估点（NAV 按 FRD 杠杆 [0.03, 0.03-0.5*b_med, -0.30] m 平移到 POI，b_med 取各序列冻结值 BY2 0.356191491865984 / BY2H 0.35418777593777223 / BY2O 0.35013463864843675），各序列闭区间评估窗（BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]）；主指标 yaw/水平/高程 RMSE，另报 3D、yaw P95、roll/pitch、输出/匹配历元数与覆盖率，并行给 v2（IMU 点）。解算失败时：失败率（带分母）、失败时段（D8 界首次越界至窗尾）、失败前截断 NAV 的同口径指标（标 PRE_FAILURE，不并入有限样本分布）。BY2H FILE_START 属解算失败：计入失败率，失败时段自 418.59999990463257 s 首次越界起，失败前指标按截断 NAV |
| evaluator_subprocess | 同 LC01；失败前截断包装为 NEW |
| notes | S 参数以 BY2 标定，BY2 行为样本内；BY2H FILE_START 的 v3 评估是 H-EXT-02 硬停起点（H_EXT_02_EXECUTION_RECORD.md:3、:54） |

### 3.21 D02_SINGLE_RECEIVER_IEKF

| 字段 | 内容 |
| --- | --- |
| category | single_antenna_gnss_ins |
| reference | HORIZONTAL18_V2 记录未给；运行时源码含 ext05_pavlasek.py 与 phase5_runner.py（HORIZONTAL18_V2_PREPARATION.json:44-48），推测为 Pavlasek 单接收机变体（未证实） |
| code_path | HORIZONTAL18_V2 未提交代码（horizontal18_v2*.py 等不在 HEAD，也不在 git 历史）；该运行记录的 ext05_pavlasek.py sha256 5e7042e9d3ec4d719651a56f34a4727a1b353496d9f93a40901bc459aab4e77a 不在任何 git 提交中（70dcaa4 与 HEAD 均为 89d5496a…），ext05_provider.py 5172276f… 等于 70dcaa4 而非 HEAD |
| entry_command | 无记录 |
| runnable_check | static_only（代码不在仓库） |
| param_source | 记录中未找到 |
| inputs | GNSS 接收机 1 位置 + Go2 body IMU（由更新计数推断）；初始机体 yaw 为 initial_attitude.yaw_ned_deg 1.3239770781292135（roll 0.9004752449568363、pitch -0.7942504551064933），与之并记的 measured_baseline_heading_ned_deg 271.3364603509171 是双接收机基线向量的方向而非机体 yaw；无腿、接触 |
| output_type | imu_point_nav |
| by2_c00_existing_result | HC00_CLEAN 原生 NATIVE_COMPLETE：NAV.csv 97275414 B（大小取自 ls），sha256 1273c8721c1fa9f4651b9957f60507955eabf0e662a74a945aab91c01997b281，receiver1_only_update_count 1471；未评估（evaluation_created false） |
| unavailable_reason_verbatim | 同 D01_DIRECT_GEOMETRIC_BASELINE："Old ranking mixes identities/support and is forbidden as active evidence."（$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/01_EVIDENCE_INDEX/INACTIVE_OR_LEGACY_EVIDENCE.csv:2）；CANARY_R3_ARCHIVE_LEDGER.json:3 archive_reason "GNSS_FORMAL_VALIDITY_FLAGS_SERIALIZED_AS_FLOAT_TOKENS_REJECTED_AT_LINE_1" |
| by2h_by2o_existing | 无 |
| proposed_metric | 若恢复：imu_point_nav：冻结评估器 aa049248，v3 评估点（NAV 按 FRD 杠杆 [0.03, 0.03-0.5*b_med, -0.30] m 平移到 POI，b_med 取各序列冻结值 BY2 0.356191491865984 / BY2H 0.35418777593777223 / BY2O 0.35013463864843675），各序列闭区间评估窗（BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]）；主指标 yaw/水平/高程 RMSE，另报 3D、yaw P95、roll/pitch、输出/匹配历元数与覆盖率，并行给 v2（IMU 点）。解算失败时：失败率（带分母）、失败时段（D8 界首次越界至窗尾）、失败前截断 NAV 的同口径指标（标 PRE_FAILURE，不并入有限样本分布） |
| evaluator_subprocess | 若恢复：hext/external_evaluation.py |
| notes | HORIZONTAL18_V2 已停用；输出点在记录中未写明；HORIZONTAL18_V2 中 D01/D02 是诊断流而非必选方法（HORIZONTAL18_V2_PREPARATION.json:28 diagnostic_stream_count 36、:30 mandatory_method_count 4），记录把 HORIZONTAL18_V2 整体归为 NOT_AN_EXTERNAL_METHOD_IDENTITY（docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload/00_ACTIVE_METHOD_REGISTRY/INACTIVE_OR_LEGACY_RESULT_REGISTRY.csv:3）；为不遗漏仍列一行，不建议作为外部对比方法 |

### 3.22 EXT06

| 字段 | 内容 |
| --- | --- |
| category | single_antenna_gnss_ins |
| reference | Yarong Luo, Yichao Chen, Anbo Tao, Chi Guo (2025) 'Leg Odometry Assisted GNSS/INS Integrated Navigation System for the Quadruped Robot', Lecture Notes in Electrical Engineering vol. 1346 (Proceedings of ICGNC 2024), Springer, pp. 253-264, doi 10.1007/978-981-96-2236-8_25——本次检索识别，置信度中，全文未读；仓库只记 'Luo et al.'（docs/paper_rebuild/CONVERSATION_HANDOFF.md:84、:199） |
| code_path | 无（仓库与 $EXTERNAL 中均无实现、合约或配置） |
| entry_command | 无 |
| runnable_check | static_only（无实现） |
| param_source | 见 HX_INVENTORY.md §7.5：左不变 EKF、局部世界系考虑地球自转、接触点动力学与腿里程计观测方程出自摘要；其余参数在可访问内容中均为'文献未给'（全文未核） |
| inputs | 按登记：单天线 GNSS + IMU（InEKF）+ 腿里程计，无 radar；航向来源未记录（无双天线航向） |
| output_type | other |
| by2_c00_existing_result | 无（无阶段目录、无评估、无封存） |
| unavailable_reason_verbatim | "pending; no execution or admission claimed"（docs/paper_rebuild/CONVERSATION_HANDOFF.md:84）；"此处不宣称已执行或已准入，不修改或重跑冻结主链。"（:199）；"EXT06 只新增对比行。"（AGENTS.md:1419） |
| by2h_by2o_existing | 无 |
| proposed_metric | 目标按 imu_point_nav：冻结评估器 aa049248，v3 评估点（NAV 按 FRD 杠杆 [0.03, 0.03-0.5*b_med, -0.30] m 平移到 POI，b_med 取各序列冻结值 BY2 0.356191491865984 / BY2H 0.35418777593777223 / BY2O 0.35013463864843675），各序列闭区间评估窗（BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]）；主指标 yaw/水平/高程 RMSE，另报 3D、yaw P95、roll/pitch、输出/匹配历元数与覆盖率，并行给 v2（IMU 点）。解算失败时：失败率（带分母）、失败时段（D8 界首次越界至窗尾）、失败前截断 NAV 的同口径指标（标 PRE_FAILURE，不并入有限样本分布）（要求输出含 roll/pitch/yaw 的 IMU 点 NAV）；若只能输出相对轨迹则按 relative_pose 口径 |
| evaluator_subprocess | 现有：hext/external_evaluation.py + clean5_parity/evaluation.transform_nav；本地 NED→11 列 LLA 适配器先例 hext/ext05_sequence_runner.materialize_exact_evaluator_nav（:318-392）。NEW：EXT06 解算器（左不变 GNSS 位置更新 + 接触/腿里程计 + 偏置 + 地球自转）、腿数据 provider（BY2H/BY2O 接触阈值与 FK 协方差需新审计）、输出适配器与合约 |
| notes | 类别说明：以单天线 GNSS 为绝对信息源、腿里程计为辅助，归 single_antenna_gnss_ins；若视腿里程计为主可改入 legged_state_estimation，记录未定。ID 冲突：旧 EXT06_YIN2023_RAEKF_LC、废弃 EXT06_HAO2018_TWO_ANTENNA_LC_EKF；Hartley 记录中的 ready_for_ext06 未说明指哪一个 |

### 3.23 Hartley

| 字段 | 内容 |
| --- | --- |
| category | legged_state_estimation |
| reference | Ross Hartley, Maani Ghaffari, Ryan M. Eustice, Jessy W. Grizzle (2020) 'Contact-Aided Invariant Extended Kalman Filtering for Robot State Estimation', IJRR 39(4), doi 10.1177/0278364919894385, arXiv 1904.09251；Ross Hartley, Maani Ghaffari Jadidi, Jessy W. Grizzle, Ryan M. Eustice (2018) 'Contact-Aided Invariant Extended Kalman Filtering for Legged Robot State Estimation', RSS XIV, doi 10.15607/RSS.2018.XIV.050, arXiv 1805.10410（docs/paper_rebuild/horizontal_literature/hartley/stage_payload/00_SOURCE_REGISTRY/PAPER_SOURCE_REGISTRY.csv:2-3）；别名 LSE01 |
| code_path | horizontal_literature/hartley_h0_h2.py、hartley_h3_h4.py、hartley_h5.py、hartley_h6.py、hartley_h6r.py、hartley_h7.py、hartley_h7c.py；C++ horizontal_literature/hartley_inekf/（目标 hartley_h5_runner）；scripts/paper_rebuild/audit_hartley_h0_h2_by2.py、validate_hartley_h3_h4.py、run_hartley_h5_by2.py、finalize_hartley_h5_native.py、run_hartley_h6.py、run_hartley_h6r.py、evaluate_hartley_h7.py、evaluate_hartley_h7c.py；外部 $EXTERNAL/hartley/invariant-ekf（ef16e8a）、Contact-Aided-Invariant-EKF（15f1ee7） |
| entry_command | 记录中无完整命令行；入口 scripts/paper_rebuild/run_hartley_h5_by2.py（子命令 prepare-provider --paths-config --attempt-root / run --attempt-root --native-executable --run-id <4 个 H5 run 之一> / verify-primary-gate），其内启动 C++ 'hartley_h5_runner CACHE CONFIG OUTPUT_DIR'（run_h5.cpp:228-234，run_hartley_h5_by2.py:508） |
| runnable_check | help_ok（run_hartley_h5_by2.py、audit_hartley_h0_h2_by2.py、validate_hartley_h3_h4.py、run_hartley_h6.py、run_hartley_h6r.py；后三者 numpy 导入期 lscpu 被拦截、未执行）；import_ok（horizontal_literature.hartley_h5）；static_only（C++ hartley_h5_runner 二进制无 --help，未运行）。仅表示入口检查跑完，不表示方法可用或可复现 |
| param_source | configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_PARAMETER_SOURCE_REGISTRY.csv:4-16 IJRR Table 1（加计噪声 0.04 m/s²、陀螺噪声 0.002 rad/s、加计偏置 RW 0.001 m/s³、陀螺偏置 RW 0.001 rad/s²、接触速度噪声 0.05 m/s、编码器 1.0 deg（BY2 无关节数据不适用）、初始 std 姿态 30.0 deg / 速度 1.0 m/s / 位置 0.1 m / 足端 0.1 m / 陀螺偏置 0.005 rad/s / 加计偏置 0.05 m/s²）；主分支 IMU 噪声取 GO2_IMU_ALLAN_90MIN_RECOVERED_V1（非文献值，:37-40）；FK 量测 std 0.010 m（BY2 实例化，:44）；接触力阈值（:48-50） |
| inputs | 仅 Go2 高层消息 by2.txt（63277 条完整记录）：IMU 陀螺/加计、foot_force（接触检测）、foot_position_body（Go2 高层 FK 代理，非编码器 FK）；无 GNSS、status、接收机 IMU；航向：初始 yaw 固定为 0，之后只由陀螺递推，是不可观的规范自由度 |
| output_type | relative_pose |
| by2_c00_existing_result | 无任何评估器下的绝对精度数值（absolute_position_RMSE null、absolute_yaw_RMSE null：$CLEAN4/07_LSE01_HARTLEY_CONTACT_INEKF/11_REPORT/LSE01_FINAL_STATUS.json:2-4）；原生证据：63,277 状态行；4 维规范（3 平移 + 重力轴 yaw）；4 接触偏置增广 rank/nullity 23/4、2 接触 17/4，0.1×/1×/10× 阈值下稳定；H6R 终态 PASS_LSE01_H6R_REAL_DATA_GAUGE_AND_OBSERVABILITY_CONFIRMED；主分支 NAV.csv sha256 dc4d95a1e634ea7f7c3aecfcb3cdd50ded8ebf4378dfcd46917ed4875338a600；评估器与评估点：无 |
| unavailable_reason_verbatim | MAIN_TABLE_V3.csv:24 failure_classification "UNAVAILABLE_ABSOLUTE_METRICS_UNANCHORED_TRANSLATION_AND_YAW_GAUGE"（notes source_line 12，scope "BY2_FROZEN_REGISTRY_REASON; NO_NEW_H_OR_O_EXECUTION"）；"Global translation and global yaw about gravity are unobservable." / "Absolute position/yaw RMSE are not applicable and have no numeric values."（$CLEAN4/07_LSE01_HARTLEY_CONTACT_INEKF/11_REPORT/LSE01_HARTLEY_CLAIM_BOUNDARY.md:7-8）；AGENTS.md:1026 "Hartley does not provide legal absolute yaw RMSE or absolute position RMSE and must not appear in a flat accuracy ranking."；H7C："The frozen deterministic mapping found 6,040 trace rows and 6,040 FP_POI geodetic rows with matching order and strict chronology. The required exact row-wise identity nevertheless failed. Differences are tiny CSV-serialization scale, but exact parsed-binary64 identity is false and the separately frozen exact-Decimal printed-token-cell test also fails. No post-result tolerance was introduced, so H1 is genuinely `CONTRADICTED`."（LSE01_H7C_FINAL_REPORT.md:5-10） |
| by2h_by2o_existing | 未运行（MAIN_TABLE_V3.csv:31、:38 复制 BY2 理由）；BY2H/BY2O 无接触阈值与 FK 协方差审计 |
| proposed_metric | relative_pose：评估窗起始 10 s（BY2 [66,76]、BY2H [413,423]、BY2O [3186,3196]）内拟合一次 4 自由度对齐（yaw + 三维平移，不拟合 roll/pitch/尺度），全窗不再调整；报告每 100 m 位置漂移、每分钟航向漂移（wrap-safe 航向误差对时间的最小二乘斜率）、对齐后全窗水平/高程/yaw RMSE；每行标注"无绝对锚定，不与绝对 v3 行比较" |
| evaluator_subprocess | NEW：10 s 窗最小二乘 yaw + 平移对齐（现有 hartley_h7.fixed_primary_gauge 只用单历元，:183-193）、每 100 m 与每分钟漂移函数、只回传指标的相对位姿评估子进程；复用 hartley_h7c.relative_pose_metrics（:325-339）/ fixed_primary_yaw_translation_gauge（:351-363）/ apply_fixed_gauge_to_pose（:366-373）与 hartley_h7 的 SO(3) 工具（:128-171）、offline_eval_aggregate._axis_stats/_norm_stats；须先人工决定 Hartley 点（Go2 body-IMU 原点）与 POI 的关系（H7_EVALUATION_CONTRACT.yaml:79-89 为 UNRESOLVED/ABSENT），且 H7C 参考血缘阻断仍在 |
| notes | 层间终态不一致：07_LSE01 记 lse01_complete false（BLOCKED_LSE01_H7C_REFERENCE_LINEAGE_CONTRADICTED），CLEAN4 13_ 综合改标 PASS_LSE01_COMPLETE_WITH_REFERENCE_EXTRINSIC_LIMITATION；H7C 为血缘检验曾读参考（历史记录，非本任务）；Corrected Classic-18 不得含 Hartley（AGENTS.md:1095）；绘图阶段 $CLEAN4/14_HORIZONTAL_FULL_PLOTTING/09_HARTLEY_OBSERVABILITY（FIG04，AGENTS.md:1132）；run_hartley_h6r.py 另有 publish 子命令（:82-84）；后端身份不可混同（HARTLEY_BACKEND_IDENTITY_REGISTRY.yaml:9-35）：BY2 生产后端 HARTLEY_IJRR2020_REPORTED_BACKEND（primary）；EXACT_QD_REFERENCE_DIAGNOSTIC（非 primary，H5 运行时不可用）；OFFICIAL_CPP_EARLY_REGRESSION（RossHartley/invariant-ekf@ef16e8a，非完整 IJRR 后端）；HARTLEY_MATLAB_HISTORICAL（RSS 2018 交叉核对，静态审计完成，MATLAB/Octave 不可用未执行，OFFICIAL_CODE_REGISTRY.csv:3） |

### 3.24 遗留目录中的外部方法（不属 CLEAN4/H-EXT 阶段记录，不入 CSV）

`src/legsa_gins/external_dual/method_contracts.py` 与 `external_dual_methods/method_contracts.py` 的 paper10 Q2R2/A1 目录项：
DA01_TEUNISSEN_CLAMBDA_COMPASS（"Blocked because this A1 implementation does not close a carrier DD/LOS integer ambiguity backend."，:41）、
DA01_TEUNISSEN_CLAMBDA（`src/legsa_gins/da_repro/`）、DA02_LIU_CONSTRAINED_WRAPPED_WLS（基于 status relpos）、DA03_YANG_BASELINE_KF_STATUS、
DA03_YANG_BASELINE_KF_MLAMBDA（runner 记 BLOCKED_WITH_PROOF / PROVIDER_CONTRACT_MISSING_INPUTS）、DA04_WU_ROBUST_EQKF_GO2、DA04_WU_ROBUST_DA_EQKF、
DA05_TEUNISSEN_AFFINE_MILS（"Blocked because affine MILS ambiguity backend is not closed without reducing it to a policy baseline."，:42）、
DA06_PAVLASEK_TWO_RECEIVER_IEKF（"Held as backup because body IMU/provider closure is higher risk."）。
前八项按信息结构属 dual_antenna_ambiguity_heading，DA06 属 loosely_coupled_gnss_ins。它们不出现在任何 CLEAN4/H-EXT 阶段记录中
（`$CLEAN4` 各记录 grep 无命中；`<CLEAN_ROOT>/08_EXTERNAL_DA` 为空），只被遗留脚本/测试引用；`docs/paper_rebuild/LEGACY_DENYLIST.md:7-8, 11, 24`
对遗留运行与 status 回退冒充完整后端作一般性禁止。其航向评分方式（最近 0.5 s、raw yaw % 360，`external_dual/trace_reference_adapter.py:17-42`）与 v3 语义不同。
另：各阶段用作诊断代理的 u-blox 接收机相对解（NAV-HPPOSECEF GNSS2−GNSS1 基线代理、A1 status 航向）是接收机原生输出与诊断参考，记录中没有方法 id，不计为外部方法（例如 `$CLEAN4/11_REPORT/PHASE1R_R2_EXT01_C00_VALIDITY_REPORT.md:51` "NAV-HPPOSECEF and RTKLIB relative positioning are diagnostic-only."）；v3 主链自身的航向输入即原始 HPPOSECEF 5 Hz 标量航向。
HORIZONTAL18_V2 的 M02_F02_BASIC_REF01、M03_F03_STRONG_REF01、M04_A04_CORE_REF01 为内部方法（原生失败保留），Go2 板载状态估计器被明确排除（HARTLEY_METHOD_CONTRACT.yaml:33），均不计入。

## 3A. 可运行检查（--help / 导入）

### 3A.1 带 NOT_AUTHORIZED_FOR_EXECUTION 标记的文件（检查前列出，只静态阅读）

命令：`git grep -l -I --untracked -e NOT_AUTHORIZED_FOR_EXECUTION`（覆盖已跟踪与未跟踪文件；文件名含 trace/truth
或扩展名为 .fpl/.bag 的文件按规则排除在 grep 之外，另对文件名含 trace 的源码/文档单独 grep，结果为空）。

| # | 路径 | 标记形式 | 处理 |
| --- | --- | --- | --- |
| 1 | `src/legsa_gins/paper_rebuild/hext/matched.py` | 模块级 `EXECUTION_STATUS = "NOT_AUTHORIZED_FOR_EXECUTION"`（:6, :22），H-EXT-04 库 | 只静态阅读；列入导入拦截表（**事故见 §9.1**） |
| 2 | `src/legsa_gins/paper_rebuild/hext/heading_provider.py` | 同上（:3, :26），H-EXT-04 库 | 只静态阅读；列入导入拦截表 |
| 3 | `src/legsa_gins/paper_rebuild/hext/t5bc_context.py` | 运行期防护字符串 `T5BC_DRAFT_NOT_AUTHORIZED_FOR_EXECUTION`（:92, :191） | 只静态阅读；列入导入拦截表 |
| 4 | `src/legsa_gins/paper_rebuild/hext/t5bc_runtime.py` | 同上（:102） | 只静态阅读；列入导入拦截表 |
| 5 | `tests/paper_rebuild/test_hext04_matched.py` | 测试文件内引用 | 只静态阅读；未运行任何测试 |
| 6 | `configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml` | `library: NOT_AUTHORIZED_FOR_EXECUTION`（:681） | 配置，只读 |
| 7 | `docs/paper_rebuild/hext/H_EXT_04L_RECORD.md` | 记录（:61） | 文档 |
| 8 | `docs/paper_rebuild/HORIZONTAL_THREE_SEQUENCES.md` | 记录 | 文档 |
| 9 | `docs/paper_rebuild/CONVERSATION_HANDOFF.md` | 记录 | 文档 |
| 10 | `AGENTS.md` | 记录（:896, :1398） | 文档 |

补充：`tests/paper_rebuild/test_hext04_heading_provider.py`（已跟踪，不含标记字符串）导入 heading_provider；
封存的 `src/legsa_gins/paper_rebuild/protocol_v3/providers.py:21` 也导入 `hext.heading_provider`
（v3 科学冻结 7d43b9a 内即如此）。本任务两者均未运行、未导入。
29 个预先存在的未跟踪草稿（§9.4 列表）一律只静态阅读，其中 8 个 hext 模块同样列入导入拦截表。

### 3A.2 检查前的入口源码阅读

对每个入口先静态阅读（AST 列出所有模块级非 def/class/import 语句，再读 `main()` 前几行），确认参数解析之前不打开数据文件：
- `run_horizontal_literature_phase1/1r/2/3/4/5.py`、`hext_native.py`、`hext02_native.py`、`run_lc02_ginav2021.py`、
  `validate_hartley_h3_h4.py`：模块级只设线程环境变量与 `sys.path`；`main()` 首句即 argparse。
- `run_hartley_h5_by2.py:53`、`run_hartley_h6.py:38`、`run_hartley_h6r.py:37` 在导入时调用私有加载器，
  以 `spec_from_file_location` 执行 `hartley_h0_h2/h5/h6/h6r.py` 的模块级代码（仅常量与导入）；
  `main()` 首句解析参数（h6r 经 `_main_impl()`，:97-98）。
- `audit_lc02_yin2023_y0_y3.py`、`audit_lc02_yin2023_y4a.py`、`audit_lc02_chang2021_r0_r4.py` 转调模块 `main()`，
  三者 `main()` 均先 `parse_args`（仅 `repository_root()` 做路径解析）。
- 对 `horizontal_literature/`、`hext/`（除 3A.1 所列）与 `protocol_v3/` 全部模块做 AST 扫描：模块级无
  open/read/load/subprocess/CDLL 调用；`ctypes.CDLL` 只在 `shared_raw_backend.py:630` 与 `ext01_clambda.py:236` 的方法内。
结论：没有入口需要改为静态检查；二进制与 MATLAB 本体按规则只做静态阅读。

### 3A.3 受控检查方式

每个目标单独一个 `python3` 进程，`PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1`，外加进程内审计钩子（内联代码，不写文件）：
- 拦截并记录：任何写模式 open；`/mnt/` 下任何 open；文件名含 trace/truth 的非源码文件；.csv/.txt/.nav/.gz/.fpl/.bag 等数据扩展名；
  scratch 目录；subprocess/os.system/exec/posix_spawn/fork；socket connect/bind。
- `meta_path` 查找器拦截 3A.1 中 4 个带标记模块与 8 个未跟踪 hext 模块（事故后加入，§9.1）。
- 允许 `ctypes.dlopen` 但记录。
检查时间：2026-09-23T12:47:22Z–12:47:26Z。

### 3A.4 结果（"help_ok / import_ok"只表示检查跑完，不表示方法可用或可复现）

| 目标 | 方式 | 结果 | 被拦截事件 | 非库文件打开 |
| --- | --- | --- | --- | --- |
| `scripts/paper_rebuild/run_horizontal_literature_phase1.py` | --help | help_ok | 无 | 仅 `$W/src`、`$W/scripts` 源码 |
| `…/run_horizontal_literature_phase1r.py` | --help | help_ok | 无 | 同上 |
| `…/run_horizontal_literature_phase2.py` | --help | help_ok | 无 | 同上 |
| `…/run_horizontal_literature_phase3.py` | --help | help_ok | 无 | 同上 |
| `…/run_horizontal_literature_phase4.py` | --help | help_ok | `lscpu` 子进程（numpy 导入期 CPU 探测，见 §9.3） | 同上 |
| `…/run_horizontal_literature_phase5.py` | --help | help_ok | 无 | 同上 |
| `…/hext_native.py` | --help | help_ok | 无 | 同上 |
| `…/hext02_native.py` | --help | help_ok | 无 | 同上 |
| `…/run_lc02_ginav2021.py` | --help | help_ok | 无 | 同上 |
| `…/audit_lc02_yin2023_y0_y3.py` | --help | help_ok | 无 | 同上 |
| `…/audit_lc02_yin2023_y4a.py` | --help | help_ok | 无 | 同上 |
| `…/audit_lc02_chang2021_r0_r4.py` | --help | help_ok | 无 | 同上 |
| `…/run_hartley_h5_by2.py` | --help | help_ok | 无 | 同上 |
| `…/audit_hartley_h0_h2_by2.py` | --help | help_ok | 无 | 同上 |
| `…/validate_hartley_h3_h4.py` | --help | help_ok | `lscpu`（同上） | 同上 |
| `…/run_hartley_h6.py` | --help | help_ok | `lscpu`（同上） | 同上 |
| `…/run_hartley_h6r.py` | --help | help_ok | `lscpu`（同上） | 同上 |
| `legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda` | 导入 | import_ok | 无 | 同上 |
| `…horizontal_literature.ext02_cwls` | 导入 | import_ok | 无 | 同上 |
| `…horizontal_literature.ext03_yang2024` | 导入 | import_ok | 无 | 同上 |
| `…horizontal_literature.ext04_wu2025` | 导入 | import_ok | `lscpu`（同上） | 同上 |
| `…horizontal_literature.ext05_pavlasek` | 导入 | import_ok | 无 | 同上 |
| `…horizontal_literature.ext05_provider` | 导入 | import_ok | 无 | 同上 |
| `…horizontal_literature.shared_raw_backend` | 导入 | import_ok | 无 | 同上 |
| `…horizontal_literature.hartley_h5` | 导入 | import_ok | 无 | 同上 |
| `…horizontal_literature.ginav2021.matlab` | 导入 | import_ok | 无 | 同上 |
| `legsa_gins.paper_rebuild.hext.ext05_sequence_runner` | 导入 | import_ok | 无 | 同上 |
| `…hext.external_evaluation` | 导入 | import_ok | 无 | 同上 |
| `…hext.readonly_closeout` | 导入 | import_ok | 无 | 同上 |

合计 29 项：help_ok 17、import_ok 12、static_only 0（入口层面）。没有任何检查打开 `/mnt/`、数据扩展名或 trace 类文件，
没有写模式 open，没有 `meta_path` 拦截（即上述入口都不经由带标记模块）。下列对象按规则只做静态阅读，
在 CSV 中记为 static_only：GINav MATLAB 本体（MATLAB 不在 WSL PATH）、Hartley C++ `hartley_h5_runner`、
RTKLIB `rnx2rtkp`、H-EXT-04 库与草稿、无实现的方法。

## 4. 评估口径

### 4.1 v3 评估点（定义与出处）

- 引擎：冻结评估器 `evaluate_nav_trace_kfgins_v2.py`（`aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`），以 strace 审计的子进程运行
  （`src/legsa_gins/paper_rebuild/protocol_v3/evaluation_process.py:22, 69-84`）；argv `--trace --nav --std --outdir --base_time <seq> --yaw_truth_mode enu`，
  外部方法不带 `--std`（`hext/external_evaluation.py:46-53`）。评估器本身不做点补偿（`configs/paper_rebuild/evaluator_contract.yaml:9`）。
- 评估点："v3"指评估点而非另一个评估器。IMU 点 NAV 先平移到 Fixposition POI：
  POI = p_IMU + C_b^n · [0.03, 0.03 − ½·b_med, −0.30] m（FRD），C_b^n 用每行 NAV 自身的 roll/pitch/yaw；只改 LLH 列 2–4，速度与姿态 token 不变，STD 不传递
  （`clean5_parity/evaluation.py:25-86`；`protocol_v3/runtime.py:230-234`）。b_med：BY2 0.356191491865984、BY2H 0.35418777593777223、BY2O 0.35013463864843675
  （`configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml:18, 45, 128`）。v2 点 = 原生 IMU 点、不变换（`runtime.py:235`）。
  参考点身份：`docs/paper_rebuild/CLEAN5_PARITY_PLAN.md:254, 270` 曾记完整参考点身份 UNAVAILABLE（TF 只证明 POI 与 VRTK 同点同向），
  随后 2026-09-09 的人工来源声明（`CLEAN5_PARITY_CONTRACT.yaml:164-167`）确立"VRTK 位于两天线正中、天线相位中心与单元参考点同高、POI→VRTK 零平移"，
  v3 据此变换；天线–IMU 高差与杠杆 z 的 CAD 核对仍待办（`AGENTS.md:491, 1462`）。
- 参考处理（由固定/观测评估器的仓库代码得出）：参考列 time/lat/lon/height/yaw/pitch/roll（`evaluator_identity.py:25-26`）；时间 = trace 时间 − base_time，
  yaw = wrap360(90 − yaw_ENU)，ENU yaw 先解缠再插值，残差 wrap-safe（`evaluator_identity.py:95-96`；`CLEAN5_PARITY_CONTRACT.yaml:152-153`）；误差历元即 NAV 历元；
  不做时间、符号、轴向搜索或对齐（`evaluator_contract.yaml:74-88`）。
- 窗口（闭区间）：BY2 [66.0, 340.0]、BY2H [413.0, 683.0]（base_time 1772784000.0）、BY2O [3186.0, 3563.0]（base_time 1772780400.0）
  （`H_EXT_CONTRACT_V1.yaml:11-14, 38-41, 121-124`）；窗口不作为 argv，由 NAV 支撑/裁剪强制，误差时刻越窗即硬停（`runtime.py:180, 225, 256-259`）。
- 指标：yaw/水平/高程 RMSE（另 3D、P95、roll/pitch）为全部匹配 NAV 历元等权的 sqrt(mean(e²))（`clean5_parity_p04/evaluation.py:18-28`）；
  输出频率不同的方法权重不同（`docs/paper_rebuild/hext/H_EXT_01_AUDIT_PROBE_ADAPTER.md:37`）。
- 准入门：评估子进程恰 1 次只读打开 trace、bag/fpl 0、写范围限于 outdir、捕获 trace 哈希（`evaluation_process.py:100-131`）；
  一致性门 ≤0.01 m / ≤0.01 deg（v3 内部行用 canonical_v2_wgs84_full_support，外部行用默认 local-ENU 检查）。

### 4.2 旧结果与 v3 的评估器版本/评估点差异（逐条）

| 旧结果 | 评估器 | 评估点/窗 | 与 v3 相比 |
| --- | --- | --- | --- |
| CLEAN4 LC01 C00（`$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION/FINAL_C00_NATIVE_FORMAL_RESULTS.csv` 第 3 行；`AGENTS.md:986-990`） | aa049248，经 `phase5_runner._run_verified_exact_evaluator`（:1144-1210），无捕获哈希、无一致性门 | IMU 点（v2 点），[66, 340] | **评估点不同**：H 0.1691391165921043 对 v3 0.0975479714305497；yaw 相同 2.9948274600591076；up 0.33917510432958425 对 0.05066431825806066 |
| CLEAN4 EXT05C C00（`EXT05A_C00_VALIDITY_REPORT.md:10`） | 同上 | IMU 点 | **评估点不同**：v2 0.17100769332496332 对 v3 0.0877508129138417；yaw 12.048641737808111 相同 |
| CLEAN4 GINav coverage-aware C00 | 只记 "exact evaluator"、10 次调用，未记 sha256，无一致性门、无封存 | GINav IMU 点无平移，[66, 340]，77/275 覆盖感知 | **评估点不同，评估器版本未能确认**；v3 同点重评估因一致性门失败为 UNAVAILABLE_EVALUATION_FAILED |
| CLEAN4 77 历元共同支撑诊断（`RESULT_IDENTITY_LEDGER.csv`） | 插值到 GINav 历元 | 非 v3 支撑 | 仅诊断，无 v3 对应 |
| CLEAN4 EXT01（phase1r）、EXT02（phase2）、EXT03（phase3）、EXT04（phase4）航向比较 | 各 runner 自带比较器，非冻结评估器；phase2/3 在父进程读 trace（`phase2_runner.py:3507`） | 天线基线 yaw，无位置；EXT01 无 66–340 s 窗 | **评估器与评估点均不同**；v3 行未评估 |
| CLEAN4 内部 F02/F03/A04/F04（`RESULT_IDENTITY_LEDGER.csv`，非外部方法） | aa049248 | IMU 点，v1 协议 | 评估点与解算协议均不同（仅备注） |
| `MAIN_TABLE_V2.csv` 全部外部完成行 | aa049248 | IMU 点（evaluator_nav = source_nav） | **评估点不同**；BY2 LC01/EXT05C 的 v2 行来自无门控的 CLEAN4 输出 |
| H-EXT H02 行（`MAIN_TABLE_V3.csv:40-47`，commit c9e5133） | aa049248，`hext/external_evaluation.py`，clean5 observer，默认 HARD_STOP 一致性策略（`hext/execution.py:354-356`） | v3 点，各序列窗 | **与 v3 相同**；差别只在一致性策略（local-ENU）、observer、STD 省略、输出频率与起点约定 |
| H-EXT H03 行（`MAIN_TABLE_V3.csv:48-53`，commit b6aaece） | 同上，D12_BOUNDED_UNAVAILABLE 策略（`hext/continuation.py:407-411`） | v3 点 | **与 v3 相同**（同上差别） |
| P07 BY2 LIT 行（`MAIN_TABLE_V3.csv:17-18`） | aa049248，`clean5_parity/evaluation._external_evaluate`（窗硬编码 [66, 340]，:147） | v3 点（`clean5_degradation/evaluation.py:166`） | **与 v3 相同** |
| HORIZONTAL18_V2 D01/D02/M01、RTKLIB 动基线诊断 | 无评估器 | — | 未评估 |

### 4.3 各输出类型的指标与评估器子进程

| 输出类型 | 方法（CSV 行） | 指标 | 现有可复用 | 需新写 |
| --- | --- | --- | --- | --- |
| imu_point_nav | LC01、LC01-S、EXT05C、EXT05C-S、LC02_GINAV；按设计 EXT06；草案 LC01-M/LC01-S-M/LC01-2D；若实现 EXT05B、Yin 等 | 冻结评估器 aa049248 在 v3 点的 yaw/水平/高程 RMSE（另 3D、yaw P95、roll/pitch、匹配数与覆盖率），并行 v2；各序列闭区间窗；注明输出频率 | `hext/external_evaluation.py`（evaluate / prepare_evaluator_nav / _evaluate_process / metrics，:69-260）；`clean5_parity/evaluation.py` transform_nav / write_transformed_nav；`clean5_parity_p04/evaluation.py:18-28`；`hext/t5a_runtime.bounded_lla_native`（:107-143）；`hext/sequence_paths.load_sequence_paths`；NAV 适配器先例 `phase5_runner._materialize_exact_evaluator_nav`（:1037-1098）、`hext/ext05_sequence_runner.materialize_exact_evaluator_nav`（:318-345）、`clean5_degradation/evaluation.ginav_nav`（:109-114） | 每个新方法的原生输出→11 列 NAV（`index time lat lon h vn ve vd roll pitch yaw`）适配器与转换合约（须证明是 IMU 点，否则走天线点路线）；运行槽与登记接线；无新指标数学 |
| heading_only | EXT01–EXT04、D01；若登记则 RTKLIB 动基线 | 固定率/可用率 = 有效航向历元 / 窗内 GNSS 历元；有效历元航向 RMSE；保持上一有效值的全窗航向 RMSE（首个有效值前单列不可用）；最大误差（两序列各一）；可加偏置、P95/P99、段数、最大缺口 | 统计：`phase2_runner.py` _wrapsafe_error_metrics（:1491 起）、_continuity_metrics（:1461 起）、_circular_statistics_deg（:1442 起）；参考 yaw 公式模板 `phase2_runner._trace_reference`（:3514-3576）；审计模式 `external_evaluation._evaluate_process`、`clean5_sequence/io_audit`、`evaluator_capture.install`；`hext/heading_provider.py` baseline_heading（:162-167）、angular_difference_statistics（:212-223）、time_to_itow_ms（:64-76）、extract_epoch_set（:103-125）仅作参考（NOT_AUTHORIZED_FOR_EXECUTION） | 航向评估子进程（trace 只开 1 次并核哈希、各序列 base_time/窗、同一 yaw 语义、GNSS 历元分母取方法原生历元表、保持上一有效值）；BY2 以外序列的窗内 GNSS 历元数需新推导（记录只有 BY2 的 1370） |
| relative_pose | Hartley；若 EXT06 只能输出相对轨迹 | 评估窗起始 10 s 对齐一次（yaw + 平移）；每 100 m 位置漂移、每分钟航向漂移、对齐后全窗 RMSE；标注无绝对锚定 | `hartley_h7c.py` relative_pose_metrics（:325-339）、fixed_primary_yaw_translation_gauge（:351-363）、apply_fixed_gauge_to_pose（:366-373）；`hartley_h7.py` SO(3) 工具（:128-171）；`H7_EVALUATION_CONTRACT.yaml:99-117`（只许一次主对齐，禁止全轨迹 Umeyama 与 roll/pitch 对齐）；`offline_eval_aggregate._axis_stats/_norm_stats` | 10 s 窗最小二乘对齐（现有代码只用单历元）；漂移函数；只回传指标的相对位姿子进程；Hartley 点（Go2 body-IMU 原点）与 POI 的关系须人工决定（H7 合约 :79-89 UNRESOLVED/ABSENT），H7C 血缘阻断仍在 |
| 解算失败（任一输出类型） | EXT05C-S BY2H FILE_START（已发生）；任何新运行 | 失败率（带分母，有限与含失败分母分开）；失败时段（D8 界：位移 >10000 m、速度 >50 m/s、高差 >1000 m、非有限或无效 LLA，首次越界至窗尾；间歇输出按缺口与段数）；失败前截断 NAV 的 v3 指标（标 PRE_FAILURE，覆盖 = 失败前时长/窗长，不并入主分布） | `hext/t5a_runtime.bounded_lla_native`；H-EXT bounded_output_gate（`H_EXT_CONTRACT_V1.yaml:512-525`）；`hext/t5bc_runtime.classify_heading_failure`（:455 起）；`protocol_v3/runtime.evaluate_native` NOT_RUN 载荷（:215-217）；`hext/aggregate.unavailable_segments`（:208 起）；类别见 `docs/paper_rebuild/v3/FC01_UNIFIED_FAILURE.md` | 失败前截断包装（写截断 NAV、重做 transform_nav、调现有评估子进程）；全部坏区间提取；跨方法失败率表；航向类失败时段 |
| antenna_point_nav | 本次盘点无此类方法 | 同 imu_point_nav，但须先用方法自身姿态把天线点移到 POI（GNSS1 点需偏移 [0, −½b_med, 0]）；无自身姿态则不得借用参考姿态，记 UNAVAILABLE_NO_OWN_ATTITUDE_FOR_POINT_TRANSFORM | `clean5_parity/evaluation.py` body_to_ned / transform_nav | transform_nav 硬编码 IMU 杠杆（:42），需带杠杆参数的变体与记录天线身份、杠杆来源、b_med 的清单 |

H-EXT-04 库（静态阅读）：`hext/matched.py`（sha256 `5f194fa6f9f0c01271721370f48fb44504b913cbb8b1a89d7395859e4d25463b`）是解算侧更新调度与 N/E 投影，不用于指标；
`hext/heading_provider.py`（sha256 `c582ce610ca134bc6120ee8e18644b6d030e343371e747849920fcdb41fcbea7`，最后提交 f7bf019）中的基线→航向、角差统计、历元身份可作航向评估参考，
但其 `clone_runtime_config` 走 YAML 往返，与后来"只做行文本替换"的规则冲突；二者均须登记授权后才能执行。
分段评估器不再启动冻结评估器，而是重切已封存并核过哈希的 error_series（`hext/aggregate.segment_rows`、`hext/readonly_closeout.run_closeout`、
`hext/t5a_reporting.derive_segments`、`protocol_v3/reporting.by2o_segments`；BY2O 主/次遮挡窗 [3369.94, 3411.95] 与 [3495.94, 3508.94]）。

## 5. A1/A2 工况清单

### 5.1 v3 注入规格文件（HX-03 据此生成映射）

v3 没有把"60 型 × 9 种子参数 + A1/A2 时间窗与种子"写在同一个文件里；v3 实际读取的是下列组合
（`src/legsa_gins/paper_rebuild/protocol_v3/registry.py:115-125` 载入工况清单与附加族合约，`providers.py:255-281` 读取逐例实现值）：

| 角色 | 路径 | sha256 |
| --- | --- | --- |
| **主：D01–D60 工况身份与参数**（C00 + 60 型 × 9 种子，541 行；参数 JSON、种子值、锚点、时长、受影响源） | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/02_MATRIX_SPEC_LOCK/CANONICAL541_CASE_MANIFEST.csv`（同目录 `CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv` 字节相同） | `ac58b992a56f3ab05c585973fa6ceef1493d0d5cd6a9f0a9e18dae8edd998cb2` |
| **主：A1/A2（D61/D62）族、锚点与 45 个 case_rows** | `$W/configs/paper_rebuild/clean6/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml`（families :29-53，case_rows :436-976；阶段副本字节相同） | `fd11e416a3bd1a67c992a3606de0bb988035cae5c80647efa2091d00614546ec` |
| A1/A2 工况登记表 | `$STAGES/CLEAN6_ADDENDUM_FAMILIES_A1_A2/00_PREREGISTRATION/CASE_REGISTRY.csv`（45 行，与合约 case_rows 一致） | `eb03f2bb5fd16d1b43475a1dff787d48ebb4132bd16b53b9efeae47d7ea719cb` |
| **逐例实现值**（区间、掩码、方向、位移、航向增量、延迟；585 = 540 核心 + 45 附加） | `$W/configs/paper_rebuild/v3/V3_PROVIDER_SOURCE_INDEX.json` → 各 `CLEAN6_SENSOR_MODEL_V21/02_CASE_PROVIDERS/<case>/PROVIDER_BUNDLE.json` | `130f93315d504bd7daddefc7eeabdbbeb10b763011531ade2766a0448a689a0e` |
| v3 航向故障映射 | `$W/configs/paper_rebuild/v3/PROTOCOL_V3_CONTRACT.yaml`（heading_fault_mapping :74-84） | `ec24079cba346f88eb047fb5d5ad48467b8060f4b8e3c7c31c48de9bac6dff31` |
| v3 航向时间语义 | `$W/docs/paper_rebuild/v3/PROTOCOL_V3_PREREG.md` | `060daf89fbf6b2e36af9286d98fcd47e35f80271faed3ecb2f2b359976f10f59` |
| 航向故障窗口账 | `$W/docs/paper_rebuild/v3/HEADING_FAULT_WINDOWS.md` | `53b34574069fee5166deedce04ac27a85b913575b36ad500af649c78db64f1fb` |
| 冻结注入库 | `$W/src/legsa_gins/paper_rebuild/canonical541/provider_generator.py`（apply_degradation :409-671） | `3328272fc994deef38600d4236afaed64cb100ea6810426a5f089f6eeb49f3a4` |
| 锚点/区间 | `canonical541/seed_anchor.py`；`configs/paper_rebuild/canonical_by2_seed_anchor_policy.yaml` | `9becbb78…`（全值 `9becbb782e5c754a06d9bd59c8dbda69b60a041c8b0aec52fd9957ed34c4ebcc`）；`aac6cc1600753baeeb01f120368e3075f6ca30aafc44c7063e4ad74977f14d3b` |
| 矩阵配置（窗 66.0–340.0、PCG64、主覆盖项） | `$W/configs/paper_rebuild/canonical_by2_degradation_541.yaml` | `92438ed46357baa459a956ce9e6e0c4160cd8eb338861007387e60b5342751dd` |
| 60 型登记 | `…/02_MATRIX_SPEC_LOCK/CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv` | `b507c997bbb41a973d0926ddc362e5b725cb051a31335974df6c6906c7edac68` |
| 型列表（仍被冻结库载入） | `$W/configs/paper_rebuild/degradation_60types_9seeds.yaml` | `9d22768be55b8b88e126f1101e5619ac0afe97cdedc3af28c1458fa9ef83b76f` |

说明：`degradation_60types_9seeds.yaml` 的型列表仍被冻结库载入（`canonical541/matrix_spec.py:226-227`；`provider_generator.py:26, :416`），
并在 v2 核心合约（`CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml` frozen_injection_library :32-40）与附加族合约（:138-139）中固定；
被取代的只是其种子/锚点块（:57-66，例如 seed_01 锚点 88.0，对应清单与附加族合约中的 107.20639），量级由处理函数硬编码。
**建议 HX-03 的生成来源**：工况身份与参数取 `CANONICAL541_CASE_MANIFEST.csv` 与附加族合约；逐例实现值取
`V3_PROVIDER_SOURCE_INDEX.json` 固定的 v2.1 bundle（与 v3 做法一致）；不要单独使用 `degradation_60types_9seeds.yaml`。

### 5.2 A1（D61）与 A2（D62）全部 45 个工况

共同设定：评估窗 [66.0, 340.0] s；切断窗为半开区间 [start, end)；种子值 = 260306001 + seed_index；
A1 与 A2 对同一种子、同一时长使用相同的切断窗（只差 dual_yaw）。
A1 切断 gnss_position、receiver_velocity、raw_doppler、dual_yaw；A2 切断前三者、保留 dual_yaw。
v3 中 A1 把窗口内 5 Hz 航向置 yaw_valid=0，A2 保留 R5 航向（`PROTOCOL_V3_PREREG.md:103-104`）。
注意：v2.1 规定 A1 航向缺口 >1.2 s 会使 Go2 HV 先验失效，v3 沿用这些 HV 文件
（`configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml:289-291, :716-717`），所以 A1 实际上也部分切断 HV
（例：hv_valid_count 基线 60867，D61_10s_seed_00 为 58834）。计数：A1 27 + A2 18 = 45，与预期一致
（合约 :42、:53；CASE_REGISTRY.csv 45 行；`$V3/07_AGGREGATE/ADDENDUM_TABLE_V3.csv` 495 行 / 45 个 case_id）。

| # | 工况 ID | 族 | 切断窗（半开）/ 锚点 / 时长 | 被切断的通道 | 种子 | 出处 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | D61_10s_seed_00 | D61 / A1 | [201.2, 211.2) s half-open; anchor 206.2 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_00 (seed_value 260306001) | configs/paper_rebuild/clean6/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:437-448; CLEAN6_ADDENDUM_FAMILIES_A1_A2/00_PREREGISTRATION/CASE_REGISTRY.csv row 2 |
| 2 | D61_10s_seed_01 | D61 / A1 | [102.20639, 112.20639) s half-open; anchor 107.20639 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_01 (seed_value 260306002) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:449-460; CASE_REGISTRY.csv row 3 |
| 3 | D61_10s_seed_02 | D61 / A1 | [184.207044, 194.207044) s half-open; anchor 189.207044 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_02 (seed_value 260306003) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:461-472; CASE_REGISTRY.csv row 4 |
| 4 | D61_10s_seed_03 | D61 / A1 | [222.201927, 232.201927) s half-open; anchor 227.201927 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_03 (seed_value 260306004) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:473-484; CASE_REGISTRY.csv row 5 |
| 5 | D61_10s_seed_04 | D61 / A1 | [143.204964, 153.204964) s half-open; anchor 148.204964 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_04 (seed_value 260306005) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:485-496; CASE_REGISTRY.csv row 6 |
| 6 | D61_10s_seed_05 | D61 / A1 | [221.215803, 231.215803) s half-open; anchor 226.215803 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_05 (seed_value 260306006) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:497-508; CASE_REGISTRY.csv row 7 |
| 7 | D61_10s_seed_06 | D61 / A1 | [253.20826699999998, 263.208267) s half-open; anchor 258.208267 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_06 (seed_value 260306007) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:509-520; CASE_REGISTRY.csv row 8 |
| 8 | D61_10s_seed_07 | D61 / A1 | [242.210403, 252.210403) s half-open; anchor 247.210403 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_07 (seed_value 260306008) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:521-532; CASE_REGISTRY.csv row 9 |
| 9 | D61_10s_seed_08 | D61 / A1 | [294.203403, 304.203403) s half-open; anchor 299.203403 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_08 (seed_value 260306009) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:533-544; CASE_REGISTRY.csv row 10 |
| 10 | D61_20s_seed_00 | D61 / A1 | [196.2, 216.2) s half-open; anchor 206.2 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_00 (seed_value 260306001) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:545-556; CASE_REGISTRY.csv row 11 |
| 11 | D61_20s_seed_01 | D61 / A1 | [97.20639, 117.20639) s half-open; anchor 107.20639 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_01 (seed_value 260306002) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:557-568; CASE_REGISTRY.csv row 12 |
| 12 | D61_20s_seed_02 | D61 / A1 | [179.207044, 199.207044) s half-open; anchor 189.207044 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_02 (seed_value 260306003) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:569-580; CASE_REGISTRY.csv row 13 |
| 13 | D61_20s_seed_03 | D61 / A1 | [217.201927, 237.201927) s half-open; anchor 227.201927 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_03 (seed_value 260306004) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:581-592; CASE_REGISTRY.csv row 14 |
| 14 | D61_20s_seed_04 | D61 / A1 | [138.204964, 158.204964) s half-open; anchor 148.204964 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_04 (seed_value 260306005) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:593-604; CASE_REGISTRY.csv row 15 |
| 15 | D61_20s_seed_05 | D61 / A1 | [216.215803, 236.215803) s half-open; anchor 226.215803 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_05 (seed_value 260306006) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:605-616; CASE_REGISTRY.csv row 16 |
| 16 | D61_20s_seed_06 | D61 / A1 | [248.20826699999998, 268.208267) s half-open; anchor 258.208267 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_06 (seed_value 260306007) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:617-628; CASE_REGISTRY.csv row 17 |
| 17 | D61_20s_seed_07 | D61 / A1 | [237.210403, 257.21040300000004) s half-open; anchor 247.210403 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_07 (seed_value 260306008) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:629-640; CASE_REGISTRY.csv row 18 |
| 18 | D61_20s_seed_08 | D61 / A1 | [289.203403, 309.203403) s half-open; anchor 299.203403 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_08 (seed_value 260306009) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:641-652; CASE_REGISTRY.csv row 19 |
| 19 | D61_30s_seed_00 | D61 / A1 | [191.2, 221.2) s half-open; anchor 206.2 s, duration 30 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_00 (seed_value 260306001) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:653-664; CASE_REGISTRY.csv row 20 |
| 20 | D61_30s_seed_01 | D61 / A1 | [92.20639, 122.20639) s half-open; anchor 107.20639 s, duration 30 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_01 (seed_value 260306002) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:665-676; CASE_REGISTRY.csv row 21 |
| 21 | D61_30s_seed_02 | D61 / A1 | [174.207044, 204.207044) s half-open; anchor 189.207044 s, duration 30 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_02 (seed_value 260306003) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:677-688; CASE_REGISTRY.csv row 22 |
| 22 | D61_30s_seed_03 | D61 / A1 | [212.201927, 242.201927) s half-open; anchor 227.201927 s, duration 30 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_03 (seed_value 260306004) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:689-700; CASE_REGISTRY.csv row 23 |
| 23 | D61_30s_seed_04 | D61 / A1 | [133.204964, 163.204964) s half-open; anchor 148.204964 s, duration 30 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_04 (seed_value 260306005) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:701-712; CASE_REGISTRY.csv row 24 |
| 24 | D61_30s_seed_05 | D61 / A1 | [211.215803, 241.215803) s half-open; anchor 226.215803 s, duration 30 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_05 (seed_value 260306006) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:713-724; CASE_REGISTRY.csv row 25 |
| 25 | D61_30s_seed_06 | D61 / A1 | [243.20826699999998, 273.208267) s half-open; anchor 258.208267 s, duration 30 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_06 (seed_value 260306007) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:725-736; CASE_REGISTRY.csv row 26 |
| 26 | D61_30s_seed_07 | D61 / A1 | [232.210403, 262.21040300000004) s half-open; anchor 247.210403 s, duration 30 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_07 (seed_value 260306008) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:737-748; CASE_REGISTRY.csv row 27 |
| 27 | D61_30s_seed_08 | D61 / A1 | [284.203403, 314.203403) s half-open; anchor 299.203403 s, duration 30 s | gnss_position, receiver_velocity, raw_doppler, dual_yaw (all GNSS off) | seed_08 (seed_value 260306009) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:749-760; CASE_REGISTRY.csv row 28 |
| 28 | D62_10s_seed_00 | D62 / A2 | [201.2, 211.2) s half-open; anchor 206.2 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_00 (seed_value 260306001) | configs/paper_rebuild/clean6/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:761-772; CLEAN6_ADDENDUM_FAMILIES_A1_A2/00_PREREGISTRATION/CASE_REGISTRY.csv row 29 |
| 29 | D62_10s_seed_01 | D62 / A2 | [102.20639, 112.20639) s half-open; anchor 107.20639 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_01 (seed_value 260306002) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:773-784; CASE_REGISTRY.csv row 30 |
| 30 | D62_10s_seed_02 | D62 / A2 | [184.207044, 194.207044) s half-open; anchor 189.207044 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_02 (seed_value 260306003) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:785-796; CASE_REGISTRY.csv row 31 |
| 31 | D62_10s_seed_03 | D62 / A2 | [222.201927, 232.201927) s half-open; anchor 227.201927 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_03 (seed_value 260306004) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:797-808; CASE_REGISTRY.csv row 32 |
| 32 | D62_10s_seed_04 | D62 / A2 | [143.204964, 153.204964) s half-open; anchor 148.204964 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_04 (seed_value 260306005) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:809-820; CASE_REGISTRY.csv row 33 |
| 33 | D62_10s_seed_05 | D62 / A2 | [221.215803, 231.215803) s half-open; anchor 226.215803 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_05 (seed_value 260306006) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:821-832; CASE_REGISTRY.csv row 34 |
| 34 | D62_10s_seed_06 | D62 / A2 | [253.20826699999998, 263.208267) s half-open; anchor 258.208267 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_06 (seed_value 260306007) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:833-844; CASE_REGISTRY.csv row 35 |
| 35 | D62_10s_seed_07 | D62 / A2 | [242.210403, 252.210403) s half-open; anchor 247.210403 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_07 (seed_value 260306008) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:845-856; CASE_REGISTRY.csv row 36 |
| 36 | D62_10s_seed_08 | D62 / A2 | [294.203403, 304.203403) s half-open; anchor 299.203403 s, duration 10 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_08 (seed_value 260306009) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:857-868; CASE_REGISTRY.csv row 37 |
| 37 | D62_20s_seed_00 | D62 / A2 | [196.2, 216.2) s half-open; anchor 206.2 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_00 (seed_value 260306001) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:869-880; CASE_REGISTRY.csv row 38 |
| 38 | D62_20s_seed_01 | D62 / A2 | [97.20639, 117.20639) s half-open; anchor 107.20639 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_01 (seed_value 260306002) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:881-892; CASE_REGISTRY.csv row 39 |
| 39 | D62_20s_seed_02 | D62 / A2 | [179.207044, 199.207044) s half-open; anchor 189.207044 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_02 (seed_value 260306003) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:893-904; CASE_REGISTRY.csv row 40 |
| 40 | D62_20s_seed_03 | D62 / A2 | [217.201927, 237.201927) s half-open; anchor 227.201927 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_03 (seed_value 260306004) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:905-916; CASE_REGISTRY.csv row 41 |
| 41 | D62_20s_seed_04 | D62 / A2 | [138.204964, 158.204964) s half-open; anchor 148.204964 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_04 (seed_value 260306005) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:917-928; CASE_REGISTRY.csv row 42 |
| 42 | D62_20s_seed_05 | D62 / A2 | [216.215803, 236.215803) s half-open; anchor 226.215803 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_05 (seed_value 260306006) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:929-940; CASE_REGISTRY.csv row 43 |
| 43 | D62_20s_seed_06 | D62 / A2 | [248.20826699999998, 268.208267) s half-open; anchor 258.208267 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_06 (seed_value 260306007) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:941-952; CASE_REGISTRY.csv row 44 |
| 44 | D62_20s_seed_07 | D62 / A2 | [237.210403, 257.21040300000004) s half-open; anchor 247.210403 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_07 (seed_value 260306008) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:953-964; CASE_REGISTRY.csv row 45 |
| 45 | D62_20s_seed_08 | D62 / A2 | [289.203403, 309.203403) s half-open; anchor 299.203403 s, duration 20 s | gnss_position, receiver_velocity, raw_doppler (dual_yaw retained) | seed_08 (seed_value 260306009) | ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml:965-976; CASE_REGISTRY.csv row 46 |

## 6. 18 型候选与注入映射

### 6.1 Classic-18 定义文件

- **没有正式的 Corrected Classic-18 工况定义文件。** `AGENTS.md:1083-1095` 只规定"若需要"时的方法集（LC01、F02、F03、A04、F04），
  且默认不需要、需人工授权；`$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION/CORRECTED_CLASSIC18_NECESSITY_DECISION.md`
  （`26b240a79f92e034b0bef491a0f6c0933802c911bd63973adb3e896848668daa`）:3、:5、:9 同样只有方法集，从未启动。
- 遗留 `$W/configs/paper_rebuild/classic_18cases.yaml`（`4bc10f06ff29fca7401b4485ea44e9d2f73b576388ea2dca1b5df219c5d72912`；
  source_kind legacy_spec_source，:16 execution_authorized_in_CLEAN0 false，:17 future_clean_use_requires_human_approval true）：
  18 例全部作用于双天线基线/DA provider，不作用于绝对位置；与 D 型只有 C00、C02→D09、C03→D10、C11–C13→D34 近似对应。
- 已停用的 `$CLEAN4/07_HORIZONTAL18_V2_*/HORIZONTAL18_V2_CASE_SPEC.csv`（`86708de414536730aeeb4178e74b2dc9d034d705eaf4d4c11fdfee9ccfc1f465`）：
  HC00–HC17 为接收机级算子（接收机 2 中断、双接收机中断、R1/R2 缩放、基线旋转尖峰等），已判定不可用，只可作 LC01 形算子的先例。

因此按任务要求从 541 故障类型清单（D01–D60）挑选。

### 6.2 候选清单（全部取 seed_00，均在 61 例退化子集内；待确认）

61 例子集 = C00 + D01_seed_00…D60_seed_00（`configs/paper_rebuild/clean5/CLEAN5_DEGRADATION_SUBSET_CONTRACT.yaml` :10-12、:24-85，
sha256 `9af4216d1c2e58011e712e60bfcb82ba58ea587034daf14a34c9985cf6b06cd6`；镜像于 `configs/paper_rebuild/hext/T5BC_CONTRACT_V1.yaml` :77-138）。
各型的其他种子（seed_01–08）都不在子集内。

| # | 型 | 工况 ID | 族（本任务分族） | 扰动量（含单位） | 作用输入通道 | 在 61 例子集 | 同族备选量级 | 出处 |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | D14 | D14_seed_00 | 位置噪声；库族 position noise (library family position_value; position_noise_medium) | Gaussian N and E sigma 1.5 m, Up sigma 2.5 m on all 1510 position rows (full sequence, including outside [66,340] s) | gnss_position (GNSS18 lat/lon/height = GNSS1 UBX-NAV-HPPOSECEF 5 Hz) | 是 | D13 h 0.5 m / v 1.0 m; D15 h 3.0 m / v 5.0 m; D27 h 3.0 m / v 5.0 m noise + position std x0.25 | CANONICAL541_CASE_MANIFEST.csv row 120; provider_generator.py:456-458; CLEAN6_SENSOR_MODEL_V21/02_CASE_PROVIDERS/D14_seed_00/PROVIDER_BUNDLE.json (affected_epoch_count 1510) |
| 2 | D21 | D21_seed_00 | 位置噪声（尖峰）；库族 position noise / outliers (position_value; position_spike_medium) | spikes on a random 5 % of valid position epochs (probability 0.05; 76 epochs for seed_00), horizontal 4.0 m in seeded direction, vertical ±2.0 m | gnss_position | 是 | D20 p 0.02, h 2.0 m / v 1.0 m (30 epochs seed_00); D22 one burst of 3-5 epochs, h 8.0 m / v 4.0 m (seed_00 burst [348.205852, 352.205852] s, outside the [66,340] s window)；D22_seed_00 实现为 20 个历元、4 s 区间，落在评估窗外 | CANONICAL541_CASE_MANIFEST.csv row 183; provider_generator.py:482-494; bundles D21_seed_00, D20_seed_00, D22_seed_00 |
| 3 | D16 | D16_seed_00 | 位置偏差（静态）；库族 position bias (position_value; position_static_bias_1p5m) | static bias horizontal 1.5 m (seed_00 direction_rad 5.788180028253129), vertical 0.5 m (seed_00 sign +1.0), all 1510 rows | gnss_position | 是 | D17 static h 3.0 m / v 1.0 m | CANONICAL541_CASE_MANIFEST.csv row 138; provider_generator.py:459-463; bundle D16_seed_00 |
| 4 | D18 | D18_seed_00 | 位置偏差（慢漂移）；库族 position bias, time-varying (position_value; position_slow_drift_bias) | linear drift 0.0 -> 3.0 m horizontal (seeded direction) and 0.0 -> 1.0 m vertical (seeded sign), normalised over [66,340] s, held at end values outside | gnss_position | 是 | D19 sinusoidal multipath, horizontal amplitude 2.0 m, vertical 0.5 m, period 188.49555921538757 s (seed_00 phase_rad 5.84740275561746) | CANONICAL541_CASE_MANIFEST.csv rows 156/165; provider_generator.py:464-481; bundles D18_seed_00, D19_seed_00 |
| 5 | D03 | D03_seed_00 | 位置中断；库族 position outage (gnss_outage; GNSS_position_outage_10s) | 10 s outage; seed_00 window [201.2, 211.2) s (50 of 1510 position epochs invalid) | gnss_position validity (GNSS18 position_valid) | 是 | D01 3 s (seed_00 [204.7, 207.7]); D02 5 s; D04 20 s; D07 three 3 s outages at anchor-6/0/+6 s (seed_00 [198.7,201.7], [204.7,207.7], [210.7,213.7]) | CANONICAL541_CASE_MANIFEST.csv row 21; provider_generator.py:425-435; seed_anchor.py:282-308; bundles D03/D01/D07_seed_00 |
| 6 | D04 | D04_seed_00 | 位置中断；库族 position outage (gnss_outage; GNSS_position_outage_20s) | 20 s outage; seed_00 window [196.2, 216.2) s (100 epochs) | gnss_position validity | 是 | D03 10 s; D58 10 s position outage + ±10 deg yaw spikes @ 0.10 inside the window + 20 s recovery | CANONICAL541_CASE_MANIFEST.csv row 30; bundle D04_seed_00 |
| 7 | D43 | D43_seed_00 | 速度噪声；库族 velocity noise (velocity_raw_doppler; receiver_velocity_noise_0p5) | Gaussian 3-axis noise sigma 0.5 m/s on all 1510 receiver-velocity rows | receiver_velocity (GNSS1 NAV-PVT velocity in GNSS18 vn/ve/vd) | 是 | D44 spikes p 0.02, 2.0 m/s 3-D (30 epochs seed_00); D45 noise sigma 0.5 m/s + velocity std x0.25 | CANONICAL541_CASE_MANIFEST.csv row 381; provider_generator.py:568-582; bundle D43_seed_00 |
| 8 | D42 | D42_seed_00 | 速度中断；库族 velocity outage (velocity_raw_doppler; receiver_velocity_outage_20s) | 20 s outage; seed_00 [196.2, 216.2) s (100 epochs) | receiver_velocity validity | 是 | D05 position+receiver velocity 10 s; D46 raw Doppler 20 s; D61/D62 addendum (position+receiver velocity+raw Doppler) | CANONICAL541_CASE_MANIFEST.csv row 372; provider_generator.py:566-567; bundle D42_seed_00 |
| 9 | D05 | D05_seed_00 | 速度中断（连同位置）；库族 velocity + position outage (gnss_outage; GNSS_position_velocity_outage_10s) | 10 s outage of gnss_position and receiver_velocity; seed_00 [201.2, 211.2) s (50 epochs each); heading not cut | gnss_position + receiver_velocity validity | 是 | D06 position+RV+yaw 20 s; D62_10s (adds raw Doppler) | CANONICAL541_CASE_MANIFEST.csv row 39; bundle D05_seed_00; CASE_DEFINITION_COMPARISON.csv D05 rows |
| 10 | D33 | D33_seed_00 | 航向噪声；库族 heading noise (dual_yaw; dual_yaw_noise_strong) | Gaussian yaw noise sigma 5.0 deg (wrap-safe) on the 301 valid 1 Hz heading rows (v2.1). In v3 the realized wrapped deltas are held over 1 s cells [t_i, t_i+1) of the 5 Hz raw heading, 56 <= t < 357 s, with no redraw | dual_yaw (GNSS18 col 14 yaw) | 是 | D32 sigma 1.0 deg; D38 sigma 10.0 deg + yaw std x0.25 | CANONICAL541_CASE_MANIFEST.csv row 291; provider_generator.py:511-516; PROTOCOL_V3_PREREG.md:78-83,89-90; providers.py:77-93 |
| 11 | D35 | D35_seed_00 | 航向噪声（尖峰）；库族 heading noise / spikes (dual_yaw; dual_yaw_spike_10pct) | signed ±10.0 deg spikes on a random 10 % of valid heading rows (30 rows for seed_00) | dual_yaw | 是 | D34 5 % (15 rows seed_00); D58 ±10 deg @ 0.10 only inside its 10 s position-outage window | CANONICAL541_CASE_MANIFEST.csv row 309; canonical_by2_degradation_541.yaml:64-65; provider_generator.py:517-521; bundles D35/D34_seed_00 |
| 12 | D41 | D41_seed_00 | 航向噪声（单天线噪声→基线）；库族 heading noise from one-antenna position noise (dual_yaw; gnss1_gnss2_asymmetric_noise) | antenna position noise N/E sigma 3.0 m, D sigma 2.0 m on one antenna (even seed_value -> GNSS1, odd -> GNSS2; seed_00 -> GNSS2) applied to the GNSS2-GNSS1 baseline, heading recomputed (+90 deg), 301 rows; the gnss_position column is unchanged | dual_yaw only (baseline-derived heading) | 是 | no type with the same operator; related D32 (1.0 deg), D33 (5.0 deg) | CANONICAL541_CASE_MANIFEST.csv row 363; provider_generator.py:558-565; bundle D41_seed_00 (affected_source GNSS2, position_valid_count 1510); PROTOCOL_V3_PREREG.md:98 |
| 13 | D31 | D31_seed_00 | 航向中断；库族 heading outage (dual_yaw; dual_yaw_outage_20s) | 20 s outage; seed_00 [196.2, 216.2) s (20 of 301 1 Hz rows in v2.1; all eligible 5 Hz rows in the window in v3) | dual_yaw validity (GNSS18 col 18) | 是 | D30 5 s (seed_00 [203.7, 208.7)); D39 three quality-dropout bursts (seed_00 [82.204517,84.204517), [182.204872,184.204872), [349.204539,352.204539)) | CANONICAL541_CASE_MANIFEST.csv row 273; HEADING_FAULT_WINDOWS.md:34,43,52; bundle D31_seed_00 |
| 14 | D06 | D06_seed_00 | 航向中断（全更新中断）；库族 all-update outage incl. heading (gnss_outage; GNSS_all_update_outage_20s) | 20 s outage of gnss_position, receiver_velocity, dual_yaw; seed_00 [196.2, 216.2) s (100/100/20 rows) | gnss_position + receiver_velocity + dual_yaw validity | 是 | D61_20s_seed_00 (adds raw Doppler); D31 heading only; D04 position only | CANONICAL541_CASE_MANIFEST.csv row 48; HEADING_FAULT_WINDOWS.md:7-9; bundle D06_seed_00 |
| 15 | D46 | D46_seed_00 | 多普勒（中断）；库族 Doppler outage (velocity_raw_doppler; raw_doppler_outage_20s) | 20 s outage; seed_00 [196.2, 216.2) s (100 rows) | raw_doppler (RAW_DOPPLER.csv factor provider) | 是 | D61 (A1) cuts raw Doppler together with all GNSS; D47-D50 value faults | CANONICAL541_CASE_MANIFEST.csv row 408; provider_generator.py:566-567; bundle D46_seed_00 |
| 16 | D47 | D47_seed_00 | 多普勒（噪声）；库族 Doppler noise (velocity_raw_doppler; raw_doppler_noise_0p5) | Gaussian 3-axis noise sigma 0.5 m/s on all 1248 raw Doppler rows | raw_doppler | 是 | D48 spikes p 0.02, 1.5 m/s, horizontal 2-D (25 rows seed_00); D49 noise sigma 0.5 m/s + std x0.25 | CANONICAL541_CASE_MANIFEST.csv row 417; provider_generator.py:568-582; bundle D47_seed_00 |
| 17 | D50 | D50_seed_00 | 多普勒（偏置/冲突）；库族 Doppler bias / conflict (velocity_raw_doppler; raw_receiver_velocity_conflict) | constant horizontal offset 1.0 m/s on all raw Doppler rows (seed_00 direction_rad 5.788180028253129); receiver velocity unchanged | raw_doppler | 是 | D59 the same 1.0 m/s conflict plus position noise h 3.0 m / v 5.0 m | CANONICAL541_CASE_MANIFEST.csv row 444; provider_generator.py:583-586,646-649; bundle D50_seed_00 |
| 18 | D57 | D57_seed_00 | 时间戳；库族 timestamp (multi_source_mixed; multi_source_latency_jitter) | per-source latency U[0.1, 0.3] s plus per-row jitter U[-j, j] with j ~ U[0.020, 0.050] s, stable sort. seed_00: gnss_position latency 0.10401432335291612 s, jitter max 0.025616545567535644 s; dual_yaw 0.2739565090052485 s / 0.047636523890068165 s；v3 中有效航向行数为 0（exact iTOW 键连接） | timestamps of gnss_position, receiver_velocity, dual_yaw, raw_doppler, go2_rp, go2_hv (IMU not shifted) | 是 | none (the only timing type) | CANONICAL541_CASE_MANIFEST.csv row 507; provider_generator.py:623-640; bundle D57_seed_00 (GNSS18 3321 rows, faulted_timing_union true) |

**两族无对应型（需确认）**：
- 航向偏差：D01–D60 没有航向偏差算子（D52 是 Go2 roll/pitch 偏差 2.0 deg，不是航向）。
- IMU：D01–D60 没有 IMU 故障型（540 个退化行的 unaffected_sources 均含 imu）。

因此 18 型覆盖 11 族中的 9 族。可选处理：(a) 接受 9 族 18 型；(b) 为两族新定义算子，但那会超出 541 清单，与 v3 结果不可直接对照，需新授权。
v3 特别说明：D57 在 v3 中因航向按 iTOW 精确键连接，有效航向行数为 0（`protocol_v3/providers.py:150-157, 180-181`；`PROTOCOL_V3_PREREG.md:99`），
对 LegSA 实际等于"全程航向丢失 + 其他源延迟/抖动"；v3 的 D08/D09/D10 把 5 Hz 航向分箱到 5/2/1 Hz（v2.1 时 1 Hz 航向不受影响）；
D22_seed_00 的突发为 20 个位置历元、4 s 区间 [348.205852, 352.205852]，落在评估窗外。

### 6.3 LC01 的输入映射（同一时间窗、同一种子、同一扰动量）

LC01 的输入（`ext05_pavlasek.py:294-417`、`ext05_provider.py:117-250`）：两台接收机 UBX-NAV-HPPOSECEF 位置 p1（GNSS1/右）与 p2（GNSS2/左）
及 pAcc（R = pAcc² I3），1510 个共同 iTOW、200 ms 节拍；Go2 body IMU 的陀螺/加计。不用接收机速度、原始多普勒、标量航向或其 std、
GNSS18 std 列、Go2 RP/HV 先验（`docs/paper_rebuild/CLEAN5_PARITY_PLAN.md:17-31, :57`；`ext05_provider.py:1-8`）。
一次更新需 valid1 与 valid2 同时有效，没有单接收机回退（`hext/ext05_sequence_runner.py:834-835`；`phase5_runner.py:502-503`）。
注入应在 provider/cache 建好之后修改 p1/p2/pacc/valid/time 数组（原始层修改会触发 200 ms 节拍与 RAWX+2 ms 守卫，并移动 NED 原点）；
现有代码没有注入钩子，缓存有哈希身份绑定，需新 provider/cache 层与新授权（H-EXT 合约 execution_authorized false、预算 0：`H_EXT_CONTRACT_V1.yaml:4, 306-311`）。

| 族 | 映射到 LC01 | LC01 不使用的通道 |
| --- | --- | --- |
| 位置中断（D01–D04、D07，及 D05/D06/D58/D61/D62 的位置部分） | 在冻结区间内置 valid1 = valid2 = False；LC01 同时失去基线（相对）信息，LegSA 在 D01–D04 期间仍有航向，这一差别在原生 LC01 中无法避免 | — |
| 位置噪声/偏差/尖峰/漂移（D13–D22，D27、D59、D60 的位置部分） | 取逐行 NED 位移（case GNSS18 − base GNSS18，按 iTOW；base `02_BASE_PROVIDERS/BY2/GNSS18.gnss` `b98b4897…`），**同时加到 p1 与 p2**（刚性平移），p2−p1 不变，与 LegSA 不动 dual_yaw 一致；只加到 p1 会引入虚假的基线/航向误差 | — |
| 位置 std（D23–D26、D28，D27/D60 的 std 部分） | p1、p2 的 pAcc 同乘系数（R 乘系数²）；基准 σ 不同（LegSA 缩放 PVT hAcc/vAcc）。D29 在两边都无有效路径，等同 C00 | — |
| 速度噪声/中断（D42–D45 及 D05/D06/D60/A1/A2 的速度部分） | 无映射 | 接收机速度 |
| 多普勒（D46–D50 及 D59/D60/A1/A2 的多普勒部分） | 无映射 | 原始多普勒 |
| 航向噪声/尖峰（D32–D35、D38 角度、D58、D60） | 按冻结的逐 1 s 单元实现增量，把 p2 绕 p1 水平旋转、保持基线长度（v3 提升的单元：`providers.py:77-93, 162-175`；`07E_UNIFIED_FAILURE/DUAL_YAW_INJECTION_MAPPING.csv`）。这是向量级转移，v3 对 LegSA 禁止（`PROTOCOL_V3_CONTRACT.yaml:107`），需单独授权 | 标量航向、yaw std |
| 航向中断/掩码（D30、D31、D39，D06/D61 航向部分，D11/D12 航向掩码） | 原生代码中无法不连带丢掉 p1（`ext05_sequence_runner.py:834`）；`hext/matched.py` 的 p1-only 调度（:149-156）标记 NOT_AUTHORIZED_FOR_EXECUTION（:6, :22） | — |
| D36、D37、D38 std 部分 | 无对应（缩放 R2 并不等价） | yaw std |
| D40 | 无有效路径，等同 C00 | — |
| D41（单天线噪声 → 航向） | LegSA 只扰动基线、gnss_position 不变；目标天线由种子值奇偶决定（偶 → GNSS1，奇 → GNSS2；`provider_generator.py:558-565`）。在 LC01 中若目标是 GNSS1 会同时移动绝对通道；实现向量只在 301 个 1 Hz 审计行上存在（`dual_yaw_AUDIT.csv`），需单元提升 | — |
| 采样（D08–D12） | D08 在 5 Hz 下幂等 → 等同 C00；D09/D10 对两台接收机施加冻结的 GNSS18 position_valid 保留掩码（seed_00 604/303）；D11/D12 施加冻结的 gnss_position 丢弃掩码（seed_00 1057/604 有效），航向掩码无法表示 | — |
| Go2（D51–D56） | 不使用，等同 C00 | Go2 RP/HV/接触元数据 |
| IMU | D01–D60 无 IMU 故障型 | — |
| 时间戳（D57） | 按实现的 gnss_position 偏移平移 p1/p2 的历元时间（seed_00 延迟 0.10401432335291612 s，抖动最大 0.025616545567535644 s），IMU 不平移；**注意** v3 下 LegSA 在 D57 有效航向为 0，若 LC01 只平移时间则保留了基线航向信息，暴露程度低于 LegSA，需说明或另行丢弃相对通道 | — |
| A1（D61） | 窗口内两台接收机均无效（全 GNSS 切断，LC01 纯 IMU 递推） | 速度、多普勒 |
| A2（D62） | 见 6.5；原生代码下与同种子同时长的 D61 输入相同（重复运行） | 速度、多普勒 |

### 6.4 EXT06（Luo 型单天线 InEKF + 腿里程计）的输入映射

EXT06 尚无实现，下列输入按"单天线 GNSS 位置 + Go2 body IMU + 腿里程计"推定：

| 族 | 映射到 EXT06 | EXT06 不使用的通道 |
| --- | --- | --- |
| 位置中断/数值/std/采样（D01–D04、D07、D09–D28 位置部分及 D05/D06/D27/D58/D59/D60/D61/D62 位置部分） | 把 LegSA 的 gnss_position 实现逐 iTOW 直接施加到单天线；若 EXT06 用 GNSS1 HPPOSECEF（与 EXT05C 相同），行即 LegSA 所用历元；无第二接收机，不存在刚性平移问题；std 故障缩放天线协方差（pAcc1 或 GNSS18 std 列）；D29 等同 C00 | — |
| 航向（D30–D41 及 D06/D58/D60/D61 航向部分） | EXT06 无航向输入，等同 C00，混合型退化为其位置（及速度）部分；D41 不动 gnss_position，等同 C00。**注意**：LegSA 的 Go2 HV 先验依赖 A1 航向（缺口 >1.2 s 失效，角度故障旋转 HV），"等同 C00"会让 EXT06 的腿里程计在这些工况下比 LegSA 的 HV 得到更多帮助，需在对比中说明 | 双天线航向 |
| 速度（D42–D45）与多普勒（D46–D50） | 按描述不使用，等同 C00；D05 退化为位置中断；同种子同时长的 A1 与 A2 对 EXT06 输入相同（都只丢位置） | 接收机速度、原始多普勒 |
| Go2（D51–D56） | D51/D52 作用于 EXT06 不用的 RP 先验，等同 C00；D53/D54 的最接近类比是对腿里程计速度施加同 σ/缩放/丢弃（LegSA 在航向旋转后的 NED 中作用，EXT06 若由 FK 推导速度，故障须定义在推导速度上）；D55/D56 在 LegSA 中无有效路径，但接触/足力是 EXT06 的有效输入，施加会造成 LegSA 未经历的故障，建议等同 C00 或仅作 EXT06 单独敏感性 | Go2 RP |
| 时间戳（D57） | GNSS 位置时间按 gnss_position 偏移平移；腿里程计时间按 go2_hv 偏移平移（seed_00 延迟 0.14251141574244855 s，抖动最大 0.031059968614732182 s）；IMU 不平移 | — |
| IMU、航向偏差 | D01–D60 无对应型 | — |

### 6.5 A2 对 LC01："切断绝对位置与速度、保留基线航向"能否单独实现

**不能**用现有 LC01 代码单独实现：
- `PavlasekIEKF.update` 的绝对接收机 1 块是无条件的：p1 是必需参数，新息总以 C^T(p1 − p̂1) 开头（`ext05_pavlasek.py:364-369`），
  雅可比第 0–2 行恒为 [skew(lever), 0, −I3]（`measurement_jacobian` :273-275），相对行只是追加（:276-277, 372-384），相对量测由 p2 − p1 构成（:378）。
- 循环在历元有效时调用 `filter_.update(arrays['p1'][index], R1, …)`（`phase5_runner.py:514`；`ext05_sequence_runner.py:221, 846`），
  把 p1 置无效会跳过整个更新，连基线一起（`phase5_runner.py:502-503`；`ext05_sequence_runner.py:834-835`）。
- "切断速度"无对象：LC01 没有速度量测，速度只是初值为零的递推状态（`phase5_runner.py:456`）。
- 唯一的可选钩子 `_h02_gnss_update` 的 `measurement_update` 参数（`ext05_sequence_runner.py:830-846`）在 `_run_h02_filter_sequence` 中未传入（:994-998）。
- H-EXT-04 库 `matched.update_relative_components`（NOT_AUTHORIZED_FOR_EXECUTION，`matched.py:22, 98-137`）保留绝对行，只把相对块切到 N/E；
  `MatchedEpochUpdate` 的非匹配路径是 p1-only 更新（:181-188），正好与 A2 相反。

替代方案：
- (i) 不需新代码：窗口内同时置 valid1 = valid2 = False（两台绝对位置同时切断）。此时 LC01 窗内没有任何 GNSS 更新、纯 IMU 递推，航向也被切断，
  这是全 GNSS 切断，不是 A2；对 LC01 而言 D62 与同种子同时长的 D61 输入相同。
- (ii) 基线保留变体（需新代码）：仅相对量测的更新，z_rel = C^T((p2 − p1) − C b)，H_rel = [skew(b), 0, 0]（即现有第 3–5 行，`ext05_pavlasek.py:277`），
  R_rel = C^T(R1 + R2)C（堆叠协方差的 block_22 边缘，:256），复用同一 Joseph/右修正步骤（:396-405），例如仿照 `matched.update_relative_components`
  以投影 P = [0 I3] 写新函数；另需：故障历元改调该更新的调度回调、把 `measurement_update` 传入 `_run_h02_filter_sequence`（:994-998）的循环改动或新 runner、
  标注故障窗口的 provider/cache 层、新合约与新授权。预期行为：b = [0, −0.350, 0] FRD 时 skew(b) 只对绕机体 x 与 z 的旋转（roll 与 yaw）有响应，
  对绕基线轴（pitch）无响应；相对行不含位置/速度信息，窗内位置速度纯 IMU 递推，航向仍被修正。

## 7. EXT06 盘点（Luo 型单天线 InEKF + 腿里程计，无 radar）

登记：`docs/paper_rebuild/CONVERSATION_HANDOFF.md:84`（"Luo et al., single-antenna InEKF + leg odometry, no radar; baseline comparison rows only | pending; no execution or admission claimed"）、:199；
`AGENTS.md:1419-1421`。**ID 冲突**：旧 `EXT06_YIN2023_RAEKF_LC` 是 LC02 Yin 2023 的兼容别名，`EXT06_HAO2018_TWO_ANTENNA_LC_EKF` 是已废弃身份
（`docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload/00_ACTIVE_METHOD_REGISTRY/ACTIVE_EXTERNAL_METHOD_BOUNDARY.md:8, :12`）；
Hartley 记录中的 `ready_for_ext06=false`（`LSE01_FINAL_CLAIM_BOUNDARY.md:27-28`）未说明指哪一个。HX-04 起建议只用 "EXT06 = Luo" 并在合约中写明。

### 7.1 仓库与 EXTERNAL 中可用的 InEKF 实现

| 实现 | 语言 | 状态定义 | 已有量测 | 测试 | 对 EXT06 的意义 |
| --- | --- | --- | --- | --- | --- |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/`（`include/hartley_inekf/backend.hpp`、`src/backend.cpp`、`tools/run_h5.cpp` 等） | C++17 + Eigen3；Python 包装 `hartley_h0_h2.py`、`hartley_h5.py`、`hartley_h6*.py`、`hartley_h7*.py` | SE_{2+K}(3)：R、v、p + 接触点字典（backend.hpp:125-130）+ 陀螺/加计偏置（:138-141）；修正左乘，即世界系右不变误差（backend.cpp:1197-1212；`HARTLEY_FRAME_CONTRACT.yaml:10`） | 仅接触正运动学（correctContactsImpl，backend.cpp:1131-1195，由 correctContacts :1117 调用；新息 p + R·foot_position_body − d，:1171-1173；H 在第 6 列为 −I、接触偏移处为 +I，:1166-1168）；**无 GNSS/绝对位置、无速度、无航向更新** | `hartley_inekf/tests/backend_tests.cpp`、`h5_backend_tests.cpp`（ctest）；Python `tests/paper_rebuild/test_hartley_h3_h4_backend.py`、`test_hartley_h5_contracts.py`、`test_hartley_h6_backend.py`、`test_hartley_h6r_backend.py`、`test_hartley_h0_h2_by2.py` 等；无位置/GNSS 更新测试 | 接触/腿部分可复用；Hartley IJRR 2020 Table 2 指出世界系观测器下 GPS 位置是左不变观测，加 GNSS 需改用左不变误差或状态相关（带杠杆）的位置雅可比；无地球自转 |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/ext05_pavlasek.py`（PavlasekIEKF） | Python（numpy、scipy expm） | 无偏置 SE_2(3)（C_nb、NED 速度、IMU 点 NED 位置），左不变误差，右侧修正（:1-7, 159-167, 402），9×9 协方差 | 单接收机绝对位置（带杠杆，:364-369，H = [skew(lever) 0 −I]）；可选第二接收机相对基线 | `tests/paper_rebuild/test_horizontal_ext05_pavlasek.py`（23 项）、`test_horizontal_phase5_c00.py`、`test_hext02_native.py`、`test_hext04_matched.py` | 最直接可复用的左不变单天线位置更新；缺偏置状态、接触/腿状态、地球自转 |
| `$EXTERNAL/hartley/invariant-ekf`（git HEAD ef16e8a） | C++（Eigen） | RobotState（R、v、p、接触/路标）+ Theta 偏置；右不变更新（src/InEKF.cpp:211） | 运动学（接触 FK）、路标、通用右不变观测 | 无单元测试（仅速度基准与示例） | 官方参考；无 GPS/左不变观测接口 |
| `$EXTERNAL/hartley/Contact-Aided-Invariant-EKF/matlab_example/example_code/RIEKF.m`（git HEAD 15f1ee7） | MATLAB | R、v、p、左右接触、路标、偏置 | 关节编码器正运动学 + 接触标志；路标 | 无 | 需要关节编码器，三序列均无（`BY2_FK_PROXY_CONTRACT.yaml:16`） |
| `src/legsa_gins/external_dual/method_pavlasek_iekf.py`、`external_dual_methods/method_pavlasek_iekf.py` | Python | 无（3/5 行目录桩） | 无 | 无 | 遗留目录项，无实现 |

### 7.2 腿里程计/接触数据的 provider 与三序列可得性

| provider | 提供 | BY2 / BY2H / BY2O |
| --- | --- | --- |
| `horizontal_literature/hartley_h0_h2.py`（`iter_hartley_input_projection`:592、`derive_force_contact_proposal`:1433、`force_hysteresis_contacts`:1486 等）；合约 `configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/BY2_FK_PROXY_CONTRACT.yaml`、`GO2_FOOT_ORDER_CONTRACT.yaml` | 时间戳、IMU、foot_force[4]、foot_position_body[4×3]（Go2 高层 FK 代理，机体 FLU）；力滞回接触标志（开 FR 34.2/FL 33.8/RR 30.6/RL 32.0，关 FR 24.8/FL 25.2/RR 23.4/RL 24.0，驻留 3 样本 = 0.012035608291625977 s）；FK 协方差下限 1e-8 m²；**无关节编码器**、无接触概率 | 仅 BY2 审计并使用（63277 条完整记录）；BY2H/BY2O 无足端/接触审计、阈值或 FK 协方差，阈值与协方差为 BY2 硬编码 |
| `src/legsa_gins/datasets/by2/go2_body_state_parser.py` | 完整 sportmodestate：IMU（四元数、陀螺、加计、rpy）、Go2 odom 位置/速度、foot_force、foot_position_body、foot_speed_body、mode、gait_type 等 | 解析器与序列无关；BY2H/BY2O 无运行记录 |
| `src/legsa_gins/go2_state/go2_body_state_parser.py` | 上述字段的标准化行（遗留 N7A 诊断模块） | 同上 |
| `horizontal_literature/ext05_provider.py:347-396`（build_imu_only_provider） | 仅 IMU（FLU→FRD，再 RzRyRx [−1,0,0] deg） | BY2 PHASE5 路线使用；H-EXT 的 `hext/ext05_sequence_runner.prepare_h02_cache`（:708-736）不调用它，而是导入 `_imu_only_messages` 等并重做同样的变换，且保留非正时间间隔交给 D1 分类器；三序列均经此得到 IMU |
| `src/legsa_gins/external_dual/go2_body_provider.py` | 仅 yaw_speed、mode、gait_type（遗留） | 无运行记录 |
| `src/legsa_gins/go2_prior/*`（接触状态、接触概率候选、足端运动学速度候选等） | 诊断用，从未作为解算先验激活（遗留） | 无 BY2H/BY2O 记录 |
| 冻结 v2.1/v3 GNSS 表中的 Go2 HV（`SENSOR_MODEL_V21_CONTRACT.yaml:282-283`） | Unitree sportmodestate 速度经 A1 航向旋转；其计算方式在仓库中无记录（解析器记帧为 go2_odom_or_body_evidence_missing，`datasets/by2/go2_body_state_parser.py:262`），项目边界不允许把 LegSA 的 Go2 先验称作完整腿里程计（`docs/codex_context/ALGORITHM_IDENTITY_AND_CLAIM_BOUNDARY.md:22`） | 三序列均重生成；EXT06 的腿里程计与 F04 的 HV 输入信息重叠，对比时需说明信息结构差异（`AGENTS.md:900`） |

Go2 原始文件（只 `ls`，未打开；哈希取自记录）：BY2 `by2.txt` 92,352,512 B，sha256 `95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278`
（`docs/paper_rebuild/CLEAN5_VERTICAL_DIAGNOSIS.md:393`；`hartley_h0_h2.py:53-54`）；BY2H `by3.txt` 92,274,688 B，`b2e80763c613a5a0d6739aea90ea3ed4f8c9170cf5f2f6b73e5a000a666f0c49`
（`configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml:105`）；BY2O `by1.txt` 140,873,728 B，`0e5c62e0a5af0b6c32c51b535cc90701677276fc73c5623b72abda66cc148f2e`
（`CLEAN5_BY2O_SEQUENCE_CONTRACT.yaml:105`）。IMU 样本数 BY2 63278、BY2H 63222、BY2O 95860，BY2O 有一次 0.2680075168609619 s 的 IMU 缺口
（`configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml:26, 53, 136, 145-150`）。BY2 文件末尾有一条截断记录；by3/by1 的文件尾完整性未见审计记录。
`V3_PROVIDER_SOURCE_INDEX.json` 不固定 Go2 body 文件，它们由原始文件 SHA-256 锁表固定：BY2 `<CLEAN_ROOT>/01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv`（`f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7`，`H_EXT_CONTRACT_V1.yaml:19-20`），BY2H/BY2O `RAW_FILE_HASH_LOCK_CLEAN5.csv`（`faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67`，:46-47、:129-130）。关节编码器不可得的旧证据（只作来源，不作性能证据）：`docs/codex_context/PAPER10G_R3_CURRENT_CONTEXT.md:17-18, 33`；`docs/paper_rebuild/horizontal_literature/hartley/stage_payload/06_IMPLEMENTATION/HARTLEY_BACKEND_IDENTITY_REGISTRY.yaml:110`。

### 7.3 单天线 GNSS 位置量测的接入点

- `horizontal_literature/ext05_pavlasek.py:354-417` `PavlasekIEKF.update` 单接收机分支（:385-386；杠杆预测 :366-369）：左不变 SE_2(3) 绝对位置更新。
- `horizontal_literature/ext05_provider.py:117-250` `build_solution_position_provider`：由 gnss1/gnss2 原始流解码 HPPOSECEF，NED 原点为首个 GNSS1 历元，R1 = pAcc1² I3，200 ms 节拍。
- `horizontal_literature/phase5_runner.py:423-514`（CLEAN4 EXT05C）与 `hext/ext05_sequence_runner.py:784-846, 897-1030`（H-EXT EXT05C/EXT05C-S）：
  更新只用 GNSS1，但**初始航向取自首个有效双天线基线**（`phase5_runner.py:443-446`；`ext05_sequence_runner.py:803-814`），
  与冻结约定 `single_antenna_dual_yaw_initialization_only: true`（`CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml:394, 459`）一致；EXT06 须声明是否沿用。
- `protocol_v3/providers.py`：v3 只改 GNSS18 的航向列，位置 token 与冻结 v2.1 base GNSS18 逐字节相同；base GNSS18 固定值 BY2 `b98b4897…`、BY2H `4cd2369e…`、BY2O `c5212cf7…`
  （`<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/02_BASE_PROVIDERS/<SEQ>/GNSS18.gnss`）。GNSS15/18 列语义见 `configs/paper_rebuild/final_v23_parity_contract.yaml:149-165`，
  位置为单接收机 GNSS1（机体右侧）status 解。
- 冻结二进制中的 KF-GINS 单天线位置更新 `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:852-871`（F01 路径，非 InEKF）。
- GINav SPP/INS 路线（`$EXTERNAL/GINav/src/main_func/gi_Loose.m`），v3 中三序列均 UNAVAILABLE。

### 7.4 冻结安装变换/杠杆臂文件

| 角色 | 路径 | sha256 | 冻结记录 |
| --- | --- | --- | --- |
| IMU→GNSS1 杠杆 [0.03, 0.03, −0.30] m（FRD）；IMU FLU→FRD；安装角 RzRyRx [−1, 0, 0] deg；天线顺序 GNSS2−GNSS1（GNSS1 右、GNSS2 左）；GNSS15 列来源 | `configs/paper_rebuild/final_v23_parity_contract.yaml`（:282、:181-185、:199-202、:149-165） | `2c215e680512bb1d630d46262c4e230a2ec58147ffc0a35b1c6a5ad21805c1da` | 被 `CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml:6-7` 与 BY2O 合约固定 |
| BY2H 冻结解算器运行 token（antlever、IMU 噪声、初始化） | `configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml`（:582-584、:798-801、:855） | `64bf78d5d4241294922fbc6c18eaeb8ad4c2e40663ba8e5306ab67e1d07d4e19` | 被 `CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml:23364` 与 `CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml:184` 固定 |
| BY2O 同上（及遮挡窗 GNSS2 fix_type≠8 主窗 3369.94–3411.95 s） | `configs/paper_rebuild/clean5/CLEAN5_BY2O_SEQUENCE_CONTRACT.yaml`（:633 antlever_frd_m、:849-852 与 :906 运行 token、:445 与 :510 single_antenna_dual_yaw_initialization_only、:1105-1133 遮挡窗） | `bf42b2bee9ed96bd81d479bbb8b5533c58c6fce2ddbb5d9eabdeaf60cfd1144d` | 被 `CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml:23442` 与 `CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml:253` 固定 |
| v3 评估点政策：固定 POI 变换杠杆 [0.03, 0.03 − ½b, −0.30] | `configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL_CONTRACT.yaml`（:155） | `79d9e4521999e1e5fa328f1921ca455df859a89559473b3864ed5f92c1600948` | 被 `SENSOR_MODEL_V21_CONTRACT.yaml:15-16` 与 `CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml:8` 固定 |
| v3 NAV→天线中点变换实现（只改 LLH 列） | `src/legsa_gins/paper_rebuild/clean5_parity/evaluation.py`（:25-55） | `cfd8b276c9fe663f823a5846dab6a54de72664688b798a6591f168dd86044d0a` | v3 科学冻结 7d43b9a 代码范围；无单独哈希固定 |
| 各序列冻结 A1 基线中位数：BY2 0.356191491865984 m、BY2H 0.35418777593777223 m、BY2O 0.35013463864843675 m | `configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml`（:18、:45、:128、:304） | `7b748b5106dace0d809947dea65ae85c4a161ad18ca78aa395d2252b15c42863` | 最后提交 f7bf019；经 `hext/sequence_paths.py:31, 76` 读取；无对该文件哈希的固定 |
| EXT05/LC01 文献几何：imu_to_gnss1_frd_m [0.03, 0.03, −0.30]、gnss2_minus_gnss1_frd_m [0.0, −0.350, 0.0]、安装角、R1、初始协方差、PSD | `configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml`（:52-69、:80、:115-122） | `a9476f909ed65c9b4760ac19dc3cde3d625fa3d390b2f133cae79182e2293392` | 被 `H_EXT_CONTRACT_V1.yaml:230-232` 固定 |
| EXT05 代码常量（BASELINE_BODY_FRD_M、LEVER_IMU_TO_RECEIVER1_FRD_M、IMU_INSTALL_RPY_DEG） | `src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py`（:33-35） | `8f924bfdc33111e2cb8baf28dcf8ad7f90f0174e6ba55abf2ed6c238e97c8576` | 只在未跟踪的 `H_EXT_04_CONTRACT_V1.yaml` 中固定（不在 HEAD） |
| v2.1 传感器模型：installation_rpy_deg [−1, 0, 0] 保留、不拟合安装角、go2_hv 来源 | `configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml`（:282-283、:293、:385-388、:406） | `5024386db501cbf02e2dd6c43963d16380decf432359a81ecc6fc478f26e2b69` | 被 `V3_PROVIDER_SOURCE_INDEX.json` source_contracts 固定 |
| v3 provider 源索引 | `configs/paper_rebuild/v3/V3_PROVIDER_SOURCE_INDEX.json` | `130f93315d504bd7daddefc7eeabdbbeb10b763011531ade2766a0448a689a0e` | 被 `PROTOCOL_V3_CONTRACT.yaml:17-19` 固定 |
| v3 合约（"frozen transforms and parameters unchanged"，冻结二进制/评估器固定） | `configs/paper_rebuild/v3/PROTOCOL_V3_CONTRACT.yaml` | `ec24079cba346f88eb047fb5d5ad48467b8060f4b8e3c7c31c48de9bac6dff31` | 由 7d43b9a 冻结 |
| Hartley FK 代理坐标：IMU 传感器→机体旋转、foot_position_body 恒等映射 | `configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_FRAME_CONTRACT.yaml`（:16-37、:73-88） | `3ab0903a1aa708e4c0e1eb1fd176c6d7a5104f7fbc82ac2ac55ebf19b717de9d` | Hartley LSE01 阶段合约 |
| Go2 FK 代理与接触阈值（仅 BY2） | `…/04_METHOD_CONTRACTS/BY2_FK_PROXY_CONTRACT.yaml` | `4a40f8aa58b7d03478b0b5984dbe2650fae98eabfc4ef250b1e3099dd3e13fb0` | LSE01 H0–H2 合约 |
| Go2 足端顺序 | `…/04_METHOD_CONTRACTS/GO2_FOOT_ORDER_CONTRACT.yaml` | `95a49f3c892df3889b58c4f8e62c406110e2ec14d42aef5f64d9aca84d28db73` | LSE01 合约 |
| Go2 IMU Allan 连续噪声密度（仓库侧备用值，非文献值） | `…/04_METHOD_CONTRACTS/GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml`（:32-72） | `fcf3964caf8142f262f9df767df62d3f18454d18ca331a9dcc0722f8786b4480` | Hartley H5 配置；另被 `horizontal_literature/ginav2021/constants.py:116-118` 固定 |

缺口：Go2 机体原点（foot_position_body 的参考点）到 IMU 的平移无记录，Hartley 视二者重合（`HARTLEY_FRAME_CONTRACT.yaml:17-22, 34-37`）；
`T_FP_POI_from_GO2_BODY_IMU` 从未得到来源证明（`LSE01_FINAL_CLAIM_BOUNDARY.md:9-12`）；天线–IMU 高差的 CAD 核对仍列为待办
（`CLEAN5_CALIBRATED_SENSOR_MODEL_CONTRACT.yaml:175`；`AGENTS.md:491, 1462`）。

### 7.5 Luo 型方法的文献与参数

文献（置信度：中）：Yarong Luo, Yichao Chen, Anbo Tao, Chi Guo（2025），"Leg Odometry Assisted GNSS/INS Integrated Navigation System for the Quadruped Robot"，
收于 L. Yan, H. Duan, Y. Deng (eds.), *Advances in Guidance, Navigation and Control — Proceedings of ICGNC 2024*, Lecture Notes in Electrical Engineering vol. 1346,
Springer, pp. 253–264，2025-03-04 在线，DOI 10.1007/978-981-96-2236-8_25；未找到 arXiv 版本。识别方式：reader 用论文题名式检索（WebSearch）并打开 Springer 章节页（WebFetch），
可访问内容只有元数据、摘要、关键词与 17 条参考文献，全文付费未读。摘要原文："In this paper, we propose a leg odometry assisted global navigation satellite system (GNSS)/inertial navigation system (INS) integrated navigation system for the quadruped robot. First, we present a left invariant extended Kalman filter for global measurement on Rotating earth in the local world frame. Next, we construct a leg odometry and derive the contact point motion dynamics and leg odometry observation equation for the quadruped robot. Finally, the field experiment shows that the odometry assisted GNSS/INS integrated system can significantly reduce the position error compared to the one without GNSS signal."
匹配度：InEKF + 腿里程计 + GNSS/INS、四足、Luo 等人一致；摘要未说明单/双天线，也未提 radar，"单天线""无 radar"无法从可访问文本证实；
检索未找到含 radar 的 Luo 腿式论文，"no radar" 更像 EXT06 的范围约束。其他候选（方法学前作，非腿式，匹配度低）：Luo, Lu, Guo, Liu，
"Matrix Lie Group based extended Kalman filtering for inertial-integrated navigation in the navigation frame"，IEEE TIM 73 (2024)（章节参考文献 [13]）；
Luo, Guo, Chen，"Filter and piecewise smoother on the matrix Lie group"，GPS Solutions 27(4):163 (2023)（[14]）。**HX-04 前需取得全文确认。**

| 参数项 | 值 | 出处 |
| --- | --- | --- |
| 滤波/误差形式 | 左不变 EKF | 摘要 |
| 导航系/地球模型 | 局部世界系下考虑地球自转（"global measurement on Rotating earth in the local world frame"） | 摘要 |
| 腿里程计模型 | 推导接触点运动动力学与腿里程计观测方程 | 摘要 |
| 正运动学约定 | 可能为 Denavit–Hartenberg（仅由参考文献 [17] 推测，非给定参数） | 参考文献表 |
| 传感器 | GNSS + INS + 腿里程计；未提 radar；天线数未说明 | 题名、摘要、关键词 |
| GNSS 接收机配置（单/双天线、RTK/SPP、频率） | 文献未给（可访问内容中未给，全文未核） | Springer 章节页 |
| 陀螺白噪声（ARW） | 文献未给（同上） | 同上 |
| 加计白噪声（VRW） | 文献未给（同上） | 同上 |
| 陀螺偏置随机游走 | 文献未给（同上） | 同上 |
| 加计偏置随机游走 | 文献未给（同上） | 同上 |
| 是否含偏置状态 | 文献未给（同上） | 同上 |
| 接触点/足端过程噪声 | 文献未给（同上） | 同上 |
| 腿运动学量测噪声（FK 位置或速度；关节编码器噪声） | 文献未给（同上） | 同上 |
| 接触检测方法与阈值 | 文献未给（同上） | 同上 |
| GNSS 位置量测噪声 R | 文献未给（同上） | 同上 |
| 天线杠杆臂处理 | 文献未给（同上） | 同上 |
| 初始状态/对准（含初始航向来源） | 文献未给（同上） | 同上 |
| 初始协方差 | 文献未给（同上） | 同上 |
| 更新频率（IMU、GNSS、腿里程计） | 文献未给（同上） | 同上 |
| 野值门限/卡方/NIS 检验 | 文献未给（同上） | 同上 |
| 机器人平台、IMU 型号、GNSS 硬件 | 文献未给（同上） | 同上 |
| 报告结果 | 仅定性："can significantly reduce the position error compared to the one without GNSS signal"，摘要无数值 | 摘要 |

仓库内可作备用（**不是文献值**，采用须声明为偏离）：Go2 IMU Allan 密度 gyro 2.865130e-04 rad/s/√Hz、accel 1.285395e-03 m/s²/√Hz、
陀螺偏置 RW 2.996871e-05 rad/s²/√Hz、加计偏置 RW 1.594412e-04 m/s³/√Hz（`GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml:36, 46, 56, 66`）；
Hartley IJRR Table 1 离散 std 0.002 rad/s、0.04 m/s²、0.001 rad/s²、0.001 m/s³、接触 0.05 m/s、编码器 1.0 deg（`hartley_inekf/include/hartley_inekf/backend.hpp:61-68`）；
GNSS R 取 pAcc²（`ext05_provider.py:182`）或 GNSS18 std 列；冻结 KF-GINS IMU 噪声 arw 0.985 deg/√h、vrw 0.077 m/s/√h、gbstd 9.38 deg/h、abstd 77.8 mGal（`final_v23_parity_contract.yaml`）。

### 7.6 其他约束

- 可比性：EXT06 若要与 EXT05C 同口径评估，必须输出带 roll/pitch/yaw 的 IMU 点 NAV（`clean5_parity/evaluation.py:34-55` 需 ≥11 列），
  经 v3 变换（`protocol_v3/runtime.py:231-234`）；本地 NED→11 列 LLA 适配器已有（`hext/ext05_sequence_runner.py:318-392`）。
- 单天线纯度：若沿用双天线初始航向，EXT06 不是纯单天线；EXT05C 的航向对起点敏感（BY2H FILE_START yaw 55.609933584769315 deg，CONTRACT_START 20.108223061254332 deg）。
- BY2O 的遮挡只作用于 GNSS2（`CLEAN5_BY2O_SEQUENCE_CONTRACT.yaml:1105-1133`），仅用 GNSS1 的 EXT06 不会经历自然遮挡。
- 腿数据只有高层 sportmodestate，无关节编码器；Luo 可能用关节角 FK，无法精确复现，FK 代理须声明为偏离。

## 8. 存储盘点

### 8.1 可用空间（`df --output=avail`，1 KiB 块）

| 时点 | /mnt/e | /mnt/g |
| --- | ---: | ---: |
| 任务开始后（约 2026-09-23T12:30Z） | 125,565,936（≈128.6 GB / 119.7 GiB） | 89,544,960（≈91.7 GB / 85.4 GiB） |
| 提交前（2026-09-23T13:31:59Z） | 125,561,860（比开始时少 4,076 KiB；本任务未在 /mnt/e 存任何文件，变化应来自 WSL 虚拟磁盘上的仓库写入，按观测记录） | 89,544,960（不变） |

守卫线 /mnt/e ≥ 40 GB、/mnt/g ≥ 30 GB：两盘均在线上。本任务未在 E: 存文件、未在 G: 新建目录、未开 scratch。

### 8.2 阶段目录大小（`du -sb` 表观字节为主；每项 300 s 超时）

V3-01-R 清理账本（`$V3/V3R_PURGE/INVENTORY.csv`，sha256 `98c177cc1458c4981f3b7736427e4e185d4dbd2c25b4a6468f6275b824a28f7b`）只是**部分枚举**：

| 阶段 | 账本数字（部分枚举） |
| --- | --- |
| CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON | 未登记阶段，账本无数据（仅 1 行 `EXCLUDED_DIRECTORY_UNENUMERATED` / `STAGE_NOT_REGISTERED_COMPLETED_WITH_VERIFIED_HANDOFF`） |
| CLEAN7_HEXT_EXTERNAL_SEQUENCES | 228 文件 / 1,750,561,217 B；41 个目录行未枚举 |
| CLEAN7_T5A_HEADING_SENSITIVITY | 1 文件 / 29,739 B；7 个目录行未枚举 |
| CLEAN7_T5BC_V3_CANDIDATE_PILOT | 清理前 9,006 文件 / 21,662,986,200 B；其中 1,267 文件 / 14,186,690,282 B 已按账本删除（`docs/paper_rebuild/v3/V3_01R_PURGE_REPORT.md`） |

`du` 实测（2026-09-23 约 20:35–20:40 北京时间）：

| 目录 | 表观字节 | 耗时 |
| --- | ---: | --- |
| CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON（整体） | 3,857,721,701 | 6 s |
| CLEAN7_HEXT_EXTERNAL_SEQUENCES（整体） | 2,856,486,105 | <1 s |
| CLEAN7_T5A_HEADING_SENSITIVITY（整体） | 2,557,710,790 | 1 s |
| CLEAN7_T5BC_V3_CANDIDATE_PILOT（整体） | 17,846,602,780 | 9 s |
| CLEAN8_PROTOCOL_V3（整体） | — | 超时跳过（324 s 后被 300 s 超时终止） |

CLEAN4 顶层（均 ≤4 s，逐项耗时：02_EXT01 4 s，05_EXT04、07_LSE01、11_LC02_GINAV、14_PLOTTING 各 1 s，其余 <1 s）：
00_CONTRACTS 14,114；01_SHARED_RAW_BACKEND 31,274,243；02_EXT01_CLAMBDA 254,147,076；03_EXT02_CWLS 642,865,735；
04_EXT03_YANG2024 417,866,958；05_EXT04_WU2025_MODULE 385,346,933；06_EXT05_PAVLASEK_TWO_RECEIVER 241,780,251；06_NATIVE_C00 7,747；
07_HORIZONTAL18_V2_CANARY_R3_SERIALIZATION_FAILURE_E7AC202C 194,932,058；07_HORIZONTAL18_V2_PREP_R2_ARCHIVE_4036382F 70,199；
07_LSE01_HARTLEY_CONTACT_INEKF 1,214,979,737；08_LC02_YIN2023_RAEKF 224,173；09_LC02_CHANG2021_FSTCKF 78,779；
10_LC02_FINAL_CANDIDATE_TRIAGE 72,529；11_LC02_GINAV2021_OFFICIAL_REPRODUCTION 246,421,763（.frozen_attempt2 90,140；.frozen_attempt3 97,327；两个 RELOCATION_LEDGER.json 11,859 / 14,234；.partial 42,744）；
11_REPORT 10,924,897；12_FINAL_EVIDENCE_INTEGRATION 68,123；13_HORIZONTAL_CROSS_LAYER_SYNTHESIS 675,626；
14_HORIZONTAL_FULL_PLOTTING 124,684,390；14_HORIZONTAL_FULL_PLOTTING.zip 91,017,576。

CLEAN7_HEXT 顶层（除 RAW_CHECKPOINTS 1 s 外均 <1 s）：00_CONFIG_AUDIT 366,639；01_PROBE 85,312；02_BY2_IDENTITY 225,270,992；
03_CONTINUATION 301,668；03_PREREG 226,019,146；03_PROVIDER_CACHE 12,937,409；04_ACCESS_AUDITS 6,254,088；
04_NATIVE_RUNS 1,743,923,898；05_GEOMETRIC_AUDIT 5,465；06_V3_NAV_INPUTS 182,466,839；07_OFFLINE_EVALUATION 455,191,406；
08_AGGREGATE 375,558；09_LEGSA_GAP_DIAGNOSTIC 45,569；10_FIGURES 698,799；11_READONLY_CLOSEOUT_H_EXT_04L 2,349,631；
99_HARD_STOP 109,740；RAW_CHECKPOINTS 60,700；顶层 json/txt 7 个合计 20,650。

现有 ext4 scratch（`/home/kaiwen/research/LegSA-GINS-SCRATCH`，只读 du）：合计 10,572,860,054（629 ms）；
CLEAN7_HEXT_EXTERNAL_SEQUENCES 5,508,621,807（24 ms）；CLEAN7_T5A_HEADING_SENSITIVITY_R 3,288,841,755（31 ms）；
CLEAN8_PROTOCOL_V3 870,584,506（6,743 ms）；CLEAN6_SENSOR_MODEL_V21 337,350,656（10,051 ms）；
CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2 291,598,336（11,719 ms）；CLEAN7_T5A_HEADING_SENSITIVITY 225,409,605（6 ms）；
CLEAN6_ADDENDUM_FAMILIES_A1_A2 28,512,256（949 ms）；lc02_ginav2021_20260825_transaction1–4 各约 5.46–5.49 MB（8–9 ms）。
`<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON` 与 scratch `CLEAN9_EXTERNAL_COMPARISON` 当前均不存在（未创建）。

### 8.3 CLEAN9 任务目录内部结构建议（只建议，未创建）

顶层已定：`HX02_FIVE_CATEGORY / HX03_DEGRADATION / HX04_EXT06 / HX05_CLOSEOUT`；scratch
`/home/kaiwen/research/LegSA-GINS-SCRATCH/CLEAN9_EXTERNAL_COMPARISON/`（≤20 GB，每批归档到 G: 校验后删除）。
每个任务目录建议：

```text
<TASK>/
  00_CONTRACT/            合约副本 + sha256；授权字符串；预算（native/evaluator 次数上限）
  01_INPUT_PINS/          输入清单：provider/cache/原始流 sha256，冻结评估器与二进制 sha256
  RUNS/<SEQ>__<METHOD>__<CONFIG>__<CASE>__<SEED>/   每次运行一个目录
    COMMAND.json          argv、cwd、环境变量白名单、代码提交号、开始/结束 UTC
    PARAMS_ECHO.json      实际生效参数回显（与合约逐项比对结果）
    INPUT_HASHES.json     本次运行实际读取的输入 sha256
    native/               方法原生输出
    OUTPUT_HASHES.json    输出封存（OUTPUT_SEAL）
    eval/v3/              EVALUATOR_OPENAT.strace、EVALUATOR_STRACE_AUDIT.json（trace 恰 1 次只读、bag/fpl 0、写范围）、
                          EVALUATOR_CAPTURE.json、summary.json、error_series
    FAILURE.json          失败标记（类别、首次越界时刻、失败前指标路径），或 DONE.json
  90_AGGREGATE/           汇总表与其 sha256 清单
  99_HARD_STOP/           硬停记录（如有）
```

每批开始前检查 /mnt/e 与 /mnt/g 守卫线；scratch 与 G: 目录一一镜像，归档后逐文件 sha256 复核再删 scratch。

## 9. 事故

### 9.1 `hext/matched.py` 意外导入（主会话）

| 问题 | 答案 | 依据 |
| --- | --- | --- |
| 期间是否调用冻结二进制或评估器 | **否** | 审计钩子拦截一切 subprocess/os.system/exec/posix_spawn/fork，被拦截事件清单只有 `ctypes.dlopen(None)`，没有任何进程启动尝试；已执行的 matched.py 第 1–15 行不含任何调用；冻结二进制与评估器只能以子进程方式启动 |
| 是否打开任何 trace/bag/fpl 数据文件 | **否** | 钩子在 open 发生前拦截 `/mnt/` 下任何路径、文件名含 trace/truth 的非源码文件、.csv/.fpl/.bag 等数据扩展名，并记入被拦截清单；清单中没有任何 open 事件。进程输出的非库打开清单以 `src/legsa_gins/__pycache__/__init__.cpython-310.pyc` 等源码缓存开头（显示被截断，未见全表，这是判断依据的局限）；静态上 matched.py 第 1–15 行与父包 `__init__`/`manifest.py`/`paths.py` 的模块级代码都没有文件读取。钩子不覆盖 C 扩展内部的底层 open，但执行到的代码没有打开数据的路径 |
| 除 `__pycache__` 外是否写入任何文件 | **否**（`__pycache__` 也未写） | `PYTHONDONTWRITEBYTECODE=1` 且 `sys.dont_write_bytecode=True`；钩子拦截并记录一切写模式 open，清单中没有；`find` 检查任务开始后新建或修改的 `*.pyc`/`__pycache__`：无（matched.cpython-310.pyc 的 mtime 仍为 2026-09-18 16:16:38，只有 atime 变为 20:34:32） |
| 该文件是否带 NOT_AUTHORIZED_FOR_EXECUTION 标记 | **是** | matched.py:6 与 :22 |

- 触发命令（2026-09-23T12:34:32.529Z，主会话 Bash）：
  `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -c "$GUARD" import legsa_gins.paper_rebuild.hext.matched`，
  其中 `$GUARD` 为第一版内联审计钩子。本意是验证钩子能否拦截该导入（负面测试），判断失误：规则 8 不允许导入，受控导入也不行。
- 进行到哪里停止：`importlib.import_module` 不触发 CPython 的 `import` 审计事件，第一版钩子的导入拦截没有生效。
  父包依次加载：`legsa_gins`（空）→ `legsa_gins.paper_rebuild`（`manifest.py`、`paths.py`，只用标准库）→
  `legsa_gins.paper_rebuild.hext`（`__init__` 为空）。随后读入 `hext/__pycache__/matched.cpython-310.pyc`
  （atime 20:34:32.669，与命令时刻一致），执行 matched.py 第 1–15 行（docstring、`from __future__`、dataclasses、functools、typing），
  第 15 行 `import numpy as np` 导入 numpy 时触发 `ctypes.dlopen(None)`，被钩子拦截并抛 PermissionError，导入中止。
  第 17 行起（导入 `ext05_pavlasek`、`EXECUTION_STATUS` 常量及全部函数/类定义）均未执行。进程输出：
  `"status": "broken", "error": "PermissionError: HX_GUARD_BLOCKED_PROCESS ctypes.dlopen", "blocked": [{"event": "ctypes.dlopen", "args": "(None,)"}]`。
- 硬停判断：前三问均为否，不按硬停处理。
- `__pycache__` 处理：未产生新的 `__pycache__`/`.pyc`，无需删除，未提交任何缓存文件。
- 纠正：改用第二版钩子（`meta_path` 查找器，`importlib` 路径同样拦截），不再用任何项目模块做负面测试；
  之后 29 项检查均带 12 个模块的拦截表，没有触发任何 `meta_path` 拦截。

### 9.2 子代理规则偏差（与 9.1 并列）

给子代理的规则（子代理提示中的编号）：规则 2 不执行项目代码；规则 3 不打开 `/mnt` 上文件名含 trace/truth 的任何文件、不打开 .fpl/.bag 与原始数据目录下的文件；
规则 4 不对 `/mnt` 做递归 grep，仓库内递归 grep 只限代码/文档扩展名，CSV 只按显式路径读。注意：本环境的 `grep` 是 Claude 内置 ugrep 的包装函数，
**不带 -r 也会递入目录参数**（已用仓库文档实测确认），这是 (2) 的成因。子代理编号见 §10。

| # | 子代理 | 时间（UTC） | 违反的规则 | 做了什么 | 写文件 | 调用冻结二进制或评估器 | 打开 trace/bag/fpl 参考轨迹数据 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| (1a) | #3 read:lc02（agent-abb3c2049d1639f21） | 2026-09-23T12:34:36Z | 规则 3 | `cat -n` 读取 `$STAGES/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/LC02_GINAV/FROZEN_EVALUATOR/EVALUATOR_STRACE_AUDIT.json`（文件名中的 "trace" 是 "STRACE" 的一部分），同命令还读了同目录 CAPTURE_CONFIG.json、EVALUATOR_CAPTURE.json、summary.json、evaluator_stdout.log | **否** | **否** | **否**：该文件是评估子进程的进程/IO 审计 JSON（argv、打开计数、写范围、strace 日志哈希），不是 trace CSV；同目录的 EVALUATOR_OPENAT.strace 与 error_series.csv 未打开 |
| (1b) | #3 read:lc02 | 2026-09-23T12:42:14Z | 规则 4 | 在仓库内 `grep -rn --include=*.py --include=*.md --include=*.yaml --include=*.json --include=*.csv … .`，读遍工作树 235 个 CSV，其中唯一文件名含 trace 的是 `suanfahengxiangduibi/PAPER4B_R2_PHYSICAL_FRAME_CLOSE_AND_YAW_REEVALUATION/04_trace_generation_script_audit/evaluator_trace_field_usage_audit.csv`；结果 0 行匹配 | **否** | **否** | **否**：只用 stat 比对，三份原始 trace 为 1,599,260 / 1,081,436 / 1,063,498 B，工作树内任何扩展名的文件都没有这些大小；该 trace 命名 CSV 为 350 B 的字段审计表（2026-06-07，提交 8a71761） |
| (2) | #6 read:injection（agent-a739e9cfc4b1c4124） | 2026-09-23T12:40:06Z | 规则 4 | `grep -il "classic" $CLEAN4/00_CONTRACTS/* $CLEAN4/11_REPORT/* …`：包装 grep 递入 `11_REPORT/` 下 3 个目录 PHASE3_EXT03_C00_NATIVE_SOURCE_PROVENANCE_R1、_R2、PHASE4_EXT04_PENDING_ARCHIVE_R6（共 27 个文件，扩展名 .py/.patch/.json/.md/SHA256SUMS）；子代理自行报告 | **否** | **否** | **否**：主会话按元数据重放该命令的全部目录参数（`os.walk` 只取名称与大小），0 个 trace/truth/.fpl/.bag 命名文件，0 个与原始 trace 同大小的文件 |
| (3) | #10 verify:lc02（agent-a53cf5ea8ee0b27b8） | 2026-09-23T13:10:59Z | 规则 4 | `git ls-files docs/paper_rebuild/hext configs/paper_rebuild/hext \| xargs grep -n -i "ginav"`，扫描了 18 个已跟踪 CSV（`H_EXT_CONFIG_PARITY_AUDIT.csv`、`t5bcr/*.csv`），均不含 trace/truth 字样，无匹配输出；另于 13:07:18Z 运行 `python3 -m pip show legsa-gins` 并导入 numpy/yaml/pypdf/pandas（第三方库，不是项目代码，不构成规则 2 违规，但超出"只用标准库读文件"的做法） | **否** | **否** | **否**：均为仓库内已跟踪 CSV，工作树内无 trace 同大小文件 |
| (4) | #15 critic（agent-adcd4a4d44923d438） | 2026-09-23T13:24:03Z | 规则 4 | `git grep -l -E 'D01_DIRECT_GEOMETRIC_BASELINE\|D02_SINGLE_RECEIVER_IEKF\|M01_EXT05_PAVLASEK_IEKF' HEAD` 未加路径过滤，搜索了全部已跟踪文件内容（含上述 350 B trace 命名审计 CSV）；`git log --oneline -S'D02_SINGLE_RECEIVER_IEKF' --all` 搜索了全部历史差异；均无匹配；子代理自行报告 | **否** | **否** | **否**：按对象元数据（`git cat-file --batch-check`，不读内容）核查，全部 git 历史中没有与三份原始 trace 同大小的 blob，历史上唯一文件名含 trace/truth 的数据文件就是该 350 B 审计 CSV |

全部 15 个子代理与主会话的 grep 目录递归已按元数据重放（§10.2）：`/mnt` 上的目录递归只有 (2) 的 3 个目录。其余"trace"字样命中均为目录列举
（#9、#15 对 `$CLEAN4/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/POST_NATIVE_TRACE_EVALUATION` 只做 `ls`；#10 对 `…/runtime/continuation_size_truth_20260826` 只做 `ls`/`find -name`；
#7 对原始 `高层数据/` 目录只做 `ls -la`），或 `ls -la /mnt/f/MATLAB2025b/bin/matlab.exe` 与 `which octave matlab` 这类存在性检查（#3、#10，未执行）。
子代理写入的只有工具框架自动保存的超长输出（`~/.claude/projects/…/tool-results/`，框架行为，不在项目、工作树或 G:/E: 上）。

### 9.3 其他披露（非事故）

- 5 项受控检查中，numpy 导入期的 CPU 特性探测（`numpy/testing/_private/utils.py:1247–1253`，经 `scipy.stats`）尝试启动 `lscpu`，
  被钩子拦截、未执行，库自行容错，检查照常完成。与项目代码、解算、评估无关。
- #3 read:lc02 与 #10 verify:lc02 对 `/mnt/f/MATLAB2025b/bin/matlab.exe` 只做 `ls -la` 与 `which octave matlab` 查看存在性，未执行。

### 9.4 预先存在的未跟踪文件

任务开始时（会话首次 `git status`）工作树已有 29 个未跟踪文件，均非本任务产生（mtime 最晚 2026-09-19 17:24:42），
本任务未修改、未删除、未暂存；提交时逐一复核 sha256 前缀不变（§11）。清单：
`configs/paper_rebuild/hext/H_EXT_04_CONTRACT_V1.yaml`、`docs/paper_rebuild/v3/STORAGE_PLACEMENT.md`、
`scripts/paper_rebuild/{LC02_GINAV2021_RESUME_20260826.py, clean6_finalize_aggregate_io.local.py, hext04_execute.py, hext04_heading_diagnostic.py, hext04_identity.py, hext04_package.py, v3_ext4_archive_execute.py, v3_failure_classification_appendix.py}`、
`src/legsa_gins/paper_rebuild/hext/{heading_diagnostic.py, heading_diagnostic_process.py, heading_readout.py, matched_aggregate.py, matched_execution.py, readiness.py, sensitivity_evaluation.py, sensitivity_execution.py}`、
`tests/paper_rebuild/{test_hext04_execution.py, test_hext04_heading_diagnostic.py, test_hext04_heading_diagnostic_process.py, test_hext04_heading_readout.py, test_hext04_matched_aggregate.py, test_hext04_package.py, test_hext04_readiness.py, test_hext04_sensitivity_evaluation.py, test_hext04_sensitivity_execution.py, test_protocol_v3_failure_classification_appendix.py, test_protocol_v3_storage_adapter.py}`。
因此 `git status --short` 在提交后除这 29 行外应为空；要做到完全干净只能删除或移走这些用户文件，本任务不做。

## 10. 读取进程审计

### 10.1 15 个子代理（逐个）

全部子代理都是本 Claude Code 会话内由 Workflow 启动的子代理进程（独立模型实例），只能经工具调用读取；
读取路径由主会话从各子代理的原始工具调用记录（transcript 中的 Bash 命令与 Read 路径，已解析 shell 变量）汇总，不依赖子代理自述。
"写文件"一栏：Write/Edit 工具调用次数均为 0，也没有 mv/cp/rm/mkdir/touch/tee/sed -i、重定向到文件或改变 git 状态的命令
（自动筛查的"重定向"命中经逐条核对均为 awk 比较式 `NR>=` 或 grep 模式中的 `>`）；工具框架自动保存的超长输出不计为子代理写入。

| # | 子代理 | agent id | 任务 | 工具调用 | 读取路径（汇总，按原始调用解析） | 自报打开文件数 | 写文件 | 打开 trace/bag/fpl 参考轨迹数据 |
| ---: | --- | --- | --- | --- | --- | ---: | --- | --- |
| 1 | read:layerA | ab5562b26a4de9747 | Layer A 原始双天线方法 EXT01–EXT04 | Bash 91、Read 1 | $CLEAN4；$CLEAN4/01_SHARED_RAW_BACKEND；$CLEAN4/02_EXT01_CLAMBDA；$CLEAN4/03_EXT02_CWLS；$CLEAN4/04_EXT03_YANG2024；$CLEAN4/05_EXT04_WU2025_MODULE；$CLEAN4/06_NATIVE_C00；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$EXTERNAL；$EXTERNAL/RTKLIB；$EXTERNAL/papers；$EXTERNAL/rtklib_bridge；$HEXT；$HEXT/03_PREREG；$HEXT/04_NATIVE_RUNS；$HEXT/08_AGGREGATE；$STAGES；$STAGES/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE；$STAGES/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE；$STAGES/CLEAN5_DEGSUBSET_BY2；$V3；$V3/07C_FAILURE_FAMILY_CONFIG；$V3/07D_CLASSIFICATION_PROVENANCE；$V3/07E_UNIFIED_FAILURE；$V3/07_AGGREGATE；$W；$W/AGENTS.md；$W/configs；$W/docs；$W/src；~/.claude/…/tool-results（框架保存的自身输出） | 120 | 否 | 否 |
| 2 | read:pavlasek | a449e0727326d7f35 | LC01/EXT05A、EXT05B、EXT05C、-S 变体与 H-EXT 序列运行；LC01 输入接口与 A2 可行性 | Bash 74、Read 16 | $CLEAN4；$CLEAN4/00_CONTRACTS；$CLEAN4/06_EXT05_PAVLASEK_TWO_RECEIVER；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$HEXT；$HEXT/03_CONTINUATION；$HEXT/04_NATIVE_RUNS；$HEXT/07_OFFLINE_EVALUATION；$HEXT/08_AGGREGATE；$HEXT/11_READONLY_CLOSEOUT_H_EXT_04L；$HEXT/FINAL_CHECK.json；$HEXT/IDENTITY_PASS.json；$STAGES/CLEAN5_DEGSUBSET_BY2；$V3；$V3/03_NATIVE；$V3/07_AGGREGATE；$V3/FINAL_EVALUATION_RECORDS.json；$V3/FINAL_RUN_RECORDS.json；$W；$W/AGENTS.md；$W/configs；$W/docs；$W/scripts；$W/src；<SCRATCH>/CLEAN7_HEXT_EXTERNAL_SEQUENCES；~/.claude/…/tool-results（框架保存的自身输出） | 100 | 否 | 否 |
| 3 | read:lc02 | abb3c2049d1639f21 | LC02 槽位（GINav、Yin 2023、Chang 2021、三角候选）与 HORIZONTAL18_V2 | Bash 110 | $CLEAN4；$CLEAN4/00_CONTRACTS；$CLEAN4/06_NATIVE_C00；$CLEAN4/07_HORIZONTAL18_V2_CANARY_R3_SERIALIZATION_FAILURE_E7AC202C；$CLEAN4/07_HORIZONTAL18_V2_PREP_R2_ARCHIVE_4036382F；$CLEAN4/08_LC02_YIN2023_RAEKF；$CLEAN4/09_LC02_CHANG2021_FSTCKF；$CLEAN4/10_LC02_FINAL_CANDIDATE_TRIAGE；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$EXTERNAL；$EXTERNAL/GINav；$EXTERNAL/papers；$HEXT；$STAGES/CLEAN5_DEGSUBSET_BY2；$V3；$V3/07_AGGREGATE；$W；$W/configs；$W/docs；$W/src；/mnt/f（仅 ls） | 162 | 否 | 否（见 §9.2 (1a)(1b)） |
| 4 | read:hartley_other | acf8b524daaa5133d | Hartley 接触辅助 InEKF 与其他外部方法清扫 | Bash 118 | $CLEAN4；$CLEAN4/00_CONTRACTS；$CLEAN4/04_EXT03_YANG2024；$CLEAN4/07_LSE01_HARTLEY_CONTACT_INEKF；$CLEAN4/08_LC02_YIN2023_RAEKF；$CLEAN4/10_LC02_FINAL_CANDIDATE_TRIAGE；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$EXTERNAL；$EXTERNAL/hartley；$EXTERNAL/papers；$HEXT；$HEXT/04_NATIVE_RUNS；$STAGES；$STAGES/CLEAN5_DEGSUBSET_BY2；$V3；$V3/07_AGGREGATE；$W；$W/AGENTS.md；$W/configs；$W/docs；$W/scripts；$W/src；$W/suanfahengxiangduibi；<CLEAN_ROOT>；<CLEAN_ROOT>/03_METHOD_SPECS；<CLEAN_ROOT>/08_EXTERNAL_DA；<CLEAN_ROOT>/99_LEGACY_DENYLIST；~/.claude/…/tool-results（框架保存的自身输出） | 171 | 否 | 否 |
| 5 | read:evaluation | ad4934721ec4e8a01 | 评估基础设施、v3 评估点、旧结果差异、各输出类型指标 | Bash 122、Read 14 | $CLEAN4；$CLEAN4/00_CONTRACTS；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$EXTERNAL；$HEXT；$HEXT/11_READONLY_CLOSEOUT_H_EXT_04L；$V3/07_AGGREGATE；$W；$W/AGENTS.md；$W/configs；$W/docs；$W/src；~/.claude/…/tool-results（框架保存的自身输出） | 107 | 否 | 否 |
| 6 | read:injection | a739e9cfc4b1c4124 | v3 注入规格、A1/A2、Classic-18、18 型候选、LC01/EXT06 映射 | Bash 85 | $CLEAN4；$CLEAN4/00_CONTRACTS；$CLEAN4/07_HORIZONTAL18_V2_CANARY_R3_SERIALIZATION_FAILURE_E7AC202C；$CLEAN4/07_HORIZONTAL18_V2_PREP_R2_ARCHIVE_4036382F；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$EXTERNAL；$EXTERNAL/papers；$STAGES；$STAGES/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX；$STAGES/CLEAN6_ADDENDUM_FAMILIES_A1_A2；$STAGES/CLEAN6_SENSOR_MODEL_V21；$V3；$V3/00_PREREQUISITES；$V3/07E_UNIFIED_FAILURE；$V3/07_AGGREGATE；$W；$W/src | 71 | 否 | 否（见 §9.2 (2)） |
| 7 | read:ext06 | a4ee49d207e0db510 | EXT06 前置（InEKF、腿/接触 provider、单天线接入点、安装/杠杆文件、Luo 文献） | Bash 121、ToolSearch 1、WebFetch 4、WebSearch 11 | $CLEAN4；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$EXTERNAL；$EXTERNAL/GINav；$EXTERNAL/hartley；$EXTERNAL/papers；$V3；$V3/03_NATIVE；$V3/07_AGGREGATE；$W；$W/configs；$W/docs；$W/src；$W/tests；<RAW_ROOT>（仅 ls）；网页（WebFetch，论文检索）；网页（WebSearch，论文检索） | 107 | 否 | 否 |
| 8 | verify:layerA | aa04f8bc61b15a82e | 对 #1 read:layerA 输出的对抗复核 | Bash 83 | $CLEAN4；$CLEAN4/00_CONTRACTS；$CLEAN4/02_EXT01_CLAMBDA；$CLEAN4/03_EXT02_CWLS；$CLEAN4/04_EXT03_YANG2024；$CLEAN4/05_EXT04_WU2025_MODULE；$CLEAN4/06_NATIVE_C00；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$EXTERNAL；$EXTERNAL/RTKLIB；$EXTERNAL/papers；$EXTERNAL/rtklib_bridge；$HEXT/04_NATIVE_RUNS；$STAGES/CLEAN5_DEGSUBSET_BY2；$V3/07_AGGREGATE；$W；$W/configs；$W/docs；$W/src；<CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY | 79 | 否 | 否 |
| 9 | verify:pavlasek | aa4c44c3b5b9ed96b | 对 #2 read:pavlasek 输出的对抗复核 | Bash 77、Read 1 | $CLEAN4；$CLEAN4/06_EXT05_PAVLASEK_TWO_RECEIVER；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$EXTERNAL；$EXTERNAL/papers；$HEXT；$HEXT/02_BY2_IDENTITY；$HEXT/03_CONTINUATION；$HEXT/04_NATIVE_RUNS；$HEXT/06_V3_NAV_INPUTS；$HEXT/07_OFFLINE_EVALUATION；$HEXT/08_AGGREGATE；$HEXT/11_READONLY_CLOSEOUT_H_EXT_04L；$HEXT/99_HARD_STOP；$HEXT/FINAL_CHECK.json；$HEXT/IDENTITY_PASS.json；$STAGES/CLEAN5_DEGSUBSET_BY2；$V3；$V3/07E_UNIFIED_FAILURE；$V3/07_AGGREGATE；$W；$W/docs；$W/src；<SCRATCH>/CLEAN7_HEXT_EXTERNAL_SEQUENCES；~/.claude/…/tool-results（框架保存的自身输出） | 81 | 否 | 否 |
| 10 | verify:lc02 | a53cf5ea8ee0b27b8 | 对 #3 read:lc02 输出的对抗复核 | Bash 101 | $CLEAN4；$CLEAN4/07_HORIZONTAL18_V2_CANARY_R3_SERIALIZATION_FAILURE_E7AC202C；$CLEAN4/07_HORIZONTAL18_V2_PREP_R2_ARCHIVE_4036382F；$CLEAN4/08_LC02_YIN2023_RAEKF；$CLEAN4/09_LC02_CHANG2021_FSTCKF；$CLEAN4/10_LC02_FINAL_CANDIDATE_TRIAGE；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.frozen_attempt2_9adb15c9fd3ee38e；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.frozen_attempt3_f56190fef675b387；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.partial；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$CLEAN4/14_HORIZONTAL_FULL_PLOTTING；$EXTERNAL/GINav；$EXTERNAL/papers；$STAGES/CLEAN5_DEGSUBSET_BY2；$V3；$V3/07_AGGREGATE；$W；/mnt/f（仅 ls） | 96 | 否 | 否（见 §9.2 (3)） |
| 11 | verify:hartley_other | afa88d13a366d37ad | 对 #4 read:hartley_other 输出的对抗复核 | Bash 107 | $CLEAN4；$CLEAN4/00_CONTRACTS；$CLEAN4/04_EXT03_YANG2024；$CLEAN4/07_LSE01_HARTLEY_CONTACT_INEKF；$CLEAN4/08_LC02_YIN2023_RAEKF；$CLEAN4/10_LC02_FINAL_CANDIDATE_TRIAGE；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$CLEAN4/14_HORIZONTAL_FULL_PLOTTING；$EXTERNAL；$EXTERNAL/hartley；$EXTERNAL/papers；$HEXT/04_NATIVE_RUNS；$STAGES；$STAGES/CLEAN5_DEGSUBSET_BY2；$V3/07_AGGREGATE；$W；$W/configs；$W/docs；$W/scripts；$W/src；<CLEAN_ROOT>；<CLEAN_ROOT>/03_METHOD_SPECS；<CLEAN_ROOT>/08_EXTERNAL_DA；<CLEAN_ROOT>/15_CLAIM_BOUNDARY；<CLEAN_ROOT>/99_LEGACY_DENYLIST | 136 | 否 | 否 |
| 12 | verify:evaluation | a1f0a9646273e6308 | 对 #5 read:evaluation 输出的对抗复核 | Bash 74、Read 1 | $CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$HEXT/11_READONLY_CLOSEOUT_H_EXT_04L；$V3/07_AGGREGATE；$W；$W/docs；$W/scripts；$W/src；<CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY；~/.claude/…/tool-results（框架保存的自身输出） | 84 | 否 | 否 |
| 13 | verify:injection | a0ac6d63e7177c587 | 对 #6 read:injection 输出的对抗复核 | Bash 50 | $CLEAN4/07_HORIZONTAL18_V2_CANARY_R3_SERIALIZATION_FAILURE_E7AC202C；$CLEAN4/07_HORIZONTAL18_V2_PREP_R2_ARCHIVE_4036382F；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$EXTERNAL/papers；$STAGES；$STAGES/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX；$STAGES/CLEAN6_ADDENDUM_FAMILIES_A1_A2；$STAGES/CLEAN6_SENSOR_MODEL_V21；$V3/07E_UNIFIED_FAILURE；$V3/07_AGGREGATE；$W；$W/configs；$W/docs；$W/src | 60 | 否 | 否 |
| 14 | verify:ext06 | ab4e280f27c101464 | 对 #7 read:ext06 输出的对抗复核 | Bash 87、ToolSearch 1、WebFetch 4 | $CLEAN4；$CLEAN4/00_CONTRACTS；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$EXTERNAL；$EXTERNAL/GINav；$EXTERNAL/hartley；$EXTERNAL/papers；$V3；$V3/00_CONTROL；$V3/00_PREREQUISITES；$V3/07_AGGREGATE；$V3/FINAL_IDENTITY_GATES.json；$V3/STATUS.json；$W；$W/configs；$W/cpp；$W/docs；$W/scripts；$W/src；$W/tests；<RAW_ROOT>（仅 ls）；网页（WebFetch，论文检索） | 109 | 否 | 否 |
| 15 | critic | adcd4a4d44923d438 | 完整性复核（记录中是否遗漏外部方法） | Bash 65、Read 4 | $CLEAN4；$CLEAN4/00_CONTRACTS；$CLEAN4/06_EXT05_PAVLASEK_TWO_RECEIVER；$CLEAN4/07_HORIZONTAL18_V2_CANARY_R3_SERIALIZATION_FAILURE_E7AC202C；$CLEAN4/07_LSE01_HARTLEY_CONTACT_INEKF；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.frozen_attempt2_9adb15c9fd3ee38e.RELOCATION_LEDGER.json；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.frozen_attempt3_f56190fef675b387.RELOCATION_LEDGER.json；$CLEAN4/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.partial；$CLEAN4/11_REPORT；$CLEAN4/12_FINAL_EVIDENCE_INTEGRATION；$CLEAN4/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS；$EXTERNAL；$EXTERNAL/hartley；$EXTERNAL/papers；$EXTERNAL/rtklib_bridge；$HEXT；$HEXT/01_PROBE；$HEXT/04_NATIVE_RUNS；$HEXT/07_OFFLINE_EVALUATION；$HEXT/09_LEGSA_GAP_DIAGNOSTIC；$HEXT/11_READONLY_CLOSEOUT_H_EXT_04L；$STAGES；$STAGES/CLEAN5_DEGSUBSET_BY2；$V3/07_AGGREGATE；$W；$W/AGENTS.md；$W/configs；$W/docs；~/.claude/…/tool-results（框架保存的自身输出） | 93 | 否 | 否（见 §9.2 (4)） |

### 10.2 grep 目录递归重放

由于包装 `grep` 会递入目录参数，主会话把 15 个子代理与主会话本身所有 grep 命令的 `/mnt` 目录参数（含 glob）按元数据重放（只取文件名与大小，不打开内容）：

| 进程 | 时间（UTC） | 被递入的 /mnt 目录 | 目录下文件数 | trace/truth/.fpl/.bag 命名文件 | 与原始 trace 同大小的文件 |
| --- | --- | --- | ---: | ---: | ---: |
| read:injection | 2026-09-23T12:40:06.705Z | `$STAGES/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_REPORT/PHASE3_EXT03_C00_NATIVE_SOURCE_PROVENANCE_R1` | 4 | 0 | 0 |
| read:injection | 2026-09-23T12:40:06.705Z | `$STAGES/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_REPORT/PHASE3_EXT03_C00_NATIVE_SOURCE_PROVENANCE_R2` | 6 | 0 | 0 |
| read:injection | 2026-09-23T12:40:06.705Z | `$STAGES/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_REPORT/PHASE4_EXT04_PENDING_ARCHIVE_R6` | 17 | 0 | 0 |

共检查 831 个以 grep 开头的命令段（`command grep` 不递归，另计）；`/mnt` 上的目录递归只有上表 3 项。

### 10.3 主会话

主会话（本 Claude Code 会话）：读取仓库文件、`$V3` 的 65 个登记文件与 5 个回执（计算 sha256）、`MAIN_TABLE_V3.csv`/`FULL_ABLATION_TABLE_V3.csv`（身份检查）、
`<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/HORIZONTAL_TABLE_V3.csv`（其中含 BY2 trace 的路径字符串，只读文本、未打开 trace）、
`$V3/V3R_PURGE/INVENTORY.csv`、冻结二进制与冻结评估器源码（只计算 sha256；评估器文件名含 trace 但它是 `.py` 源码，按规则可读），
对阶段目录做 `ls`/`du`/`stat`（含对三份原始 trace 文件只做 `stat` 取大小、从未打开）；受控检查见 §3A；事故见 §9.1。
主会话写入的只有本文件、`HX_INVENTORY.csv` 与 `AGENTS.md` 一行。

## 11. 调用计数与收尾复核

| 项 | 结果 |
| --- | --- |
| 解算调用 | 0 |
| 评估调用 | 0 |
| 导入事故（单列，不并入上两行） | 1 起：`hext/matched.py` 部分导入至第 15 行（§9.1），三问均为否 |
| 子代理规则偏差 | 5 项，涉及 4 个子代理（#3 两项、#6、#10、#15），均未写文件、未调用二进制或评估器、未打开 trace/bag/fpl 参考轨迹数据（§9.2） |
| 受控入口检查 | 29 项：help_ok 17、import_ok 12（§3A；只表示检查跑完） |
| 冻结二进制/评估器 | 各做一次只读 sha256，均与登记一致（§1.3） |
| 封存表 sha256 比对 | 见 §1.2 两次比对 |
| 预存未跟踪文件 | 29 个，sha256 前缀在提交前复核与任务开始时一致 |
| 提交前 `git status --short` | 29 行预存未跟踪文件（§9.4，内容未变）+ 本任务 2 个新文件（`docs/paper_rebuild/hext/HX_INVENTORY.md`、`HX_INVENTORY.csv`）+ `AGENTS.md` 一行修改；除此之外为空 |
| 启动目录 `/home/kaiwen/research/LegSA-GINS` | `git status --short` 为空；任务开始后没有新建或修改任何文件（含 `__pycache__`） |
| 提交与 push | 提交号与提交前后的 git 状态在回报中给出（本文件无法记录自身所在提交的哈希） |
