#!/usr/bin/env python3
"""Read-only source checks for the manuscript number ledger (no scientific runs).

CSV locator: JSON with where, column, optional regex/group, display_digits.
DOC/YAML locator: JSON with line_start/line_end or key_path and display_digits.
DERIVED: JSON with expression and input claim IDs. Only arithmetic is accepted.
"""
import argparse, ast, csv, json, math, re
from pathlib import Path
def arithmetic(expr, env):
    node=ast.parse(expr,mode='eval')
    def run(n):
        if isinstance(n,ast.Expression):return run(n.body)
        if isinstance(n,ast.Name):return env[n.id]
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)):return n.value
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return -run(n.operand) if isinstance(n.op,ast.USub) else run(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
            a,b=run(n.left),run(n.right)
            return {ast.Add:lambda:a+b,ast.Sub:lambda:a-b,ast.Mult:lambda:a*b,ast.Div:lambda:a/b,ast.Pow:lambda:a**b}[type(n.op)]()
        raise ValueError('Unsupported expression')
    return run(node)
def check(repo, package):
    rows=list(csv.DictReader((package/'NUMBER_LEDGER.csv').open()));out=[];values={};cache={}
    for r in rows:
        try:
            loc=json.loads(r['source_locator']);digits=loc.get('display_digits',0);want=float(r['value']);mode=r['check_mode']
            p=Path(r['source_path'].replace('<V3>',str(Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3'))))
            if not p.is_absolute():p=repo/p
            if mode=='DERIVED':
                d=json.loads(r['derivation']);actual=arithmetic(d['expression'],{k:values[k] for k in d['inputs']})
            else:
                if any(t in str(p).lower() for t in ['.bag','.fpl','/raw/']) or 'trace' in p.name.lower():raise ValueError('Forbidden source')
                if p not in cache:cache[p]=p.read_text()
                content=cache[p]
                if mode=='CSV':
                    found=[x for x in csv.DictReader(content.splitlines()) if all(x[k]==v for k,v in loc['where'].items())]
                    if len(found)!=1:raise ValueError(f'CSV matches={len(found)}')
                    token=found[0][loc['column']]
                    if 'regex' in loc:token=re.search(loc['regex'],token).group(loc.get('group',1))
                    actual=float(token)
                elif mode in ['DOC','YAML']:
                    if 'key_path' in loc:
                        import yaml
                        val=yaml.safe_load(content)
                        for k in loc['key_path']:val=val[k]
                        actual=float(val)
                    else:
                        lines=content.splitlines();snippet='\n'.join(lines[loc['line_start']-1:loc['line_end']])
                        token=loc.get('literal',r['value'])
                        if not re.search(r'(?<![\d.])'+re.escape(token)+r'(?![\d.])',snippet):raise ValueError('Number literal absent from cited lines')
                        actual=float(token.replace('−','-').replace(',','').replace(' ',''))
                else:raise ValueError('Unknown mode')
            ok=math.isfinite(actual) and round(actual,digits)==round(want,digits)
            values[r['claim_id']]=actual
            out.append(dict(claim_id=r['claim_id'],status='PASS' if ok else 'FAIL',expected=r['value'],actual=repr(actual),detail='round to '+str(digits)+' decimal places'))
        except Exception as e:out.append(dict(claim_id=r['claim_id'],status='FAIL',expected=r['value'],actual='',detail=str(e)))
    with (package/'NUMBER_LEDGER_CHECK.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['claim_id','status','expected','actual','detail'],lineterminator='\n');w.writeheader();w.writerows(out)
    failed=sum(r['status']=='FAIL' for r in out);print(f'ledger checks: {len(out)-failed} PASS / {failed} FAIL')
    for r in out:
        if r['status']=='FAIL':print(r)
    return min(1,failed)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[2]);ap.add_argument('--package',default='paper_package/gpss_v0');a=ap.parse_args();raise SystemExit(check(a.repo_root,a.repo_root/a.package))
