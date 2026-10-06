# 专门绘图对话的接手说明

本轮按作者要求暂不重绘。以下交接说明目前两刊稿件需要什么，以及数据从哪里取得；它不表示现有图样已经符合作者期望。

## 入口与任务边界

- GPS正文：[manuscript_gps_solutions_r3.md](manuscript/manuscript_gps_solutions_r3.md)；TIM正文：[manuscript_tim_r3.md](manuscript/manuscript_tim_r3.md)。同研究的两个备选写法，当前以GPS为主。
- 八张主图的论证/面板/图注：[MAIN_FIGURE_PLAN_R2.json](../JOURNAL_REFRAME_20261004/story/MAIN_FIGURE_PLAN_R2.json)。这是待制作计划，不是八张已验收新图。
- 32个既有图源的目录：[FIGURE_CATALOG.csv](../JOURNAL_REFRAME_20261004/figures/FIGURE_CATALOG.csv)。先按目录读取数值来源再设计；不要仅替旧图换颜色。
- 原V3数据/配置/指标索引：[CURRENT_STORY_INDEX.md](../V3_STORY_20261004/CURRENT_STORY_INDEX.md)。主结果保留原版本。
- 新横向身份与结果：[comparisons/README.md](comparisons/README.md)及67条[运行索引](comparisons/RUN_EVALUATION_INDEX.csv)。索引定位真实误差与输出文件，不必重新求解。

## 图应承担的论证

1. 实物平台与实际坐标/点位定义：经过干净裁切、标注和配套几何示意，明确天线、参考输出点与Go2 IMU。图像美化不能移动设备或猜测敏感中心；照片与示意分别标清。
2. 方法的信息依赖和接受条件：显示receiver heading怎样进入滤波、机器人速度怎样依赖航向/倾斜，避免只有模块名称堆叠的流程图。
3. 三自然序列的航向/位置时序和环境状态：单位、时间轴、共同支持、缺测和输出物理点明确。
4. BY2O局部区间与补集：保留挑选区间的回顾性身份，不能只画有利片段冒充整窗结论。
5. 全矩阵失败分母加完成样本分布：ECDF/尾部与发散/无初始航向同时呈现，588case不是独立采集数。
6. 真正单开关成对效应：水平改善和垂直/航向负效应均展示，原basic→gated的联合变化不写成单模块效应。
7. 原失效实验的heading保留/完全缺失：先显示可用源，再展示位置效果。135新诊断若使用，单独标版本。
8. 外部GNSS/FGO/接触方法按输入层与量定义对比：至少同时展示误差和支持，严格Oi与分段Oi分开。模块诊断不得列为完整论文方法。

TIM可另外用本轮[23项预算](sdk_and_metrology/INPUT_UNCERTAINTY_BUDGET.csv)做输入/依赖示意；未知U不能画成零或虚构误差条。实际实测预算未完成前，不制作看似已验证的覆盖率图。

## 安装图新证据

[安装报告](installation/INSTALLATION_EVIDENCE_REVIEW.md)与[作者事实](AUTHOR_CLARIFICATIONS_AND_SCOPE.md)优先于旧CAD占位图。相机朝前、结构一致已由作者确认。base→FP 0.275m是旧占位，不可标为实测；0.35m是名义天线间距，不是相位中心survey。原始照片仍为作者供给的实际安装照片，库中历史入口`paper_package/gpss_v0/assets/installation/author_installation_metadata.json`记录源身份；原件为桌面`3ea6720b5e477e28ce8bec9d475423f5.jpg`。机械源位于作者供给的“机器狗背部拓展”目录，供给Go2_URDF.zip的模型身份见本轮安装manifest。

新八段实际POI/VRTK identity只能用于这八段，不回贴旧BY2/H/O。不要把URDF link框架、设备图示原点或CAD零件中心画成已经测量的IMU/天线敏感中心。

## 绘图交付验收

每个面板保存来源表/真实run identity、物理量和点、支持/原分母、绘图脚本及矢量文件；导出后按期刊实际栏宽查看。数据变换如插值、降采样、区间选择与reference运输必须明确，不能因为曲线难看而换窗。缺测应断开，hold与fresh区分，不平滑隐藏失效。图注需要读者独立理解，不使用只有项目内部知道的F04/EXT代码。

本轮Word只有八张计划图注，没有嵌入新制主图；版面QA没有替主图像素验收。绘图对话可直接继续制作，无需重跑原V3矩阵。改图也按作者要求分小块提交Git。
