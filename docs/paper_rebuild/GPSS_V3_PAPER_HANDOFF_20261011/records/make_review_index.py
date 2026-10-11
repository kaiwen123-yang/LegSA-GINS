"""Build an index of the completed record review; no scientific execution."""
from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parent
def save(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

claims=[
('C01','自身IMU与接触观测缺少绝对航向约束','研究动机','已完成结构验证','H6R七初始方向集合、五窗口可观测性、四维零空间','robot/ROBOT_RECORDS.md','图2','使用既有规范集合与秩谱'),
('C02','机器人运动学输入提供有用相对运动信息','平台背景','已完成实测与诊断','官方Hartley六配置与HX05接触运动学积分三记录','robot/ROBOT_RECORDS.md','图2/补充','恢复LEG-DR真实公式与名称'),
('C03','当前短基线方向获取存在连续性和质量问题','观测问题','已完成实测、控制和诊断','HX07R十二运行、EXT V2九组合、DG01R、trace4','heading/HEADING_RECORDS.md','图3','误差、有效输出与拒绝原因配合展示'),
('C04','基础GNSS/INS加入既定双天线航向链改善航向','本文方法证据','已有三记录结果与配置','F01/F03自然结果及实际运行manifest','internal/INTERNAL_RECORDS.md','图4或消融补充','调用已有时序，避免把F01/F04差值当单项航向作用'),
('C05','机身倾角辅助改善roll/pitch','本文方法证据','已完成单开关','F04/A05，519共同完成案例roll/pitch均改善','internal/SINGLE_MODULE_RESULTS.csv','图6','保留倾角原误差时序'),
('C06','保留航向的平移中断中机身速度辅助抑制水平漂移','本文核心结果','已完成单开关及中断矩阵','F04/A06；20s九布置全窗H中位0.241/7.961m','internal/ADDENDUM_RELEVANT_RESULTS.csv','图6','中断局部与布置配对，注明全窗指标'),
('C07','来源加权改善完成和部分尾部表现并付出典型误差代价','本文方法证据','已完成单开关','F04/A04，完成519/513，H中位差+0.981mm','internal/SINGLE_MODULE_RESULTS.csv','图7','异常时序与全体代价一起展示'),
('C08','最近IEKF路线提供自然与退化系统对照','外部系统验证','已完成三记录和Classic-18/A2','LC01/EXT05C、LIT/S、HX03R2','fusion/FUSION_RECORDS.md','图4','保留已有参数和起点条件'),
('C09','保留方向不自动保证平移精度','跨实验联系','已有外部控制','LC01-BR A2十八例，H中位2.786m；LC01为1.407m','fusion/FUSION_RECORDS.md','图6/补充','与内部HV结果相邻解释，不当作同全部输入消融'),
('C10','V3与OiSAM已有同点共同时间比较','外部系统验证','现成表与曲线已找到','COMMON_POI_OISAM_V3_TIME，274/0/54共同点','fusion/V3_OISAM_EXISTING_COMMON_POINT.csv','图5','恢复本文对照和全窗输出支持'),
('C11','真实IMU缺口策略影响FGO输出连续性','外部系统验证','已完成strict/segmented及无缺口控制','OiSAM三新native、十一预登记块、BY2状态事件exact控制','fusion/FUSION_RECORDS.md','图5','两协议各自保留原物理点和支持'),
('C12','共同后端QA研究此前已经完成','研究历史','历史完成汇总已定位','PAPER2A七类QA、1897可评行；与当前七R形状不同集合','fusion/FUSION_RECORDS.md','研究记录/补充候选','定位旧逐行载荷，不能替换冻结V3指标'),
]
save('CLAIM_EVIDENCE_MAP.csv',[dict(zip(['claim_id','statement','paper_role','evidence_status','existing_evidence','review_source','proposed_figure','next_organization_action'],r)) for r in claims])

pending=[
 {'item':'机器人不可观测性','status':'已找到','action':'使用既有H6R数据重组图','new_experiment_required':'否'},
 {'item':'航向准入/失败原因','status':'已找到','action':'使用DG01R/HX07R/trace4时序','new_experiment_required':'否'},
 {'item':'V3/OiSAM同点比较','status':'已找到','action':'采用已有strict共同点表，segmented另列','new_experiment_required':'否'},
 {'item':'LC01-BR与外部退化','status':'已找到后续完成版本','action':'采用HX03R2并保留原失败','new_experiment_required':'否'},
 {'item':'历史PAPER2A逐行载荷','status':'历史完成汇总已找到，原载荷待定位','action':'保留历史完成事实；按既有引用继续找载荷','new_experiment_required':'未提出'},
 {'item':'当前七种R倍率形状完整性能矩阵','status':'源码/范围表已找到，具体完整运行矩阵尚待定位','action':'与历史七类QA分开登记；不从复现资格状态推断执行状态','new_experiment_required':'未提出'},
 {'item':'组图版式与主副图选择','status':'已有方案','action':'先恢复图2与图5，再逐图重排','new_experiment_required':'否'},
]
save('FOLLOW_UP_RECORDS.csv',pending)

allrows=[]
for group in ['robot','heading','fusion','internal']:
    file=ROOT/group/'SOURCES_READ.csv'
    records=list(csv.DictReader(file.open(encoding='utf-8-sig')))
    for row in records:allrows.append({'review_group':group,**row})
save('READING_COVERAGE.csv',allrows)
summary={}
for group in ['robot','heading','fusion','internal']:
    summary[group]={}
    for name in ['SOURCES_READ.csv','EXPERIMENTS.csv','CURVE_INVENTORY.csv']:
        f=ROOT/group/name
        if f.exists():summary[group][name]=sum(1 for _ in csv.DictReader(f.open(encoding='utf-8-sig')))
summary['interpretation']='Counts are source reads or evidence records, not independent experiments. See each report for full/selected/array-header reading depth.'
summary['work_scope']='Existing source recovery and paper/figure planning only; no new solver, evaluator, provider or figure rendering.'
(ROOT/'REVIEW_SCOPE.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
