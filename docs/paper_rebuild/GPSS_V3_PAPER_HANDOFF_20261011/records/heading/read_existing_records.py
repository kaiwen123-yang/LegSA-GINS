"""Read saved records only; never import or invoke scientific project code."""
from pathlib import Path
import csv, json, collections

ROOT=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
DOC=ROOT/'docs/paper_rebuild'
STAGE=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages')
OUT=Path('/mnt/g/LegSA-GINS-project/V3研究记录梳理_20261011/heading')
EXT=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/EXT_REPRODUCTION_V2_TECH_RETRY_2_20261004T054256Z')
records=[]
def public(p):
    s=str(p)
    if s.startswith('/mnt/g/'): return 'G:/'+s[7:]
    return '//wsl.localhost/Ubuntu-22.04'+s
def read(p,purpose,depth='全文解析；核对字段与保存记录'):
    p=Path(p); text=p.read_text(encoding='utf-8-sig')
    records.append(dict(absolute_path=public(p),linux_path=str(p),read_depth=depth,purpose=purpose,bytes=p.stat().st_size,lines=len(text.splitlines())))
    if p.suffix=='.json': return json.loads(text)
    if p.suffix=='.csv': return list(csv.DictReader(text.splitlines()))
    return text

docs=[
'hext/HX02/HX02_RESULTS.md','hext/DG01/DG01_REPORT.md','hext/DG01R/DG01R_REPORT.md',
'hext/HX07R/HX07R_REPORT.md','hext/EXT_REPRODUCTION/README.md','hext/EXT_REPRODUCTION/REPRODUCTION_NOTES.md',
'hext/EXT_REPRODUCTION/FAILURE_EXPLANATION.md','hext/EXT_REPRODUCTION/V2_REPAIR_NOTES.md',
'hext/EXT_REPRODUCTION/v2_fix/README.md','hext/EXT_REPRODUCTION/existing_clean/CLEAN4_CLEAN7_OVERVIEW.md',
'AR_V3_RESEARCH_20261006/README.md','AR_V3_RESEARCH_20261006/CAUSE_AUDIT.md',
'AR_V3_RESEARCH_20261006/INPUT_AUDIT_RESULTS.md','AR_V3_RESEARCH_20261006/RTKLIB_DIAGNOSTIC_READOUT.md',
'AR_V3_RESEARCH_20261006/CLASSIC_QUALIFICATION_RESULTS.md','AR_V3_RESEARCH_20261006/MOTION_PAIR_RESULTS.md',
'AR_V3_RESEARCH_20261006/COMPARISON_ADMISSION_DECISION.md',
'hext/EXT_REPRODUCTION/v2_fix/post_result_heading_guard/README.md',
]
for f in docs: read(DOC/f,'恢复阶段结论、修正历史与论文用途','全文获取；人工阅读主要结论与历史修正')
for f in ['ACTIVE_CONTEXT.md','DATA_ROLES.md','METHOD_SCOPE.md','EXPERIMENT_PROTOCOL.md','LEGACY_DENYLIST.md','CLAIM_BOUNDARY.md','NEXT_ACTIONS.md']:
    read(DOC/f,'项目入口、版本与数据使用边界','全文获取；重点阅读当前入口与相关规则')
read(ROOT/'AGENTS.md','仓库工作规则','全文获取；重点阅读航向、HX/DG、V3及历史成果规则')
tables={}
parsed_tables={}
for f in ['hext/DG01/DG01_OVERVIEW.csv','hext/DG01/DG01_FIX_STATUS_TIMELINE.csv','hext/DG01/DG01_RTKLIB_CONFIG_AUDIT.csv',
'hext/DG01R/DG01R_CLOCK_OFFSET.csv','hext/DG01R/DG01R_VERSION_COMPARISON.csv','hext/DG01R/DG01R_RINEX_CROSSCHECK.csv',
'hext/HX07R/HX07R_MANUSCRIPT_ROWS.csv','hext/HX07R/HX07R_SUPPLEMENT_ROWS.csv','hext/HX07R/HX07R_BY2O_SEGMENTS.csv',
'hext/EXT_REPRODUCTION/v2_fix/COMPARISON_TABLE.csv','hext/EXT_REPRODUCTION/v2_fix/COMMON_SUPPORT_ALL.csv',
'hext/EXT_REPRODUCTION/v2_fix/V1_V2_SAME_METHOD_COMMON_SUPPORT.csv','hext/EXT_REPRODUCTION/v2_fix/NATIVE_RUN_SUMMARY.csv',
'AR_V3_RESEARCH_20261006/RTKLIB_EPOCH_DIAGNOSTICS.csv','AR_V3_RESEARCH_20261006/RTKLIB_Q1_LARGE_LENGTH_DIAGNOSTICS.csv',
'AR_V3_RESEARCH_20261006/classic_qualification/RESULTS.csv','AR_V3_RESEARCH_20261006/motion_pair_qualification/RESULTS.csv']:
    rows=read(DOC/f,'全行核对保存指标、状态及分母')
    parsed_tables[f]=rows
    tables[f]={'rows':len(rows),'columns':list(rows[0]) if rows else [],'first_row':rows[0] if rows else {}}
read(ROOT/'configs/paper_rebuild/horizontal_literature/EXT_REPRODUCTION_V2.json','核实三方法实际配置')

hx=[]
hxroot=STAGE/'CLEAN9_EXTERNAL_COMPARISON/HX07R/RUNS'
for folder in sorted(hxroot.iterdir()):
    if not folder.is_dir() or not (folder/'COMMAND.json').exists(): continue
    cmd=read(folder/'COMMAND.json','原生调用、输入、配置及终态')
    assoc=read(folder/'ASSOCIATION_SUMMARY.json','核对原生输出与窗内配对分母')
    met=read(folder/'eval/OUTPUT/HEADING_METRICS.json','原评价终态与指标来源')
    heading=read(folder/'HEADING_TABLE.csv','全行读取原生航向与有效标志；供后续画图')
    errfiles=list((folder/'eval/OUTPUT').glob('*ERROR*csv'))
    for p in errfiles: read(p,'全行读取已有误差时序；未重算指标')
    hx.append({'run':folder.name,'returncode':cmd['returncode'],'status':cmd['status'],'window':assoc,'heading_rows':len(heading),'metric_keys':list(met),'error_files':[public(p) for p in errfiles]})
for p in sorted((STAGE/'CLEAN9_EXTERNAL_COMPARISON/HX07/CONFIGS').glob('*.conf')):
    read(p,'RTKLIB四变体具体配置全文')

ext=[]
for folder in sorted((EXT/'runs').iterdir()):
    if not folder.is_dir(): continue
    run=read(folder/'RUN.json','三方法V2原始运行身份与失败统计')
    heading=read(folder/'HEADING.csv','全行读取原生航向、基线和状态；供后续画图')
    ext.append({'run':folder.name,'run_keys':list(run),'status':run.get('status'),'rows':len(heading),'columns':list(heading[0]) if heading else [],'epoch_status':dict(collections.Counter(r['solution_state'] for r in heading))})
for seq in ['BY2','BY2H','BY2O']:
    folder=EXT/'evaluation'/seq
    for p in sorted(folder.glob('*.csv')): read(p,'全行读取已有航向评价输出与共同支持，不调用评价器')

far=[]
hx02=STAGE/'CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/RUNS'
for folder in sorted(hx02.glob('*__EXT04__*')):
    base=folder/'native/ARTIFACT/05_EXT04_WU2025_MODULE/C00'
    summ=read(base/'EXT04_C00_NATIVE_SUMMARY.json','FAR/PAR既有原生结果及接受状态')
    policy=read(base/'EXT04_C00_POLICY_SUMMARY.csv','FAR/PAR各策略结果全表')
    failures=read(base/'EXT04_C00_FAILURE_LEDGER.csv','FAR/PAR原始失败分类全表')
    read(base/'EXT04_POLICY_PARAMETER_REGISTRY.csv','FAR/PAR准入策略和参数')
    read(base/'EXT04_STOCHASTIC_PARAMETER_REGISTRY.csv','FAR/PAR随机模型参数')
    far.append({'run':folder.name,'summary_keys':list(summ),'policy':policy,'failure_rows':len(failures),'failure_columns':list(failures[0]) if failures else []})

rtk=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/AR_V3_RESEARCH_20261006/rtklib/BY2_V0_TRACE4_PREP02')
rtk_files=[]
for name in ['INVOCATION.json','solution.pos','solution.pos.stat','stdout.log','stderr.log']:
    p=rtk/'RUN'/name
    if p.exists():
        value=read(p,'追到已有trace4原生调用与输出日志；不新执行')
        rtk_files.append(public(p))
for name in ['RTKLIB_DIAGNOSTIC_SUMMARY.json','INPUT_AUDIT_SUMMARY.json','INPUT_AUDIT_OLD_LLI.csv']:
    read(DOC/'AR_V3_RESEARCH_20261006'/name,'已完成诊断的原始结构化结果')

summary={'table_inventory':tables,'hx07r_runs':hx,'ext_v2_runs':ext,'hx02_far_par':far,'rtklib_trace4_files':rtk_files,
'scientific_calls_this_task':0,'raw_reference_reads_this_script':0,'evaluation_or_metric_recomputation':False}
(OUT/'READOUT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'SOURCES_READ.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)

experiments=[]
def add(identity,version,mode,scope,status,work,result,source,curves,role,limit):
    experiments.append(dict(record_id=identity,version=version,data_mode=mode,scope=scope,status=status,completed_work=work,key_result=result,source_path=source,curve_source=curves,paper_role=role,limit=limit))
comparison=parsed_tables['hext/EXT_REPRODUCTION/v2_fix/COMPARISON_TABLE.csv']
for run in hx:
    seq,var=run['run'].split('_',1)
    rr=[r for r in comparison if r['sequence_id']==seq and r['method_id']=='RTKLIB_'+var]
    vals={r['support']:r for r in rr}
    v=vals['native_valid']; h=vals['causal_held']
    add('HX07R_'+run['run'],'HX07R official RTKLIB','recorded_raw_gnss',seq,'COMPLETED',
        '同原完整obs；顺序更换星历/星座/AR模式；全行原生与旧评价已查',
        f"valid={v['available_epoch_count']}/{v['paired_epoch_denominator']}; valid_RMSE_deg={v['rmse_deg']}; held_RMSE_deg={h['rmse_deg']}",
        public(hxroot/run['run']/'COMMAND.json'),';'.join(run['error_files']),'方向观测可用性与保持误差',
        'Q1不是整数真值；投影航向与Euler参考的物理量差异保留')
for run in ext:
    seq,method,*_=run['run'].split('__')
    v=next(r for r in comparison if r['sequence_id']==seq and r['method_id']==method and r['support']=='native_valid')
    add(run['run'],'EXT raw reproduction V2 generation2','recorded_raw_gnss',seq,run['status'],
        '各自发射时刻DD与几何飞行时间SPP下新身份运行；保存完整原生状态',
        f"valid={v['available_epoch_count']}/{v['paired_epoch_denominator']}; RMSE_deg={v['rmse_deg']}; maximum_gap_s={v['native_valid_maximum_gap_s']}",
        public(EXT/'runs'/run['run']/'RUN.json'),public(EXT/'runs'/run['run']/'HEADING.csv'),
        '方向生成处理链及质量限制','EXT01/02是候选而非已接受FIX；不是同输入完整导航排名')
for run in far:
    for p in run['policy']:
        base=hx02/run['run']/'native/ARTIFACT/05_EXT04_WU2025_MODULE/C00'
        add(run['run']+'__'+p['policy_identity'],'HX02 FAR/PAR declared policy','recorded_raw_gnss',run['run'].split('__')[0],'COMPLETED_ZERO_ACCEPTED',
            'FAR或递归PAR策略已实际运行，含原生参数、拒绝及失败记录',
            f"full_history_rows={p['row_count']}; accepted={p['accepted_count']}; FAR_rejected={p['FAR_REJECTED_count']}; PAR_exhausted={p['PAR_EXHAUSTED_count']}; invalid={p['INVALID_count']}",
            public(base/'EXT04_C00_POLICY_SUMMARY.csv'),public(base/'EXT04_C00_FAILURE_LEDGER.csv'),
            '补充：当前声明准入策略的实际输出','历史完整域计数；不能代替当前V2或作者整套算法')
extra=[
('DG01','原始质量诊断','recorded_raw_diagnostic','3 sequences','COMPLETED','双机NAV/RAWX/信号/CMC/配置/运动分布核查','RELPOSNED长度约3.05km；B/H双FIX100%，O84.6%','hext/DG01/DG01_REPORT.md','原始观测与接收机状态背景','时钟未修正的相位残差后被DG01R修正'),
('DG01R','钟差与半周续作','recorded_raw_diagnostic','3 sequences / 6 receivers','COMPLETED','钟差几何、半周处理并列、官方convbin六文件对照','BY2 GPS L1 P95 0.476949→0.191856 cycles','hext/DG01R/DG01R_REPORT.md','补充：测量链资格与历史纠错','几何代理不是相位真值；不可唯一归因振动或硬件'),
('AR_V3_INPUT_HISTORY','同历史输入恢复','recorded_raw_diagnostic','6 streams','COMPLETED','原提帧规则和原二进制选项匹配；六次转换已完成','631733码/299516相位及LLI/SSI差异0；15旧LLI恢复','AR_V3_RESEARCH_20261006/INPUT_AUDIT_RESULTS.md','输入可信性说明','未单因素分离截窗/提帧/选项'),
('AR_V3_RTKLIB_TRACE4','官方固定版本trace4','recorded_raw_diagnostic','BY2 V0 full 1509 epochs','COMPLETED','唯一重放字节一致；SPP/AR/postfit分支逐历元诊断','680+168 SPP拒绝；482 ratio失败；35 Q1有长度警告','AR_V3_RESEARCH_20261006/RTKLIB_DIAGNOSTIC_READOUT.md','质量准入动机与现有机制证据','其他序列/变体无新trace4，不推定整数真值'),
('CLASSIC_QUALIFICATION','经典候选器有限资格','synthetic_on_saved_geometry','12 slots','COMPLETED','完整Q、单位、接收机/pivot变换与生成整数恢复核查','12/12恢复生成整数','AR_V3_RESEARCH_20261006/CLASSIC_QUALIFICATION_RESULTS.md','补充：复现资格','非真实固定正确率'),
('MOTION_PAIR','两历元角度约束','synthetic_mechanism','16 slots','COMPLETED_NEGATIVE_GATE','角度先验整数分离机制及退化反例','14返回，2错误先验超时；积极扩展门未满足','AR_V3_RESEARCH_20261006/MOTION_PAIR_RESULTS.md','研究支线，通常不入V3主文','条件导航12身份未执行；不能记作失败绩效'),
('PD_PAR_GYRO_ADMISSION','新增文献候选资格','literature_review','2 candidates','REVIEW_COMPLETED_IMPLEMENTATION_NOT_ADMITTED','PD-PAR与gyro-integral适配和纳入决策已完成','新实现/实测行=0，已明确不强凑','AR_V3_RESEARCH_20261006/COMPARISON_ADMISSION_DECISION.md','相关工作或研究支线','不是HX02已实现PAR策略的别名'),
]
for ident,version,mode,scope,status,work,result,src,role,limit in extra:
    add(ident,version,mode,scope,status,work,result,public(DOC/src),'见对应文档链接的已有表/时序',role,limit)
with (OUT/'EXPERIMENTS.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(experiments[0]));w.writeheader();w.writerows(experiments)
with (OUT/'EXISTING_HEADING_METRICS.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(comparison[0]));w.writeheader();w.writerows(comparison)
print(json.dumps({'sources':len(records),'hx07r_runs':len(hx),'ext_v2_runs':len(ext),'far_par_runs':len(far),'table_inventory':{k:v['rows'] for k,v in tables.items()},'rtklib_trace4_files':rtk_files},ensure_ascii=False,indent=2))
