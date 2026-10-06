# r2 文稿归因修订

最新可编辑稿为 manuscript_restructured_r2.docx，源文为 manuscript_restructured_r2.md。此次只修两个结构基线的解释，原V3源码、配置、结果与所有旧版r1文件保持。r2不包含新求解、重新评价或重新统计原科学指标。

## 实际差异与能够支持的结论

基础位置+航向EKF（内部F02）关闭接收机速度更新，走basic直接航向更新分支，实际固定航向标准差为2.933193°；不使用Scheme-C的观测标准差与残差降权、拒绝。航向门控位置/速度EKF（内部F03）开启RV，走Scheme-C航向处理，实际更新次序也不同。BY2的实际algorithm_id为strong_dual_yaw_EKF，BY2H/BY2O为AB0000；不能把配置中的algorithm_id当作无效元数据。

所以F02→F03是联合结构对比，差值不能分离归因于接收机速度，也不能单独归因于航向门控或航向噪声权重。两者仍然可以完整展示各自表现、支持与失败，数值不用撤换。注册表1.5°约定不等于六份历史运行中实际采用的2.933193°。F03保留的basic_std配置字段不表示其门控航向实际使用该固定权重。

同一门控骨架内，Proposed与无Doppler/无来源膨胀/无机器人倾斜/无机器人水平速度仍保持对应单组件开关定义。无Doppler配置仍有RV。修订没有把该四组对照变成F02/F03对照，也没有撤销原来的正负效应或失败分母。

## 修订位置与旧表述替代关系

- r2正文仅Sect.3.2第一段扩为两段，交代实际航向分支、固定权重与联合归因限制；Results、Discussion、Conclusions、References整段与r1字节一致。
- INTERNAL_READER_LABELS_R2.csv替代新稿中的旧标签表，追加Scheme-C与basic有效路由、实际固定sigma和三个自然序列的algorithm_id；旧CSV原样保留作为版本记录。
- 三份MAIN_FIGURE_PLAN_R2/MAIN_FIGURE_PANEL_PLAN_R2/05_MAIN_FIGURE_ARGUMENT_PLAN_R2仅修Fig5面板a标签与图注解释；8幅图、23面板、来源和评价scope保持。
- r2解释明确替代01_ARGUMENT_REFRAME_ZH.md中‘只按信息构成改名’的F02/F03段落：仅写位置/速度开关不足以描述真实分支。02术语候选与英文标题摘要未作RV独立归因，保持原文件；任何后续标签统一使用R2标签表。
- 旧52页蓝图的附录‘11×6开关表’不能当作有效分支的完整描述，应加入Scheme-C/basic算法路由。当前PPT由根代理修订，本文件不改已封蓝图或成品PPT。

## 证据与阅读范围

F02_F03_ACTUAL_NATIVE_EVIDENCE_R2.csv逐条保留六个实际manifest/config的路由、RV及三类航向计数；MANUSCRIPT_R2_CORRECTION_INPUT_IDENTITY.json封存12个小文件SHA。manifest读选定字段、config核选定路由与参数；没有将哈希读取、JSON解析称作raw逐字阅读。相邻figures/REVIEW_RV_CONFOUNDING_CORRECTION.md的独立核对给出实际配置与更早版本代码证据。

另选读既有原V3方法故事所声明冻结源码7d43b9a的GIEngine 382–421、955–980、1001–1021，确认basic return、门控更新、固定权重直接更新的语义；不以现行诊断源码回贴旧实验身份，不声称在本轮全读该文件。六份实际运行计数是归因判定的直接依据。

## Word核验与提交边界

LibreOffice实际渲染11页，逐张原分辨率查看：第5页联合结构解释与第10页Fig5图注完整可见，其余页面无缺字、溢出或不可读公式。Word保留6个可编辑展示公式、11个可编辑行内数学对象和4×7原结果表；11条参考文献保持。本研究稿仍为八幅主图的文本与图注稿，未因此宣称图像嵌入、作者信息或投稿材料已经齐全。

旧r1收据不回写；新Word/PDF、文稿差异、读者标签与图计划各有独立r2身份。所有原科学结果保持，新的图注只更正能由对照识别的归因范围。
