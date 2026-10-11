"""Finalize the three visually reviewed Q2 figures and their evidence inventory."""
from pathlib import Path
import json, csv, hashlib, subprocess, sys, shutil
import pandas as pd
from PIL import Image
import fitz

OUT=Path(__file__).resolve().parent
SCRIPTS=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
OLD=Path('/mnt/g/LegSA-GINS-project/V3论文组图_20261008/redesign_20261009/figures')
def public(p):return str(p).replace('/mnt/g/','G:/')
ids=['Q2_heading_availability_and_consistency','SQ2_RTKLIB_all_configurations','SQ2_raw_dual_antenna_methods']
titles=['RTKLIB原配置下短基线航向的输出与物理一致性','RTKLIB四配置的航向误差与输出连续性','三种原始双天线处理路线的误差分布与输出']
figures=[];captions=['# Q2 中英文图注\n']
for id,title in zip(ids,titles):
    p=OUT/(id+'.json');d=json.loads(p.read_text())
    if id=='SQ2_RTKLIB_all_configurations':
        for name in ['alignment.json','pdf_text.log','collisions.json','collisions.log']:
            shutil.copy2(OLD/'qa'/('C03.'+name),OUT/'qa'/(id+'.original_'+name))
        run=subprocess.run([sys.executable,str(SCRIPTS/'audit_pdf_text.py'),str(OUT/(id+'.pdf')),'--min-pt','5','--json'],text=True,capture_output=True)
        (OUT/'qa'/(id+'.pdf_text.log')).write_text(run.stdout+run.stderr)
        d['audit_returncodes']['pdf_text']=run.returncode
        run=subprocess.run([sys.executable,str(SCRIPTS/'audit_figure_collisions.py'),str(OUT/(id+'.pdf')),'--json-out',str(OUT/'qa'/(id+'.collisions.json'))],text=True,capture_output=True)
        (OUT/'qa'/(id+'.collisions.log')).write_text(run.stdout+run.stderr)
        d['audit_returncodes']['collisions']=run.returncode
    assert all(v==0 for v in d['audit_returncodes'].values()) and d['alignment_status']=='PASS'
    with Image.open(OUT/(id+'.png')) as im:
        dpi=im.info.get('dpi');size=im.size
        assert dpi and min(dpi)>599
    with fitz.open(OUT/(id+'.pdf')) as pdf:
        w=pdf[0].rect.width/72*25.4; assert abs(w-174)<.02
    d['title_zh']=title;d['visual_review']='PASS'
    d['visual_review_receipt']={'date':'2026-10-11','color':'viewed','grayscale':'viewed','assessment':'Panel alignment, uncut labels, retained full error scales and clear independent output rows. CDF panels retain all native-valid samples. Main figure has0–20deg inset and10–22s baseline enlargement.','export_sha256':{e:hashlib.sha256((OUT/(id+'.'+e)).read_bytes()).hexdigest() for e in ['png','pdf','svg']},'png_size':size,'png_dpi':dpi,'pdf_width_mm':w}
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    figures.append({'id':id,'title_zh':title,'role':'main' if id==ids[0] else 'supplement','question':'Q2','path':public(OUT/(id+'.png')),'preview_path':public(OUT/'preview'/(id+'.png')),'metadata_path':public(p)})
    captions.extend([f'## {title}\n',d['caption_en']+'\n',d['caption_zh']+'\n','读图目的：'+d['meaning_zh']+'\n'])
(OUT/'CAPTIONS.md').write_text('\n'.join(captions),encoding='utf-8')
coverage=[]
for ident,label in [('V0','原配置'),('V0E','更换星历'),('V1','多星座'),('V2','fix-and-hold')]:
    coverage.append({'method':'RTKLIB '+ident,'version':'HX07R','scope':'3 trials','status':'completed','used_in':ids[1]+(' + '+ids[0] if ident=='V0' else ''),'source_table':'tables/EXISTING_HEADING_METRICS.csv','role':'heading_output_comparison'})
for method in ['EXT01 C-LAMBDA','EXT02 C-WLS','EXT03 DD-KF']:
    coverage.append({'method':method,'version':'EXT V2 generation2','scope':'3 trials','status':'completed','used_in':ids[2],'source_table':'tables/EXISTING_HEADING_METRICS.csv','role':'candidate_direction_comparison'})
for method in ['EXT04 FAR','EXT04 PAR']:
    coverage.append({'method':method,'version':'HX02 declared policies','scope':'3 trials','status':'completed_zero_accepted','used_in':'Supplemental result table','source_table':'tables/FAR_PAR_ALL_THREE_TRIALS.csv','role':'acceptance_outcome'})
for method,table,role in [('DG01','DG01_OVERVIEW.csv','input_conditions'),('DG01R','DG01R_VERSION_COMPARISON.csv','clock_and_halfcycle_diagnosis'),('RTKLIB trace4','RTKLIB_EPOCH_DIAGNOSTICS.csv','main_figure_mechanism'),('Input history','INPUT_AUDIT_SUMMARY.json','input_equivalence'),('Classic candidate qualification','CLASSIC_QUALIFICATION_RESULTS.csv','synthetic_implementation_qualification'),('Two-epoch motion prototype','MOTION_PAIR_RESULTS.csv','separate_research_branch')]:
    coverage.append({'method':method,'version':'Saved completed results','scope':'See source table','status':'completed','used_in':ids[0] if method=='RTKLIB trace4' else 'Supplemental evidence table','source_table':'tables/'+table,'role':role})
pd.DataFrame(coverage).to_csv(OUT/'METHOD_COVERAGE.csv',index=False)
f=pd.read_csv(OUT/'tables/FAR_PAR_ALL_THREE_TRIALS.csv')
f['window_paired_epochs']=f.sequence.map({'BY2':1370,'BY2H':1350,'BY2O':1885})
f['window_accepted_count']=0
f[['sequence','policy_identity','row_count','accepted_count','FAR_REJECTED_count','PAR_EXHAUSTED_count','INVALID_count','window_paired_epochs','window_accepted_count']].to_csv(OUT/'tables/FAR_PAR_READER_TABLE.csv',index=False)
metrics=pd.read_csv(OUT/'tables/EXISTING_HEADING_METRICS.csv')
metrics[['sequence_id','method_id','support','paired_epoch_denominator','available_epoch_count','rmse_deg','p95_absolute_deg','max_absolute_deg','native_valid_maximum_gap_s']].to_csv(OUT/'tables/HEADING_METRICS_READER_TABLE.csv',index=False)
tables=[{'path':public(p),'rows':len(pd.read_csv(p))} for p in sorted((OUT/'tables').glob('*.csv'))]
tables.extend({'path':public(p),'type':'structured_diagnostic'} for p in sorted((OUT/'tables').glob('*.json')))
package={'question':'Q2','title_zh':'短基线GNSS方向何时可靠','claim_zh':'当前0.35m安装中，新固定输出的连续性与已输出方向的物理一致性需要分别判断。','figures':figures,'tables':tables,'method_coverage':coverage,'method_coverage_path':public(OUT/'METHOD_COVERAGE.csv'),'results_path':public(OUT/'RESULTS_ZH.md'),'captions_path':public(OUT/'CAPTIONS.md'),'source_notes_path':public(OUT/'SOURCE_NOTES.md'),'source_reads_path':public(OUT/'SOURCES_READ.csv'),'new_solver_calls':0,'new_evaluator_calls':0,'new_provider_calls':0,'validation':'PASS: actual color/grayscale review, panel alignment, PDF text, PDF collisions,174mm and600dpi checks','status':'COMPLETE'}
(OUT/'SECTION_PACKAGE.json').write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'figures':len(figures),'tables':len(tables),'methods_or_evidence_rows':len(coverage),'status':'COMPLETE'},ensure_ascii=False))
