#!/usr/bin/env python3
"""Fixed-bin comparison figures; no new scientific filtering."""
from dg01r_common import *
os.environ['MPLCONFIGDIR']=str(S/'matplotlib')
import importlib.util
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def module(name):
 p=read(W/'src/legsa_gins/paper_rebuild/publication'/f'{name}.py');spec=importlib.util.spec_from_file_location('dg01r_'+name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
style=module('style');qa=module('qa');qa.UNIT_RE=re.compile(r'\((m|°|deg|s|%|count|cases|ratio|fraction|m/s|cycle|1/cycle)\)')
style.apply_rcparams();plt.rcParams.update({'font.size':7,'axes.labelsize':7,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7})
def main():
 d=pd.read_csv(O/'DD_ALL_VERSIONS.csv.gz',float_precision='round_trip');checks=[];keys=[(0,0,'GPS L1 C/A'),(0,3,'GPS L2C'),(3,0,'BeiDou B1I'),(3,2,'BeiDou B2I'),(5,0,'QZSS L1 C/A'),(5,5,'QZSS L2C')];versions=['R0','R1','R2A','R2B'];titles=['Original','Clock corrected','Half-cycle exclusion','Half-cycle +0.5'];colors=['#0072B2','#D55E00','#009E73'];styles=['-','--',':'];bins=np.linspace(-.5,.5,41)
 for fix,name in [('both_fixed','SFIG-DG2R'),('other','SFIG-DG2R-OTHER')]:
  fig,axs=plt.subplots(6,4,figsize=(174/25.4,240/25.4),layout='constrained',sharex=True,sharey='row')
  for row,(g,signal,label) in enumerate(keys):
   for col,version in enumerate(versions):
    ax=axs[row,col]
    missing=[]
    for k,s in enumerate(SEQ):
     subset=d[(d.sequence==s)&(d.fix_group==fix)&(d.gnss==g)&(d.signal==signal)];a=subset[version].dropna().to_numpy()
     if len(a):ax.hist(a,bins=bins,density=True,histtype='step',color=colors[k],ls=styles[k],lw=.8,label=s)
     elif len(subset):missing.append(s)
    if missing:ax.text(.04,.95,'\n'.join(s+': n=0' for s in missing),transform=ax.transAxes,va='top',fontsize=7)
    ax.set_xlim(-.5,.5);ax.set_xticks([-.5,0,.5]);ax.text(-.18,1.02,'('+chr(97+row*4+col)+')',transform=ax.transAxes,fontsize=7,fontweight='bold')
    if row==0:ax.set_title(titles[col],fontsize=7)
    if col==0:ax.set_ylabel(label+'\nDensity (1/cycle)')
    if row==5:ax.set_xlabel('Fractional DD (cycle)')
  handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside upper center',ncol=3,frameon=False)
  result=qa.check_figure(fig,name)
  for ext in ['png','pdf','svg']:
   p=O/f'{name}.{ext}';fig.savefig(p,dpi=610)
   if ext=='svg':p.write_text('\n'.join(l.rstrip() for l in p.read_text().splitlines())+'\n')
   shutil.copyfile(p,R/p.name)
  result+=qa.check_png(O/f'{name}.png',name)
  for x in result:x['pass']=bool(x['pass'])
  assert all(x['pass'] for x in result),result;checks+=result;plt.close(fig);log(name+' QA '+str(len(result))+'/'+str(len(result)))
 (R/'DG01R_FIGURE_QA.json').write_text(json.dumps(checks,indent=2)+'\n');save_sources()
if __name__=='__main__':main()
