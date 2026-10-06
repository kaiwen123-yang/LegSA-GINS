#!/usr/bin/env python3
"""Ubuntu read-only raw audit. No solver, evaluator, reference, fitted offset or provider.
Reuse historical full-body profiles only after current whole-file SHA256 equality.
Decode selected UBX messages from the 16 GNSS raw ZIP members; do not extract ZIP.
"""
from pathlib import Path
import argparse,ast,collections,csv,datetime,hashlib,io,json,math,os,struct,zipfile
import numpy as np

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with Path(p).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,keys,lineterminator='\n');w.writeheader();w.writerows(rows)
def stats(v):
 a=np.asarray(v,float);a=a[np.isfinite(a)]
 return {'n':len(a),'min':float(a.min()),'p50':float(np.median(a)),'p95':float(np.quantile(a,.95)),'max':float(a.max())} if len(a) else {'n':0}
def utc(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat()
def state(p):
 if not p['ok']:return 'INVALID'
 return {0:'OTHER_VALID',1:'FLOAT',2:'FIX'}.get(p['carrier'],'RESERVED')
class HashReader(io.RawIOBase):
 def __init__(self,f):self.f=f;self.h=hashlib.sha256();self.n=0
 def readable(self):return True
 def readinto(self,b):
  q=self.f.read(len(b));b[:len(q)]=q;self.h.update(q);self.n+=len(q);return len(q)
 def close(self):self.f.close();super().close()
def payload(row,cls,msg):
 b=ast.literal_eval(row['data']);assert isinstance(b,bytes) and b[:4]==bytes([181,98,cls,msg])
 assert len(b)==struct.unpack_from('<H',b,4)[0]+8
 a=c=0
 for v in b[2:-2]:a=(a+v)&255;c=(c+a)&255
 assert b[-2:]==bytes([a,c]);return b[6:-2]
def decode(z,name,prior):
 h=HashReader(z.open(name));f=io.TextIOWrapper(io.BufferedReader(h),encoding='utf-8',newline='')
 pv={};hp={};rel={};rx={};messages=collections.Counter();versions=collections.Counter();dups=collections.Counter()
 for row in csv.DictReader(f):
  n=row['name'];messages[n]+=1
  if n=='UBX-NAV-PVT':
   p=payload(row,1,7);assert len(p)==92;k=struct.unpack_from('<I',p)[0]
   dt=datetime.datetime(struct.unpack_from('<H',p,4)[0],*p[6:11],tzinfo=datetime.timezone.utc)
   t=dt.timestamp()+struct.unpack_from('<i',p,16)[0]*1e-9
   dups['PVT']+=k in pv;pv[k]={'time':t,'ok':p[20]==3 and bool(p[21]&1),'carrier':(p[21]>>6)&3,'utc_valid':p[11]&3==3,'fixType':p[20],'hAcc_m':struct.unpack_from('<I',p,40)[0]*.001,'vAcc_m':struct.unpack_from('<I',p,44)[0]*.001,'flags3_invalidLLH':bool(p[78]&1),'llh':[struct.unpack_from('<i',p,o)[0]*s for o,s in [(28,1e-7),(24,1e-7),(32,.001)]]}
  elif n=='UBX-NAV-HPPOSECEF':
   p=payload(row,1,19);assert len(p)==28;k=struct.unpack_from('<I',p,4)[0];dups['HP']+=k in hp
   hp[k]={'xyz':np.array(struct.unpack_from('<iii',p,8))*.01+np.array(struct.unpack_from('<bbb',p,20))*.0001,'valid':p[23]==0,'pAcc_m':struct.unpack_from('<I',p,24)[0]*.0001}
  elif n=='UBX-NAV-RELPOSNED':
   p=payload(row,1,60);assert len(p)==64 and p[0]==1;k=struct.unpack_from('<I',p,4)[0];fl=struct.unpack_from('<I',p,60)[0];dups['RELPOS']+=k in rel
   rel[k]={'flag':fl,'valid':bool(fl&4),'fix_ok':bool(fl&1),'carrier':(fl>>3)&3,'moving':bool(fl&32),'heading_valid':bool(fl&256),'refStationId':struct.unpack_from('<H',p,2)[0],'length_m':struct.unpack_from('<i',p,20)[0]*.01+struct.unpack_from('<b',p,35)[0]*.0001,'heading_deg':struct.unpack_from('<i',p,24)[0]*1e-5,'acc_heading_deg':struct.unpack_from('<I',p,52)[0]*1e-5}
  elif n=='UBX-RXM-RAWX':
   p=payload(row,2,21);assert len(p)==16+p[11]*32;week=struct.unpack_from('<H',p,8)[0];tow=struct.unpack_from('<d',p)[0];key=(week,tow);dups['RAWX']+=key in rx;versions[p[13]]+=1
   pr=set();cp=set();half=set()
   for j in range(p[11]):
    o=16+j*32;pm,cm,dm=struct.unpack_from('<ddf',p,o);sig=tuple(p[o+20:o+24]);fl=p[o+30]
    if fl&1 and math.isfinite(pm):pr.add(sig)
    if fl&2 and math.isfinite(cm) and p[o+28]&15!=15:
     cp.add(sig)
     if fl&4:half.add(sig)
   rx[key]={'pr':pr,'cp':cp,'half':half}
 f.close();assert h.n==z.getinfo(name).file_size and h.h.hexdigest()==prior[name]['sha256']
 return {'pvt':pv,'hp':hp,'rel':rel,'rawx':rx,'identity':{'member':name,'bytes':h.n,'sha256':h.h.hexdigest(),'matches_20261005':True,'messages':dict(messages),'RAWX_versions':dict(versions),'duplicates':dict(dups),'selected_UBX_checksummed':True}}
def gap_counts(times):
 t=np.asarray(sorted(times));d=np.diff(t)
 return {'rows':len(t),'first_utc':utc(t[0]) if len(t) else None,'last_utc':utc(t[-1]) if len(t) else None,'span_s':float(t[-1]-t[0]) if len(t)>1 else 0,'max_consecutive_s':float(d.max()) if len(d) else None,'gaps_gt_0p3':int((d>.3).sum()),'nominal_5Hz_missing_grid_epochs':int(sum(max(0,round(x/.2)-1) for x in d))}
def run(a):
 assert os.uname().sysname=='Linux';a.out.mkdir(parents=True,exist_ok=False)
 body=json.loads((a.prior/'BODY_FILE_PROFILE_PUBLIC.json').read_text());oldraw={r['member']:r for r in json.loads((a.prior/'ZIP_RAW_SELECTED_PROFILE.json').read_text())}
 pairs=list(csv.DictReader((a.prior/'CANDIDATE_PAIRING_SELECTED8.csv').open()));oldzip=json.loads((a.prior/'ZIP_CONTAINER_IDENTITY.json').read_text());r5=json.loads(a.r5_plan.read_text())
 ident=[];brows=[];bst={};pins={}
 for name in ['BODY_FILE_PROFILE_PUBLIC.json','ZIP_RAW_SELECTED_PROFILE.json','ZIP_CONTAINER_IDENTITY.json','CANDIDATE_PAIRING_SELECTED8.csv','BODY_GAPS.csv']:
  pins[name]=sha(a.prior/name)
 for b in body:
  p=a.raw/'高层数据'/b['file'];pre=(p.stat().st_size,p.stat().st_mtime_ns);h=sha(p);assert h==b['sha256'] and pre==(p.stat().st_size,p.stat().st_mtime_ns)
  info=r5['sequences'][b['file'][:-4].upper()];assert h==info['body_sha256']
  ident.append({'role':'BODY','path_alias':'<JAN5_RAW>/高层数据/'+b['file'],'bytes':pre[0],'sha256':h,'same_20261005':True,'same_R5_path':str(p)==info['body'],'same_R5_hash':True})
  gaps=[float(r['dt']) for r in csv.DictReader((a.prior/'BODY_GAPS.csv').open()) if r['file']==b['file']]
  row={k:b[k] for k in ['file','frames','complete_expected_fields_rows','first_t','last_t','first_utc_interpretation','last_utc_interpretation','elapsed_s','gaps_gt_0p1_n','duplicate_timestamp_rows','backward_clock_rows']};row.update(continuous_support_excluding_gaps_gt_0p1_s=b['elapsed_s']-sum(gaps),max_dt_s=b['positive_dt']['max'],median_dt_s=b['positive_dt']['p50'],R5_status=info['status'],profile_reused_after_live_SHA256_match=True)
  brows.append(row);bst[b['file']]=b;print('BODY_IDENTITY_PASS',b['file'],flush=True)
 zp=a.raw/'fixpositon数据/vrtk2_a87c6e_2026-01-05-11-16-59_minimal.zip';before=(zp.stat().st_size,zp.stat().st_mtime_ns);zh=sha(zp);assert zh==oldzip['sha256'];ident.append({'role':'ZIP','path_alias':'<JAN5_RAW>/fixpositon数据/'+zp.name,'bytes':before[0],'sha256':zh,'same_20261005':True,'same_R5_path':True,'same_R5_hash':'via member pins'})
 table(a.out/'FILE_IDENTITY.csv',ident);table(a.out/'BODY_AND_SESSION.csv',brows)
 receivers=[];cross=[];head=[];rawpairs=[];rawids=[];relrows=[];details=[];accuracy=[]
 with zipfile.ZipFile(zp) as z:
  assert len(z.infolist())==176
  for pair in pairs:
   seq=pair['body_file'][:-4].upper();folder=pair['receiver_folder'];b=bst[pair['body_file']];data=[decode(z,folder+'/gnss'+str(n)+'-raw.csv',oldraw) for n in (1,2)]
   rawids += [v['identity'] for v in data];pv1,pv2=[v['pvt'] for v in data];hp1,hp2=[v['hp'] for v in data]
   domains={'FULL_SESSION':(-math.inf,math.inf),'BODY_RECORDED':(b['first_t'],b['last_t']),'BODY_MINUS_1p1':(b['first_t']-1.1,b['last_t']-1.1)}
   for domain,(start,end) in domains.items():
    for n,d in enumerate(data,1):
     pv={k:v for k,v in d['pvt'].items() if start<=v['time']<=end};counts=collections.Counter(state(v) for v in pv.values());valid=[v['time'] for k,v in pv.items() if v['ok'] and v['utc_valid'] and k in d['hp'] and d['hp'][k]['valid']]
     receivers.append({'sequence':seq,'domain':domain,'receiver':n,**gap_counts([v['time'] for v in pv.values()]),**{k:counts[k] for k in ['FIX','FLOAT','OTHER_VALID','INVALID','RESERVED']},'R5_position_valid_epochs':len(valid),'R5_nonFIX_position_valid_epochs':sum(v['ok'] and v['utc_valid'] and state(v)!='FIX' and k in d['hp'] and d['hp'][k]['valid'] for k,v in pv.items()),'max_gap_between_valid_position_s':gap_counts(valid)['max_consecutive_s'],'flags3_invalidLLH':sum(v['flags3_invalidLLH'] for v in pv.values())})
     for quality in ['FIX','FLOAT','OTHER_VALID','INVALID']:
      values=[v for v in pv.values() if state(v)==quality]
      if values:accuracy.append({'sequence':seq,'domain':domain,'receiver':n,'state':quality,'epochs':len(values),**{'hAcc_'+k:v for k,v in stats([v['hAcc_m'] for v in values]).items() if k!='n'},**{'vAcc_'+k:v for k,v in stats([v['vAcc_m'] for v in values]).items() if k!='n'},'lat_min':min(v['llh'][0] for v in values),'lat_max':max(v['llh'][0] for v in values),'lon_min':min(v['llh'][1] for v in values),'lon_max':max(v['llh'][1] for v in values)})
     rel=[v for k,v in d['rel'].items() if k in pv];relrows.append({'sequence':seq,'domain':domain,'receiver':n,'epochs':len(rel),'rel_valid':sum(v['valid'] for v in rel),'heading_valid':sum(v['heading_valid'] for v in rel),'moving':sum(v['moving'] for v in rel),'valid_moving_heading':sum(v['valid'] and v['fix_ok'] and v['moving'] and v['heading_valid'] for v in rel),'moving_heading_FLOAT':sum(v['valid'] and v['fix_ok'] and v['moving'] and v['heading_valid'] and v['carrier']==1 for v in rel),'moving_heading_FIXED':sum(v['valid'] and v['fix_ok'] and v['moving'] and v['heading_valid'] and v['carrier']==2 for v in rel),'length_median_m':stats([v['length_m'] for v in rel]).get('p50'),'reference_station_ids':';'.join(map(str,sorted(set(v['refStationId'] for v in rel))))})
    keys=sorted(k for k in pv1.keys()&pv2.keys() if start<=pv1[k]['time']<=end and start<=pv2[k]['time']<=end);states=collections.defaultdict(list)
    for k in keys:
     p,q=pv1[k],pv2[k];kind=state(p)+'/'+state(q);length=float(np.linalg.norm(hp2[k]['xyz']-hp1[k]['xyz'])) if k in hp1 and k in hp2 and hp1[k]['valid'] and hp2[k]['valid'] else None
     states[kind].append((k,length))
    for kind,vals in sorted(states.items()):
     lengths=[v for k,v in vals if v is not None];ss=stats(lengths)
     cross.append({'sequence':seq,'domain':domain,'GNSS1_GNSS2_state':kind,'paired_epochs':len(vals),'HP_valid_pairs':len(lengths),'baseline_0p2_to_0p6_epochs':sum(.2<=v<=.6 for v in lengths),**{'baseline_'+k:v for k,v in ss.items() if k!='n'}})
    eligible=[]
    for k in keys:
     p,q=pv1[k],pv2[k]
     if p['ok'] and p['utc_valid'] and q['ok'] and k in hp1 and k in hp2 and hp1[k]['valid'] and hp2[k]['valid']:
      length=float(np.linalg.norm(hp2[k]['xyz']-hp1[k]['xyz']))
      if p['carrier']==2 and q['carrier']==2 and .2<=length<=.6:eligible.append(p['time'])
    head.append({'sequence':seq,'domain':domain,'PVT_exact_iTOW_pairs':len(keys),'both_FIX':len(states.get('FIX/FIX',[])),'both_FLOAT':len(states.get('FLOAT/FLOAT',[])),'mixed_FIX_FLOAT':len(states.get('FIX/FLOAT',[]))+len(states.get('FLOAT/FIX',[])),'R5_heading_eligible':len(eligible),'heading_first_utc':utc(eligible[0]) if eligible else None,'heading_last_utc':utc(eligible[-1]) if eligible else None,'max_gap_between_eligible_heading_s':gap_counts(eligible)['max_consecutive_s']})
   ra,rb=[d['rawx'] for d in data];kb=sorted(rb);tb=np.array([w*604800+t for w,t in kb]);ds=[];npr=[];ncp=[];nhalf=[];gps=[];used=[]
   for ka in sorted(ra):
    t=ka[0]*604800+ka[1];idx=int(np.searchsorted(tb,t));idx=min([i for i in [idx-1,idx] if 0<=i<len(tb)],key=lambda i:abs(tb[i]-t));dt=float(tb[idx]-t)
    if abs(dt)>.1:continue
    used.append(idx);ds.append(dt);x,y=ra[ka],rb[kb[idx]];pr=x['pr']&y['pr'];cp=x['cp']&y['cp'];hc=x['half']&y['half']
    npr.append(len(set((v[0],v[1]) for v in pr)));ncp.append(len(set((v[0],v[1]) for v in cp)));nhalf.append(len(set((v[0],v[1]) for v in hc)));gps.append(len(set(v[1] for v in hc if v[0]==0)))
   assert len(used)==len(set(used))
   rawpairs.append({'sequence':seq,'RAWX_gnss1':len(ra),'RAWX_gnss2':len(rb),'exact_week_tow_pairs':len(ra.keys()&rb.keys()),'nearest_le_0p1s_unique_pairs':len(ds),'dt_min_s':min(ds),'dt_median_s':float(np.median(ds)),'dt_max_s':max(ds),'common_PR_unique_SV_ge4_epochs':sum(v>=4 for v in npr),'common_CP_unique_SV_ge4_epochs':sum(v>=4 for v in ncp),'common_CP_halfcycle_valid_unique_SV_ge4_epochs':sum(v>=4 for v in nhalf),'common_CP_halfcycle_valid_GPS_SV_ge4_epochs':sum(v>=4 for v in gps),'common_CP_halfcycle_valid_unique_SV_median':float(np.median(nhalf)),'observations_retimed':False,'AR_or_ephemeris_executed':False})
   details.append({'sequence':seq,'body_file':pair['body_file'],'receiver_folder':folder,'rel_flags_by_receiver':[dict(collections.Counter(v['flag'] for v in d['rel'].values())) for d in data],'rel_length_all_by_receiver':[stats([v['length_m'] for v in d['rel'].values()]) for d in data]})
   for name,rows in [('GNSS_RECEIVER_STATES.csv',receivers),('RECEIVER_ACCURACY_BY_STATE.csv',accuracy),('GNSS_PAIR_STATES.csv',cross),('HEADING_SUPPORT.csv',head),('RAWX_PAIR_OPPORTUNITIES.csv',rawpairs),('RELPOSNED_SUPPORT.csv',relrows)]:table(a.out/name,rows)
   dump(a.out/'RAW_MEMBER_IDENTITIES.json',rawids);dump(a.out/'DECODE_DETAILS.json',details);print('RAW_DECODE_PASS',seq,flush=True)
 assert before==(zp.stat().st_size,zp.stat().st_mtime_ns)
 dump(a.out/'AUDIT_SCOPE.json',{'status':'COMPLETE_RAW_ONLY','script_sha256':sha(__file__),'environment':'Linux Ubuntu-22.04 WSL','body_full_byte_hashes':8,'body_profiles_reused_after_hash_match':8,'zip_container_hash_match':True,'selected_raw_members':16,'members_extracted':0,'reference_members_decoded':0,'native_navigation_invocations':0,'evaluator_invocations':0,'raw_member_hashes_match_previous':True,'profile_source_pins':pins,'R5_plan_sha256':sha(a.r5_plan),'counts_scope':'GNSS full/session and two body supports are separate; near RAWX pairs are opportunities, not AR success','route_identity':'not established by filenames or timestamps; do not claim new route/day','source_formula_urls':['https://content.u-blox.com/sites/default/files/u-blox_ZED-F9H_InterfaceDescription_(UBX-19030118).pdf','https://content.u-blox.com/sites/default/files/ZED-F9P_IntegrationManual_UBX-18010802.pdf']})
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for k in ['raw','prior','r5-plan','out']:p.add_argument('--'+k,type=Path,required=True)
 run(p.parse_args())
