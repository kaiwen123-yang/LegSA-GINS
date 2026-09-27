"""Render source-bound number tokens and selected tables into the manuscript."""
from common import *
import re
SPECS={};LEDGER=[]
DOCS={'budget':U/'UNC01_UNCERTAINTY_BUDGET.md','dist':U/'UNC02_DISTINGUISHABILITY.md','unc3':U/'UNC03_MANUSCRIPT_TEXT.md','replacement':W/'docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md','setup':W/'docs/paper_rebuild/CLEAN5_STAGE2_CLOSEOUT.md','hx':H/'HX05_CLOSEOUT.md','geometry':W/'docs/paper_rebuild/hext/HX05_PREREG.md','method':W/'docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md','contract':W/'configs/paper_rebuild/final_v23_parity_contract.yaml','options':W/'cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp'}
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
    if key.startswith('NEG|') or key.startswith('PCT|'):
        op,inner=key.split('|',1);shown=emit(inner,section,quoted);input_id=LEDGER[-1]['claim_id'];sp=SPECS[inner];value=sp['value']*(-1 if op=='NEG' else 100);digits=sp['digits'] if op=='NEG' else 0;display=f'{value:.{digits}f}';cid=f'N{len(LEDGER)+1:05d}'
        LEDGER.append(dict(claim_id=cid,section=section,quoted_text=quoted or display,value=display,unit='as stated in quoted text',source_path=LEDGER[-1]['source_path'],source_locator=json.dumps({'display_digits':digits}),derivation=json.dumps({'inputs':[input_id],'expression':('-' if op=='NEG' else '100*')+input_id}),check_mode='DERIVED'));return display
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
    sp=SPECS[key];value=sp['value'];display=f"{value:.{sp['digits']}f}"
    cid=f'N{len(LEDGER)+1:05d}'
    path=sp['path'].replace(str(W)+'/','').replace(str(V),'<V3>')
    LEDGER.append(dict(claim_id=cid,section=section,quoted_text=quoted or display,value=display,unit=sp.get('unit','as stated in quoted text'),source_path=path,source_locator=json.dumps(sp['locator']),derivation='direct',check_mode=sp['mode']))
    return display
def table_md(name):
    rows=list(csv.DictReader((P/'tables'/f'{name}.csv').open()));cols=list(rows[0]);esc=lambda x:str(x).replace('|','\\|').replace('\n',' ')
    return '| '+' | '.join(cols)+' |\n| '+' | '.join('---' for _ in cols)+' |\n'+'\n'.join('| '+' | '.join(esc(r[c]) for c in cols)+' |' for r in rows)
def required_unc(section):
    text=record(DOCS['unc3']).read_text();blocks=re.split(r'\n## ',text);block=next(x for x in blocks if x.startswith(section+'.'))
    # Original English paragraphs end before any following explanatory subheading.
    lines=block.splitlines()[1:];paras=[]
    for l in lines:
        if l.startswith(('**Measurement uncertainty.**','Three limitations concern','Values are exact')):paras.append(l)
    assert paras,section
    return '\n\n'.join(paras)
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
            lines.append(original);continue
        start=len(LEDGER)
        line=re.sub(r'\[\[([^\]]+)\]\]',lambda m:emit(m.group(1),section,line),line)
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
