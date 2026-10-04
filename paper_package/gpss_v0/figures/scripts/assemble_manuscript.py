"""Render source-bound number tokens and selected tables into the manuscript."""
from common import *
import re
from method_names import reader_text
from decimal import Decimal
SPECS={};LEDGER=[]
UA_CSV_TOKENS={
    'UA|a1_30_h_mean':('UA01_ADDENDUM_STATS.csv',{'type':'D61','duration_s':'30','method':'F04','metric':'horizontal_rmse_m'},'mean',3,None),
    'UA|a2_20_h_delta':('UA01_ADDENDUM_PAIRED.csv',{'type':'D62','duration_s':'20','pair':'F04-F03','metric':'horizontal_rmse_m'},'mean',2,None),
    'UA|f04_f03_yaw_pairs':('UA01_PAIRED_OVERALL.csv',{'pair':'F04-F03','metric':'yaw_rmse_deg'},'n_pairs_finite',0,'N00208'),
    'UA|paired_fault_registered':('UA01_PAIRED_OVERALL.csv',{'pair':'F04-F03','metric':'yaw_rmse_deg'},'n_registered',0,'N00209'),
    'UA|f04_yaw_median_ci_low':('UA01_DISTRIBUTION_QUANTILES.csv',{'method':'F04','metric':'yaw_rmse_deg'},'cluster_q50_low',16,'N00210'),
    'UA|f04_yaw_median_ci_high':('UA01_DISTRIBUTION_QUANTILES.csv',{'method':'F04','metric':'yaw_rmse_deg'},'cluster_q50_high',16,'N00211'),
}
DISPLAY_APPENDED_IDS={spec[4] for spec in UA_CSV_TOKENS.values() if spec[4]}
UNC_DISPLAY_REPLACEMENTS={
    'The reported values are exact for the recorded windows and reproduce bit-for-bit under the same software version and configuration':
        'The retained V3 error-series exports match their recorded hashes, and the statistics supported by their fields agree with the existing records within the declared validation tolerances',
    'Values are exact for the evaluated windows (bit-for-bit reproducible)':
        'Values are the retained statistics for the evaluated windows, with export hashes and supported numerical checks verified within the declared validation tolerances',
}
def claim_id(key=None):
    # D01 additions use new IDs without shifting any of the original 207 IDs.
    fixed=UA_CSV_TOKENS[key][4] if key in UA_CSV_TOKENS else None
    if fixed:
        assert all(row['claim_id']!=fixed for row in LEDGER),fixed
        return fixed
    used={row["claim_id"] for row in LEDGER}
    candidate=1
    while f"N{candidate:05d}" in used or f"N{candidate:05d}" in DISPLAY_APPENDED_IDS: candidate+=1
    return f"N{candidate:05d}"
def ua_csvspec(key):
    filename,where,column,digits,_=UA_CSV_TOKENS[key]
    p=U/filename
    found=[row for row in readcsv(p) if all(row[k]==v for k,v in where.items())]
    assert len(found)==1,(key,len(found))
    source_value=found[0][column]
    SPECS[key]={'path':p.relative_to(W).as_posix(),'locator':{'where':where,'column':column,'display_digits':digits},'mode':'CSV','value':float(source_value),'source_value':source_value,'digits':digits}
DOCS={'budget':U/'UNC01_UNCERTAINTY_BUDGET.md','dist':U/'UNC02_DISTINGUISHABILITY.md','unc3':P/'uncertainty_display_source.md','replacement':W/'docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md','setup':W/'docs/paper_rebuild/CLEAN5_STAGE2_CLOSEOUT.md','hx':H/'HX05_CLOSEOUT.md','geometry':W/'docs/paper_rebuild/hext/HX05_PREREG.md','method':W/'docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md','contract':W/'configs/paper_rebuild/final_v23_parity_contract.yaml','options':W/'cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp'}
def csvspec(key,p,where,col,digits=3,regex=None):
    loc={'where':where,'column':col,'display_digits':digits}
    if regex:loc['regex']=regex
    rows=readcsv(p);r=[r for r in rows if all(r[k]==v for k,v in where.items())];assert len(r)==1,(key,len(r))
    val=r[0][col];val=re.search(regex,val).group(1) if regex else val
    SPECS[key]={'path':str(p),'locator':loc,'mode':'CSV','value':float(val),'digits':digits}
def docspec(alias,literal):
    key='D|'+alias+'|'+literal
    if key in SPECS:return key
    p=record(DOCS[alias]);lines=p.read_text().splitlines()
    matches=[i for i,l in enumerate(lines,1) if re.search(r'(?<![\d.])'+re.escape(literal)+r'(?![\d.])',l)]
    assert matches,(alias,literal)
    digits=len(literal.split('.')[-1]) if '.' in literal else 0
    if alias=='hx':digits=min(3,digits)
    if alias=='budget' and literal in ['−0.346','−0.029','+0.0003','−1.61','−10.5']:digits=2
    if alias=='budget' and literal in ['0.0023','30.8']:digits=3
    SPECS[key]={'path':str(p),'locator':{'line_start':matches[0],'line_end':matches[0],'literal':literal,'display_digits':digits},'mode':'DOC','value':float(literal.replace('−','-').replace(',','').replace(' ','')),'digits':digits}
    return key
main=V/'07_AGGREGATE/MAIN_TABLE_V3.csv'
for s in ['BY2','BY2H','BY2O']:
 for m in ['F01','F02','F03','A04','F04','LC01','LC01-S','EXT05C']:
  where={'sequence_id':s,'method_id':m,'start_convention':('FROZEN_V21_RUNTIME_CONFIG' if m in ['F01','F02','F03','A04','F04'] else 'CONTRACT_START' if s=='BY2H' else 'FILE_START')}
  for c in ['yaw_rmse_deg','h_rmse_m','up_rmse_m','roll_rmse_deg','pitch_rmse_deg','matched_epoch_count']:
   csvspec('M|'+s+'|'+m+'|'+c,main,where,c,0 if c.endswith('count') else 3)
def emit(key,section,quoted=None):
    if key=='BR':csvspec(key,H/'EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv',{'method':'LC01-BR'},'BY2',3,r'horizontal_rmse_m=([-+\d.eE]+)')
    if key.startswith('E|'):
        _,s,m,c=key.split('|');csvspec(key,H/'EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv',{'method':m},s,3,re.escape(c)+r'=([-+\d.eE]+)')
    if key.startswith('NEG|') or key.startswith('PCT|'):
        op,inner=key.split('|',1);shown=emit(inner,section,quoted);input_id=LEDGER[-1]['claim_id'];sp=SPECS[inner];value=sp['value']*(-1 if op=='NEG' else 100);digits=sp['digits'] if op=='NEG' else 0;display=f'{value:.{digits}f}';cid=claim_id()
        LEDGER.append(dict(claim_id=cid,section=section,quoted_text=quoted or display,value=display,unit=('%' if op=='PCT' else LEDGER[-1]['unit']),source_path=LEDGER[-1]['source_path'],source_locator=json.dumps({'display_digits':digits}),derivation=json.dumps({'inputs':[input_id],'expression':('-' if op=='NEG' else '100*')+input_id}),check_mode='DERIVED'));return display
    if key.startswith('D|'):
        _,alias,literal=key.split('|');docspec(alias,literal)
    if key.startswith('G|'):
        literal={'BY2':'0.356191491865984','BY2H':'0.35418777593777223','BY2O':'0.35013463864843675'}[key.split('|')[1]]
        origin=docspec('geometry',literal);SPECS[key]=dict(SPECS[origin]);SPECS[key]['digits']=3;SPECS[key]['locator']=dict(SPECS[key]['locator'],display_digits=3)
    if key.startswith('Y|'):
        import yaml
        path=W/'configs/paper_rebuild/degradation_60types_9seeds.yaml';k=key.split('|')[1];v=yaml.safe_load(record(path).read_text())['matrix'][k]
        SPECS[key]={'path':str(path),'locator':{'key_path':['matrix',k],'display_digits':0},'mode':'YAML','value':v,'digits':0}
    if key.startswith('X|'):
        _,fam,m,col,stat=key.split('|');pattern=col+'='+('([-+\\d.eE]+)/' if stat=='median' else '[-+\\d.eE]+/([-+\\d.eE]+)');csvspec(key,H/'DEGRADATION_MANUSCRIPT.csv',{'family':fam},m,3,pattern)
    if key.startswith('S|'):
        _,m,s,c=key.split('|');csvspec(key,V/'07_AGGREGATE/BY2O_SEGMENT_TABLE.csv',{'method_id':m,'segment_id':s,'variant':'' if m=='LC01' else 'PROTOCOL_V3','evaluator_contract':'evaluator_contract_v3'},c)
    if key.startswith('P|'):
        _,s,pair,metric,c,d=key.split('|');csvspec(key,U/'UNC_DISTINGUISHABILITY.csv',{'sequence':s,'segment':'full','pair_A_minus_B':pair,'metric':metric},c,int(d))
    if key.startswith('C|'):
        _,m,metric,c,d=key.split('|');csvspec(key,V/'07_AGGREGATE/CORE_541_SUMMARY_V3.csv',{'method_id':m,'metric':metric},c,int(d))
    if key.startswith('VR|'):
        p=P/'evidence/original_v3_registry_receipt.json';v=json.loads(record(p).read_text());parts=key.split('|')[1:]
        for field in parts:v=v[field]
        SPECS[key]={'path':str(p),'locator':{'key_path':parts,'display_digits':0},'mode':'YAML','value':v,'digits':0}
    if key.startswith('NAT|'):
        _,seq,method,column=key.split('|');csvspec(key,P/'evidence/natural33.csv',{'sequence_id':seq,'method_id':method},column,0 if column.endswith('epochs') or column=='gap_restart_count' else 3)
    if key.startswith('CLM|'):
        _,family,duration,ablation,domain,metric,column,digits=key.split('|');csvspec(key,P/'evidence/claim_placement280.csv',{'family':family,'duration_s':duration,'ablation_method':ablation,'domain':domain,'metric':metric},column,int(digits))
    if key.startswith('FGO|'):
        _,seq,method,column=key.split('|');csvspec(key,P/'evidence/fgo_metrics.csv',{'sequence_id':seq,'method_id':method,'support':'OWN_VALID'},column,0 if column.endswith('count') else 3)
    if key.startswith('UA|'):ua_csvspec(key)
    sp=SPECS[key];value=Decimal(sp['source_value']) if 'source_value' in sp else sp['value'];display=f"{value:.{sp['digits']}f}"
    cid=claim_id(key)
    path=sp['path'].replace(str(W)+'/','').replace(str(V),'<V3>')
    unit='count'
    if any(t in key for t in ['yaw_rmse','yaw_p95','roll_rmse','pitch_rmse','|yaw|']):unit='deg'
    if any(t in key for t in ['horizontal_rmse','h_rmse','up_rmse','|horizontal|']):unit='m'
    if any(t in key for t in ['finite_count','failure_count','registered_count']):unit='cases'
    if 'matched_epoch_count' in key:unit='epochs'
    if key in ['UA|a1_30_h_mean','UA|a2_20_h_delta']:unit='m'
    if key in ['UA|f04_f03_yaw_pairs','UA|paired_fault_registered']:unit='cases'
    if key in ['UA|f04_yaw_median_ci_low','UA|f04_yaw_median_ci_high']:unit='deg'
    if key.startswith('G|') or key in ['D|contract|0.03','D|contract|-0.30']:unit='m'
    if key.startswith('VR|'):unit='tasks or cases as explicitly named in the sentence'
    if key.startswith('NAT|'):unit='deg' if 'yaw_' in key else 'epochs' if key.endswith('epochs') else 'restarts' if 'gap_restart_count' in key else 'm'
    if key.startswith('CLM|'):unit='cases' if '|worsened|' in key or '|improved|' in key else 'deg' if '|yaw|' in key else 'm'
    if key.startswith('FGO|'):unit='epochs' if key.endswith('count') else 'deg' if 'yaw_' in key else 'm'
    if 'availability' in key:unit='fraction'
    if 'drift_pct' in key:unit='%'
    if key=='D|contract|90':unit='deg'
    if quoted and '[['+key+']]' in quoted:
        tail=quoted.split('[['+key+']]',1)[1]
        m=re.match(r'[\s,\]\[−–+\d.]*(°|%|ms|m(?:/s)?|s|Hz)(?![A-Za-z])',tail)
        if not m and any(x in key for x in ['D|budget|2.00','D|budget|4.18']):unit='deg'
        if m:unit={'°':'deg'}.get(m.group(1),m.group(1))
    if key in ['D|unc3|2.20','D|unc3|4.44']:unit='deg'
    if key in ['D|hx|0.111679','D|hx|0.132593','D|hx|0.059416']:unit='fraction'
    if key in ['D|hx|33.633600','D|hx|47.525517','D|hx|28.558852']:unit='m per 100 m'
    LEDGER.append(dict(claim_id=cid,section=section,quoted_text=quoted or display,value=display,unit=unit,source_path=path,source_locator=json.dumps(sp['locator']),derivation='direct',check_mode=sp['mode']))
    return display
def table_md(name):
    rows=list(csv.DictReader((P/'tables'/f'{name}.csv').open()));cols=[c for c in rows[0] if c not in ['source_id','source_path','run_id','sha256']];esc=lambda x:str(x).replace('|','\\|').replace('\n',' ')
    return '| '+' | '.join(cols)+' |\n| '+' | '.join('---' for _ in cols)+' |\n'+'\n'.join('| '+' | '.join(esc(r[c]) for c in cols)+' |' for r in rows)
def required_unc(section):
    text=record(DOCS['unc3']).read_text();blocks=re.split(r'\n## ',text);block=next(x for x in blocks if x.startswith(section+'.'))
    # Original English paragraphs end before any following explanatory subheading.
    lines=block.splitlines()[1:];paras=[]
    for l in lines:
        if l.startswith(('**Measurement uncertainty.**','Three limitations concern','Values are')):paras.append(l)
    assert paras,section
    display='\n\n'.join(paras)
    for original,replacement in UNC_DISPLAY_REPLACEMENTS.items():display=display.replace(original,replacement)
    return display
def render(text,doc):
    section=doc;lines=[]
    for line in text.splitlines():
        if line.startswith('##'):section=doc+': '+line.lstrip('# ')
        if line.startswith('{{TABLE:'):
            lines.append(table_md(line[8:-2]));continue
        if line.startswith('{{UNC:'):
            original=required_unc(line[6:-2]);alias='unc3'
            for match in re.finditer(r'(?<![\w.])\d+(?:\.\d+)?(?![\w.])',original):
                docspec(alias,match.group());emit('D|'+alias+'|'+match.group(),section,original)
                suffix=original[match.end():];u=re.match(r'[\s,\]\[−–+\d.]*(°|%|m|s|Hz)(?![A-Za-z])',suffix)
                if original.startswith('Values are') and match.group()!='95':LEDGER[-1]['unit']='deg' if match.start()<original.index('for heading') else 'm'
                if match.group()=='2' and 'Vision-RTK 2' in original:LEDGER[-1]['unit']='model identifier'
                if u:LEDGER[-1]['unit']={'°':'deg'}.get(u.group(1),u.group(1))
            lines.append(reader_text(original));continue
        start=len(LEDGER)
        line=re.sub(r'\[\[([^\]]+)\]\]',lambda m:emit(m.group(1),section,line),line)
        line=reader_text(line)
        for entry in LEDGER[start:]:entry['quoted_text']=line
        lines.append(line)
    return '\n'.join(lines)+'\n'
def main():
    raw=(P/'manuscript_source.md').read_text();(P/'MANUSCRIPT_GPSS_v0.md').write_text(render(raw,'Main'))
    if (P/'supplement_source.md').exists():(P/'SUPPLEMENT_GPSS_v0.md').write_text(render((P/'supplement_source.md').read_text(),'Supplement'))
    writecsv(P/'NUMBER_LEDGER.csv',LEDGER)
    (P/'CLAIM_SPECS.json').write_text(json.dumps(SPECS,indent=2)+'\n')
    print('Ledger entries',len(LEDGER))
if __name__=='__main__':main()
