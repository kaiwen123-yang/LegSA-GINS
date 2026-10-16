from pathlib import Path
import pandas as pd, numpy as np, json, shutil, hashlib
ROOT=Path('/mnt/g/LegSA-GINS-project')
OUT=ROOT/'V3五问题论文组图_20261011/navigation'
DATA=OUT/'data';DATA.mkdir(parents=True,exist_ok=True)
REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
SRC=REPO/'docs/paper_rebuild/GPSS_V3_FIGURES_20261008/redesign_20261009'
FUS=ROOT/'V3研究记录梳理_20261011/fusion'
SEG=ROOT/'V3论文组图_20261008/focused_20261011/comparison/data'
OLD=ROOT/'V3论文组图_20261008/redesign_20261009/figures'
R2=REPO/'docs/paper_rebuild/hext/HX03R2'
manifest=[];profiles=[]
def read(p):
    p=Path(p);b=p.read_bytes();manifest.append({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'reading':'full'})
    if p.name.endswith(('.csv','.csv.gz')):
        d=pd.read_csv(p);profiles.append({'path':str(p),'rows':len(d),'columns':list(d),'missing':d.isna().sum().to_dict(),'numeric_ranges':{c:[float(d[c].min()),float(d[c].max())] for c in d.select_dtypes('number') if d[c].notna().any()}});return d
    return json.loads(b) if p.suffix=='.json' else b.decode('utf-8-sig')
for f in ['paper_style.py','paper_names.py']:shutil.copy2(SRC/f,OUT/f)
for old,new in [('C01','Q3_01_IEKF_natural'),('C02','Q3_05_FGO_position')]:
    for ext in ['png','pdf','svg']:shutil.copy2(OLD/(old+'.'+ext),OUT/(new+'.'+ext))
    j=read(OLD/(old+'.json'));j['id']=new;j['reused_original_id']=old
    for p in j['sources']:
        if Path(p).exists():read(p)
    if old=='C02':
        j['caption_en']+=' OiSAM uses reinitialization at recorded IMU gaps, with initialization-only states excluded. OiSAM uses RTK position and IMU, TC-FGO uses raw code and adapted attitude/velocity inputs, and GNC-FGO uses raw code and Doppler; input information is not identical.'
        j['caption_zh']+=' OiSAM在实测IMU缺口处重新初始化，仅初始化的状态不计入曲线。OiSAM使用RTK位置与IMU，TC-FGO使用原始码及适配姿态/速度输入，GNC-FGO使用原始码和Doppler；三条路线的输入信息不同。'
    (OUT/(new+'.json')).write_text(json.dumps(j,ensure_ascii=False,indent=2))
    (OUT/'preview').mkdir(exist_ok=True);(OUT/'qa').mkdir(exist_ok=True)
    for suffix in ['.png','_gray.png']:shutil.copy2(OLD/'preview'/(old+suffix),OUT/'preview'/(new+suffix))
    for p in (OLD/'qa').glob(old+'.*'):shutil.copy2(p,OUT/'qa'/p.name.replace(old,new,1))
for name in ['DEGRADATION_EXTERNAL_TABLE_R2.csv','DEGRADATION_PAIRED_R2.csv','DEGRADATION_EXTERNAL_SUMMARY_R2.csv']:
    d=read(R2/name);d.to_csv(DATA/name,index=False)
tab=pd.read_csv(DATA/'DEGRADATION_EXTERNAL_TABLE_R2.csv')
add=read(REPO/'docs/paper_rebuild/GPSS_V3_PAPER_START_20261008/FIGURE_PLAN_INTERNAL/ADD495.csv')
av=read(REPO/'docs/paper_rebuild/GPSS_V3_PAPER_START_20261008/FIGURE_PLAN_INTERNAL/ERROR_SERIES_AVAILABILITY6468.csv')
f04=add[(add.case_family=='A2')&(add.internal_method_id=='F04')].copy()
f04.to_csv(DATA/'A2_F04_existing.csv',index=False)
for m in ['LC01','EXT05C','LC01-BR']:
    p=ROOT/f'clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL/RUNS/BY2__{m}__LIT__D62_20s_seed_00__seed_00/v3_R2/error_series_R2.csv.gz'
    read(p).to_csv(DATA/(m+'_A2_20s_seed00.csv.gz'),index=False)
row=f04[(f04.duration_s==20)&(f04.seed_index=='seed_00')].iloc[0]
fp=Path(av.loc[av.run_id==row.run_id,'path'].iloc[0]);read(fp).to_csv(DATA/'F04_A2_20s_seed00.csv.gz',index=False)
for s in ['BY2','BY2H','BY2O']:
    for suffix in ['COMMON_SEGMENTED_HEADING.csv.gz','OISAM_SEGMENTED_heading.csv.gz','OISAM_SEGMENTED_EXISTING_METRICS.csv','METADATA.json']:
        p=SEG/(s+'_'+suffix);d=read(p);shutil.copy2(p,DATA/p.name)
for n in ['GAPS.csv','SOURCE_BLOCKS.csv','OUTPUT_INTERVALS.csv']:read(SEG/n).to_csv(DATA/n,index=False)
for n in ['LC_NATIVE_TABLE_READ.csv','EXPERIMENTS.csv']:
    d=read(FUS/n)
    if n=='EXPERIMENTS.csv':
        # Repair only the exported locator spelling; metrics and states stay unchanged.
        d['error_series']=d.error_series.str.replace('HX03R2_AUDIT_REEVALR2','HX03R2_AUDIT_REEVAL',regex=False).str.replace('/v3_R2/v3_R2/','/v3_R2/',regex=False)
    d.to_csv(DATA/n,index=False)
params=[]
for rec in read(FUS/'HX03_ACTUAL_RUNS_READ.json'):
    params.append({'method':rec['method'],**pd.json_normalize(rec['params']).iloc[0].to_dict(),'source_parameter_sha256':rec['params'].get('parameter_source_sha256'),'intervals_s':json.dumps(rec['input']['report']['intervals']),'relative_only_updates':rec['native'].get('relative_only_update_count')})
pd.DataFrame(params).to_csv(DATA/'IEKF_A2_PARAMETERS.csv',index=False)
ex=pd.read_csv(DATA/'EXPERIMENTS.csv');gin=[];ginfull=[]
for _,r in ex[ex.method.str.contains('GINav',na=False)].iterrows():
    native=read(r.native_record);ev=read(r.error_series);gate=ev['bounded_gate'];cov=ev['coverage'];metrics=ev.get('v3',{})
    gd={'sequence':r.sequence,'method':r.method,'configuration':r.configuration,'status':r.status,'native_returncode':native['returncode'],'native_runtime_s':native['runtime_seconds'],'input_config':native['config'],'first_output_rel_s':cov.get('first_valid_rel_s'),'last_output_rel_s':cov.get('last_valid_rel_s'),'leading_missing_s':cov.get('leading_missing_s'),'output_count':cov.get('valid_rows_in_window'),'nominal_count':cov.get('expected_integer_epochs'),'temporal_coverage_fraction':cov.get('temporal_coverage_fraction'),'row_coverage_fraction':cov.get('row_coverage_fraction'),'first_violation':json.dumps(gate.get('first_violation')),'max_speed_mps':gate['maxima']['speed_mps'],'horizontal_rmse_m':metrics.get('horizontal_rmse_m'),'yaw_rmse_deg':metrics.get('yaw_rmse_deg'),'up_rmse_m':metrics.get('up_rmse_m'),'native_pos_sha256':native['native_pos_sha256']}
    ini=read(native['config']);gd['config_text']=ini;gin.append(gd);ginfull.append({'sequence':r.sequence,'native':native,'evaluation':ev,'config_text':ini})
pd.DataFrame(gin).to_csv(DATA/'GINAV_ACTUAL_RESULTS.csv',index=False)
(DATA/'GINAV_FULL_RECORDS.json').write_text(json.dumps(ginfull,ensure_ascii=False,indent=2))
pd.DataFrame(manifest).to_csv(DATA/'SOURCE_MANIFEST.csv',index=False)
(DATA/'FULL_RESULT_PROFILE.json').write_text(json.dumps(profiles,ensure_ascii=False,indent=2))
print('read',len(manifest),'files;',sum(x['rows'] for x in profiles),'rows; A2 rows',len(f04))
