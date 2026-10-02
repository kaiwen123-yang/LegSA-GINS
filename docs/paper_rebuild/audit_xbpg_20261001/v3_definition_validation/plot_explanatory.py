#!/usr/bin/env python3
"""Three new explanatory figures from actual candidate errors and accepted R only."""
import argparse,csv,json,os
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
OBJECTS=[('N12_ONLY','RUN_01401','D15 F04','dual_antenna_yaw',['horizontal_err_m','yaw_err_deg']),
         ('N16_ONLY','RUN_00004','C00 F04','go2_horizontal_velocity',['horizontal_err_m','yaw_err_deg']),
         ('N09_RP_ONLY','ADD_RUN_00103','A1 20 s seed 00 F04','go2_attitude_roll_pitch',['horizontal_err_m','err_u_m','roll_err_deg','pitch_err_deg'])]
LABELS={'horizontal_err_m':'Horizontal error (m)','yaw_err_deg':'Yaw error (deg)',
        'err_u_m':'Up error (m)',
        'roll_err_deg':'Roll error (deg)','pitch_err_deg':'Pitch error (deg)'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--roots',type=Path,required=True)
    p.add_argument('--only',choices=[x[0] for x in OBJECTS]);a=p.parse_args()
    aliases=json.loads(a.roots.read_text())['aliases'];out=HERE/'figures';out.mkdir(exist_ok=bool(a.only))
    def resolve(s):
        for k,v in aliases.items():
            if s==k or s.startswith(k+'/'):return Path(v+s[len(k):])
        raise ValueError(s)
    sources=[]
    if a.only:
        with (out/'SOURCES.csv').open(newline='') as f:
            sources=[r for r in csv.DictReader(f) if not r['figure'].startswith(a.only+'_')]
    for candidate,run,title,source,cols in OBJECTS:
        if a.only and candidate!=a.only:continue
        fig,axes=plt.subplots(len(cols)+1,1,figsize=(10,2.1*(len(cols)+1)),sharex=True,layout='constrained')
        for variant,color in [('BASELINE','#34495e'),(candidate,'#d35400')]:
            metrics=json.loads((HERE/'evaluation/results'/variant/run/'FULL_METRICS.json').read_text())
            path=metrics['source_path'];data=pd.read_csv(resolve(path),encoding='utf-8-sig')
            t=data.time.to_numpy();gap=np.flatnonzero(np.diff(t)>.1)+1
            for ax,col in zip(axes,cols):
                y=data[col].to_numpy()
                # Display-only separators preserve the first real sample after each gap.
                ax.plot(np.insert(t,gap,np.nan),np.insert(y,gap,np.nan),lw=.65,color=color,
                        label='Original V3' if variant=='BASELINE' else candidate)
                ax.set_ylabel(LABELS[col]);ax.grid(alpha=.22)
                sources.append(dict(figure=candidate+'_'+run+'.png',variant=variant,run_id=run,source_path=path,
                    row_key='time; all retained matched rows',column=col,rows=len(data),plotted_finite=int(np.isfinite(y).sum()),
                    treatment='line break after dt > 0.1 s; all source rows retained; no smoothing/interpolation'))
            cache='<VALIDATION_ROOT>/analysis/event_cache/'+variant+'__'+run
            receipt=json.loads((resolve(cache)/'SCAN_RECEIPT.json').read_text())
            if receipt['stream_status']!='COMPLETE' or receipt['analysis_status']!='VALIDATED':raise ValueError('unvalidated event cache')
            tt=[];rr=[]
            with (resolve(cache)/'MEASUREMENTS.csv').open(newline='') as f:
                for row in csv.DictReader(f):
                    if row['source']!=source or row['actual_accepted']!='True':continue
                    record=json.loads(row['record']);sa=record.get('sa');ekf=record.get('ekf')
                    if not sa or not ekf:continue
                    def mat(x):return np.array(x['data']).reshape(x['rows'],x['cols'])
                    base=np.trace(mat(sa['base_R']));actual=np.trace(mat(ekf['R']))
                    if base<=0:raise ValueError('invalid R ratio domain')
                    tt.append(float(row['measurement_time']));rr.append(actual/base)
            if candidate=='N09_RP_ONLY':
                # Categorical lanes show original missing RP events without shifting a metric.
                axes[-1].plot(tt,[0 if variant=='BASELINE' else 1]*len(tt),ls='none',marker='.',ms=2.5,color=color)
                axes[-1].set_yticks([0,1],labels=['Original V3','N09_RP_ONLY'],fontsize=8)
                axes[-1].set_ylim(-.5,1.5)
                treatment='categorical accepted-event raster; y is variant, not R; actual R/base_R values='+repr(sorted(set(rr)))
            else:
                axes[-1].plot(tt,rr,ls='none',marker='.',ms=2.5,color=color,label='Original V3' if variant=='BASELINE' else candidate)
                treatment='actual accepted EKF R; source base_R at pre-SA stage; point markers, no gap bridging'
            sources.append(dict(figure=candidate+'_'+run+'.png',variant=variant,run_id=run,source_path=cache+'/MEASUREMENTS.csv',
                row_key='source='+source+';actual_accepted=True',column=('measurement_time;variant (categorical lane)' if candidate=='N09_RP_ONLY' else 'trace(ekf.R)/trace(sa.base_R);measurement_time'),rows=len(tt),plotted_finite=len(tt),
                treatment=treatment))
        axes[0].legend(loc='upper right',fontsize=8)
        axes[-1].set_ylabel('Accepted RP updates\n(categorical rows)' if candidate=='N09_RP_ONLY' else 'Accepted R / base R\n'+source.replace('_',' '),fontsize=8)
        axes[-1].set_xlabel('Original solver time (s); arrival time unknown');axes[-1].grid(alpha=.22)
        for ax in axes:
            ax.set_xlim(66,340)
            if 'ADD_RUN' in run:ax.axvspan(196.2,216.2,color='#9b59b6',alpha=.11)
        fig.suptitle(candidate+' | '+title+' | new validation, full original window',fontsize=12)
        fig.savefig(out/(candidate+'_'+run+'.png'),dpi=160);plt.close(fig)
    with (out/'SOURCES.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,sources[0].keys(),lineterminator='\n');w.writeheader();w.writerows(sources)
    (out/'README.md').write_text('''# 三张本轮说明图

本目录是新验证派生图，不覆盖或替代原论文图。N12展示D15不利变化，N16展示C00小变化，N09展示A1新增RP能力及水平/Up权衡；其余所有对象的完整指标仍以evaluation结果为准，不用这三图代表总体分布。

误差来自相同冻结评价器的新error_series，单位按字段标注；没有参考加误差重建NAV，也没有伪造轨迹。全窗固定66..340，A1阴影为原[196.2,216.2)；dt>0.1s处断线，不平滑、不插值、不改变指标样本。N12/N16权重点只取实际接受的EKF_BEFORE.R与同事件pre-SA base_R之比。N09末行是实际接受RP的分类事件轨道，y只标原版/候选，不代表R大小；实际RP倍率均1.5，原版中断窗没有更新的缺口保留。未接受/无事件处不补点，不能把策略accepted当真实更新。时间是原measurement_time，实际到达时刻未知。

逐图/列/筛选键/读取行数见SOURCES.csv；绘图属于新描述性派生，不是新增solver/evaluator或显著性检验。数学正确性与性能优劣分开，图不能证明因果收益或全矩阵结论。
''')
if __name__=='__main__':main()
