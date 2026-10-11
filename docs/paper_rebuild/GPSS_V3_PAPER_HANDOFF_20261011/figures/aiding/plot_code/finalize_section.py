"""Assemble reviewed Q4/Q5 figures and complete saved-result tables."""
from pathlib import Path
import json, hashlib, subprocess, sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
figs=[('Q4_body_velocity','保留航向时的机身速度辅助','main','Q4'),('Q5_source_weighting','来源加权的收益与精度代价','main','Q5'),('S_Q4_tilt_aiding','机载倾角辅助与姿态误差','supplement','Q4'),('S_Q4_heading_information','基础GNSS/INS加入双天线航向的作用','supplement','Q4')]
reviews={
'Q4_body_velocity':'彩色/灰度逐面板检查；完整GNSS中断曲线近重合保留；0–2.5 m插图已明确纵轴范围；全部45布置成对显示。插图零刻度位于浅灰中断填充边界，文字可读且无描边碰撞。',
'Q5_source_weighting':'彩色/灰度逐面板检查；来源图例置于真实权重最大值上方；实际6来源保留表、图选3来源；513个成对点全部保留。中位差文字与散点栅格图层包围框重叠但不遮任何数据点。',
'S_Q4_tilt_aiding':'彩色/灰度逐面板检查；同一误差分量跨场景共享纵轴；三场景自然全时序无降采样，叠合保留。',
'S_Q4_heading_information':'彩色/灰度逐面板检查；三条曲线全时序保留；F03/F04近重合为原始结果；局部窗口与浅灰标记一一对应，纵轴跨场景一致。'}

out=[];caps=[]
for ident,title,role,q in figs:
    p=ROOT/'figures'/(ident+'.json');d=json.loads(p.read_text())
    assert all(v==0 for v in d['audit_returncodes'].values())
    assert abs(d['width_mm']-174)<1e-6
    d.update(visual_review='PASS',visual_review_notes=reviews[ident],role=role,question=q,title_zh=title)
    hashes={ext:hashlib.sha256((ROOT/'figures'/(ident+'.'+ext)).read_bytes()).hexdigest() for ext in ['png','pdf','svg']}
    d['export_sha256']=hashes
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    out.append({'id':ident,'title_zh':title,'role':role,'question':q,'path':str(ROOT/'figures'/(ident+'.png')),'preview_path':str(ROOT/'figures/preview'/(ident+'.png')),'metadata_path':str(p),'audit_returncodes':d['audit_returncodes'],'visual_review':'PASS'})
    caps.extend(['## '+title,'',d['caption_zh'],'',d['caption_en'],''])
(ROOT/'CAPTIONS.md').write_text('\n'.join(caps))
tables=[{'path':str(p),'rows':len(pd.read_csv(p))} for p in sorted((ROOT/'tables').glob('*.csv'))]
package={'section':'Q4_Q5','scientific_commit':'7d43b9af26120ed5dde21f53e515386361072ba6','figures':out,'tables':tables,'configuration_coverage':{'unique_runs':6468,'core_runs':5951,'natural_rows':33,'addendum_runs':495,'effective_configurations':11,'singlemodule_case_pairs':2164,'full_duration_combinations':55,'addendum_placements':45,'full_loss_duration_s':[10,20,30],'heading_retained_duration_s':[10,20],'placements_per_duration':9,'source_weight_trace_rows':7930},'new_solver_runs':0,'new_evaluator_runs':0,'figure_sources_read_in_full':True,'results':str(ROOT/'RESULTS_ZH.md'),'captions':str(ROOT/'CAPTIONS.md')}
(ROOT/'SECTION_PACKAGE.json').write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n')
qa=ROOT/'figures/qa'
source='\n'.join((ROOT/'plot_code'/n).read_text() for n in ['paper_style.py','build_aiding_figures.py','build_section.py'])
(qa/'assembled_source_for_static_check.py').write_text(source)
r=subprocess.run([sys.executable,'/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts/validate_figure.py',str(qa/'assembled_source_for_static_check.py')],capture_output=True,text=True)
(qa/'static_validation.log').write_text(r.stdout+r.stderr)
assert r.returncode==0
(qa/'QA_REVIEW.md').write_text('四幅图均实际检查彩色与灰度、最终PDF文字和对齐。所有导出碰撞检查返回0。\n\n静态检查的宽度警告将174*MM误读为174英寸，实际四图均174 mm；600 dpi PNG和矢量PDF/SVG是本次输出合同，未请求TIFF。中断配对图显示全部九个值而非用误差棒替代。对数坐标所用原始RMSE均正数。所有时间曲线使用原记录，局部视窗筛选只是显示范围。\n\n'+ '\n\n'.join(k+': '+v for k,v in reviews.items()))
print(json.dumps({'figures':len(out),'tables':len(tables),'qa':'PASS'},ensure_ascii=False))
