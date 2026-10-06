import {c,addVenueSection} from './deck_venues.mjs';
const {base,text,table,figure,figureCrop,prose,source,caption,BLUE,REF,STORY,fs,path,REPO}=c;
// All continuous external figures precede venue interpretation.
for(const seq of ['BY2','BY2H','BY2O']) await figure(seq+'：载波方向的全窗误差',REF+`figures/block_06/R13_${seq}_raw_heading_error_support.png`);
await figure('载波约束：九组合误差与可用率',REF+'figures/block_06/R14_raw_heading_all_nine_accuracy_coverage.png');
for(const seq of ['BY2','BY2H','BY2O']) await figure(seq+'：FGO 全窗位置误差',REF+`figures/block_07/R15_${seq}_FGO_position_curves.png`);
await figure('FGO：连续、动态及含初值支持',REF+'figures/block_07/R16_FGO_dynamic_secondary_strict_support.png');
// Final block 08 contains the true saved GNSS1 trajectories and own Oi yaw.
const block8=path.join(REPO,REF,'figures/block_08');
const block8Names=(await fs.readdir(block8)).filter(x=>x.endsWith('.png')).sort();
if(block8Names.length!==4)throw new Error('Expected four reviewed block08 plots');
for(const f of block8Names){const seq=f.includes('BY2H')?'BY2H':f.includes('BY2O')?'BY2O':'BY2';await figure(f.includes('trajectory')?seq+'：FGO 的 GNSS1 轨迹':'OiSAM：自身航向的连续曲线',REF+'figures/block_08/'+f);}
await addVenueSection();
{
 const s=await base('附录：配置映射与单开关语义');
 table(s,[['内部 ID','论文显示名称','相对完整配置的变化'],['F04 / AB1111','Proposed','完整配置'],['A03','Without Doppler aid','仅关闭 RD；接收机速度 RV 保留'],['A04','Without covariance inflation','仅关闭来源协方差膨胀'],['A05','Without robot tilt prior','仅关闭 SDK roll / pitch 先验'],['A06','Without robot horizontal velocity','仅关闭 HV']],{y:164,h:404,widths:[227,493,452],font:23});
 caption(s,'内部标识用于追溯文件；不作为论文算法名称。');source(s,[REF+'story/INTERNAL_READER_LABELS.csv']);
}
{
 const s=await base('附录：结构基线与组合消融');
 table(s,[['内部 ID','论文显示名称','配置含义'],['F01','GNSS/INS EKF','无在线双天线航向；初始化仍共享双天线信息'],['F02','Position + heading EKF','RV 关闭；2.933193° 固定噪声直接航向更新'],['F03','Position/velocity + gated heading EKF','RV 与 Scheme-C 启用；无 RD / RP / HV / 来源膨胀'],['A07','Without robot priors','关闭 RP 与 HV'],['A08','Backbone + Doppler aid','骨架上只增加 RD'],['A09','Backbone + covariance inflation','骨架上只增加来源膨胀']],{y:154,h:454,widths:[150,506,516],font:23});
 source(s,[REF+'story/INTERNAL_READER_LABELS.csv']);
}
await figure('附录：原故障类型的多量纲图谱','paper_package/gpss_v0/figures/SFig02.png',{sub:'原图保留；空白代表无可用结果，原始尺寸版本随材料提供',sourceText:'Legacy original package figure. D01-D60 registered fault types, selected structural configurations; all 11 outcomes are separately provided in new R05-R08. Kept at original aspect ratio.'});
await figureCrop('故障图谱放大：水平、竖直与航向','paper_package/gpss_v0/figures/SFig02.png',{top:0,bottom:.505},{sub:'D01–D60；原图 (a)–(c)，三个色标分别对应各自量纲',sourceText:'Upper row of original SFig02; all D01-D60 rows preserved. Structural baselines are not pure receiver-velocity ablations.'});
await figureCrop('故障图谱放大：横滚、俯仰与三维位置','paper_package/gpss_v0/figures/SFig02.png',{top:.514,bottom:0},{sub:'D01–D60；原图 (d)–(f)，空白表示原图中没有可用结果',sourceText:'Lower row of original SFig02; all D01-D60 rows preserved. Color scales differ by measurand.'});
await figure('附录：接触辅助路线的相对结果','paper_package/gpss_v0/figures/SFig01.png',{sub:'作者核心与项目代理输入；相对规范对齐后的漂移',sourceText:'Project SDK foot/contact proxy rather than original joint forward kinematics. Relative/gauge-aligned drift; not absolute GNSS accuracy or same-input comparison. Failed initialization is retained.'});
await figureCrop('接触辅助放大：三序列位置漂移','paper_package/gpss_v0/figures/SFig01.png',{top:.108,bottom:.45},{sub:'原图 (a)–(c)：每 100 m 的位置漂移；保留初始化失败',sourceText:'Gauge-aligned relative position drift. Project SDK foot/contact proxies are not original joint forward kinematics.'});
await figureCrop('接触辅助放大：三序列航向漂移','paper_package/gpss_v0/figures/SFig01.png',{top:.587,bottom:0},{sub:'从左到右 BY2 / BY2H / BY2O；每分钟航向漂移（°）',sourceText:'Original panels (d)-(f), gauge-aligned relative heading drift. Project proxy input and initialisation failures retained.'});
{
 const s=await base('附录：横向比较的保留边界');
 table(s,[['路线','保留的条件或问题','本轮处理'],['两接收机 IEKF','BY2H 几何审查未通过；调参版单列','原运行不重跑'],['RTKLIB moving-base','四种配置 × 三序列；保留 native 与 hold 差别','仅重绘原结果'],['接触辅助 InEKF','SDK 代理输入；相对 gauge 评价','不称完整传感器级复现'],['GINav SPP/INS','部分对准失败或有效输出很少','保留失败，不改成零误差'],['文献与模块数量','读者身份 / 模块对照 / 实际作者核心各自计数','不说 30 篇完整复现']],{y:159,h:418,widths:[265,555,352],font:23});
 source(s,[STORY+'04_COMPARISON_INVENTORY_AND_FAIRNESS_STORY.md']);
}
{
 const s=await base('附录：结果的时间与版本身份');
 table(s,[['结果层','科学身份','与当前报告关系'],['原 V3 全量矩阵','冻结代码、输入和评价合同','主结果；全量读取、数值不改'],['EXT 九次修订运行','传播时间 / 时钟跳变修正后的已封存版本','原始方向与缺测完整展示'],['IMU / 条件辅助诊断','新缺测与辅助合同；33 + 135 成员','解释边界，不回贴旧矩阵'],['FGO 严格连续','真实连续失败及前缀支持','保留原终止结果'],['FGO 分段动态主结果','3 新 Oi + 6 重用 Wen/GNC 身份','段间重新初始化，排除 prior-only']],{y:164,h:408,widths:[276,444,452],font:23});
 source(s,[STORY+'CURRENT_STORY_INDEX.md','docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/README.md']);
}
{
 const s=await base('附录：GNSS 几何与验证文献');
 table(s,[['作者 / 年','研究主题','DOI'],['Teunissen / 2010','Integer least-squares theory for the GNSS compass','10.1007/s00190-010-0380-8'],['Verhagen & Teunissen / 2013','The ratio test for future GNSS ambiguity resolution','10.1007/s10291-012-0299-z'],['Farkas, Rózsa & Vanek / 2024','Quaternion constrained AR and dynamic synchronization','10.1007/s40328-024-00441-2'],['Zaminpardaz & Teunissen / 2019','DIA-datasnooping and identifiability','10.1007/s00190-018-1141-3']],{y:179,h:360,widths:[324,478,370],font:23});
 source(s,[REF+'venue/PRIMARY_LITERATURE_AND_CLAIM_MAP.csv']);
}
{
 const s=await base('附录：测量与状态估计文献');
 table(s,[['作者 / 文件','使用范围','DOI / 标准号'],['Cucci 等 / 2023','随机标定、导航性能与不确定度验证','10.1109/TIM.2023.3267360'],['García Crespillo 等 / 2023','时间相关误差的模型与界','10.1109/TAES.2023.3242943'],['Hartley 等 / 2020','接触辅助 invariant EKF','10.1177/0278364919894385'],['Solà / 2017','四元数与误差状态约定','arXiv:1711.02508'],['JCGM GUM / VIM','被测量、联合传播、覆盖与术语','100 / 101 / 102 / 200']],{y:165,h:403,widths:[324,456,392],font:23});
 source(s,[REF+'venue/PRIMARY_LITERATURE_AND_CLAIM_MAP.csv',REF+'story/manuscript_restructured.md']);
}
{
 const s=await base('附录：图优化原文与复现记录');
 table(s,[['方法','论文标识','记录位置'],['OiSAM','10.1186/s43020-025-00173-w','FGO_COMPLETE_AUDIT_20261004'],['Wen 紧耦合 GNSS/INS','10.1002/navi.421','同目录及 local_instantiation_scripts'],['GNC 鲁棒 GNSS','10.1109/TVT.2021.3130909','同目录；SEGMENTED_RESULTS']],{y:220,h:270,widths:[310,464,398],font:24});
 text(s,'三篇原文对应、工程差异、运行与评价表均保留。\n完整信息见讲者备注和配套文档；本报告不把模块对照等同于完整作者实验复现。',73,539,1124,83,26);source(s,['docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/README.md']);
}
await prose('讨论：下一项最值得验证的问题',['GPS Solutions：\n短基线的几何、时间与状态，能否预测航向辅助可用域？','TIM：在共享输入与姿态依赖下，量测模型能否在独立数据上给出可信区间？','载波新方向：带几何与时差不确定度的准入，能否改善可用率与可靠性的折中？'],{end:'先固定问题、量和验证标准，再增加实验。',paths:[REF+'venue/RESEARCH_QUESTIONS_AND_MAIN_FIGURE_PLAN.csv']});
export {c};
