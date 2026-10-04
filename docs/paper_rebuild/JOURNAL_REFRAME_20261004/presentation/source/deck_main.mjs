import {fs,path,p,ROOT,REPO,REF,STORY,order,metadata,assets,tableOwners,chartOwners,BLUE,GREY,MUTED,FONT,text,base,photo,cover,box,connect,line,caption,table,figure,figureCrop,chart,prose,note,source,equation,PresentationFile} from './deck_engine.mjs';
await cover();
await prose('报告结构',['测量问题与方法：短基线航向、观测准入、速度辅助','完整实验证据：三序列、消融、失效与横向比较','论文推进：学术命名、GPS Solutions 与 TIM'],{end:'正文围绕科学问题，附录保留完整结果与实现条件。',paths:[REF+'story/PPT_CONTENT_BLUEPRINT_52.json']});
await photo(await base('实验平台与真实安装','Unitree Go2 四足机器人及顶部搭载装置'));
{
 const s=await base('机体航向与运动方向','低速、停顿和侧向运动时，速度方向不能直接替代机体朝向');
 table(s,[['运动状态','机体朝向','运动方向','导航信息需求'],['前行','随机体姿态变化','可近似一致','位置、速度与航向'],['停顿 / 原地转向','仍然存在并可变化','速度接近零，方向不稳定','保持可用的姿态约束'],['侧向 / 小半径运动','未必沿位移方向','与机体朝向存在夹角','区分 body yaw 与 course']],{y:184,h:280,widths:[240,300,330,302]});
 text(s,'短基线提供独立于持续前进运动的几何方向线索。',80,509,1110,65,33,BLUE,true);source(s,['paper_package/gpss_v0/manuscript_source.md'],'Conceptual motion comparison, not a new measured trial.');
}
{
 const s=await base('研究问题与验证路径');
 text(s,'航向观测的可用条件',72,173,1100,51,35,BLUE,true);text(s,'何时可以把双接收机位置差构成的方向，作为 GNSS/INS 的航向观测？',72,235,1120,72,29);
 text(s,'速度辅助的有效条件',72,350,1100,51,35,BLUE,true);text(s,'接收机速度、Doppler 速度与机器人水平速度，在何种失效条件下仍能提供信息？',72,412,1120,86,29);
 caption(s,'自然记录检验实际表现；完整配对消融和失效试验解释信息贡献。');source(s,[REF+'story/CLAIM_EVIDENCE_MAP.csv']);
}
{
 const s=await base('短基线几何与评价物理点','声明安装模型；示意图不按比例绘制');
 const a2=box(s,'GNSS 2\n左天线',670,219,173,91);const a1=box(s,'GNSS 1\n右天线',1005,219,173,91);connect(s,a1,a2,{from:'left',to:'right'});
 text(s,'b = p₂ − p₁',845,168,160,46,24,BLUE,true,'center');
 const imu=box(s,'机体 IMU',827,421,190,77);connect(s,imu,a1,{from:'top',to:'bottom',dashed:true});
 text(s,'杆臂 l₁',1030,374,172,46,26);
 text(s,'名义基线约 0.35 m',65,190,538,60,34,BLUE,true);text(s,'GNSS1 杆臂声明值\n[0.03, 0.03, −0.30] m（FRD）',65,283,535,106,28);
 text(s,'原主结果：声明的双天线中点\n新 FGO 比较：统一到 GNSS1 点',65,439,541,112,26);
 caption(s,'同一轨迹在不同物理点上的位置不可直接混用。');source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md','docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/README.md']);
}
{
 const s=await base('方法与输入层次','按实际进入估计器的信息解释外部比较');
 table(s,[['方法路线','GNSS 信息','惯性 / 机器人信息','主要输出'],['Proposed','位置、速度、位置差航向\nDoppler 速度','机体 IMU + SDK\n倾斜 / 水平速度','位置、速度、姿态'],['双接收机 IEKF','两端接收机位置解','机体 IMU','位置、速度、姿态'],['RTKLIB moving-base','两接收机原始观测','原生 GNSS 解算','基线与方向'],['载波约束方法','双差相位 / 码与整数结构','项目安装及状态模型','基线 / 方向'],['FGO 方法','按论文使用位置、伪距或 Doppler','方法对应的惯性 / 动力学链','位置；部分方法自行估姿']],{y:164,h:420,widths:[230,335,362,245],font:23});
 caption(s,'不同信息层次可比较实际表现，但不能作为同输入求解器的统一排名。');source(s,[STORY+'04_COMPARISON_INVENTORY_AND_FAIRNESS_STORY.md']);
}
{
 const s=await base('GNSS/INS 与多来源辅助结构');
 const g=box(s,'GNSS 接收机输出\n位置 · 速度 · 双位置差',57,177,313,100);
 const d=box(s,'原始 Doppler\n派生速度与质量量',57,344,313,94);
 const r=box(s,'机器人 SDK\n倾斜 · 机体水平速度',57,512,313,94);
 const ins=box(s,'机体 IMU\n惯导传播',476,165,302,89);
 const q=box(s,'观测准入与\n来源协方差膨胀',476,341,302,102);
 const ekf=box(s,'误差状态 EKF\n校正与反馈',915,302,298,110);
 const out=box(s,'位置 / 速度 / 姿态',915,515,298,81);
 connect(s,g,q);connect(s,d,q);connect(s,r,q);connect(s,ins,ekf);connect(s,q,ekf);connect(s,ekf,out,{from:'bottom',to:'top'});
 source(s,[STORY+'METHOD_SOURCE_MAP.csv',STORY+'02_METHOD_CONFIG_METRIC_STORY.md'],'Diagram depicts frozen original V3 information paths. Robot velocity depends on heading and SDK tilt; correlations addressed separately.');
}
{
 const s=await base('六类观测与真实来源');
 table(s,[['观测','输入来源','作用与条件'],['位置','GNSS1 高精度位置','以杆臂连接天线与 IMU'],['接收机速度 RV','GNSS1 NAV-PVT','接收机级速度观测'],['双天线航向','两端共同 iTOW 的位置差','双 fixed 状态、有效方向和残差准入'],['Doppler 速度 RD','RAWX + 卫星状态解算','派生速度产品；原配置至少 5 星'],['机器人倾斜 RP','Go2 SDK roll / pitch','二维弱先验'],['机器人水平速度 HV','SDK 机体速度经姿态旋转','依赖航向、倾斜和实际调度']],{y:149,h:469,widths:[240,405,527],font:23});
 source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md'],'RV and RD are different channels, not independent noise realizations. HV is not independently reconstructed joint kinematics.');
}
{
 const s=await base('基线投影方向与机体航向','原标量航向工作模型及其几何适用域');
 await equation(s,'baseline',73,169,1080,58);
 await equation(s,'heading',73,257,1080,62);
 await equation(s,'sensitivity',73,344,1080,62);
 text(s,'侧向安装与天线次序决定 90° 变换。\nbH 表示水平基线，δb⊥ 为横向扰动；线性式的 δψ 单位为 rad。\n水平投影越短，对相同扰动越敏感。\n倾斜时，投影方向与 Euler yaw 一般存在几何差。',73,456,1106,140,27);
 source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md','docs/paper_rebuild/EXT_MEASURAND_20261004/README.md'],'First-order heading sensitivity for small baseline errors. Not a new calibration result.');
}
{
 const s=await base('航向构造的时间与状态准入','使用接收机共同的整数 iTOW 时间键');
 const a=box(s,'两端位置\n时间精确配对',64,196,270,110);const b=box(s,'两端 carrier\n状态均 fixed',499,196,280,110);const c=box(s,'有效基线\n构造投影航向',934,196,282,110);connect(s,a,b);connect(s,b,c);
 table(s,[['条件','输出处理','含义'],['共同时间键且状态合格','形成当前航向观测','接收机位置解级准入'],['时间键缺失 / 不匹配','保持缺测','不插值成新的航向样本'],['接收机状态不满足','当前观测不准入','fixed 状态不是正确固定概率']],{y:383,h:218,widths:[376,356,440],font:23});
 source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md']);
}
{
 const s=await base('标量航向的残差门限','使用包角残差及标准差两类门限');
 await equation(s,'residual',74,164,1120,63);
 table(s,[['门限量','普通区间','软门区间','硬门'],['观测标准差','< 3°','[3°, 6°)' ,'达到 6° 拒绝'],['包角残差绝对值','< 6°','[6°, 15°)' ,'达到 15° 拒绝'],['观测协方差','使用当前 R','软区放大 2.5 倍','本次不更新']],{y:282,h:257,widths:[303,280,280,309],font:24});
 caption(s,'残差包含预测与测量的共同误差，需要结合运行条件解释拒绝事件。');source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md']);
}
{
 const s=await base('误差状态与惯导更新');
 await equation(s,'state',70,156,1138,71);
 await equation(s,'covariance',70,274,520,60);await equation(s,'innovation',693,274,520,60);
 await equation(s,'gain',70,392,520,60);await equation(s,'correction',693,392,520,60);
 text(s,'15 个活动误差状态；六个比例因子槽位在原配置中冻结为零。\n同一状态接收位置、速度、航向与机器人弱先验，协方差采用 Joseph 更新。',70,515,1138,93,27);
 source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md'],'Equations summarize inherited first-order ESKF. Exact residual sign and cumulative error-state update follow original source; not a new filter-theory contribution.');
}
{
 const s=await base('两条 GNSS 速度来源','RV 与 RD 的信息入口不同，统计误差可能相关');
 const raw=box(s,'GNSS1\n卫星与接收机观测',78,304,293,99);
 const rv=box(s,'接收机内部速度解\nNAV-PVT → RV',516,173,319,94);
 const rd=box(s,'项目 Doppler 后端\nRAWX → RD',516,458,319,94);
 const filt=box(s,'GNSS/INS\n速度更新',972,304,234,99);
 connect(s,raw,rv);connect(s,raw,rd);connect(s,rv,filt);connect(s,rd,filt);
 caption(s,'关闭 RD 后 RV 仍可保留；“冗余”表示处理路径互补，不能直接解释为独立。');source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md']);
}
{
 const s=await base('机器人水平速度的姿态依赖');
 await equation(s,'hv',67,164,1146,60);
 const h=box(s,'预生成双位置差航向',65,324,283,82);const tilt=box(s,'SDK roll / pitch',65,492,283,82);
 const rot=box(s,'坐标旋转与\n水平投影',492,394,287,102);const vel=box(s,'SDK 机体速度',492,243,287,79);
 const obs=box(s,'水平速度弱先验\nHV',934,394,280,102);
 connect(s,h,rot);connect(s,tilt,rot);connect(s,vel,rot,{from:'bottom',to:'top'});connect(s,rot,obs);
 caption(s,'工程姿态代理包含 FLU→FRD、−SDK pitch 与历史尺度；有效域需明确。');source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md'],'The original provider retains historical A1 heading for HV; upgrading scalar heading in V3 did not regenerate HV.');
}
{
 const s=await base('观测有效性与实际更新顺序');
 const labels=['位置','航向','RV','RD','HV','RP'];const nodes=labels.map((v,i)=>box(s,v,61+i*199,183,165,78));for(let i=0;i<5;i++)connect(s,nodes[i],nodes[i+1]);
 table(s,[['输入情况','机器人辅助的实际条件'],['GNSS 事件有效，HV/RP provider 有效','进入对应辅助检查流程'],['航向失效，HV 旋转依赖不满足','不能认为 HV 仍提供独立导航速度'],['位置 / RV / 航向全无效','原调度不另建 RP/HV 事件']],{y:352,h:233,widths:[536,636],font:25});
 caption(s,'故障窗内是否有更新，比辅助文件是否存在更能说明实际信息输入。');source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md',STORY+'03_SELECTION_HISTORY_AND_FULL_MATRIX_RESULTS.md']);
}
{
 const s=await base('来源协方差膨胀','按来源质量与滤波创新减小可疑观测的影响');
 text(s,'R′ = aR,   1 ≤ a ≤ cap',70,155,1110,60,37,BLUE,true);
 chart(s,'各来源的原配置膨胀上限',['位置','RV','航向','RD','RP','HV'],[{name:'上限',values:[5,8,10,15,10,10],fill:BLUE}],{y:257,h:330,yTitle:'协方差倍数',max:18});
 caption(s,'工程权重由观测条件控制；其数值需要与计量不确定度区分。');source(s,[STORY+'02_METHOD_CONFIG_METRIC_STORY.md']);
}
{
 const s=await base('估计输出与共享参考的关系');
 const gnss=box(s,'共享 GNSS 观测',80,196,305,91);const imu=box(s,'Go2 机体 IMU / SDK',80,409,305,91);
 const prop=box(s,'Proposed\nGNSS/INS',512,376,299,100);const ref=box(s,'商业融合参考\n相机 + 自有 IMU',513,172,299,104);const evaln=box(s,'相同定义下\n差值与统计量',971,284,245,117);
 connect(s,gnss,ref);connect(s,gnss,prop,{from:'bottom',to:'top'});connect(s,imu,prop);connect(s,prop,evaln);connect(s,ref,evaln);
 await equation(s,'difference',520,527,540,55);caption(s,'本文现有 RMSE 表示相对该参考的一致性；独立精度验证需额外测量证据。');source(s,['paper_package/gpss_v0/manuscript_source.md',REF+'venue/OFFICIAL_VENUE_AND_ORIGINAL_INPUT_BOUNDARY.md']);
}
{
 const s=await base('三条实录与评价窗口');
 table(s,[['序列','时间窗 / s','时长 / s','输出匹配历元','参考路径长 / m'],['BY2','66–340','274','56,642','328.471'],['BY2H','413–683','270','58,580','325.514'],['BY2O','3186–3563','377','76,548','337.422']],{y:193,h:268,widths:[170,235,210,290,267],font:26});
 text(s,'BY2：历史开发及参数选择\nBY2H / BY2O：同一安装条件下冻结设置的迁移检验',78,511,1119,98,29,BLUE,true);text(s,'历史研发曾查看参考与 O 序列结果；不是盲测。',78,614,1119,37,23);source(s,['paper_package/gpss_v0/manuscript_source.md'],'Reference distance and observation support are different recorded quantities; counts are not independent physical samples.');
}
{
 const s=await base('完整实验矩阵的构成');
 table(s,[['评价部分','案例 × 配置','运行数','承担的验证任务'],['CORE','541 × 11','5,951','自然基准与预定故障谱'],['失锁扩展 ADD','45 × 11','495','不同失锁时长与信息保留条件'],['H/O 自然迁移','2 × 11','22','同安装另两序列'],['合计','588 个案例单元','6,468','保留全部运行结果与失败']],{y:184,h:345,widths:[236,253,205,478],font:25});
 caption(s,'故障 placement 共用基础实录；案例数不等于独立采集环境数。');source(s,[STORY+'CURRENT_STORY_INDEX.md',STORY+'03_SELECTION_HISTORY_AND_FULL_MATRIX_RESULTS.md']);
}
// Later experimental and venue sections are appended below.
export {p,ROOT,REPO,REF,STORY,order,metadata,assets,tableOwners,chartOwners,BLUE,GREY,MUTED,FONT,text,base,box,connect,line,caption,table,figure,figureCrop,chart,prose,source,equation,fs,path,PresentationFile};
