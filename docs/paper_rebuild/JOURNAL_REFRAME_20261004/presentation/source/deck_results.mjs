import * as c from './deck_main.mjs';
const {base,text,table,figure,prose,source,caption,chart,BLUE,REF,STORY}=c;
{
 const s=await base('三序列的主结果','Proposed；原 V3 冻结合同，位置评价点为声明的双天线中点');
 table(s,[['序列','水平 RMSE / m','竖直 RMSE / m','3D RMSE / m','航向 RMSE / °'],['BY2','0.097906','0.048996','0.109481','1.886272'],['BY2H','0.068362','0.045352','0.082038','1.933770'],['BY2O','0.054543','0.045859','0.071260','2.433815']],{y:198,h:274,widths:[176,249,249,249,249],font:26});
 text(s,'完整曲线用于观察瞬态与持续偏差；各量纲单独解释。',70,528,1120,71,31,BLUE,true);source(s,[STORY+'NATURAL_METHOD_RESULTS.csv']);
}
await figure('BY2：原始轨迹与参考路径',REF+'figures/block_02/R03_BY2_original_trajectory.png',{finding:'仅改变轨迹显示坐标系；不做轨迹拟合，也不改变原评价结果。'});
for(const seq of ['BY2','BY2H','BY2O']) await figure(seq+'：全窗位置与航向',REF+`figures/block_01/R01_${seq}_full_window.png`,{sourceText:'Original frozen V3 and historical LC01; each retains its own matching grid. BY2H LC01 geometry audit FAIL is printed in the plot. Not a fresh solver run.'});
for(const seq of ['BY2','BY2H','BY2O']) await figure(seq+'：三个姿态分量',REF+`figures/block_02/R04_${seq}_attitude_errors.png`,{sourceText:'All original stored roll, pitch and yaw error samples retained. No reconstructed missing H/O trajectory.'});
await figure('自然实录：全部 11 个配置',REF+'figures/block_01/R02_natural_all_11_configurations.png',{sourceText:'All 33 natural recording/configuration combinations; no best configuration selection.'});
await figure('区域结果与全窗结论', 'paper_package/gpss_v0/figures/Fig04.png',{sub:'BY2O；复用原结果图，图中 LegSA-GINS 对应本报告 Proposed',finding:'选定区域内的改善与区域外的排序反转同时保留；区域并非独立预注册验证。'});
await figure('航向准入：实际发生了哪些更新',REF+'figures/block_05/R12_BY2_native_heading_decisions.png',{sourceText:'All 1369 native heading events. Normal 1225, downweighted 123, rejected 21. Saved innovation field empty; no reconstructed residual curve.'});
for(const seq of ['BY2','BY2H','BY2O']) await figure(seq+'：接收机速度与航向策略的联合比较',REF+`figures/block_05/R11_${seq}_receiver_velocity_toggle.png`,{sourceText:'F02/F03 jointly change receiver velocity RV and heading treatment (direct fixed-sigma heading versus Scheme-C). This is a structural comparison, not a pure RV causal effect. Archived numeric curves are unchanged.'});
await figure('完整 CORE：典型误差与尾部',REF+'figures/block_03/R05_CORE_all_11_error_tails.png');
await figure('完整 CORE：四类单组件效果',REF+'figures/block_03/R06_CORE_single_module_paired_contrasts.png');
{
 const s=await base('同一组件对不同量可能有相反效果','原 CORE：仅统计双方均完成的配对案例，保持原分母');
 table(s,[['加入的信息','量','Proposed 更低','Proposed 更高','共同完成'],['机器人水平速度','水平 RMSE','472','47','519 / 541'],['机器人水平速度','竖直 RMSE','154','365','519 / 541'],['Doppler 速度','水平 RMSE','453','65','518 / 541'],['Doppler 速度','航向 RMSE','81','437','518 / 541']],{y:194,h:335,widths:[299,259,195,195,224],font:25});
 caption(s,'水平收益不能扩写成全部量纲、全部案例的统一收益。');source(s,[STORY+'SINGLE_MODULE_PAIRED_DIRECTION.csv']);
}
await figure('完整 CORE：成功与失败同报',REF+'figures/block_03/R07_CORE_all_5951_outcomes.png');
{
 const s=await base('失锁实验的两种信息条件');
 table(s,[['输入 / 调度','全部 GNSS 输入失效','保留航向的失锁'],['位置 / RV / RD','失效','失效'],['航向','失效','保留'],['HV 的姿态依赖','不再满足','依准备流有效性而定'],['机器人辅助更新入口','无独立入口','可由有效航向事件触发'],['原 ADD 案例数','27 × 11 配置','18 × 11 配置']],{y:158,h:419,widths:[361,405,406],font:25});
 caption(s,'两种信息条件共同解释失锁表现；不能把后者写成完全无 GNSS 导航。');source(s,[STORY+'03_SELECTION_HISTORY_AND_FULL_MATRIX_RESULTS.md']);
}
await figure('失锁扩展：全部 45 个案例',REF+'figures/block_03/R08_ADD_all_45_conditions.png');
{
 const s=await base('失锁时，保留哪些信息决定结果','原 ADD 的全窗口水平 RMSE 均值，不是故障窗内或端点指标');
 table(s,[['条件 / 配置','全窗水平 RMSE / m','解释'],['全部 GNSS 失效 · Proposed','14.4234','航向与依赖辅助同时受限'],['保留航向 · Proposed','0.18961','允许条件式机器人辅助'],['保留航向 · 关闭 HV','4.88065','水平速度在此条件下有贡献'],['保留航向 · 关闭 RD','0.18956','故障段没有接受 RD 更新']],{y:190,h:338,widths:[475,303,394],font:25});
 caption(s,'结论落在实际进入更新的信息上；有效文件行不等于已接受观测。');source(s,[STORY+'03_SELECTION_HISTORY_AND_FULL_MATRIX_RESULTS.md']);
}
{
 const s=await base('IMU 缺测：保留旧结果，说明新诊断');
 table(s,[['材料','已完成内容','解释边界'],['原 V3','H/O 共 7 段时域问题，涉及 22 个正式成员','原矩阵封存，数值不改'],['后续缺测处理','明确真实 gap；等待有效重新初始化','等待与无输出保留在分母'],['新诊断矩阵','33 自然成员 + 135 控制成员','多个合同项同时改变'],['因果解释','分开报告新旧输入和处理策略','不能把全部变化归因于单个 IMU 修复']],{y:184,h:371,widths:[220,499,453],font:24});
 caption(s,'缺测政策决定可解释的传播区间；不得跨未观测时段虚构惯性增量。');source(s,['docs/paper_rebuild/v3/IMU_CLAIM_SUBSET_20261004/README.md'], 'Source path is supplemented in final source index with the verified repository diagnostic documents. Original V3 is unchanged.');
}
await prose('横向比较回答什么问题',['同级位置解比较：两接收机 IEKF 及参数条件，完整保留初始化和几何定义。','原始观测比较：动基线与载波约束方法，同时展示有效输出、缺测和方向误差。','图优化比较：分别说明观测模型、连续或分段协议、自行估计的状态。'],{end:'差的结果属于已声明的数据与实现条件；其来源需要具体证据解释。',paths:[STORY+'04_COMPARISON_INVENTORY_AND_FAIRNESS_STORY.md']});
for(const seq of ['BY2','BY2H','BY2O']) await figure(seq+'：动基线方向与实际支持',REF+`figures/block_04/R09_${seq}_moving_base_error_and_support.png`);
await figure('动基线：全部四种配置的结果',REF+'figures/block_04/R10_moving_base_all_12_accuracy_coverage.png');
{
 const s=await base('载波约束比较：九次修订运行','修正信号传播时间和接收机时钟跳变；各方法自身有效历元');
 table(s,[['序列','C-LAMBDA / °','C-WLS / °','DD-KF / °','期望历元'],['BY2','85.015 / 980','85.180 / 961','79.932 / 541','1370'],['BY2H','89.127 / 1059','89.193 / 1029','63.995 / 467','1350'],['BY2O','81.273 / 1173','81.486 / 1210','103.754 / 269','1885']],{y:203,h:276,widths:[160,277,277,277,181],font:24});
 text(s,'单元格：航向 RMSE / 有效匹配数。\nQ / ratio 接受状态不能替代正确模糊度标签。',69,526,1145,81,27);source(s,['docs/paper_rebuild/EXT_MEASURAND_20261004/README.md',STORY+'FROZEN_EXTERNAL_METRICS_OVERVIEW.csv']);
}
{
 const s=await base('投影角与 Euler yaw 能解释大误差吗？','仅检验声明安装模型下的几何量差');
 table(s,[['名义几何检查','保存的结果','结论范围'],['投影角 − Euler yaw RMS','0.031°–0.044°','远小于 64°–104° 的比较误差'],['最大名义量差','0.454°','不能解释全部大幅失效'],['改用对应投影量后的 RMSE 最大变化','0.00428°','量定义仍需正确，但不是主要解释'],['两种检查支持域','正式匹配 7,689\n全窗原生 9,100','不同支持域，非覆盖率分数']],{y:184,h:350,widths:[469,285,418],font:24});
 caption(s,'下一步定位输入、轴向、天线次序及实际安装；不由差分数直接否定论文方法。');source(s,['docs/paper_rebuild/EXT_MEASURAND_20261004/README.md']);
}
{
 const s=await base('FGO：已实现的关键方法链');
 table(s,[['方法','已落实的关键结构','论文对应与工程差异'],['OiSAM','结构化 Givens、A-JSWR、Ceres 重线性化','论文选定支路；惯性点与输出点转换'],['Wen 紧耦合','伪距、运动及 AHRS/INS 关系','外部姿态信息；无自行估计航向成绩'],['GNC','GM 连续化、交替权重、原始 Doppler','输出位置；无独立航向状态']],{y:179,h:295,widths:[220,464,488],font:25});
 text(s,'实现、真实运行、适配差异及失败均分别记录。\n“关键链已落实”不能替代作者全部实验协议的逐项一致。',71,521,1137,91,27);source(s,['docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/README.md']);
}
{
 const s=await base('OiSAM：连续协议与分段协议');
 table(s,[['序列','单次初始化有效 / 期望','缺测分段数','分段主结果有效 / 期望'],['BY2','275 / 275','1','275 / 275'],['BY2H','0 / 271','3','267 / 271'],['BY2O','55 / 378（仅前缀）','7','370 / 378']],{y:205,h:271,widths:[171,373,223,405],font:26});
 text(s,'分段仅按已知真实 IMU 缺口；各段重新初始化。\n主结果排除 prior-only 输出，保留缺测分母。',74,531,1134,80,28);source(s,['docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/README.md']);
}
{
 const s=await base('FGO：自身支持下的位置结果','分段主合同；输出统一到 GNSS1 点；3D RMSE / m');
 table(s,[['序列','OiSAM','Wen TC','GNC'],['BY2','0.107594 · 275/275','13.654694 · 274/275','5.037039 · 274/275'],['BY2H','0.077222 · 267/271','14.360929 · 270/271','4.722683 · 270/271'],['BY2O','0.064826 · 370/378','19.016172 · 377/378','4.012433 · 377/378']],{y:208,h:274,widths:[158,338,338,338],font:25});
 caption(s,'RMSE 旁保留匹配 / 期望；输入和自身支持不同，不构成同输入求解器排名。');source(s,['docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/README.md']);
}
{
 const s=await base('FGO：航向成绩的可报告范围');
 chart(s,'OiSAM 分段主合同的自身航向 RMSE',['BY2','BY2H','BY2O'],[{name:'Yaw RMSE',values:[4.652921,2.534907,3.971789],fill:BLUE}],{y:194,h:346,yTitle:'°',max:6});
 text(s,'Wen TC 与 GNC 没有自行估计的航向成绩。\nOiSAM 的分段初始化与严格连续失败需同时披露。',71,563,1141,64,26);source(s,['docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/README.md']);
}
export {c};
