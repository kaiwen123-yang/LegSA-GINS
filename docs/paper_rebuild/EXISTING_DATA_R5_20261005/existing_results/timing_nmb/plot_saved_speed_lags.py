#!/usr/bin/env python3
"""Plot only the saved lag CSV; no experiment or reference reads."""
from pathlib import Path
import hashlib,json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent
f=p/'LAG_PROFILE_ALL_2004.csv'; before=hashlib.sha256(f.read_bytes()).hexdigest()
d=pd.read_csv(f); s=pd.read_csv(p/'TIMING_SUMMARY_4.csv').set_index('sequence')
fig,axs=plt.subplots(2,2,figsize=(10,6.6),sharex=True,sharey=True)
for ax,name in zip(axs.flat,['NMB1','NMB2','NMB3','NMB4']):
    x=d[d.sequence==name]; r=s.loc[name]
    ax.plot(x.lag_s,x.pearson_r_fixed_support,lw=1.8,color='#1458a2')
    ax.axvline(0,color='#888',ls='--',lw=1)
    ax.axvline(r.peak_lag_s,color='#bc492a',ls=':',lw=1.3)
    ax.set_title(f'{name}: peak {r.peak_lag_s:+.2f} s, r={r.peak_r:.3f}')
    ax.text(.03,.04,f'fixed epochs: {int(r.fixed_common_n)}; r(0)={r.zero_r:.3f}',transform=ax.transAxes,fontsize=9)
    ax.grid(alpha=.2); ax.set_xlim(-5,5); ax.set_ylim(.2,1.01)
for ax in axs[1]: ax.set_xlabel('HV query lag (s): GNSS(t) vs HV(t + lag)')
for ax in axs[:,0]: ax.set_ylabel('Pearson correlation of horizontal speed')
fig.suptitle('Prepared-input timing diagnostic — no reference or applied offset',fontsize=13)
fig.tight_layout(rect=(0,0,1,.95)); fig.savefig(p/'NMB_SPEED_LAG_PROFILE.png',dpi=180)
assert hashlib.sha256(f.read_bytes()).hexdigest()==before
(p/'PLOT_RECEIPT.json').write_text(json.dumps(dict(profile_sha256=before,figure_sha256=hashlib.sha256((p/'NMB_SPEED_LAG_PROFILE.png').read_bytes()).hexdigest(),reference_reads=0,native_runs=0),indent=2)+'\n')

g=p/'IMU_CROSSCHECK_LAG_PROFILE_4008.csv'; gbefore=hashlib.sha256(g.read_bytes()).hexdigest()
x=pd.read_csv(g)
fig,axs=plt.subplots(1,2,figsize=(10,3.8),sharey=True)
for ax,name in zip(axs,['NMB1','NMB2']):
    for w,c in [(2.,'#1458a2'),(1.,'#bc492a')]:
        q=x[(x.sequence==name)&(x.signal=='signed_heading_rate_vs_gyro_z')&(x.centered_smoothing_window_s==w)]
        ax.plot(q.lag_s,q.pearson_r,label=f'{w:g} s centered window',color=c)
    ax.axvline(0,color='#888',ls='--',lw=1);ax.set_title(name);ax.set_xlabel('IMU query lag (s)');ax.grid(alpha=.2);ax.legend(fontsize=8);ax.set_xlim(-5,5)
axs[0].set_ylabel('Heading-rate / gyro-z correlation')
fig.suptitle('Direct IMU time-chain cross-check — no reference or applied offset')
fig.tight_layout();fig.savefig(p/'NMB_IMU_GYRO_LAG_PROFILE.png',dpi=180)
assert hashlib.sha256(g.read_bytes()).hexdigest()==gbefore
r=json.loads((p/'PLOT_RECEIPT.json').read_text());r.update(imu_profile_sha256=gbefore,imu_figure_sha256=hashlib.sha256((p/'NMB_IMU_GYRO_LAG_PROFILE.png').read_bytes()).hexdigest())
(p/'PLOT_RECEIPT.json').write_text(json.dumps(r,indent=2)+'\n')
