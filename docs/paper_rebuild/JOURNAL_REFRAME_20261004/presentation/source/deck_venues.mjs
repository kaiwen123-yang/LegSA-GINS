import {c} from './deck_results.mjs';
const {base,text,table,figure,prose,source,caption,box,connect,equation,BLUE,REF,STORY}=c;
// FGO and EXT continuous figures are appended by the final assembly immediately
// before this section. This file defines a deferred section to keep ordering explicit.
async function addVenueSection(){
await prose('现有证据支持的结论',['约 0.35 m 横向短基线提供方向线索，无需持续前进运动。\n可用性受几何、时间和状态约束。','自然实录、消融和失锁案例显示条件式收益，\n也显示负向效果和不可用边界。','现有结果支持已声明安装与输入条件下的应用结论。\n推广到新安装和新环境需要独立采集。'],{paths:[REF+'story/manuscript_restructured.md']});
{
 const s=await base('学术命名：先确定核心贡献','以下是讨论稿；主结果统一显示 Proposed，内部编号保留在追溯表');
 text(s,'建议采用描述性标题，暂不强造缩写',70,173,1120,55,33,BLUE,true);
 text(s,'Short-baseline heading and conditional velocity aiding\nfor quadruped GNSS/INS navigation',70,248,1120,102,31,BLUE);
 text(s,'中文：短基线航向与条件速度辅助的四足机器人 GNSS/INS 导航',70,384,1120,84,29);
 text(s,'可讨论的侧重：观测准入（SQ-GINS）／航向条件辅助（HRV-GINS）。\n最终名称要对应真实机制；不暗示内部 AR、接触运动学或已校准完整性。',70,526,1120,94,26);source(s,[REF+'story/02_PROVISIONAL_NAMES_AND_TERMS.md'],'Descriptive title proposed for author discussion, not a finalized algorithm rename.');
}
{
 const s=await base('GPS Solutions：当前最有证据的主线');
 table(s,[['研究问题','主要证据','需要强化的论证'],['短基线何时能提供可用航向？','时间、fixed 状态、残差准入；三序列与故障谱','实体几何、倾斜适用域与实际时间关系'],['速度辅助何时产生信息增量？','RV / 航向联合结构比较、RD/HV 配对与失锁','共享来源与航向依赖；保留负结果'],['当前方法相对已有路线的意义？','同级 IEKF、动基线、载波与 FGO 条件比较','同输入主张边界和真实适配说明']],{y:192,h:358,widths:[367,406,399],font:25});
 caption(s,'以可验证的 GNSS 问题组织贡献；该刊并不要求每篇论文都提出新 AR。');source(s,[REF+'venue/GPS_SHORT_BASELINE_MOVING_BASE_DECISION.md','https://link.springer.com/journal/10291/aims-and-scope']);
}
{
 const s=await base('三种“短基线”处理不能混称');
 table(s,[['层次','实际解算对象','当前 V3 的关系'],['上游 RTK 固定解','接收机内部的位置与模糊度','使用其位置及状态输出'],['两个位置解作差','共同历元的基线向量与投影方向','本文现有航向构造'],['moving-base / 约束 AR','相对载波模型、float ambiguity、整数候选及验证','外部比较或未来独立研究']],{y:208,h:295,widths:[322,439,411],font:26});
 caption(s,'“两端 fixed”是准入状态；它不等于本算法提出并验证了整数求解。');source(s,[REF+'venue/GPS_SHORT_BASELINE_MOVING_BASE_DECISION.md']);
}
{
 const s=await base('若转向载波与 moving-base，需要新增什么');
 const a=box(s,'原始码 / 载波 / Doppler\n信号、星历与时间身份',57,187,349,99);const b=box(s,'相对观测模型\nfloat 解与联合协方差',467,187,349,99);const d=box(s,'整数搜索 / 验证\n拒绝与重初始化',877,187,345,99);connect(s,a,b);connect(s,b,d);
 table(s,[['新增证据','验证内容'],['实体基线与安装轴','独立量测、误差来源和适用域'],['同步与动态条件','真实偏移 / 漂移 / 延迟，旋转和运动影响'],['公平载波层比较','同信息、同初值、同物理点、全部尝试和失败'],['独立正确性标签','错误固定、可用率、复固定时间和延迟']],{y:354,h:258,widths:[356,816],font:24});
 source(s,[REF+'venue/GPS_SHORT_BASELINE_MOVING_BASE_DECISION.md'],'Future research design, not executed results.');
}
{
 const s=await base('载波研究的文献基线');
 table(s,[['已有工作','已解决的问题','本项目应进一步回答'],['Teunissen 2010','基线长度约束的整数最小二乘','几何不确定时的实际可用域'],['Verhagen & Teunissen 2013','模型相关的模糊度验证与失败率','真实环境偏差、标签和验证域'],['Farkas 等 2024','四元数约束 AR 与动态同步','短横向基线、相关输入和独立验证'],['近期 ambiguity validation','困难环境中的验证特征与方法','相对已有方法的实质差异']],{y:184,h:368,widths:[336,400,436],font:25});
 caption(s,'加入长度约束、INS 或 Monte Carlo 本身，均不足以单独作为创新。');source(s,['https://doi.org/10.1007/s00190-010-0380-8','https://doi.org/10.1007/s10291-012-0299-z','https://doi.org/10.1007/s40328-024-00441-2','https://doi.org/10.1186/s43020-026-00216-w']);
}
{
 const s=await base('论文主图 1–4：从问题到真实结果');
 table(s,[['主图','科学内容','图所支持的主张'],['1','实物、基线几何、物理点与投影角','定义短基线方向观测及适用域'],['2','观测准入、辅助依赖与滤波结构','说明信息何时进入估计器'],['3','三序列位置与航向连续曲线','展示自然实录的完整时间结构'],['4','区域内 / 区域外的配对结果','局部改善与排序反转同时存在']],{y:188,h:360,widths:[138,545,489],font:25});
 caption(s,'一张主图承担一个主张；正文采用少量关键证据，完整结果进入补充材料。');source(s,[REF+'story/05_MAIN_FIGURE_ARGUMENT_PLAN.md']);
}
{
 const s=await base('论文主图 5–8：机制、边界与比较');
 table(s,[['主图','科学内容','图所支持的主张'],['5','误差分布 + 成功 / 失败分母','完成样本中的收益不掩盖失败'],['6','四组件配对：水平 / 竖直 / 航向','同一组件的效果依量和条件而变'],['7','失锁信息条件 + 全部案例点','机器人速度辅助取决于航向与调度'],['8','角误差 + 原生可用率 + 输入层次','比较结论落在具体观测合同上']],{y:188,h:360,widths:[138,545,489],font:25});
 caption(s,'标准 EKF 推导、完整矩阵、FGO 全部协议与复现差异进入补充材料。');source(s,[REF+'story/05_MAIN_FIGURE_ARGUMENT_PLAN.md']);
}
{
 const s=await base('GPS Solutions：稿件结构与篇幅');
 table(s,[['部分','组织方式'],['Introduction','低速 / 倾斜下短基线航向问题 → 现有研究 → 两个研究问题'],['Methods','物理量与安装 → 准入条件 → 条件速度辅助'],['Results','自然实录 → 配对消融 → 失效边界 → 条件横向比较'],['Discussion','信息依赖、相关参考与推广范围'],['投稿格式','全文约 5,000–5,500 词；摘要 150–250 词；4–6 关键词']],{y:165,h:399,widths:[305,867],font:25});
 caption(s,'英文重构草稿已形成；提交前还需最终主图组装、完整参考文献和实体信息核定。');source(s,[REF+'story/manuscript_restructured.md','https://link.springer.com/journal/10291/submission-guidelines']);
}
await prose('TIM：把研究对象落到“量”上',['明确被测量：投影方向、Euler yaw、指定点的速度和位置分别定义。','建立测量模型：几何、时间、坐标变换、共同来源及交叉协方差进入传播。','验证不确定度：使用独立或相关性可识别的参考，检查未参与拟合的数据上的区间覆盖。'],{end:'现有 RMSE 和工程协方差不能直接改名为测量不确定度。',paths:[REF+'venue/TIM_MEASUREMENT_MODEL_AND_VALIDATION_PLAN.md','https://ieee-ims.org/publication/ieee-tim/information-authors']});
{
 const s=await base('TIM：短基线的相关误差传播');
 await equation(s,'baseline_cov',72,164,1130,71);await equation(s,'heading_jac',72,279,1130,64);await equation(s,'heading_cov',72,388,1130,67);
 text(s,'C 表示误差协方差；角度以 rad 表示。\n相关误差可在作差时抵消；短水平投影会放大方向敏感度。',73,529,1125,92,28);source(s,[REF+'venue/TIM_MEASUREMENT_MODEL_AND_VALIDATION_PLAN.md'],'Local first-order propagation; C12 denotes Cov(p1 error,p2 error). Angles in radians. Input covariance must be identified, not inferred from moving positions.');
}
await figure('解析示例：短投影与接收机相关性',REF+'venue/assumed_sensitivity/Fig_U01_projection_correlation.png',{sourceText:'Assumed analytical illustration only; 1 mm per-axis receiver position sigma, not measured project calibration. The 1-degree target is illustrative.'});
{
 const s=await base('TIM：时间偏差与安装误差');
 await equation(s,'timing',77,158,1110,58);
 text(s,'共同平移的一阶示例：Δt = t₂ − t₁；完整模型还含旋转与点位速度。',77,239,1110,53,25);
 table(s,[['来源','进入方向误差的路径','所需记录'],['接收机异步','运动 × 时间差改变位置差','共同事件、偏移、漂移、延迟'],['旋转与杆臂','不同点的速度和姿态变换','三维杆臂、安装角及其不确定度'],['相位中心与天线次序','改变几何模型、角度符号与偏置','设备型号、轴向照片和实测记录']],{y:323,h:276,widths:[272,441,459],font:25});
 source(s,[REF+'venue/TIM_MEASUREMENT_MODEL_AND_VALIDATION_PLAN.md'],'First-order translational timing illustration; full model also includes rotation and point-specific velocity.');
}
await figure('解析示例：短投影放大异步影响',REF+'venue/assumed_sensitivity/Fig_U03_asynchronous_direction.png',{sourceText:'Deterministic assumed geometry, V=1 m/s; not a measured clock error or standard uncertainty.'});
{
 const s=await base('TIM：姿态依赖的速度不确定度');
 await equation(s,'rotation',73,183,1135,83);
 await equation(s,'gum',73,317,1135,69);
 text(s,'δαᵇ：body 系右乘小角，单位 rad；Cᵦⁿ 为 body → navigation 旋转。\n联合误差协方差含交叉项；SDK、GNSS 与参考的共享信息不能默认独立。\n模型偏差与错误固定须单独描述，不能都表示为小高斯噪声。',73,454,1135,157,28);source(s,[REF+'venue/TIM_MEASUREMENT_MODEL_AND_VALIDATION_PLAN.md'],'Right-multiplicative body small-angle convention: C_true = C_nom Exp([delta alpha^b]x); velocities linearized about nominal values. Model describes measurement propagation, not an asserted mapping to native estimator PHI. Angles in rad; C_y and C_z are error covariance matrices.');
}
await figure('解析示例：交叉相关可改变速度不确定度',REF+'venue/assumed_sensitivity/Fig_U02_heading_velocity_cross_term.png',{sourceText:'Assumed sigma_v=0.05 m/s and sigma_heading=2 degrees; illustrative cross correlation sweep only.'});
{
 const s=await base('TIM：共享参考下的差值协方差');
 await equation(s,'difference',74,179,1120,66);await equation(s,'ref_cov',74,305,1120,80);
 text(s,'误差差值的协方差同时含估计端、参考端和交叉项。\n仅知道差值 RMSE，通常不能唯一拆出估计器本身的不确定度。\n未估计的相关项应标为未知；不能为了计算方便一律设为零。',74,451,1120,155,28);source(s,[REF+'venue/TIM_MEASUREMENT_MODEL_AND_VALIDATION_PLAN.md']);
}
{
 const s=await base('TIM：不确定度预算需要哪些输入');
 table(s,[['输入量','当前材料','仍需取得的证据'],['三维基线 / 杆臂 / 安装旋转','声明值及位置解统计','独立量测、工具与不确定度'],['接收机位置 / 速度误差','输出 accuracy 与质量字段','联合误差模型及时间相关'],['时钟与延迟','时间戳与软件配对','硬件事件、偏移与漂移'],['IMU 与 SDK','数据与有效工程参数','噪声标定、输出点、内部融合说明'],['商业参考','可用的融合输出','参考点、参考 U 与共享相关性']],{y:169,h:405,widths:[357,356,459],font:24});
 caption(s,'Type A / Type B 是评价方式，不是“随机误差 / 系统误差”的简单对应。');source(s,[REF+'venue/REQUIRED_RECORDS_AND_ACCEPTANCE.csv','https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf']);
}
{
 const s=await base('TIM：怎样验证模型可信');
 const a=box(s,'独立标定输入\n几何 / 时间 / 噪声',56,196,350,101);const b=box(s,'锁定测量模型\n传播联合分布',465,196,350,101);const d=box(s,'未参与拟合的数据\n覆盖与失效域',874,196,350,101);connect(s,a,b);connect(s,b,d);
 table(s,[['检验','报告内容'],['局部线性与非线性','短投影、倾斜和角度环绕的适用域'],['区间覆盖','预设名义覆盖率、实际覆盖及统计单位'],['错误固定与缺测','离散失效状态；不并入小噪声正态模型'],['推广验证','新采集 / 新安装 / 自然退化；保留反例']],{y:354,h:262,widths:[334,838],font:25});
 source(s,[REF+'venue/TIM_MEASUREMENT_MODEL_AND_VALIDATION_PLAN.md'],'Proposed validation plan, not completed coverage results.');
}
{
 const s=await base('两条投稿路线的推进顺序');
 table(s,[['优先级','GPS Solutions','TIM'],['当前完成','凝练条件融合主线、图表与科学草稿','明确被测量、10 个模型式与预算框架'],['首先补充','实体几何、时间与输入事实；完整论文图','标定输入、参考相关性与验证链'],['随后验证','未参与开发的新场景与可用条件','独立数据上的区间覆盖和失效域'],['应避免的主张','改名成新 AR；混输入排名','把 RMSE、R 或假设曲线当已校准 U']],{y:183,h:376,widths:[220,476,476],font:25});
 caption(s,'优先把现有论文写完整；新增测量或载波研究按独立协议积累证据。');source(s,[REF+'venue/GPS_SHORT_BASELINE_MOVING_BASE_DECISION.md',REF+'venue/TIM_MEASUREMENT_MODEL_AND_VALIDATION_PLAN.md']);
}
await prose('结论与下一步实质工作',['已有完整自然记录和控制矩阵，可以写出条件明确、正负结果并存的导航论文。','本轮已将方法机制、连续曲线、成功失败、比较协议及期刊问题系统连接起来。','投稿前重点补齐实体安装与参考测量证据；载波 AR 和校准不确定度属于需要验证的新研究。'],{end:'下面保留扩展结果、配置映射和文献，供完整讨论与追溯。',paths:[REF+'story/manuscript_restructured.md',REF+'venue/REQUIRED_RECORDS_AND_ACCEPTANCE.csv']});
}
export {c,addVenueSection};
