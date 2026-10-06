# 同完整历史的输入诊断登记

仅以既有 V3 三序列的六个接收机原始 CSV 为输入，使用已登记的官方 convbin。
不调用导航、整数解算或评价，不读取参考。运行计划见 INPUT_AUDIT_PLAN.json。

1. 每个 raw 文件只读取一次，核已有原始哈希；按文件顺序提取完整 UBX 帧并校验。
2. 旧 LLI 表、六份完整 UBX、六份截窗 UBX 共 13 项全部绑定历史 SHA-256：
   LLI 表及截窗文件来自 DG01R/OUTPUT_SHA256.json；完整文件来自各 HX02 run 的
   OUTPUT_HASHES.json，并与 ARCHIVE_MANIFEST.json 交叉核对。计划逐项列出来源、条目和封存表哈希。
   没有以当前重新哈希冒充历史封存；tracked LLI 表的小文件副本已与旧封存值核对。
3. 每次执行对所有实际读取的输入记录 expected_sha256、actual_sha256、identity_equal，
   再校验；不一致立即停止并保留 STATE。与 HX02 完整 UBX 逐字节比较，同时核旧 OBS 身份；
   按旧窗口提取的 UBX 与 DG01R 截窗输入逐字节比较。
4. 同一官方 convbin、同一选项转换完整 UBX 一次，共六次，单次 120 秒上限，无自动重试。
5. science_equal 同时要求历元集合一致、全部已解析观测字段无差异、RINEX 头语义一致、
   科学记录正文一致。字段包含 C/L/D/S、载波 LLI/SSI，字段缺失也计差异。
   头语义包括各系统有序 OBS TYPES、首/末历元声明的时间系统及版本/观测解释记录。
   未声明的时间系统保留 null，不默认为 GPS；程序名、生成日期和注释不参与头语义比较。
   正文单独保留 science_records_byte_identical，不能用它独自推断科学一致。
6. 旧 15 个 LLI 事件逐项报告 full_history_equal 和 old_full_table_consistent，
   后者另汇总 all_old_lli_table_consistent。旧表定位的 +18 秒是原登记时标映射的逆变换，
   必须有 GPS 时间声明；不将 GPST 日历字段误读为独立 UTC 真值。
7. 所有差异保留，不因支持或数值不一致重新选窗口/改标志。
   COMPLETE / execution_complete 仅表示六项比较执行完成，不代表科学 PASS。
   科学一致性、旧表一致性、UBX 字节一致性均查看各自独立字段。
   若完整输入及输出均一致，只能解释被控制的转换/历史差异；
   不由此断言原始载波无物理偏差或整数一定正确。

转换是输入诊断，不增加正式方法结果。原始文件、HX02/DG01R 及 V3 不写入。
输出在 WSL 研究 scratch；小型差异表与回执提交研究分支。
