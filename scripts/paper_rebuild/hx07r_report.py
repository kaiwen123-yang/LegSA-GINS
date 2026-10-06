#!/usr/bin/env python3
"""HX-07-R tables/plots from retained outputs only; no native or reference access."""
import argparse
import collections
import json
import math
import os
from pathlib import Path
import shutil
import sys
import numpy as np
from hx07r_prepare import (W,C,H,OLD,O,R,S,EXT,SEQS,VARIANTS,EXPECTED,now,sha,dump,alias,resolve,
                          csvrows,csvwrite,verify_pins,scope_check,progress)
sys.path.insert(0,str(W/'src'))
from legsa_gins.paper_rebuild.horizontal_literature.phase3_runner import _parse_rtklib_enu_pos
from legsa_gins.paper_rebuild.hext.hx05_tables import heading_slice_statistics

SYSTEMS=['G','R','E','C','J','S']


def finite(x):
    try:return math.isfinite(float(x))
    except (ValueError,TypeError):return False


def fmt(x):
    return f'{float(x):.6f}'.rstrip('0').rstrip('.') if finite(x) else 'UNAVAILABLE'


def rel(week,tow,data):
    return 315964800+int(week)*604800+float(tow)-18-data['base_time']


def stats(values):
    a=np.asarray([float(v) for v in values if finite(v)])
    if not len(a):return {'n':0,**{k:'UNAVAILABLE' for k in ['min','p05','mean','median','p95','max','max_abs','rms']}}
    return {'n':len(a),'min':float(a.min()),'p05':float(np.percentile(a,5,method='linear')),
            'mean':float(a.mean()),'median':float(np.median(a)),'p95':float(np.percentile(a,95,method='linear')),
            'max':float(a.max()),'max_abs':float(np.abs(a).max()),'rms':float(np.sqrt(np.mean(a*a)))}


def metrics(run):
    p=run/'eval/OUTPUT/HEADING_METRICS.json'
    return json.loads(p.read_text())['variants']['RTKLIB'] if p.exists() else None


def cells(m):
    if m is None:return 'NOT_AVAILABLE'
    return f'availability={fmt(m["availability"])} [{m["valid_epochs_in_window"]}/{m["denominator_native_paired_epochs_in_window"]}]; valid_rmse_deg={fmt(m["valid"]["rmse_deg"])}; hold_rmse_deg={fmt(m["hold_last_valid"]["rmse_deg"])}'


def fix_statistics(seq,v,run,data,table):
    p=(OLD/'RUNS/BY2_V0/solution.pos') if v=='V0-convbin' else run/'solution.pos'
    if not p.exists():return [{'variant':v,'sequence':seq,'scope':'all','metric':'status','status':'NOT_AVAILABLE','source':alias(run/'NOT_AVAILABLE.json')}]
    parsed=_parse_rtklib_enu_pos(p.read_text());lo,hi=data['window']
    window=[r for r in parsed if lo<=rel(r['gps_week'],r['gps_tow_seconds'],data)<=hi]
    paired=[r for r in csvrows(table) if lo<=float(r['time_unix_s'])-data['base_time']<=hi]
    out=[]
    for scope,rows,key in [('full_file',parsed,'quality'),('pos_label_window',window,'quality'),('paired_window',paired,'rtklib_q')]:
        for q in [1,2,5,-1]:
            n=sum(int(r[key])==q for r in rows)
            out.append({'variant':v,'sequence':seq,'scope':scope,'metric':f'Q{q}','n':n,'denominator':len(rows),
                        'fraction_own_denominator':n/len(rows) if rows else 'UNAVAILABLE','paired_denominator':data['expected'][0],
                        'fraction_paired_denominator':n/data['expected'][0],'source':alias(table if scope=='paired_window' else p)})
    for q in ['all',1,2]:
        selected=window if q=='all' else [r for r in window if r['quality']==q]
        out.append({'variant':v,'sequence':seq,'scope':'pos_label_window','metric':f'ratio_Q{q}',**stats(r['ratio'] for r in selected),'source':alias(p)})
        if q!='all':
            out.append({'variant':v,'sequence':seq,'scope':'pos_label_window','metric':f'baseline_residual_m_Q{q}',
                        **stats(np.linalg.norm(r['baseline_enu_m'])-.350 for r in selected),'source':alias(p)})
    return out


def satellite_statistics(seq,v,run,data):
    path=run/'solution.pos.stat';lo,hi=data['window'];records=[];epoch_quality={};malformed=[]
    if path.exists():
        with path.open() as f:
            for ln,line in enumerate(f,1):
                fields=line.rstrip().split(',')
                if fields[0]=='$POS':
                    if len(fields)!=10:malformed.append(ln);continue
                    key=(int(fields[1]),float(fields[2]));epoch_quality[key]=int(fields[3])
                if fields[0]!='$SAT':continue
                if len(fields)!=17:malformed.append(ln);continue
                try:
                    week=int(fields[1]);tow=float(fields[2]);t=rel(week,tow,data)
                    records.append({'week':week,'tow':tow,'t_rel_s':t,'satellite':fields[3],'system':fields[3][0],
                                    'frequency':int(fields[4]),'az_deg':float(fields[5]),'el_deg':float(fields[6]),
                                    'resp_m':float(fields[7]),'resc_m':float(fields[8]),'vsat':int(fields[9]),
                                    'snr':float(fields[10]),'fix':int(fields[11]),'slip':int(fields[12]),
                                    'lock':int(fields[13]),'outc':int(fields[14]),'slipc':int(fields[15]),'rejc':int(fields[16])})
                except ValueError:malformed.append(ln)
    if not records or malformed:
        status={'variant':v,'sequence':seq,'status':'UNAVAILABLE','source':alias(path),'reason':'missing $SAT or malformed fields','malformed_first20':str(malformed[:20])}
        return [status],[status],[]
    epochs=sorted(k for k in epoch_quality if lo<=rel(*k,data)<=hi)
    window=[r for r in records if lo<=r['t_rel_s']<=hi]
    # All $POS epochs in the window are the common denominator; absent systems have zero usage.
    counted=collections.defaultdict(set);unions=collections.defaultdict(set)
    for r in window:
        if r['vsat']==1:
            counted[(r['week'],r['tow'],r['system'],r['frequency'])].add(r['satellite'])
            unions[(r['week'],r['tow'],r['system'])].add(r['satellite'])
    timeline=[]
    for k in epochs:
        timeline.append({'variant':v,'sequence':seq,'week':k[0],'tow':k[1],'t_rel_s':rel(*k,data),'Q':epoch_quality[k],
                         **{s:len(unions[(*k,s)]) for s in SYSTEMS}})
    usage=[];residuals=[]
    for system in SYSTEMS:
        for frequency in [1,2]:
            counts=[len(counted[(*k,system,frequency)]) for k in epochs]
            unique=set().union(*(counted[(*k,system,frequency)] for k in epochs)) if epochs else set()
            usage.append({'variant':v,'sequence':seq,'system':system,'frequency':frequency,'stat_epochs':len(epochs),
                          'min':min(counts,default=0),'median':float(np.median(counts)) if counts else 'UNAVAILABLE',
                          'max':max(counts,default=0),'distinct_valid_satellites':len(unique),
                          'epochs_at_least_one':sum(c>0 for c in counts),
                          'epochs_at_least_one_union_frequencies':sum(bool(unions[(*k,system)]) for k in epochs),
                          'status':'AVAILABLE','source':alias(path)})
        for frequency in ['all',1,2]:
            # Q=1 is the solver solution state, not the per-satellite ambiguity flag.
            subset=[r for r in window if r['system']==system and r['vsat']==1 and
                    (frequency=='all' or r['frequency']==frequency) and epoch_quality.get((r['week'],r['tow']))==1]
            s=stats(r['resc_m'] for r in subset)
            residuals.append({'variant':v,'sequence':seq,'system':system,'frequency':frequency,'Q':1,
                              'n':s['n'],'resc_rms_m':s['rms'],'resc_p95_signed_m':s['p95'],
                              'resc_p95_absolute_m':stats(abs(r['resc_m']) for r in subset)['p95'],
                              'status':'AVAILABLE' if s['n'] else 'UNAVAILABLE_NO_Q1_VALID_SAMPLES','source':alias(path)})
    csvwrite(run/'SAT_DETAIL.csv',records)
    csvwrite(run/'SAT_USAGE_TIMELINE.csv',timeline)
    return usage,residuals,timeline


def tables():
    plan=json.loads((O/'PLAN.json').read_text());fix=[];usage=[];residuals=[];segments=[];diagnostics=[];summary=[];all_metrics={}
    for v in [*VARIANTS,'V0-convbin']:
        for seq in (['BY2'] if v=='V0-convbin' else SEQS):
            run=O/'RUNS'/f'{seq}_{"V0convbin" if v=="V0-convbin" else v}';data=plan['sequences'][seq]
            m=metrics(run);all_metrics[(v,seq)]=m
            table=OLD/'RUNS/BY2_V0/HEADING_TABLE.csv' if v=='V0-convbin' else run/'HEADING_TABLE.csv'
            fix.extend(fix_statistics(seq,v,run,data,table))
            if v!='V0-convbin':
                u,r,t=satellite_statistics(seq,v,run,data);usage.extend(u);residuals.extend(r)
            if m is None:continue
            source=run/'eval/OUTPUT/HEADING_ERROR_SERIES_RTKLIB.csv';series=csvrows(source)
            errors=np.asarray([float(r['error_valid_deg']) for r in series if finite(r['error_valid_deg'])]);a=np.abs(errors)
            diag={'variant':v,'sequence':seq,'n_valid_scored':len(a),'abs_p50_deg':float(np.percentile(a,50)) if len(a) else 'UNAVAILABLE',
                  'abs_p95_deg':float(np.percentile(a,95)) if len(a) else 'UNAVAILABLE','abs_max_deg':float(a.max()) if len(a) else 'UNAVAILABLE',
                  'abs_gt10_count':int(np.count_nonzero(a>10)),'abs_gt10_fraction':float(np.mean(a>10)) if len(a) else 'UNAVAILABLE','source':alias(source)}
            diagnostics.append(diag)
            summary.append({'variant':v,'sequence':seq,'valid_count':m['valid_epochs_in_window'],
                            'paired_denominator':m['denominator_native_paired_epochs_in_window'],'availability':m['availability'],
                            'valid_rmse_deg':m['valid']['rmse_deg'],'hold_rmse_deg':m['hold_last_valid']['rmse_deg'],
                            'hold_scored':m['hold_last_valid']['count'],'no_heading_before_first':m['hold_last_valid']['no_heading_epochs_before_first_valid'],
                            'q2_count':m['q2_float']['count'],'q2_rate':m['q2_float']['rate'],'q2_rmse_deg':m['q2_float']['errors']['rmse_deg'],
                            'source':alias(run/'eval/OUTPUT/HEADING_METRICS.json')})
            if seq=='BY2O':
                t=np.array([float(r['t_rel_s']) for r in series]);primary=(t>=3369.94)&(t<=3411.95);secondary=(t>=3495.94)&(t<=3508.94)
                for name,mask in [('occlusion_primary',primary),('occlusion_secondary',secondary),('outside',~(primary|secondary)),('full',np.ones(len(t),bool)),('inside_union',primary|secondary)]:
                    s=heading_slice_statistics([r for r,keep in zip(series,mask) if keep])
                    segments.append({'variant':v,'method':f'RTKLIB_{v}','segment':name,**s,
                                     'horizontal_rmse_m':'NOT_APPLICABLE_HEADING_ONLY','up_rmse_m':'NOT_APPLICABLE_HEADING_ONLY',
                                     'status':'AVAILABLE' if s['valid_scored_epochs'] else 'NO_VALID_HEADING',
                                     'source_id':f'HX07R.SEGMENT.{v}.{name}','original_fields_json':'NOT_APPLICABLE_DERIVED_SEGMENT','source':alias(source)})
    old=next(r for r in csvrows(W/'docs/paper_rebuild/hext/HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv') if 'MAIN.06.' in r['source_ids'])
    manuscript=[{'variant':'V0',**old,'source':'UNCHANGED_HX05_MAIN_06; '+';'.join(
        alias(resolve(plan['sequences'][s]['metrics_source'])) for s in SEQS)}]
    new=dict(old);new.update(method='RTKLIB_MOVING_BASE_GPS_GAL_BDS_QZS_BRDC',config='V1',source_ids=' | '.join('MAIN.06b.'+s for s in SEQS),
                            notes='RTKLIB moving-base, GPS+Galileo+BDS+QZSS, external broadcast ephemeris (BKG BRDC)')
    new.update({s:cells(all_metrics.get(('V1',s))) for s in SEQS})
    manuscript.append({'variant':'V1',**new,'source':';'.join(f'RUNS/{s}_V1/eval/OUTPUT/HEADING_METRICS.json' for s in SEQS)})
    supplement=[]
    def supplement_row(v,kind,values,note):
        return {'variant':v,'category':old['category'],'method':f'RTKLIB_{v}_{kind}','config':v,'role':'SUPPLEMENT',
                'output_type':'heading_only',**values,'source_ids':f'HX07R.{v}.{kind}','notes':note,
                'source':';'.join(f'RUNS/{s}_{"V0convbin" if v=="V0-convbin" else v}/eval/OUTPUT/HEADING_METRICS.json' for s in values if values[s]!='NOT_RUN')}
    for v in ['V0E','V2','V0-convbin']:
        supplement.append(supplement_row(v,'MAIN',{s:cells(all_metrics[(v,s)]) if (v,s) in all_metrics else 'NOT_RUN' for s in SEQS},
                           'external-ephemeris-only control' if v=='V0E' else 'fix-and-hold' if v=='V2' else 'archived window-conversion/input-history sensitivity; no native rerun'))
    for v in VARIANTS:
        vals={}
        for s in SEQS:
            m=all_metrics.get((v,s));q=m['q2_float'] if m else None
            vals[s]=f'q2_float_rate={fmt(q["rate"])} [{q["count"]}/{m["denominator_native_paired_epochs_in_window"]}]; q2_float_rmse_deg={fmt(q["errors"]["rmse_deg"])}' if q else 'NOT_AVAILABLE'
        supplement.append(supplement_row(v,'Q2',vals,'Q=2 subset, HX05 SUPP.07 definition'))
    for v in [*VARIANTS,'V0-convbin']:
        vals={}
        for s in SEQS:
            d=next((d for d in diagnostics if d['variant']==v and d['sequence']==s),None)
            vals[s]='; '.join(f'{k}={fmt(d[k])}' for k in ['n_valid_scored','abs_p50_deg','abs_p95_deg','abs_max_deg','abs_gt10_count','abs_gt10_fraction']) if d else 'NOT_RUN'
        supplement.append(supplement_row(v,'VALID_DIAGNOSTIC',vals,'absolute-error >10 deg proxy, not verified integer correctness'))
    for name,rows in [('HX07R_MANUSCRIPT_ROWS.csv',manuscript),('HX07R_SUPPLEMENT_ROWS.csv',supplement),('HX07R_BY2O_SEGMENTS.csv',segments),
                      ('HX07R_FIX_STATISTICS.csv',fix),('HX07R_SATELLITE_USAGE.csv',usage),('HX07R_RESIDUALS.csv',residuals)]:
        csvwrite(R/name,rows)
    csvwrite(O/'VALID_DIAGNOSTICS.csv',diagnostics);csvwrite(O/'SUMMARY.csv',summary)
    dump(O/'REPORT_DATA.json',{'summary':summary,'diagnostics':diagnostics,'fix':fix,'usage':usage,'residuals':residuals,'segments':segments})
    return json.loads((O/'REPORT_DATA.json').read_text())


def figure(data):
    S.mkdir(parents=True,exist_ok=True);os.environ['MPLCONFIGDIR']=str(S/'mpl');os.environ['MPLBACKEND']='Agg'
    from legsa_gins.paper_rebuild.publication import style,qa
    import matplotlib.pyplot as plt
    style.apply_rcparams();fig,axes=plt.subplots(2,2,figsize=(174/25.4,6.8),gridspec_kw={'hspace':.40,'wspace':.32})
    fig.subplots_adjust(left=.095,right=.985,bottom=.07,top=.97)
    colors=[style.COLORS[k] for k in ['F01','F02','A04','F04']];markers=['o','s','^','D']
    ax=axes[0,0];width=.18;x=np.arange(3)
    for j,v in enumerate(VARIANTS):
        vals=[next((r['availability']*100 for r in data['summary'] if r['variant']==v and r['sequence']==s),np.nan) for s in SEQS]
        ax.bar(x+(j-1.5)*width,vals,width,label=v,color=colors[j],hatch=['','///','xx','...'][j],linewidth=.4,edgecolor='black')
    ax.set_xticks(x,[f'{s}\nn={EXPECTED[s][0]}' for s in SEQS]);ax.set_ylabel('Q=1 availability (%)');ax.set_ylim(0,100);ax.legend(ncol=2,loc='upper left')
    ax=axes[0,1]
    for v,color,offset,ls in [('V0',colors[0],-.06,'-'),('V1',colors[2],.06,'--')]:
        rows=csvrows(O/f'RUNS/BY2_{v}/HEADING_TABLE.csv');rows=[r for r in rows if 66<=float(r['time_unix_s'])-1772784000<=340]
        times=[float(r['time_unix_s'])-1772784000 for r in rows];q=[{1:2,2:1}.get(int(r['rtklib_q']),0)+offset for r in rows]
        ax.step(times,q,where='post',color=color,ls=ls,lw=.7,label=v)
    ax.set_yticks([0,1,2],['None','Float','Fixed']);ax.set_xlabel('Time (s)');ax.set_xlim(66,340);ax.legend(ncol=2,loc='upper right');ax.set_ylim(-.2,2.5)
    ax=axes[1,0]
    for v,color,marker in [('V0',colors[0],'.'),('V1',colors[2],'x')]:
        rows=csvrows(O/f'RUNS/BY2_{v}/eval/OUTPUT/HEADING_ERROR_SERIES_RTKLIB.csv');times=[float(r['t_rel_s']) for r in rows]
        errors=[float(r['error_valid_deg']) if finite(r['error_valid_deg']) else np.nan for r in rows]
        ax.plot(times,errors,color=color,marker=marker,markersize=1.8,lw=.4,label=v)
    ax.set_xlabel('Time (s)');ax.set_ylabel('Heading error (deg)');ax.set_ylim(-180,180);ax.set_xlim(66,340);ax.legend(ncol=2,loc='upper right')
    ax=axes[1,1];ax.axis('off')
    sycolors=[style.COLORS['F04'],style.COLORS['neutral'],style.COLORS['A04'],style.COLORS['F02'],style.COLORS['F03'],'#009E73']
    max_count=1;all_rows={}
    for v in ['V0','V0E','V1']:
        p=O/f'RUNS/BY2_{v}/SAT_USAGE_TIMELINE.csv'
        rows=csvrows(p) if p.exists() else [];all_rows[v]=rows
        if rows:max_count=max(max_count,max(sum(int(r[s]) for s in SYSTEMS) for r in rows))
    for i,v in enumerate(['V0','V0E','V1']):
        child=ax.inset_axes([0,.70-i*.33,1,.26]);rows=all_rows[v]
        if rows:
            child.stackplot([float(r['t_rel_s']) for r in rows],*[[int(r[s]) for r in rows] for s in SYSTEMS],colors=sycolors,labels=SYSTEMS,step='post',linewidth=0)
        else:child.text(.5,.5,'Unavailable',ha='center',transform=child.transAxes)
        child.set_xlim(66,340);child.set_ylim(0,max_count+1);child.set_yticks([0,int(math.ceil(max_count/10)*10)]);child.text(.02,.80,v,transform=child.transAxes,fontsize=7)
        if i<2:child.tick_params(labelbottom=False)
        else:child.set_xlabel('Time (s)')
        if i==1:child.set_ylabel('Satellites (count)')
        if i==0:child.legend(ncol=6,loc='lower center',bbox_to_anchor=(.48,1.0),handlelength=.7,columnspacing=.6,fontsize=7)
    for i,ax in enumerate(axes.flat):ax.text(-.12,1.015,f'({chr(97+i)})',transform=ax.transAxes,fontsize=8)
    out=O/'FIGURES';out.mkdir(exist_ok=True)
    identity=style.save_figure(fig,out,'SFIG-HX7');checks=qa.check_figure(fig,'SFIG-HX7')+qa.check_png(out/'SFIG-HX7.png','SFIG-HX7')
    for ext in ['png','pdf','svg']:
        p=out/f'SFIG-HX7.{ext}'
        if ext=='svg':p.write_text('\n'.join(l.rstrip() for l in p.read_text().splitlines())+'\n')
        shutil.copyfile(p,R/p.name)
    checks=[{k:bool(v) if k=='pass' else v for k,v in r.items()} for r in checks]
    dump(R/'HX07R_FIGURE_QA.json',{'checks':checks,'passed':all(r['pass'] for r in checks),'identity':{k:alias(v) if isinstance(v,str) and v.startswith('/') else v for k,v in identity.items()},'visual_review':'PENDING'})
    plt.close(fig);assert all(r['pass'] for r in checks),'figure QA failed'


def mdtable(rows,fields):
    return '| '+' | '.join(fields)+' |\n|'+'|'.join('---' for _ in fields)+'|\n'+''.join('| '+' | '.join(str(r.get(k,'')).replace('|','/') if not isinstance(r.get(k),float) else fmt(r[k]) for k in fields)+' |\n' for r in rows)


def report(data):
    counts=json.loads((R/'HX07R_EXECUTION_COUNTS.json').read_text());g2=json.loads((R/'HX07R_V0_GATE.json').read_text());g3=json.loads((R/'HX07R_EVAL_REPRODUCTION.json').read_text())
    reg=json.loads((O/'REGISTRATION_RECEIPT.json').read_text());h1=json.loads((O/'HISTORY_COMMIT.json').read_text())['commit']
    source='来源：所有表的 source 列；G: <HX07R>/RUNS/<sequence>_<variant>/COMMAND.json、ASSOCIATION_SUMMARY.json、eval/OUTPUT/HEADING_METRICS.json。'
    text=f'''# HX-07-R 结果报告

## 1. 硬停解释与控制组修正

HX-07 的 V0 使用 DG-01R 仅评估窗内帧转换的观测，去复现 HX-02 完整重建流的结果，输入历史不一致。HX-02 三序列完整观测历元数为 1509/1483/2231，窗内 1370/1350/1885；DG-01R 共同伪距 551568、相位 247270 的数值差异为 0，LLI bit0 差异 15 处。原控制组登记了覆盖差异却仍采用 ±2 门，得到 BY2 157/1370 对 153/1370、差 +4 后按规则硬停。原生退出码为 0，该记录不作为解算错误证据；控制组设计没有固定输入历史。来源：已 pin 的 DG01R_RINEX_EPOCHS.csv、DG01R_RINEX_CROSSCHECK.csv、HX07/HARD_STOP.json。HX-07 的原文与产物一字不改，157/1370 保留为转换路径/输入历史敏感性补充行。

本次只用 HX-02 自己的完整 obs，与原二进制、配置和起点参数复现；在其基础上依次更换星历（V0E）、星座掩码（V1）、AR 模式（V2）。不按結果选择配置。

## 2. G1–G6 与逐运行计数

登记前 BRDC 头为 `     3.05           NAVIGATION DATA     MIXED               RINEX VERSION / TYPE`；主版本 3。继承 91 pin、RTKLIB 927 源码均匹配；完整 pin 数见 HX07R_INPUT_SHA256.json（{len(json.loads((R/'HX07R_INPUT_SHA256.json').read_text()))} 项）。G2 三序列计数精确复现，G2b 非注释行差异如下；G3 三序列全部通过，逐字段实际值与期望值见 HX07R_EVAL_REPRODUCTION.json。

'''
    text+=mdtable([{'sequence':g['sequence'],'expected':g['expected'],'observed':g['observed'],'G2_passed':g['passed'],'G2b_different_lines':g['G2b']['different_lines']} for g in g2],['sequence','expected','observed','G2_passed','G2b_different_lines'])
    text+='\n'+mdtable([{'sequence':g['sequence'],**g['actual'],'passed':g['passed']} for g in g3],['sequence','valid_count','valid_rmse_deg','hold_rmse_deg','q2_count','q2_rmse_deg','passed'])
    text+='\n实际计数：'+json.dumps(counts['actual'],ensure_ascii=False)+'。每条原生和评估审计见 HX07R_AUDIT.json；每个评估参考只读打开一次并核验同一批 bytes 的 SHA-256；父进程拒绝 raw/reference 打开，其他外部方法未运行。\n\n'
    command_rows=[]
    for p in sorted((O/'RUNS').glob('*/COMMAND.json')):
        c=json.loads(p.read_text());command_rows.append({'sequence':c['sequence'],'variant':c['variant'],'returncode':c.get('returncode'),'start':c['start'],'end':c.get('end'),'source':alias(p)})
    text+=mdtable(command_rows,['sequence','variant','returncode','start','end'])
    text+='\nG5/G6 最终结果由 HX07R_PROTECTED_METADATA_CHECK.json 与 FINAL_RECEIPT.json 记录；本报告末尾追加最终复核与视觉检查回执。\n\n## 3. 三序列结果、Q 分布、ratio 与长度残差\n\n'
    text+=mdtable(data['summary'],['variant','sequence','valid_count','paired_denominator','availability','valid_rmse_deg','hold_rmse_deg','hold_scored','no_heading_before_first','q2_count','q2_rmse_deg'])+'\n'+source+'\n\n'
    q=[r for r in data['fix'] if r.get('metric','').startswith('Q')]
    text+='三种分母分别保留；全文件计数不替代窗内配对分母。\n\n'+mdtable(q,['variant','sequence','scope','metric','n','denominator','fraction_own_denominator','paired_denominator','fraction_paired_denominator'])
    text+='\nratio（窗内 .pos 标签时间，所有/Q1/Q2）：\n\n'+mdtable([r for r in data['fix'] if r.get('metric','').startswith('ratio')],['variant','sequence','metric','n','min','p05','median','p95','max'])
    text+='\n长度残差为 norm(ENU)−0.350 m，仅作诊断，不改配置中 0.350±0.010 m 的约束。\n\n'+mdtable([r for r in data['fix'] if r.get('metric','').startswith('baseline')],['variant','sequence','metric','n','mean','median','p05','p95','max_abs'])
    text+='\n来源 HX07R_FIX_STATISTICS.csv；原始 .pos 路径逐行列在 source。\n\n## 4. 卫星使用与残差\n\n$SAT 字段顺序来自官方 rtkpos.c L151/L342–346；等级 2，每行 17 字段。使用统计分母为窗内 $POS 输出历元；每个系统缺失的历元计 0，频率 1/2 分别计 vsat=1 的不同卫星。union 为跨频率去重；不是把两个频率相加成卫星数。Q1 载波残差只取 vsat=1，Q 来自 $POS 的解状态，不用单颗卫星 fix 标志代替。P95 同时报带符号与绝对值，RMS 用带符号残差平方。\n\n'
    text+=mdtable(data['usage'],['variant','sequence','system','frequency','stat_epochs','min','median','max','distinct_valid_satellites','epochs_at_least_one','epochs_at_least_one_union_frequencies'])
    text+='\nQ1 残差汇总（跨频率；分频完整表在 HX07R_RESIDUALS.csv）：\n\n'+mdtable([r for r in data['residuals'] if r.get('frequency')=='all'],['variant','sequence','system','n','resc_rms_m','resc_p95_signed_m','resc_p95_absolute_m'])
    text+='\nV0→V0E 只改星历文件，V0E→V1 再改星座掩码；上述逐步对照分别保留，不把组合差异直接归为单一原因。每个表的 source 指向本 run 的 solution.pos.stat；解析明细与跨频率去重时间线留在 G:，未进仓库。\n\n## 5. BY2O 分段\n\n'
    text+=mdtable(data['segments'],['variant','segment','paired_epochs','valid_epochs','availability','valid_rmse_deg','hold_scored_epochs','hold_rmse_deg'])
    text+='\nprimary=[3369.94,3411.95]、secondary=[3495.94,3508.94] s，闭区间；outside 为补集。沿用 HX-05 heading_slice_statistics，不在段首重启因果保持，不再读取参考。来源 HX07R_BY2O_SEGMENTS.csv。\n\n## 6. 有效历元诊断\n\n'
    text+=mdtable(data['diagnostics'],['variant','sequence','n_valid_scored','abs_p50_deg','abs_p95_deg','abs_max_deg','abs_gt10_count','abs_gt10_fraction'])
    text+='\n10° 为任务事先指定阈值，分母为有参考支持的有效评分历元。该比例是整数固定错误的代理，不能确认每个整数解的正确性；参考航向不确定度约 1.1° 取自已 pin UNC_BUDGET.csv，未重新计算。明细来源各 HEADING_ERROR_SERIES_RTKLIB.csv；没有把缺失值当零。\n\n## 7. 手稿放置规则\n\nMAIN.06 原样保留，HX07R_MANUSCRIPT_ROWS.csv 的 V0 行保留 HX-05 全部原列内容，source 标 UNCHANGED_HX05_MAIN_06。V1 新增 MAIN.06b，行名“RTKLIB moving-base, GPS+Galileo+BDS+QZSS, external broadcast ephemeris (BKG BRDC)”。V0E、V2、V0-convbin、四变体 Q2、分段和诊断进补充。EXT01–EXT03 自写实现行的去向由作者依据已提交的 HX07_EXT_CLOCK_AUDIT.md 决定。本任务不改 HX-05 任何表。\n\n## 8. 勘误\n\nDG-01R 报告第 23 行“0.2 s 内自身运动 ≤1.2 mm”来自任务提示的单位笔误。应按两机钟差界 |Δclk|≤0.443 ms（DG01R_CLOCK_OFFSET.csv 的 max_abs_ms 最大值向上舍入）陈述：若平台速度≤1.2 m/s，则该时间内位移上界约 0.53 mm；若取 2 m/s，上界约 0.89 mm。计算分别为 0.443×1.2=0.5316 mm、0.443×2=0.886 mm；速度是此处的条件界，不是本任务新测的最大速度。DG-01R 原文不改，本条仅为勘误记录。\n\n## 9. 未做、不能判定与归档\n\n未运行 LegSA、其他外部方法、convbin，未调参、未重试、未新增观测或参考匹配规则，未改历史结果。不判断单一原因，也不以固定率替代整数正确率。缺少或格式不符的 $SAT 应明确 UNAVAILABLE。没有交接包。图数据仅由 HX07R 产物读取，机器 QA 在 HX07R_FIGURE_QA.json，实际视觉检查随后记入本报告。\n\n'
    text+=f'旧硬停提交 {h1}；登记提交 {reg["commit"]}（已 push）。结果提交为本文件所属提交（`git log -1 --format=%H -- docs/paper_rebuild/hext/HX07R/HX07R_REPORT.md`）；精确三提交哈希与 push 回执保存在 G: FINAL_RECEIPT.json。\n'
    (R/'HX07R_REPORT.md').write_text(text);(O/'HX07R_REPORT.md').write_text(text)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['build','report']);a=ap.parse_args()
    assert (O/'EXECUTION_DONE.json').exists() and not (O/'HARD_STOP.json').exists(),'scientific execution not completed'
    verify_pins()
    if a.mode=='build':data=tables();figure(data)
    else:data=json.loads((O/'REPORT_DATA.json').read_text())
    report(data);progress('REPORT_WRITTEN; visual/final metadata checks pending')


if __name__=='__main__':main()
