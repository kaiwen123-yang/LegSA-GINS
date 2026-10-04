# GPS Solutions 压缩母稿及作者决定项（2026-10-04）

当前源文件是 manuscript_source.md 与 supplement_source.md，assemble_manuscript.py 生成可读稿。正文聚焦短基线航向准入、补充速度的可用条件与失效边界；数字与误差图仍属历史V3科学冻结ca73，不能改名为当前纠错版本。当前正文、摘要、台账及图表检查的精确计数以FINAL_QA.json为准。MS01_REPORT.md的9871词是原2026-09-27稿，先前修订长稿为10256词；两者都不是当前压缩稿。

主文保留6张图、4张表。S1–S10原证据保留；S11扩展自然窗及ladder，S12全部失败/离散与A1/A2，S13外部方法与控制故障，S14航向敏感性和不确定度解释，S15详细velocity/SA合同，S16故障族和heading-only分段支持，S17实际交付IMU时间间隔和参考输入血缘，S18既有F04/A06标量RMSE配对。Fig07/Fig08移作FigS3/S4，文件保持原历史图身份。主图2已将“leg velocity”改成真实高层机器人body-velocity来源，重新绘图并实际检视。

正文保持F01共有dual-yaw初始化；F02→F03同时改receiver velocity与gate，F03不含RP；21维表示不等于全部状态活跃；RD/RV不等于完整紧耦合或独立卫星误差；HV来自Go2高层状态并依赖外部status heading；F04−F03是复合改变。新增只读既有F04/A06对照更窄地支持A2条件下的HV switch贡献，尚无新原生机制回放或共同历元区间，不能替代纠错版本的复核。

参考是Fixposition Vision-RTK 2融合输出，与导航GNSS同session、Go2 IMU另一路；实际状态文件证实三个正式窗camera used、wheel not used。教程不证明实际连接、物理输出点、外参、固件或时钟关系；不能写“independent truth”。原厂家指标、内部covariance、fast residual以及moving-block区间不构成完整可溯源仪器不确定度。共同加性项一般不会从RMSE差严格抵消，未做方差扣除。

已关闭的文案/已有记录分析：删主系统“low-cost”贡献标签；IMU中位输出间隔约4ms而非把配置500Hz当实测；窗口有效记录率及7长间隔由锁定文件只读统计，文件哈希前后不变。N01倾斜侧向baseline不等Euler yaw、N12条件创新、N16活跃维metadata、IMU增量/时长纠错各有版本边界；新阶段合并多项改变，旧/新差不能归为单独gap收益。

还不能自动补造：实际硬件接线/序列号/固件/安装照片；measured lever和mount transform及误差；reference POI/topic/时标及独立性；作者/基金/贡献/利益冲突/数据发布权；新FGO、EXT、IMU stage的已验收结果。参考占位需要primary书目核验与author–year列表。正文计数排除图注/表格等，官方5000–5500“manuscripts”未说明排除规则；完整Word成稿须重新计数，不因body check通过就宣称符合全部长度要求。

完整审查与P0/P1/P2、最小实验及接受标准见G:/LegSA-GINS-project/修复_20261004/GPSS_COMPRESSION_READINESS_REVIEW.md。可读稿不是可直接投稿文件：GPS Solutions要求Word、editable equations、图像最终格式与Data Availability；当前submission_ready=False有意保留。
