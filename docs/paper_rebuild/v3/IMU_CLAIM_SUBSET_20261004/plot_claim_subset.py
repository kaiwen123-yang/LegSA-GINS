from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
STAGE=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/IMU_V3_CLAIM_SUBSET_20261004T064538Z')
root=STAGE/'PUBLICATION';table=root/'PAIRED_ALL_90_CASES_DOMAINS.csv'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
receipt=json.loads((root/'REDUCTION_RECEIPT.json').read_text());before=sha(table)
assert receipt['publication_csv_sha256'][table.name]==before
reduction_receipt_before=sha(root/'REDUCTION_RECEIPT.json')
data=pd.read_csv(table);assert len(data)==2520
cases=sorted(data.case_id.unique());assert len(cases)==45
panels=[('fault','H','Outage horizontal RMSE difference (m)'),
        ('outage_end','H','Exact outage-end horizontal error difference (m)'),
        ('fault','yaw','Outage yaw RMSE difference (deg)'),
        ('outage_end','yaw','Exact outage-end absolute yaw error difference (deg)')]
plt.rcParams.update({'font.size':10,'axes.titlesize':11,'axes.labelsize':10,'pdf.fonttype':42,'ps.fonttype':42})
fig,axes=plt.subplots(2,2,figsize=(13,24),layout='constrained')
for ax,(domain,metric,title) in zip(axes.flat,panels):
    subset=data[(data.domain==domain)&(data.metric==metric)]
    array=subset.pivot(index='case_id',columns='ablation_method',values='delta_full_minus_ablation').reindex(index=cases,columns=['A03','A06']).to_numpy(float)
    maximum=float(np.nanmax(np.abs(array))) if np.isfinite(array).any() else 1.;maximum=max(maximum,1e-12)
    color=plt.get_cmap('coolwarm').copy();color.set_bad('#dddddd')
    image=ax.imshow(np.ma.masked_invalid(array),aspect='auto',cmap=color,vmin=-maximum,vmax=maximum,interpolation='nearest')
    ax.set_yticks(range(45),[c.replace('_seed_',' / ') for c in cases],fontsize=8)
    ax.set_xticks([0,1],['F04 - A03\nRD increment','F04 - A06\nHV increment'])
    ax.set_title(title,pad=10)
    for row in range(45):
        for col in range(2):
            v=array[row,col];label='NA' if not np.isfinite(v) else f'{v:+.3g}'
            ax.text(col,row,label,ha='center',va='center',fontsize=7,
                    color='white' if np.isfinite(v) and abs(v)>maximum*.6 else 'black')
    for y in (8.5,17.5,26.5,35.5):ax.axhline(y,color='black',lw=.65)
    fig.colorbar(image,ax=ax,fraction=.035,pad=.015)
fig.suptitle('All 45 fixed controlled cases; diagnostic error relative to commercial fused reference\nNegative: F04 lower error. Positive: F04 higher error. No case selection. Nine placement anchors are reused.',fontsize=12)
fig.savefig(root/'ALL45_PAIRED_HEATMAP.png',dpi=170);fig.savefig(root/'ALL45_PAIRED_HEATMAP.pdf');plt.close(fig)
groups=[('D61',10),('D61',20),('D61',30),('D62',10),('D62',20)]
fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
colors={'A03':'#2075b4','A06':'#d87414'}
for ax,(domain,metric,title) in zip(axes.flat,panels):
    for method,offset in [('A03',-.14),('A06',.14)]:
        for x,(family,duration) in enumerate(groups):
            sample=data[(data.domain==domain)&(data.metric==metric)&(data.ablation_method==method)&(data.family==family)&(data.duration_s==duration)].sort_values('seed_index')
            assert len(sample)==9
            values=sample.delta_full_minus_ablation.to_numpy(float)
            jitter=(np.arange(9)-4)*.019
            ax.scatter(x+offset+jitter,values,s=18,alpha=.8,color=colors[method],label=('F04 - '+method) if x==0 else None)
            good=values[np.isfinite(values)]
            if len(good):ax.scatter([x+offset],[np.mean(good)],s=65,marker='_',linewidths=2.2,color='black')
    ax.axhline(0,color='black',lw=.8);ax.grid(axis='y',alpha=.2)
    ax.set_xticks(range(5),[f'{a}\n{b}s' for a,b in groups]);ax.set_title(title)
    ax.set_ylabel('F04 minus ablation');ax.legend(fontsize=8)
fig.suptitle('Every one of the nine original placement anchors retained in each condition\nPoints: individual paired differences. Black marks: placement mean. No independent-trial inference.',fontsize=12)
fig.savefig(root/'PLACEMENT_BLOCK_DIFFERENCES.png',dpi=190);fig.savefig(root/'PLACEMENT_BLOCK_DIFFERENCES.pdf');plt.close(fig)
assert sha(table)==before==receipt['publication_csv_sha256'][table.name]
assert sha(root/'REDUCTION_RECEIPT.json')==reduction_receipt_before
outputs={p.name:sha(p) for p in root.iterdir() if p.suffix in ('.png','.pdf')}
with (root/'FIGURE_GENERATION_RECEIPT.json').open('x') as f:
    json.dump({'status':'ALL45_AND_ALL9_PLACEMENTS_PLOTTED_WITH_NO_CASE_EXCLUSION',
        'reduction_receipt_sha256':reduction_receipt_before,'paired_table_sha256':before,'plot_helper_sha256':sha(__file__),
        'source_or_provider_changes':0,'reference_trace_reads':0,'solver_or_evaluator_calls':0,
        'outputs':outputs,'visual_inspection_status':'PENDING_ACTUAL_IMAGE_VIEW'},f,indent=2)
print(json.dumps({'figures':outputs}))
