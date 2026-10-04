# LegSA-GINS：保留原 V3 的 GPS Solutions 母稿与 TIM 后续条件

当前真实源是 manuscript_source.md 与 supplement_source.md；assemble_manuscript.py 生成可读稿。论文正式名 LegSA-GINS（source-aware dual-antenna GNSS/INS for legged robots），正文/图例不用 F04 等配置号，准确代码映射只在 S24。SDK body velocity 不是独立关节编码器腿部运动学。当前投稿范围仅 GPS Solutions 与 TIM。

作者保留的原 V3 是主科学版本：原源码7d43、二进制96ae，ca73是既有定义/文档锚点，三者不能混用。正文6.1–6.5、四主表与图3–6保留原全量矩阵/比较/区间；三自然窗航向为1.886272/1.933770/2.433815 deg。完整6468 native、283失败及两个评价点合同已在 S25 和原矩阵收据定位；原输入/结果没有修订或重跑。后来33自然/135受控、FGO和EXT是分别绑定的合同诊断/外部复现，不取代原方法选择，不把旧数改成新版本结果。

当前台账、正文/摘要词数、图表检查的准确数量见 FINAL_QA.json。正文计数排除图注、表格、标题、公式、摘要、声明/书目；官方约5000–5500词未明确排除规则，因此并非全篇提交长度认证。MS01_REPORT.md中9871词是旧2026-09-27稿，10256词是先前修订长稿，都不是当前母稿。最终仍需要Word与editable equations/tables、正式书目、作者材料和投稿版图像/Online Resources检查。

主文保留6图4表，S1–S18保留原配置、完整消融、全部失败/类型/离散、条件中断、外部适配、敏感性和既有不确定度诊断。S19明确保留模型近似；S20–S23独立后续队列；S24代码映射；S25版本/完整任务账本。Fig1加入作者授权原片，原JPEG字节未改；它仅记录可见装配，不证明器件身份、坐标/尺寸/接线/时钟或对应采集。图中RTK基线中位长度不是实测刚性phase-centre基线或其不确定度，不能替换EXT名义0.35m参数。

共有dual-yaw初始化、基础方法复合开关、固定六维scale协方差、RD/RV不同角色但同源相关、HV依赖prepared heading和GNSS全局调度、原scalar heading倾斜近似、原条件创新与disabled-sentinel边界均保留。后续135说明heading-preserved条件HV横向改善和V负结果，D61故障内无来源更新，D62无P/RV/RD新更新，RD全窗yaw44/45更差；不宣称独立断星桥接或每模块普遍改善。后续自然窗采用显式GNSS重启，不是无缝延续或单独IMU gap因果收益。

参考为Fixposition Vision-RTK 2商业融合输出，三个正式窗camera-used、wheel-not-used，估计器Go2机体IMU另一路但GNSS同记录血缘。因此写agreement，不写已证独立truth/厘米绝对accuracy。online-reference0只证明执行访问边界，不证明此前参数/方法选择对共享参考盲。厂家指标、设备covariance、fast residual、moving-block区间不能代替实体校准或完整可溯源不确定度；共用误差不能从两个RMSE直接扣除。

待作者提供实际安装/通道/固件与对应采集、测量坐标/杆臂/reference POI及误差、时标/延迟、SDK速度语义、作者/基金/利益/数据权限/AI声明。已核书目可以凭primary来源完成，不重复要求作者寻找可查事实。GPS/TIM差距、现有数据可补与必须实体测量的最小记录/接受标准见 docs/paper_rebuild/PAPER_IDENTITY_20261004/GPS_TIM_CLAIMS_AND_READINESS.md。两个官方预印本措辞冲突需实际投稿前向期刊确认，不能自行判拒稿或推断开源代码禁止。

可审查母稿当前 submission_ready=false。本块只改论文/文档/出版生成与检查，不调用科学输入生成器、native/evaluator、raw/reference，不改变原V3或后续封存科学数据。


2026-10-04 accepted 外部增补：S26 单独绑定三次新 OiSAM 序列分段尝试与六个原 Wen/GNC batch 身份复用，主动态支持275/267/370，初始化-only排除；原 strict H0/O55仍保留，不用分段填原缺测。名义参考投影仅复核原7689正式评分键（不是9100完整native有效baseline），九格RMSE最大变化0.004278deg，不能解释旧大误差；实体安装/ordering仍待量测。完整证据副本和不变性见 ACCEPTED_EXTERNAL_ADDENDUM_FINAL_RECEIPT.json；原V3数值/31旧表/6主图未改。正文计数仍仅排除项定义下的body，不认证官方全篇长度；submission_ready=false。
