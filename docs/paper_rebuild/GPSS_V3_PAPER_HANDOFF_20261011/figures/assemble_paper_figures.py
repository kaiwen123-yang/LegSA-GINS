"""Assemble already reviewed scientific figures, captions and comparison coverage."""
from pathlib import Path
import csv,json,html,re
import fitz

ROOT=Path(__file__).resolve().parent
REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
Q={'Q1':'机器人自身观测缺少什么约束？','Q2':'短基线GNSS方向何时可靠？','Q3':'融合精度与输出连续性如何？','Q4':'机身运动信息起了什么作用？','Q5':'来源加权的收益与代价是什么？'}
def posix(p):
    p=str(p)
    return Path('/mnt/g/'+p[3:]) if p.startswith('G:/') else Path(p)
def win(p):
    s=str(p);return 'G:/'+s[len('/mnt/g/'):] if s.startswith('/mnt/g/') else s
def csvsave(name,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def main():
    figures=json.loads((ROOT/'REUSED_FIGURES.json').read_text());tables=[];packages={}
    for name in ['robot','heading','navigation','aiding']:
        p=ROOT/name/'SECTION_PACKAGE.json';d=json.loads(p.read_text());packages[name]=d
        figures.extend(d['figures']);tables.extend([{**t,'section':name} for t in d.get('tables',[])])
    tables.extend(json.loads((ROOT/'EXTRA_TABLES.json').read_text()))
    assert len({f['id'] for f in figures})==len(figures)
    supplemental_order={'S_Q4_tilt_aiding':0,'S_Q4_heading_information':1}
    figures.sort(key=lambda r:(r['role']!='main',r['question'],supplemental_order.get(r['id'],0),r['id']))
    records=[];counts={'main':0,'supplement':0};errors=[]
    for entry in figures:
        path=posix(entry['path']);meta=posix(entry['metadata_path']);r=json.loads(meta.read_text())
        for suffix in ['.png','.pdf','.svg']:
            if not path.with_suffix(suffix).exists():errors.append([entry['id'],'missing',suffix])
        if r.get('visual_review')!='PASS':errors.append([entry['id'],'visual_review',r.get('visual_review')])
        if any(int(v)!=0 for v in r.get('audit_returncodes',{}).values()):errors.append([entry['id'],'audit',r.get('audit_returncodes')])
        with fitz.open(path.with_suffix('.pdf')) as doc:
            width=doc[0].rect.width*25.4/72;height=doc[0].rect.height*25.4/72
        if abs(width-174)>.05:errors.append([entry['id'],'width',width])
        counts[entry['role']]+=1;label=('M' if entry['role']=='main' else 'S')+str(counts[entry['role']])
        preview=path.parent/'preview'/path.name
        assert preview.exists(),preview
        records.append({**entry,'label':label,'path':win(path),'metadata_path':win(meta),'preview':win(preview),
          'caption_zh':r['caption_zh'],'caption_en':r['caption_en'],'meaning_zh':r['meaning_zh'],
          'pdf':win(path.with_suffix('.pdf')),'svg':win(path.with_suffix('.svg')),
          'width_mm':round(width,3),'height_mm':round(height,3),'relative_image':str(preview.relative_to(ROOT))})
    assert not errors,errors
    byid={r['id']:r for r in records}
    # Every completed identity receives an explicit paper destination; unexecuted
    # registrations remain visible in the mapping without fabricated performance.
    registry=REPO/'docs/paper_rebuild/GPSS_V3_PAPER_START_20261008/EXTERNAL_METHOD_ACCEPTANCE.csv'
    original=list(csv.DictReader(registry.open(encoding='utf-8-sig')))
    dest={
      'EXT01':('SQ2_raw_dual_antenna_methods','heading/tables/EXISTING_HEADING_METRICS.csv'),
      'EXT02':('SQ2_raw_dual_antenna_methods','heading/tables/EXISTING_HEADING_METRICS.csv'),
      'EXT03':('SQ2_raw_dual_antenna_methods','heading/tables/EXISTING_HEADING_METRICS.csv'),
      'EXT04':('','heading/tables/FAR_PAR_ALL_THREE_TRIALS.csv'),
      'RTKLIB_UNMODIFIED_MOVING_BASE':('Q2_heading_availability_and_consistency','heading/tables/EXISTING_HEADING_METRICS.csv'),
      'RTKLIB_V0E':('SQ2_RTKLIB_all_configurations','heading/tables/EXISTING_HEADING_METRICS.csv'),
      'RTKLIB_V1':('SQ2_RTKLIB_all_configurations','heading/tables/EXISTING_HEADING_METRICS.csv'),
      'RTKLIB_V2':('SQ2_RTKLIB_all_configurations','heading/tables/EXISTING_HEADING_METRICS.csv'),
      'LC01':('Q3_01_IEKF_natural','navigation/data/IEKF_ALL16_CONDITIONS_WITH_PARAMETERS.csv'),
      'LC01-S':('Q3_01_IEKF_natural','navigation/data/IEKF_ALL16_CONDITIONS_WITH_PARAMETERS.csv'),
      'EXT05C':('Q3_02_heading_retention','navigation/data/IEKF_ALL16_CONDITIONS_WITH_PARAMETERS.csv'),
      'EXT05C-S':('','navigation/data/IEKF_ALL16_CONDITIONS_WITH_PARAMETERS.csv'),
      'LC02_GINAV':('','navigation/data/GINAV_ACTUAL_RESULTS.csv'),
      'Hartley':('S01_robot_relative_motion','robot/ROBOT_RELATIVE_RESULTS.csv'),
      'LEG_DR':('S01_robot_relative_motion','robot/ROBOT_RELATIVE_RESULTS.csv'),
      'OISAM':('Q3_oisam_precision_continuity','navigation/data/V3_OISAM_COMMON_POINT.csv'),
      'WEN_TC':('Q3_05_FGO_position','navigation/data/FGO_GNSS1_ALL36_RESULTS.csv'),
      'GNC':('Q3_05_FGO_position','navigation/data/FGO_GNSS1_ALL36_RESULTS.csv'),
    }
    coverage=[];methods=[]
    for row in original:
        ident=row['internal_identity'];executed=row['execution_ledger_acceptance']=='PASS'
        fid,table=dest.get(ident,('',''))
        if executed and ident not in dest:errors.append([ident,'missing completed destination'])
        if table and not (ROOT/table).exists():errors.append([ident,'missing table',table])
        label=byid[fid]['label'] if fid else ''
        name=row['reader_name'];inputs=row['input_layer']
        if ident=='LEG_DR':name='Contact-kinematic integration with onboard attitude';inputs='contact-foot position/velocity + body angular rate + onboard attitude'
        coverage.append({'identity':ident,'reader_name':name,'execution_record':'completed execution record' if executed else 'not an executed comparison',
          'figure':label,'figure_id':fid,'figure_file':byid[fid]['path'] if fid else '',
          'table':win(ROOT/table) if table else '',
          'paper_use':('main figure' if fid and byid[fid]['role']=='main' else 'supplement figure/table') if executed else 'registration history only',
          'actual_result_scope':row['actual_result_scope'],'input_layer':inputs,
          'original_evidence':row['existing_asset_roots_or_evidence']})
        if executed:
            methods.append({'method_condition':name,'online_inputs':inputs,'initialization':row['initialization_information'],
              'estimated_state':row['estimated_state'],'heading_quantity':row['attitude_quantity'],
              'position_and_evaluation_point':row['position_quantity_and_POI'],'paper_figure':label,
              'implementation':row['author_algorithm_vs_project_boundary']})
    # Additional completed controls and diagnostic studies beyond the 30-row index.
    extras=[
      ('LC01-BR','Q3_02_heading_retention','navigation/data/A2_ALL18_MATCHED_RESULTS.csv','Relative-baseline updates during translational interruption; all18 retained'),
      ('Classic-18 and A2','Q3_04_all_degradation_pairs','navigation/data/DEGRADATION_EXTERNAL_TABLE_R2.csv','396 logical rows and744 paired summaries; native failures retained'),
      ('OiSAM gap reinitialization','Q3_03_OiSAM_reinitialized_heading','navigation/data/FGO_GNSS1_ALL36_RESULTS.csv','11 input-defined blocks and all dynamic outputs'),
      ('Hartley gauge/observability','Q1_proprioception_absolute_heading','robot/Q1_proprioception_absolute_heading.json','Seven initial headings and five structural windows'),
      ('Historical QA wrappers','','review/HISTORICAL_QA_COMPLETION_RECORD.csv','1897 evaluable rows documented in historical summary; payload retired/unlocated, not frozen-V3 performance'),
      ('Later NMB/XB transfer','','review/LATER_TRANSFER_RESULTS.csv','16 recorded combinations, eight completed/eight no-init; later stage07 IMU-time implementation and input alignment, separate from frozen-V3 performance'),
    ]
    for ident,fid,table,scope in extras:
        if table:assert (ROOT/table).exists(),table
        coverage.append({'identity':ident,'reader_name':ident,'execution_record':'completed record; see version scope','figure':byid[fid]['label'] if fid else '',
          'figure_id':fid,'figure_file':byid[fid]['path'] if fid else '', 'table':win(ROOT/table) if table else win(ROOT/'历史研究与暂未使用项.md'),
          'paper_use':'supplement/structural evidence' if fid else 'research-history appendix','actual_result_scope':scope})
    assert not errors,errors
    csvsave('COMPARISON_USE_MAP.csv',coverage);csvsave('METHODS_AND_EVALUATION.csv',methods)
    csvsave('FIGURE_CATALOG.csv',[{k:v for k,v in r.items() if k!='relative_image'} for r in records])
    unique_tables={str(posix(t['path'])):t for t in tables}
    for path in unique_tables:assert Path(path).exists(),path
    csvsave('TABLE_CATALOG.csv',[{'table_id':'T'+str(i+1),'section':t['section'],'title':t.get('title',Path(p).stem),'path':win(p)} for i,(p,t) in enumerate(unique_tables.items())])
    md=['# 五个问题的主文与补充图\n\n先读主文6组图，再按需要展开补充。完整结果与方法去向见COMPARISON_USE_MAP.csv。\n']
    caps=['# 完整中英文图注\n']
    sections=[]
    for q in Q:
        cards=[];md.append('## '+q+' '+Q[q]+'\n')
        for r in [x for x in records if x['question']==q]:
            kind='正文' if r['role']=='main' else '补充'
            md.append(f"### {r['label']} {r['title_zh']}（{kind}）\n\n{r['meaning_zh']}\n\n![{r['title_zh']}]({r['preview']})\n\n{r['caption_zh']}\n\n[PDF]({r['pdf']}) · [SVG]({r['svg']})\n")
            caps.append(f"## {r['label']} {r['title_zh']}\n\n{r['caption_zh']}\n\n{r['caption_en']}\n")
            relpdf=str(posix(r['pdf']).relative_to(ROOT));relsvg=str(posix(r['svg']).relative_to(ROOT));relpng=str(posix(r['path']).relative_to(ROOT))
            content=f'<article class="{r["role"]}"><h3>{r["label"]} {html.escape(r["title_zh"])}</h3><p>{html.escape(r["meaning_zh"])}</p><a href="{relpng}"><img loading="lazy" src="{r["relative_image"]}" alt="{html.escape(r["title_zh"])}"></a><p class="caption">{html.escape(r["caption_zh"])}</p><details><summary>English caption</summary><p>{html.escape(r["caption_en"])}</p></details><p><a href="{relpdf}">PDF</a> · <a href="{relsvg}">SVG</a></p></article>'
            if r['role']=='supplement':content='<details class="supplement"><summary>'+r['label']+' '+html.escape(r['title_zh'])+'</summary>'+content+'</details>'
            cards.append(content)
        sections.append(f'<section id="{q}"><h2>{q} {Q[q]}</h2>'+''.join(cards)+'</section>')
    (ROOT/'完整图件与读法.md').write_text('\n'.join(md),encoding='utf-8')
    (ROOT/'CAPTIONS_ZH_EN.md').write_text('\n'.join(caps),encoding='utf-8')
    doc='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>五个问题 · 论文图件</title><style>body{max-width:1120px;margin:25px auto;padding:0 25px;font:16px system-ui,sans-serif;color:#222;background:#fff}h1{font-size:27px}h2{font-size:24px;margin-top:52px;border-bottom:1px solid #ccc;padding-bottom:10px}h3{font-size:20px}p{line-height:1.75}nav{line-height:2.2}nav a{margin-right:18px}a{color:#08658c}img{display:block;width:100%;height:auto}article{margin:25px 0 45px}summary{cursor:pointer;font-weight:600;padding:12px 0}.caption{font-size:15px}section{scroll-margin:20px}</style><h1>五个连续问题的论文图件</h1><p>主文6组图承担论证；9组补充图保留完整比较和条件。每组图可打开PDF或SVG，补充图点击标题展开。</p><nav>'+''.join(f'<a href="#{q}">{q}</a>' for q in Q)+'</nav>'+''.join(sections)+'</html>'
    (ROOT/'五问题图件总览.html').write_text(doc,encoding='utf-8')
    completed=sum(r['execution_ledger_acceptance']=='PASS' for r in original)
    result={'status':'FIGURES_AND_COVERAGE_VALIDATED','main_figures':counts['main'],'supplement_figures':counts['supplement'],
      'total_figure_groups':len(records),'exports_png_pdf_svg':len(records)*3,'table_files':len(unique_tables),
      'registered_identities':len(original),'completed_identities_with_destinations':completed,
      'additional_control_and_history_rows':len(extras),'five_questions_covered':sorted({r['question'] for r in records}),
      'new_scientific_solver_calls':0,'new_scientific_evaluator_calls':0,'new_provider_calls':0,
      'errors':errors}
    (ROOT/'DELIVERY_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
