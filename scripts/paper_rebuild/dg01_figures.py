#!/usr/bin/env python3
"""DG01 publication figures from diagnostic CSVs only."""
import os
from pathlib import Path
from dg01_analysis import *
SCRATCH=Path(CFG['hx02_scratch']).parent/'DG01'
os.environ['MPLCONFIGDIR']=str(SCRATCH/'matplotlib')
import importlib.util,shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def module(name):
 p=read(W/'src/legsa_gins/paper_rebuild/publication'/f'{name}.py');spec=importlib.util.spec_from_file_location('dg_'+name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
style=module('style');style.apply_rcparams();plt.rcParams.update({'font.size':7,'axes.labelsize':7,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7})
qa=module('qa');qa.UNIT_RE=re.compile(r'\((m|°|deg|s|%|count|cases|ratio|fraction|m/s|dB-Hz|cycle|1/cycle|state)\)');colors=['#0072B2','#D55E00'];checks=[]
def shade(ax,s):
 if s=='BY2O':ax.axvspan(3369.94,3411.95,color='.9',zorder=-10)
def finish(fig,name):
 for i,ax in enumerate(fig.axes):
  ax.set_title(re.sub(r'^\([a-z]\)\s*','',ax.get_title()),fontsize=7)
  ax.text(-.12,1.03,'('+chr(97+i)+')',transform=ax.transAxes,fontsize=7,fontweight='bold')
 result=qa.check_figure(fig,name)
 for ext in ['png','pdf','svg']:
  p=O/f'{name}.{ext}';fig.savefig(p,dpi=max(610,4097/fig.get_figwidth()))
  if ext=='svg':p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
  shutil.copyfile(p,R/p.name)
 result+=qa.check_png(O/f'{name}.png',name)
 for x in result:x['pass']=bool(x['pass'])
 checks.extend(result);assert all(x['pass'] for x in result),(name,result);plt.close(fig);log(name+' machine QA '+str(len(result))+'/'+str(len(result)))
def figure1():
 fig,axs=plt.subplots(3,3,figsize=(174/25.4,145/25.4),layout='constrained')
 for col,s in enumerate(SEQ):
  for r in [1,2]:
   d=inside(load(s,r,'obs'),s);a=d.groupby('time').cno_dbhz.median();axs[0,col].plot(a.index,a.values,color=colors[r-1],ls='-' if r==1 else '--',lw=.7,label=f'GNSS{r}')
   n=d[['time','gnss','sv']].drop_duplicates().groupby('time').size();axs[1,col].plot(n.index,n.values,color=colors[r-1],ls='-' if r==1 else '--',lw=.7)
   q=inside(load(s,r,'nav'),s);axs[2,col].step(q.time,q.carrSoln,where='post',color=colors[r-1],ls='-' if r==1 else '--',lw=.7)
  axs[0,col].set_title('('+chr(97+col)+') '+s,fontsize=8);axs[2,col].set_xlabel('Time (s)');axs[2,col].set_yticks([0,1,2],['None','Float','Fixed'])
  for row in range(3):shade(axs[row,col],s);axs[row,col].set_xlim(SEQ[s][1:]);axs[row,col].grid(alpha=.2)
 axs[0,0].set_ylabel('Median C/N0 (dB-Hz)');axs[1,0].set_ylabel('Tracked satellites (count)');axs[2,0].set_ylabel('NAV-PVT (state)');axs[0,0].legend(loc='best');finish(fig,'SFIG-DG1')
def figure2():
 data={s:pd.read_csv(O/f'{s}_FRACTIONAL_DD_DETAIL.csv.gz') for s in SEQ};groups=sorted(set((int(g),int(sig)) for d in data.values() for g,sig in d[['gnss','signal']].drop_duplicates().itertuples(index=False,name=None)))
 fig,axs=plt.subplots(len(groups),3,figsize=(174/25.4,(28*len(groups)+14)/25.4),layout='constrained',squeeze=False);systems={0:'GPS',2:'Galileo',3:'BeiDou',5:'QZSS',6:'GLONASS'};bins=np.arange(-.5,.50001,.025)
 for row,(gnss,sig) in enumerate(groups):
  for col,s in enumerate(SEQ):
   ax=axs[row,col];d=data[s];d=d[(d.gnss==gnss)&(d.signal==sig)]
   for k,label in enumerate(['both_fixed','other']):
    g=d[d.fix_group==label]
    if len(g):ax.hist(g.fractional_cycles,bins=bins,density=True,histtype='step',color=colors[k],ls='-' if k==0 else '--',lw=.8,label=label.replace('_',' '))
   if not len(d):ax.text(.5,.5,'Unavailable',ha='center',transform=ax.transAxes)
   ax.set_xlim(-.5,.5);ax.grid(alpha=.15);ax.set_title(f'({chr(97+row*3+col)}) {s} · {systems[gnss]} sig {sig}',fontsize=7)
   if col==0:ax.set_ylabel('Density (1/cycle)')
   if row==len(groups)-1:ax.set_xlabel('Fractional DD (cycle)')
 axs[0,2].legend(loc='upper left');finish(fig,'SFIG-DG2')
def figure3():
 fig,axs=plt.subplots(3,2,figsize=(174/25.4,145/25.4),layout='constrained')
 for row,s in enumerate(SEQ):
  fix=pd.read_csv(O/f'{s}_FIX_DETAIL.csv.gz');d=pd.read_csv(O/f'{s}_RTKLIB_POS_DETAIL.csv.gz')
  axs[row,0].step(fix.time,fix.both_fixed.astype(int),where='post',color=colors[0],lw=.9);axs[row,0].set_yticks([0,1],['No','Yes']);axs[row,0].set_ylim(-.12,1.12);axs[row,0].set_ylabel('Both fixed (fraction)')
  for q,color,mark in [(1,'#009E73','o'),(2,'#E69F00','x'),(5,'#CC79A7','+')]:
   g=d[d.Q==q];axs[row,1].scatter(g.time,g.Q,s=5,color=color,marker=mark,label=f'Q={q}',linewidths=.5)
  axs[row,1].set_yticks([1,2,5]);axs[row,1].set_ylim(.5,5.5);axs[row,1].set_ylabel('RTKLIB Q (state)')
  for col in [0,1]:
   axs[row,col].set_title('('+chr(97+2*row+col)+') '+s,fontsize=8);axs[row,col].set_xlabel('Time (s)');axs[row,col].set_xlim(SEQ[s][1:]);shade(axs[row,col],s);axs[row,col].grid(alpha=.2)
 axs[0,1].legend(ncol=3,loc='upper right');finish(fig,'SFIG-DG3')
def main():
 figure1();figure2();figure3();(R/'DG01_FIGURE_QA.json').write_text(json.dumps(checks,indent=2)+'\n');save_sources()
if __name__=='__main__':main()
