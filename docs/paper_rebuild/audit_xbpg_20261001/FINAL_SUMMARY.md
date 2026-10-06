# 本轮实质交付与未完成范围

**四段全量数据检查和首轮可执行GNSS-only全窗调用已完成；代码审查是有实证的部分交付，尚未完成全仓语义审查。** smoke技术失败、无解、输出损坏、timeout和异常回执已分开处理。没有把无解抹成成功，也没有用参考误差选择参数或安装关系。

## 一、代码究竟审查了多少

修订库存 **3,119文件、554,133物理行**（3,091个tracked与28个原worktree未跟踪代码/配置）。初始3,085项之后只追加遗漏的25个配置CSV/9个自有补丁，原已审标记和身份保留，未重跑inventory。

完整语义审查 **248文件、40,419行：文件7.95%，物理行7.29%**。其中已识别自有C++ **154文件/22,356行全部读完并逐函数/关键组审查**，另有两个CMake共111行；不是所有原生分支都动态测过。其余完整项覆盖raw_gnss全部38文件、共享传感器/关键输入、正式控制、部分评价与统计。冻结外部评价器421行另审；本轮新增36代码文件/3,957行另列，不加入原源码分母。

仍有 **14文件部分审查、40个既有测试文件仅动态执行/选定函数执行、2,817文件未读**，合计2,871文件未完成全文语义审查。完整缺口包含大量Python控制/生成/评价/绘图、测试、配置和历史自有代码。逐项见 [CODE_REVIEW_COVERAGE.csv](CODE_REVIEW_COVERAGE.csv) 和 [REMAINING_REVIEW_QUEUE.csv](REMAINING_REVIEW_QUEUE.csv)；不以“legacy”豁免，也不以全C++已审替代全仓完成。

正式身份已辨清：当前科学源eb3cbed；正式留存binary来自ca73cb，SHA256为96ae436d…；正式v3的F04仍为raw HPPOSECEF **标量航向**，B3关闭；F03=A02、F04=A01，不重复计数。F01有RV而F02没有，因此F01→F02→F03不是严格单项递增。二进制/配置/native echo/冻结评价器身份有实物核验，但全部历史provider的raw生成lineage和恢复评价身份仍未彻底闭合。

最重要的已确认问题：全GNSS失效时RD/RP/HV失去更新调度；SA NIS未用`dz−Hdx`；异步杆臂速度使用未补偿当前IMU；缺字段可能形成有效零观测；矩阵二维越界、wrap不返回及数值/IO防护；旧输出门接受截断时间支撑；恢复评价缺少NAV/方法身份强制绑定。条件风险包括倾斜下标量heading近似、共享源相关、传播/P-reset约定、v3新heading配旧HV源、非独立参考及测试集选择历史。B3雅可比错误、小pitch标量符号错误、v3必定丢失败分母等泛化说法已在明确范围内反证。

[CODE_AUDIT_REPORT.md](CODE_AUDIT_REPORT.md) 给出数学、调用链和上轮13项重新裁定；[FINDINGS.csv](FINDINGS.csv) 有128条裁定，含重叠、风险和反证，不能当128个独立严重bug。旧实验先做身份/时间支撑只读复核；调度、SA、倾斜和相关性结论需重新限定，确需改算法时另版本验证，不能覆盖旧表。没有证明所有旧NAV错误，也未重跑Canonical-541。

实际构建并执行完整port target，既有原生相关测试21通过，另有有限差分、真实config/file-loader、状态健康、超时/无效数值和已知噪声局部NIS/NEES测试。最终新增Python测试 **60 passed/59 strict-xfailed、exit0**；另一个既有合约测试组 **1 failed/9 passed/4 strict-xfailed、exit1**（旧7路径键断言与当前11键样例失配）。失败保留，重叠组不累加；不宣称全仓CI全绿或全21维NEES完成。

## 二、四段分别怎样

88个原始文件完整流式扫描，保留951,504,695字节身份、1,155,417条混合源记录及损坏位置；这不是独立样本数。完整4×4时间矩阵仅对角有交集，配对如下；Go2唯一时间戳平均约221–235Hz，不是500Hz独立IMU的证明。

|GNSS session后缀 / Go2|G1 RAWX时长/历元|RTKLIB完整输入调用结果|RD完整输入调用结果|完整LegSA/绝对误差|
|---|---:|---|---|---|
|12-25-13 / xb1|405.200s / 2027|exit0，0历元，0%覆盖，NO_SOLUTION|exit6，0速度，NO_USABLE_DOPPLER_SOLUTION|5主槽未资格；RMSE NA|
|12-33-29 / xb2|376.200s / 1882|exit0，7历元，0.371945%，仅1.2s；Q1=3/Q2=4|exit4，0速度，INPUT_NAV_READ_FAILED|5主槽未资格；RMSE NA|
|12-40-53 / xb3|351.399s / 1758|exit0，0历元，0%覆盖，NO_SOLUTION|exit6，0速度，NO_USABLE_DOPPLER_SOLUTION|5主槽未资格；RMSE NA|
|12-49-30 / xb4|356.000s / 1781|exit0，0历元，0%覆盖，NO_SOLUTION|exit6，0速度，NO_USABLE_DOPPLER_SOLUTION|5主槽未资格；RMSE NA|

S2的7点基线长度15.290–16.919m，中位16.306m，不能解释为可信机载短基线或body yaw。四段原始PVT均无双fixed；HP双位置差长度中位约11.26/14.10/14.94/35.18m。旧`.35m`、BY2安装角与杆臂均未移植。没有稳定连续的被测算法轨迹，不能把商业POI补成算法输出；4张真实数据/实际输出诊断图保留全窗和断线，PNG已图审，SVG及大文件在独立输出根，见 [FIGURE_INDEX.csv](FIGURE_INDEX.csv)。

**F01未运行的理由是Go2 IMU→GNSS APC/POI安装关系、采集时钟映射、初始heading基准未闭合；不是缺双fixed。** 现有tf/设备输出没有把Go2 body/IMU接到GNSS天线；时间交集不证明零偏/零延迟；接收机IMU身份不能换成Go2 IMU；商业姿态不用于参考初始化。其它主方法还缺正式v3所需heading输入。20个主槽全保留NOT_RUN_INPUT_UNQUALIFIED，没有暗降级F04。

现有RD helper实际只编译GPS/SBAS。S2 NAV无该helper支持的GPS/SBAS星历；S3最多2GPS+1SBAS、S4最多2GPS有星历，连不考虑健康/几何/残差的SPP必要输入上界都不足。S1有6颗GPS星历，1560/2027历元满足宽松候选数量条件，但仍无解，内部拒绝原因尚未全部归类。该补充只读诊断是post-hoc，零重跑；不能把当前编译能力与星历组合的失败推成原始多星座数据完全无用。

商业trace原始列与POI/INSPVAX已做全量对应，processed列有纬经/表示陷阱；它是共享GNSS/IMU的融合reference，非独立ground truth，且评价点/时钟未闭合。所有位置、速度、姿态RMSE/P95/max为NA，F04对照有限配对分母0、百分比NA。没有“降低覆盖换来精度改善”的证据；S2只证明极低覆盖的向量输出存在。内部观测尝试/接受/拒绝计数未由既有GNSS binary输出，保留UNKNOWN_INTERNAL，不拿输入历元数冒充更新次数。

四段可以支持自然GNSS退化与输入/同步/软件适用性诊断，目前不能支持完整F04精度、跨场景泛化或任何期刊精度达标主张。它们是同日录制，不当四个独立场地；历史调参/几何选择用途未知，不能保证盲测。

## 三、本轮推进、版本与最小续作

- 新增安全终端日志/CSV bytes/UBX/设备输出解析、全量质量/配对表；GNSS-only驱动、输出校验、独立失败和无解回执、完整分母汇总及真实图。8次convbin、1次RTK smoke、4次RTK full、4次RD full；真实LegSA=0、参考性能评价器=0。数据审查本身读取了4份trace，不能宣称全任务trace打开0。
- 先提交协议再运行；原始COMMAND及输出不改，追加校验回执绑定哈希。RUNS共37行，METRICS共28行；完整日志/轨迹/build留 `<AUDIT_ROOT>`/`<AUDIT_SCRATCH>`，共享路径只用ignored local config解析。
- 隔离候选只处理Matrix索引与wrap有限性，保存补丁并做正常输入回归；未装入正式solver、未用候选重跑XB。其它已发现问题未修。正式求解器、raw、冻结结果未修改；原worktree仍eb3cbed、tracked无改动，28个未跟踪代码/配置hash一致，29个未跟踪项仍在；原未跟踪文档未有起始hash，不虚称已做其字节前后证明。

|科学工作单元|提交|push状态|
|---|---|---|
|身份/覆盖基线|ee26e90cefb9d470ef74c5913d377a25065e35c9|成功，远端核验|
|原生数学反例与初始数据审查|e2ac8fe0b5e5b2fbc5a1559359cd598c0fb0582a|成功，远端核验|
|完整数据检查与冻结探索协议|2271d5a38a49aa957bbc3539244ec18ad7fa55ff|成功，早于首个新数据native|
|四段实际运行/失败/图与raw模块审查|e24d4735dd51724560f030275179d7e5efc19763|成功，远端核验|
|原生全覆盖、正式控制/合约与增量清单|9fa465a79f0f33d34eaf6603198317e8176728df|成功，远端核验|
|本综合报告/图谱/续作状态|包含本文件的提交，最终终端回执给SHA|push命令退出与远端SHA另记 `<AUDIT_ROOT>/GIT_RECEIPTS.jsonl`，不递归把提交写进自身|

分支 `audit/code-xbpg-20260105-20261001`。没有主分支合并、release、强推、历史重写、删除旧证据或ZIP交接包。没有开展三篇目标论文的新复现/全比较/稿件工作，仍保留其未完成状态。

最小续作按科学优先级：先在隔离候选验证调度/NIS/缺测与外层异常合同；只读绑定旧NAV/评价恢复身份与完整时间支撑；补此次安装/采集时钟证据后冻结F01迁移；RD多星座编译能力如需修正，应独立版本、合成回归和事前补充协议，保留本首轮失败；代码按剩余队列优先补formal_generation/clean5 provider chain及其控制依赖，再系统完成其它自有Python/配置/测试。只用 `update_coverage.py` 合并新人工回执，不重建inventory。可续作入口为 [STATE.json](STATE.json)；没有后台科学运行等待交付。
