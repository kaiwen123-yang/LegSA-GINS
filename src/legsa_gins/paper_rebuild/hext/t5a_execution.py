"""T5a exclusive controller: pushed preregistration, immutable sources, 16/32 slots."""
from __future__ import annotations
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np
import pandas as pd
import yaml
from .sequence_paths import load_sequence_paths
from . import heading_provider as hp
from .t5a_provider import raw_yaw_from_ned, build_t5a_variants
from .t5a_diagnostics import diagnose
from .t5a_parser_audit import run_parser_audit
from .t5a_runtime import run_native, evaluate_native
from ..clean5_parity.input_audit import decode_receiver
from ..horizontal_literature.ext05_provider import fixed_ecef_to_ned_rotation
from ..manifest import sha256_file

CONTRACT = Path('configs/paper_rebuild/hext/T5A_CONTRACT_V1.yaml')
PROVIDER_KEYS = ('gnsspath','imupath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path')
FLAGS = dict(data_mode='real_raw_heading_sensitivity_outside_v21',synthetic_data_used=False,
    semisynthetic_data_used=False,trace_used_online=False,receiver_imu_as_body_imu=False,
    final_v23_output_solver_input=False,LegSA_output_solver_input=False,per_case_tuning=False,
    output_only_correction=False,epoch_deleted_for_metric=False,old_runtime_input_count=0)


def write_json(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        json.dump({**FLAGS,**data},f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def write_csv(path, rows, fields=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(dict.fromkeys(k for r in rows for k in r)) or ['status']
    with path.open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,tuple)) else v for k,v in r.items()})


class Context:
    def __init__(self,code_freeze):
        self.code=Path.cwd();self.contract=yaml.safe_load(CONTRACT.read_text());self.freeze=code_freeze
        if not self.contract['execution_ready'] or not self.contract['preregistered']:raise RuntimeError('T5A_NOT_PREREGISTERED')
        def git(*args):return subprocess.check_output(['git',*args],text=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()
        if git('rev-parse','HEAD')!=code_freeze:raise RuntimeError('CODE_FREEZE_HEAD_MISMATCH')
        if git('ls-remote','origin','refs/heads/stage/clean3-math-repair').split()[0]!=code_freeze:raise RuntimeError('CODE_FREEZE_NOT_PUSHED')
        if git('diff','--name-only') or git('diff','--cached','--name-only'):raise RuntimeError('TRACKED_WORKTREE_DIFF_BEFORE_LAUNCH')
        local=yaml.safe_load(Path('configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
        self.roots={k:Path(local[k]) for k in ('code_root','clean_root','raw_root','handoff_root','t5a_scratch')}
        self.scratch=self.roots['t5a_scratch'];self.archive=self.resolve(self.contract['output_root'])
        if self.scratch.exists() or self.archive.exists():raise FileExistsError('Preserve existing T5a attempt, never auto-resume/retry')
        self.scratch.mkdir(parents=True);self.pins={};self.accesses=set();self.code_source_receipts={}
        tree=git('ls-tree','-r',code_freeze)
        self.git_blobs={line.split('\t',1)[1]:line.split('\t',1)[0].split()[2] for line in tree.splitlines() if '\t' in line}
        def guard(event,args):
            if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
            p=Path(os.fsdecode(args[0])).absolute()
            if p.name.lower().startswith('trace_') or p.suffix.lower() in ('.bag','.fpl'):raise PermissionError('Parent cannot open trace/bag/fpl')
            flags=args[2] if len(args)>2 and isinstance(args[2],int) else 0
            if flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                allowed=(self.scratch,self.archive,self.roots['handoff_root'])
                if p != Path('/dev/null') and not any(p==r or r in p.parents for r in allowed):raise PermissionError('T5a write outside dedicated roots: '+str(p))
            else:self.accesses.add(str(p))
        sys.addaudithook(guard)
        self.sequences={s:load_sequence_paths(s) for s in self.contract['matrix']}
        self.tables={}
        for v in ('v3','v2'):
            spec=self.contract['frozen']['sequence_tables'];path=self.resolve(spec['root'])/v/spec['filename']
            self.tables[v]=list(csv.DictReader(io.StringIO(self.read(path,spec[v+'_sha256']).decode('utf-8-sig'))))
        manifest=self.contract['frozen']['hext04l_data_manifest']
        self.h04_sources={r['path']:r['sha256'] for r in json.loads(self.read(self.resolve(manifest['path']),manifest['sha256']))['sources']}
        self.binary=self.resolve(self.contract['frozen']['executable']['path']);self.pin(self.binary,self.contract['frozen']['executable']['sha256'])
        self.evaluator=self.resolve(self.contract['frozen']['evaluator']['path']);self.pin(self.evaluator,self.contract['frozen']['evaluator']['sha256'])
        source=self.contract['frozen']['frozen_heading_conversion'];self.pin(self.code/source['path'],source['sha256'])
        self.matrix=[dict(run_id=f'{s}__{cfg}__{v}',sequence_id=s,configuration_id=cfg,variant=v) for s,m in self.contract['matrix'].items() for cfg in m['configurations'] for v in m['variants']]
        self.native_ids=[r['run_id'] for r in self.matrix];self.eval_ids=[i+'__'+v for i in self.native_ids for v in ('v3','v2')]
        assert len(self.native_ids)==16 and len(self.eval_ids)==32
        self.figure_snapshot=self.figures()
        if self.figure_snapshot['RENDER_MANIFEST.json'] != '800df76ad82b68e3fca7aded30081f6d1ad01241175978baf440c9e0f290dd4e':raise RuntimeError('FROZEN_RENDER_MANIFEST_PIN')
        write_json(self.scratch/'07_HANDOFF/CODE_FREEZE.json',dict(code_freeze=code_freeze,pushed_head=code_freeze,contract_sha256=sha256_file(CONTRACT),matrix=self.matrix,original_figure_hashes=self.figure_snapshot))
        self.check_sources()
        write_json(self.scratch/'07_HANDOFF/SOURCE_CODE_FREEZE.json',dict(code_commit=self.freeze,sources=self.code_source_receipts))
        self.native=[];self.evaluations=[];self.diagnostics=[];self.sources_by_sequence={};self.prepared={};self.echoes={}
        prior=self.contract['predecessor'];self.pin(self.resolve(prior['zip']),prior['zip_sha256'])
        write_json(self.scratch/'07_HANDOFF/PREDECESSOR_INVALIDATION.json',dict(classification='INVALID_CONFIG_PARSE',historical_native_invocations=3,historical_evaluator_invocations=0,excluded_from_all_tables=True,original_records_preserved=True,prior=prior,new_budget=self.contract['budget']))

    def resolve(self,value):
        text=str(value)
        for k,p in self.roots.items():text=text.replace('<'+k.upper()+'>',str(p))
        if '<' in text:raise ValueError('Unresolved alias '+text)
        return Path(text)
    def alias(self,path):
        p=Path(path)
        for k,r in self.roots.items():
            if p==r or r in p.parents:return '<'+k.upper()+'>'+('/'+p.relative_to(r).as_posix() if p!=r else '')
        return str(p)
    def pin(self,path,expected):
        p=Path(path)
        if any(q.is_symlink() for q in (p,*p.parents)) or not p.is_file():raise RuntimeError('HARD_STOP_INPUT_PATH '+str(p))
        got=sha256_file(p)
        if got!=expected or p in self.pins and self.pins[p]!=got:raise RuntimeError('HARD_STOP_INPUT_HASH '+str(p))
        self.pins[p]=got;return got
    def read(self,path,expected):
        self.pin(path,expected);return Path(path).read_bytes()
    def check_sources(self):
        paths={Path(getattr(m,'__file__','')).absolute() for m in tuple(sys.modules.values()) if getattr(m,'__file__',None)}
        paths.update((self.code/'scripts/paper_rebuild/clean5_evaluator_observer').rglob('*.py'))
        paths.update(self.code/p for p in [CONTRACT,Path('scripts/paper_rebuild/t5a_execute.py'),Path('configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml'),Path('configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml')])
        for p in sorted(paths):
            if self.code not in p.parents or p.suffix not in ('.py','.yaml'):continue
            rel=p.relative_to(self.code).as_posix()
            data=p.read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if self.git_blobs.get(rel)!=blob:raise RuntimeError('HARD_STOP_UNFROZEN_IMPORTED_SOURCE '+rel)
            h=hashlib.sha256(data).hexdigest();self.pin(p,h)
            self.code_source_receipts[rel]=dict(code_commit=self.freeze,git_blob=blob,sha256=h)

    def checkpoint(self,name):
        self.check_sources()
        for p,h in self.pins.items():self.pin(p,h)
        if self.figures()!=self.figure_snapshot:raise RuntimeError('HARD_STOP_FROZEN_FIGURE_HASH')
        write_json(self.scratch/'07_HANDOFF'/f'{name}_CHECKPOINT.json',dict(code_commit=self.freeze,status='PASS',hashes={self.alias(p):h for p,h in self.pins.items()},frozen_figures_unchanged=True,code_sources=self.code_source_receipts))
    def figures(self):
        root=self.roots['clean_root']/'stages/CLEAN6_PUBLICATION_FIGURES/figures/v21'
        # The original render registry owns the 28 frozen composites; HEXT extras are separate.
        manifest=root/'RENDER_MANIFEST.json';out={'RENDER_MANIFEST.json':sha256_file(manifest)}
        for p in sorted(root.iterdir()):
            if p.is_dir() and not p.name.startswith(('HEXT','FIG02S')):
                for q in sorted(p.rglob('*')):
                    if q.is_file():out[str(q.relative_to(root))]=sha256_file(q)
        return out
    def frozen(self,s,cfg):
        matches=[r for r in self.tables['v3'] if r['dataset_id']==s and r['method_id']==cfg]
        if len(matches)!=1:raise RuntimeError('FROZEN_ROW_IDENTITY')
        row=matches[0];spec=self.contract['frozen']['runtime_configs'][s+'_'+cfg]
        path=self.resolve(self.contract['frozen']['runtime_config_template'].replace('<RUN_ID>',spec['run_id']))
        payload=self.read(path,spec['sha256']);config=yaml.safe_load(payload)
        echo=path.with_name('RUN_MANIFEST.json');self.pin(echo,spec['effective_echo_sha256'])
        self.echoes[s,cfg]=(echo,spec['effective_echo_sha256'])
        if row['config_hash']!=spec['sha256']:raise RuntimeError('FROZEN_CONFIG_TABLE_HASH')
        providers=json.loads(row['provider_hashes'])
        for k in PROVIDER_KEYS:self.pin(Path(config[k]),providers[k])
        if providers['gnsspath']!=self.contract['frozen']['gnss18_sha256'][s]:raise RuntimeError('FROZEN_GNSS_HASH')
        return row,path,config,providers
    def prepare(self,s):
        seq=self.sequences[s];sources=[]
        self.pin(seq.hash_lock,seq.hash_lock_sha256)
        lock={r['relative_path']:r['sha256'] for r in csv.DictReader(seq.hash_lock.open())}
        raws=[seq.gnss1_raw,seq.gnss2_raw,seq.gnss1_raw.with_name('gnss1-status.csv'),seq.gnss2_raw.with_name('gnss2-status.csv')]
        for p in raws:
            h=lock[p.relative_to(seq.raw_root).as_posix()];self.pin(p,h);sources.append({'path':self.alias(p),'sha256':h})
        info={cfg:self.frozen(s,cfg) for cfg in ('F02','F04')}
        self.checkpoint(s+'_PRE')
        first,second=(decode_receiver(p)[0] for p in raws[:2]);keys=sorted(set(first)&set(second))
        if not keys:raise RuntimeError('NO_COMMON_RAW_HPPOS')
        origin=np.asarray(first[keys[0]]['ecef_m']);rotation=fixed_ecef_to_ned_rotation(origin)
        p1=np.array([rotation@(np.array(first[k]['ecef_m'])-origin) for k in keys]);p2=np.array([rotation@(np.array(second[k]['ecef_m'])-origin) for k in keys])
        raw_yaw,adapter=raw_yaw_from_ned(p1,p2,itow_ms=keys,gps_week=2408,base_time=seq.base_time,adapter_root=self.scratch/'02_PROVIDER_TABLES'/s/'RAW_ADAPTER')
        flags=[hp.pvt_flags_from_csv_bytes(p.read_bytes(),expected_sha256=self.pins[p]) for p in raws[:2]]
        _,_,config,providers=info['F02'];frozen=Path(config['gnsspath']).read_bytes()
        payloads,audit,rows=build_t5a_variants(frozen,expected_sha256=providers['gnsspath'],gps_week=2408,base_time=seq.base_time,raw_yaw_rows=raw_yaw,pvt_flags1=flags[0],pvt_flags2=flags[1],sequence=s,window=seq.window)
        audit['epoch_set']['raw_grid_diff_ms_counts']={str(int(d)):int(n) for d,n in zip(*np.unique(np.diff(keys),return_counts=True))}
        audit['epoch_set']['closed_window_raw_grid_matched_count']=sum(r['a1_valid'] and r['raw_epoch_matched'] and seq.window[0]<=r['time_s']<=seq.window[1] for r in rows)
        ep=self.scratch/'01_EPOCH_SETS'/s;write_json(ep/'EPOCH_SET.json',audit['epoch_set']);write_csv(ep/'A1_EPOCHS.csv',[r for r in rows if r['a1_valid']])
        write_csv(ep/'EXCLUDED_A1_EPOCHS.csv',[r for r in rows if r['a1_valid'] and not r['both_fixed_valid']])
        write_json(ep/'FRAME_AND_ADAPTER.json',dict(origin_ecef_m=origin.tolist(),ecef_to_ned=rotation.tolist(),adapter=adapter,raw_source_hashes=sources))
        for variant,payload in payloads.items():
            folder=self.scratch/'02_PROVIDER_TABLES'/s/variant;folder.mkdir(parents=True)
            p=folder/'T5A.gnss';p.write_bytes(payload)
            manifest={**audit,'code_commit':self.freeze,'config_hash':sha256_file(CONTRACT),'raw_source_hashes':sources,'provider_hashes':{**providers,'gnsspath':sha256_file(p)},'variant':variant,'byte_gate':audit['byte_gates'][variant]}
            write_json(folder/'PROVIDER_MANIFEST.json',manifest)
            self.prepared[s,variant]=dict(path=str(p),sha256=sha256_file(p),byte_gate=audit['byte_gates'][variant])
        try:
            imu=np.loadtxt(config['imupath']);rp=pd.read_csv(config['go2_attitude_prior_path'])[['time','roll_rad','pitch_rad']].to_numpy(float)
            statuses=[list(csv.DictReader(p.open())) for p in raws[2:]]
            diag=diagnose(s,seq.window,rows,imu,rp,*statuses)
        except (ValueError,TypeError,KeyError,IndexError) as exc:
            # D4 is diagnostic-only; missing diagnostic support cannot stop authorized native runs.
            diag={'source_consistency_rows':[{'sequence_id':s,'category':'diagnostic_unavailable','scope':'all','status':'UNAVAILABLE','reason':type(exc).__name__+': '+str(exc)}],
                  'per_epoch':rows,'histograms':[],'sigma_pairs':[],'timing_rows':[],'diagnostic_exception':str(exc)}
        target=self.scratch/'02_PROVIDER_TABLES'/s/'D4'
        write_json(target/'SOURCE_CONSISTENCY.json',diag)
        for k,v in diag.items():
            if isinstance(v,list) and all(isinstance(r,dict) for r in v):write_csv(target/(k.upper()+'.csv'),v)
        self.diagnostics.append(dict(sequence_id=s,path=str(target/'SOURCE_CONSISTENCY.json')))
        self.sources_by_sequence[s]=sources
        return info

    def execute(self):
        terminal='COMPLETED';error=None
        try:
            print('T5a-R A0 read-only config/parser audit',flush=True)
            fields=('run_id','dataset_id','method_id','config_hash','output_root','native_run_manifest','archive_receipt')
            self.a0=run_parser_audit(self.roots['clean_root']/'stages/CLEAN6_SENSOR_MODEL_V21',
                [{k:r.get(k,'') for k in fields} for r in self.tables['v3']],self.scratch/'07_HANDOFF/A0',self.freeze)
            print('T5a-R A0 '+str(self.a0.get('status')),flush=True)
            self.checkpoint('A0_POST')
            for s in self.sequences:
                print('T5a sequence '+s+' prepare',flush=True);info=self.prepare(s)
                for slot in [r for r in self.matrix if r['sequence_id']==s]:
                    _,config_path,config,providers=info[slot['configuration_id']]
                    print('T5a native '+slot['run_id'],flush=True)
                    rec=run_native(self.sequences[s],contract=self.contract,frozen_config_path=config_path,
                        expected_config_sha256=sha256_file(config_path),frozen_provider_hashes=providers,
                        prepared_gnss=self.prepared[s,slot['variant']],output_root=self.scratch/'03_NATIVE'/s/slot['configuration_id']/slot['variant'],
                        scratch_root=self.scratch,code_commit=self.freeze,slot_identity=slot,launch_ledger=self.scratch/'07_HANDOFF/NATIVE_LEDGER.jsonl',allowed_run_ids=self.native_ids,raw_source_hashes={r['path']:r['sha256'] for r in self.sources_by_sequence[s]},
                        frozen_echo_path=self.echoes[s,slot['configuration_id']][0],expected_echo_sha256=self.echoes[s,slot['configuration_id']][1])
                    self.native.append(rec)
                    for v in ('v3','v2'):
                        if rec['status']!='COMPLETED':
                            self.evaluations.append({'row':{**slot,'evaluator_contract':'evaluator_contract_'+v,'evaluation_status':'NOT_RUN_ALGORITHM_FAILURE' if rec['status']=='ALGORITHM_FAILURE_DIVERGED' else 'NOT_RUN_NATIVE_UNAVAILABLE','reason':rec['status']}});continue
                        print('T5a evaluate '+slot['run_id']+' '+v,flush=True)
                        value=evaluate_native(self.sequences[s],self.evaluator,rec['nav_path'],rec['std_path'],self.scratch/'04_EVAL'/v/s/slot['configuration_id']/slot['variant'],v,{**slot,'code_commit':self.freeze},
                            expected_nav_sha256=rec['nav_sha256'],expected_std_sha256=rec['std_sha256'],baseline_median_m=self.sequences[s].baseline_median_m,
                            bounded_gate=rec['bounded_gate'],scratch_root=self.scratch,launch_ledger=self.scratch/'07_HANDOFF/EVALUATOR_LEDGER.jsonl',allowed_run_ids=self.eval_ids)
                        self.evaluations.append(value)
                self.checkpoint(s+'_POST')
                # Completed sequence artifacts copied only after its immutable-input checkpoint.
                self.archive_files()
        except Exception as exc:
            terminal='HARD_STOP_PARTIAL_EVIDENCE';error=dict(type=type(exc).__name__,message=str(exc));print(terminal+' '+repr(error),flush=True)
            import traceback;traceback.print_exc()
            known={r['run_id'] for r in self.native}
            for path in sorted((self.scratch/'03_NATIVE').rglob('T5A_NATIVE_SUMMARY.json')):
                value=json.loads(path.read_text())
                if value['run_id'] not in known:self.native.append(value);known.add(value['run_id'])
        result=dict(status=terminal,error=error,code_commit=self.freeze,contract_sha256=sha256_file(CONTRACT),native=self.native,evaluations=self.evaluations,diagnostics=self.diagnostics,
                    input_hashes={self.alias(p):h for p,h in self.pins.items()},parent_trace_open_count=0,raw_source_hashes=self.sources_by_sequence,
                    a0=getattr(self,'a0',{'status':'NOT_EXECUTED'}),fidelity_native_invocations=0,fidelity_evaluator_invocations=0,fidelity_route='EFFECTIVE_ECHO_PRESENT',historical_invalid_native=3)
        write_json(self.scratch/'07_HANDOFF/EXECUTION_SUMMARY.json',result)
        self.archive_files()
        return result

    def archive_files(self):
        for source in sorted(self.scratch.rglob('*')):
            if not source.is_file():continue
            dest=self.archive/source.relative_to(self.scratch);dest.parent.mkdir(parents=True,exist_ok=True)
            digest=sha256_file(source)
            if dest.exists():
                if sha256_file(dest)==digest:continue
                # Append-only live ledgers may grow, preserve each version by content hash.
                if source.suffix!='.jsonl':raise RuntimeError('ARCHIVE_EXISTING_BYTES_DIFFER '+str(dest))
                history=dest.parent/(dest.name+'.previous.'+sha256_file(dest));shutil.copyfile(dest,history)
            shutil.copyfile(source,dest)
            if sha256_file(dest)!=digest:raise RuntimeError('HARD_STOP_ARCHIVE_HASH')
