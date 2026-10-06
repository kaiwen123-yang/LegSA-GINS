# 八张论文主图的完整图意和面板计划

原V3作为主证据；后续135、FGO分段、EXT物理量诊断用各自版本解释。一个figure承担一个主张，标准ESKF推导、dense external tables及版本收据进入SI。新计划未重绘这些主图，现图只作为可复用来源。

色彩与标签：Proposed蓝、两接收机IEKF橙、其他输入路线用稳定灰/青；正负效果不是红绿正确率。原codeID只出现在SI映射；每幅图caption明确量、物理点、支持和版本。图内英文文字建议最终印刷约8–10pt；PPT重排为24–28px标签，不直接把论文15面板缩小。优先SVG/PDF可编辑文字，照片保留raster。

## Fig1 A compact lateral baseline defines a conditional heading observation

**唯一主张**：平台的短侧向基线提供方向观测，但几何与物理点必须先定义。  **锚面板**：b。

- **a / definition**：作者供给机器人照片，标两天线/Go2IMU/商业融合装置位置，不由照片断言准确天线序号；来源 `paper_package/gpss_v0/figures/Fig01.png`, `paper_package/gpss_v0/assets/installation/author_installation_metadata.json`；身份 PHOTO_DECLARE_NOT_SURVEY。
- **b / methodological bridge**：FRD三轴与p1/p2/midpoint/IMU的3D示意；+90°侧向投影；来源 `docs/paper_rebuild/V3_STORY_20261004/02_METHOD_CONFIG_METRIC_STORY.md`；身份 ORIGINAL_V3。
- **c / failure domain**：水平投影b_H与倾斜图，投影方向、Euler yaw分别命名；r→0数学无定义；来源 `paper_package/gpss_v0/manuscript_source.md`；身份 CONCEPTUAL_NOT_EMPIRICAL_BOUND。

**英文图注草案**：Platform and heading geometry. (a) The supplied photograph shows the compact quadruped installation. (b) The fixed receiver order defines the lateral baseline and its relation to the IMU and evaluation midpoint. (c) Heading uses the horizontal baseline projection; an inclined lateral baseline does not generally yield Euler yaw without an attitude model. Nominal separation and declared lever arms are installation parameters rather than an independent survey.

**对应Results段**：A lateral baseline supplies heading information under a declared geometry and attitude domain.

**移至SI**：安装照片原件/作者声明、坐标/杆臂全字段；假设噪声敏感性U01另SI，不画实测U。

**视觉制作要点**：照片60%宽，几何40%；中点与IMU用不同符号；0.356m标RTK-derived median不当survey。

## Fig2 Measurement eligibility determines when auxiliary observations enter the estimator

**唯一主张**：辅助观测受不同准入与依赖条件控制，而非六个互相独立的输入。  **锚面板**：b。

- **a / definition**：IMU propagation+p/RV/yaw/RD/RP/HV输入图，15active+6fixed简标；来源 `docs/paper_rebuild/V3_STORY_20261004/METHOD_SOURCE_MAP.csv`, `docs/paper_rebuild/V3_STORY_20261004/02_METHOD_CONFIG_METRIC_STORY.md`；身份 ORIGINAL_V3。
- **b / claim-supporting definition**：heading exactpair→BOTH_FIXED→wrap gate；A1heading虚线→HV外部Ĉ；global GNSS入口AND→RP/HV；主面板占60%；来源 `paper_package/gpss_v0/manuscript_source.md`, `docs/paper_rebuild/V3_STORY_20261004/02_METHOD_CONFIG_METRIC_STORY.md`；身份 ORIGINAL_V3。
- **c / method definition**：R′=aR，maxmeta/innov与cap图；软硬门用简短piecewisekey；来源 `docs/paper_rebuild/V3_STORY_20261004/02_METHOD_CONFIG_METRIC_STORY.md`；身份 ORIGINAL_V3_ENGINEERING_RULE。

**英文图注草案**：Eligibility and aiding structure. Solid arrows carry measurement inputs, while dashed arrows denote preparation or dispatch dependencies. Heading requires exact receiver-time pairing, qualifying receiver status and wrapped-residual admission. Robot horizontal velocity is formed using the heading stream and SDK tilt, and robot aids are also subject to the GNSS update entrance. Covariance inflation remains bounded. The graph represents the archived configuration rather than independent information channels.

**对应Results段**：The proposed configuration makes heading and robot-aid eligibility explicit.

**移至SI**：标准ESKF/Joseph细式、完整状态/门限、七QAshape moduleanalogue及source-to-function表。

**视觉制作要点**：从左到右单向；来源颜色蓝GNSS/青SDK/灰传播，拒绝出口小灰叉；没有decorativebox或Git图。

## Fig3 Natural recordings show version-specific navigation agreement

**唯一主张**：三段自然实录的航向与水平位置agreement具有可见时间结构，不能只报一个平均。  **锚面板**：a–c。

- **a–c / claim-supporting evidence**：三序列有符号yaw差；Proposed与Two-receiver IEKF原曲线各网格；来源 `paper_package/gpss_v0/figures/Fig03.svg`, `docs/paper_rebuild/V3_STORY_20261004/NATURAL_METHOD_RESULTS.csv`；身份 ORIGINAL_V3_NATIVE_GRIDS。
- **d–f / complementary evidence**：三序列H误差原曲线；匹配/期望计数写caption；来源 `paper_package/gpss_v0/figures/Fig03.svg`, `docs/paper_rebuild/V3_STORY_20261004/NATURAL_METHOD_RESULTS.csv`；身份 ORIGINAL_V3_MIDPOINT。

**英文图注草案**：Navigation agreement in three natural recordings. Panels (a–c) show signed yaw discrepancies and panels (d–f) horizontal position discrepancies relative to the commercial fusion reference. Proposed denotes the archived LegSA-GINS configuration. Curves retain each method’s frozen matching support; paired statistics are reported separately. Reference and estimator share GNSS lineage, so the panels characterize agreement rather than independent absolute accuracy.

**对应Results段**：Natural recordings yield approximately two-degree heading agreement at the frozen midpoint contract.

**移至SI**：全部11配置natural66v2/v3分合同表、roll/pitch/Up/3D与共同时刻interval。

**视觉制作要点**：固定3列2排，统一time units和lineweight，局部尖峰不能被ylimclip；图例1个统一放外。

## Fig4 Regional yaw differences coexist with reversals outside the selected region

**唯一主张**：BY2O选定区域的优势与窗外反转同时成立。  **锚面板**：c。

- **a / case illustration**：BY2O yaw时间曲线，以淡色标primary/secondary且outside完整显示；来源 `paper_package/gpss_v0/figures/Fig04.svg`, `paper_package/gpss_v0/tables/T05_by2o_segments.csv`；身份 ORIGINAL_V3_POSTREVIEW_REGION。
- **b / definition**：区域状态支持/持续时间信息，不只突出最优区域；来源 `paper_package/gpss_v0/tables/T05_by2o_segments.csv`, `docs/paper_rebuild/V3_STORY_20261004/SELECTION_HISTORY_LEDGER.csv`；身份 REGION_SELECTION_DISCLOSED。
- **c / paired evidence**：primary/secondary/outside成对yaw ΔRMSE interval，legend定义A−B；来源 `paper_package/gpss_v0/tables/S09b_paired_intervals.csv`；身份 EXISTING_PAIRED_MBB_NOT_NEW_BOOTSTRAP。

**英文图注草案**：Regional comparison in BY2O. (a) Signed yaw discrepancies retain the full recording, with primary and secondary intervals marked. (b) Region definitions and receiver-state context distinguish the selected interval from its complement. (c) Existing paired intervals summarize common-support differences, including the outside-region reversal. Region selection used the recorded sequence and is not an independently prespecified held-out evaluation.

**对应Results段**：The selected region supports a local difference, while its complement prevents a global ordering claim.

**移至SI**：区域敏感性全部窗、共同支持数、block参数/CI及相关性字段。

**视觉制作要点**：CI跨0要见0line；有bar不能冒充CI；state与motion共同变化，勿写fixed状态造成优势。

## Fig5 Finite-output distributions must be read with completion and failure outcomes

**唯一主张**：完整CORE的分布只有结合失败分母才能界定配置表现。  **锚面板**：c。

- **a / claim evidence**：yaw finiteECDF：Position+heading、Position/velocity+heading、Without inflation、Proposed；来源 `paper_package/gpss_v0/figures/Fig05.svg`；身份 ORIGINAL_CORE_541_CONDITIONAL_FINITE。
- **b / complementary evidence**：H finiteECDF同四配置；来源 `paper_package/gpss_v0/figures/Fig05.svg`；身份 ORIGINAL_CORE_541_CONDITIONAL_FINITE。
- **c / failure evidence**：四配置541分母complete/diverged/noinitialheading条，11全配置SI；来源 `docs/paper_rebuild/V3_STORY_20261004/FULL_MATRIX_OUTCOME_LEDGER.csv`；身份 ORIGINAL_CORE_FULL_DENOMINATOR。

**英文图注草案**：Controlled-case distributions and outcomes. (a,b) Empirical distributions of yaw and horizontal-position RMSE are conditional on finite completed outputs for the displayed configurations. (c) Completion, divergence and unavailable-heading initialization retain the original 541-case denominator. The proposed configuration completes 519 cases, with 13 divergences and nine unavailable initializations. Case placements reuse a recorded trajectory and do not represent independent field realizations.

**对应Results段**：The full CORE reveals finite performance gains together with nonzero failure boundaries.

**移至SI**：全部11配置ECDF/61类型heatmap、其他量纲与原全部588案例状态。

**视觉制作要点**：fail灰/红/纹理固定；ECDFlegend写nfinite/N541；无输出不得贴到x0。

## Fig6 Component effects differ across horizontal vertical and heading quantities

**唯一主张**：单组件信息加入的收益并不一致：水平收益可同时伴随竖直或航向负向。  **锚面板**：a。

- **a / paired claim evidence**：四单变量×H/Up/yaw等主要quantity的lower/higher计数；每格全pairedN；来源 `docs/paper_rebuild/V3_STORY_20261004/SINGLE_MODULE_PAIRED_DIRECTION.csv`；身份 ORIGINAL_CORE_SINGLE_SWITCH。
- **b / complementary definition**：同四组件meanΔ与medianΔ两个分开展示，不以mean颜色标胜负；来源 `docs/paper_rebuild/V3_STORY_20261004/SINGLE_MODULE_PAIRED_DIRECTION.csv`；身份 SAVED_SUMMARY_ONLY_NO_NEW_METRICS。
- **c / failure membership**：paired/one-sidedcomplete/bothfailed示意或小表；来源 `docs/paper_rebuild/V3_STORY_20261004/SINGLE_MODULE_PAIRED_DIRECTION.csv`；身份 ORIGINAL_DENOMINATOR_PRESERVED。

**英文图注草案**：Single-component effects on common completed cases. Lower and higher counts compare the full configuration with the corresponding one-switch ablation; missing membership is retained separately. Means and medians summarize the same saved paired differences. Robot horizontal velocity lowers horizontal RMSE in 472 of 519 pairs, while vertical RMSE is higher in 365 pairs. The counts are descriptive for dependent controlled cases, not independent-trial significance tests.

**对应Results段**：The ablations support conditional component effects rather than uniform all-axis improvement.

**移至SI**：56行全量direction/v2v3合同；组合关闭A07–09与同源标定/初始条件表。

**视觉制作要点**：所有四组件展示相反方向，慎用绿=成功；mean/median单位分别deg/m不能共用一条数轴。

## Fig7 Heading availability conditions robot-velocity aiding during outages

**唯一主张**：heading保留与全GNSS失效是不同信息条件，HV不能被描述为无条件续桥。  **锚面板**：a。

- **a / methodological bridge**：A1/D61与A2/D62故障窗P/RV/RD/yaw/RP/HV资格矩阵，画AND依赖；来源 `docs/paper_rebuild/V3_STORY_20261004/CASE_TYPE_STORY.csv`, `docs/paper_rebuild/V3_STORY_20261004/03_SELECTION_HISTORY_AND_FULL_MATRIX_RESULTS.md`；身份 ORIGINAL_V3_SCHEDULING。
- **b / claim evidence**：原ADD27A1全点whole-windowHlogscatter；来源 `paper_package/gpss_v0/figures/Fig06.svg`；身份 ORIGINAL_ADD_FULL_WINDOW。
- **c / validation under new condition**：原ADD18A2全点whole-windowHlogscatter；来源 `paper_package/gpss_v0/figures/Fig06.svg`；身份 ORIGINAL_ADD_FULL_WINDOW。

**英文图注草案**：Outage information conditions in the original addendum. (a) The masks distinguish simultaneous loss of position, receiver velocity, Doppler velocity and heading from position-related loss with heading retained; robot-aid eligibility follows the preparation and dispatch dependencies. (b,c) Whole-window horizontal RMSE retains all 27 complete-loss and 18 heading-retained cases. These scores do not by themselves describe in-outage updates, endpoint errors or recovery.

**对应Results段**：Robot-velocity aiding is conditional on surviving heading and update eligibility.

**移至SI**：135新合同fault/endpoint/recovery全量独立版本；actualGNSS-anchoraccepted账本，而非provider timestamp当更新时刻。

**视觉制作要点**：顶部资格matrix先读后两个散点，单位log尺度注明；不用fault-time图词描述wholewindow。

## Fig8 Availability accompanies angular agreement across observation routes

**唯一主张**：不同GNSS航向路线必须同时报告支持与角量，较差结果只属于所列条件。  **锚面板**：b。

- **a / comparison definition**：rawcompass3+RTKLIB4的input/core/adaptation简表，不混navRMSE；来源 `docs/paper_rebuild/V3_STORY_20261004/EXTERNAL_METHOD_STORY.csv`；身份 LATEST_EXT_V2_AND_RTKLIB_HX07R。
- **b / practical consequence**：3seqownvalid/expected支持条；held另hollowmarker不可混fresh；来源 `docs/paper_rebuild/V3_STORY_20261004/FROZEN_EXTERNAL_METRICS_OVERVIEW.csv`；身份 OWN_SUPPORT_ORIGINAL_DENOMINATOR。
- **c / conditional benchmark evidence**：同各method自身支持angularRMSE，与baselineprojection/Euler区别图注；来源 `docs/paper_rebuild/V3_STORY_20261004/FROZEN_EXTERNAL_METRICS_OVERVIEW.csv`, `docs/paper_rebuild/EXT_MEASURAND_20261004/README.md`；身份 CONDITION_SPECIFIC_NO_SOLVER_RANK。

**英文图注草案**：Angular agreement and output support for raw-observation compass and moving-base routes. Inputs and project adaptations are identified before the numerical results. Output counts use each declared formal window; held values are distinguished from fresh valid solutions. Angular metrics retain their declared projection-heading and reference-yaw definitions. Large discrepancies under this installation do not establish universal method inadequacy or a same-input solver ordering.

**对应Results段**：External angular results must be interpreted jointly with their observation contract and availability.

**移至SI**：LC01-S/EXT05C初始化、GINav H2/271、Hartleyrelative及strict/segFGO全部量纲/结果放SI，navFGO不能挤在heading榜中。

**视觉制作要点**：不要沿用旧Fig7的15面板大图当最新结果；支持条跟角差图并排，NA空框不是0。
