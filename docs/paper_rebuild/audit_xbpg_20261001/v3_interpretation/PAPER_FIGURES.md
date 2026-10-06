# 论文包十个图号与阶段图的区别

本轮只读 planner 实际打开 `paper_package/gpss_v0/figures/` 中 Fig01–Fig08、SFig01、SFig02 的全部十个 PNG，结合现有 FIGURE_MAP、图脚本和来源表阅读。没有把格式导出成功当作内容阅读，没有改原图。源关系 49 条见 `figures/PAPER_SOURCE_LINKS.csv`，实际查看记录见 `figures/PAPER_VIEW_RECEIPT.csv`。完整精度数字仍来自 CSV/JSON，未从图像反推。

## Fig01 与 Fig02：装置几何和方法流程

Fig01a 画 GNSS2 左、GNSS1 右的蓝色基线，橙色评价中点、黑色 IMU 和灰色杆臂；前向 X、FLU 左向 Y 与 FRD 的 −Y 必须分清。0.356 m 是既有中位数标注，不是本轮新测量。来源 HX05_PREREG 与 final_v23_parity_contract；示意图不能独立验证安装几何。**Fig01b 仍显示 [NEED: photo] 占位，实拍尚缺。**

Fig02 是惯性状态与量测流程，展示 raw dual 精确时轴、BOTH_FIXED、wrap/gate、RD、HV/RP、SA 权重。它没有统计分母，也不表示十一方法均启用所有模块；实际开关见 METHOD_CONFIGS。箭头只说明结构，不能证明某次故障内 HV 已接受或 SA 引起精度变化。

## Fig03：三序列误差时序

三列分别 BY2/BY2H/BY2O，横轴时间，纵轴 yaw error（°）和 H error（m）。F04 橙实线、LC01 蓝虚线；BY2O 灰底保留原 primary/secondary 区间。F04 来自三个正式 v3 gzip，LC01 来源沿 CLEAN5/H_EXT_02/H_EXT_03 的既有链，两个方法的匹配时间网格不完全相同。

图能显示误差随时间变化，不能把两条曲线的全支持 RMSE 当成共同有限 paired RMSE。F04 的保留误差已按本轮同一次主扫描读取；本图未新增原始参考评价或轨迹重建。LC01 的当前展示身份保持原始起点及协议，不以更晚外部结果替换。

## Fig04：BY2O 分段对照

a 是 primary 内 F04 与 LC01 的 yaw-error 时序；b 是 primary/secondary/outside 的 yaw RMSE。F02 黄、F03 浅蓝、A04 粉、F04 橙、LC01 蓝纹理；A04 的颜色与阶段图不同，不能跨图靠颜色自动关联。

源 BY2O_SEGMENT_TABLE 中 F04 primary=0.2325140820805299°、secondary=1.861542194198912°；LC01 分别 4.008201405335621°、6.174020555087572°。outside 的 LC01 更低。柱不是 CI，支持数不完全相同；full 与 inside_union 仍需在原五段表看。本轮不据此重新选择主段；R5/R5F 既有选择用过此序列。

## Fig05：四个配置的有限 ECDF

横轴 case RMSE，纵轴有限 case 累积比例，只画 F02/F03/A04/F04，有限数 498/512/513/519、失败数 43/29/28/22，注册各 541。它没有 F01，也不是全部十一配置。

F04 的有限 yaw P95 低于 F03，H P95 却更高；失败集合不同，不能把单条 ECDF 左移推广为“所有案例整体更鲁棒”。直接源为 CORE_541_DISTRIBUTION_V3 的 metric/method/ordered_rank → value/ecdf，以及 CORE_541_SUMMARY_V3 的有限/失败数（figures/scripts/fig05.py 3–10 行）；上游按 case 关联，各族完成 2×2 和失败原 token 见 `core/`。

## Fig06：A1/A2 时长散点

横轴中断秒数，纵轴为对数尺度的**全窗 horizontal_rmse_m**，F03/A04/F04 每时长九个种子点；水平微小偏移仅用于避让。A1 各法 27 点、A2 各法 18 点，合计 135 个显示点；全部十一法实际 495 个 native，两个 evaluator 视图不倍增实验数。

A2_30s 未注册。图不是故障期间最大误差、终点误差或新恢复时间图。A2 保留 heading，不能称完整 GNSS 拒止；A1 27/27 完成不代表误差可接受。按时长的全部配置及真实窗口支持见 `addendum/`。

## Fig07：HX05 的多种输出类别

此图复制 **HX05/FIG02S**，不是 `<V3_ROOT>/08_FIGURES/FIG02S`。有 heading-only 的有效率/航向误差、navigation 的 yaw/H、relative pose 的漂移等面板，不能以同一 accuracy 排名混合。

MAIN.01.BY2 heading 可用数 980/1370=0.7153284671532847，yaw=120.36002862722869°；EXT04 FAR/PAR 没有有效 heading，NA 不是零。GINav 在 BY2/BY2O DIVERGED，BY2H 只有 2/271 个窗口期望点；其 matched/output=2/2=1 不是全窗覆盖，yaw=11.662263303395555°、H=2.894928083236164 m 只描述两点。F04/F02/F01 是 A 层已计数引用，不再加 native。

来源 EXTERNAL_THREE_SEQUENCE_MANUSCRIPT 与 SOURCE_CITATIONS 的 MAIN.*.sequence；具体 start、output_type、输入约束和验证身份见 `EXTERNAL_AND_SENSITIVITY.md`。后续 HX07R 未替换本图旧 RTKLIB 行。

## Fig08：外部退化子集

复制 HX05/FIG02D，九个选定外部族，LC01/F02/F04，yaw/H/up 采用对数尺度。柱为有限 case median，上须为 P95，**不是 CI**。来源 HX03R2_AUDIT_REEVAL 的 DEGRADATION_EXTERNAL_TABLE_R2 及 HX05 DEGRADATION_MANUSCRIPT；不是 CORE 八族的全集。

LC01 position-noise 为 0/18 完成并 DIVERGED；D57 的 F02/F04 零有限用灰叉表示，不赋值 0。F04 此处 position-noise H median=1.2624288869293778 m、P95=1.9402875087451732 m，18 有限；A2 H median=0.17667112573862742 m、P95=0.2877465570267067 m，18 有限。不同保留时轴/失败子集不能靠图消除。

## SFig01 与 SFig02：相对位姿与内部热图

SFig01 复制 HX05/SFIG-HX：Port-S、Port-LIT、Official-LIT、Official-DEF、LEG-DR 五类相对位姿，横向区分序列，纵轴为位置漂移 m/100m 与有符号 yaw 漂移 deg/min。Port 在 BY2H 初始化停止，无柱不等于零；Port 身份仍 UNVALIDATED_PORT。LEG-DR BY2 的 0.06942580845419305 m/100m 是既有 OLS slope，BY2O yaw −0.37939114728288426 deg/min 是带符号斜率，不是负的绝对误差。低斜率不证明完整路径正确，也不证明输入弱参考独立。

SFig02 复制阶段 SFIG01，沿用五配置、D01–D60、有限均值、对数色阶、白色不可用的边界；没有新增实验。详见 STAGE_FIGURES。

## 两个历史 pin 保持并列

`figures/HISTORICAL_PINS.csv` 保存 READ_FILES.json 的 recorded pin 与上一轮实际读取 current pin。AGENTS 与 FIGURE_MAP 的历史 SHA 均不等于当前字节；当前两个 worktree 的小文件字节曾核实一致。旧 FIGURE_MAP 的具体字节未取得，因此不能定位旧图号哪一行发生变更，也不能由 hash 差异直接断言 PNG 数值变化或宣称无影响。

本轮对当前 11 行 FIGURE_MAP（Fig01 有两面板）逐项检查，十图说明保留 current 身份；不覆盖历史 pin。阶段 55 + 论文 49 = 104 条图关系涉及 48 个不同直接来源，48 个入口存在。入口存在不证明所有上游 NAV/STD 仍保留，也不是 104 项数值复算 PASS。

整个上一轮 1,065 条来源关系中，858 条 comparison_status 空白、134 条 SOURCE_READ_NO_NEW_DERIVATION、73 条 DISPLAY_ROUNDING_MATCH。后者是有唯一 CSV 单元格和舍入规则的核对；不能说“1,065 条都数值通过”。论文数字本轮识别的精度传播差异另见 CLAIM_EVIDENCE_MATRIX 与最终说明。
