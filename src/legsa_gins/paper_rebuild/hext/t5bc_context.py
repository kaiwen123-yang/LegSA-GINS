"""Frozen T5bc entrypoint wiring; no I/O or execution occurs on import.

The command validates pushed Git identity before any scientific input is read.
Calibration, identity, provider generation and the matrix have separate immutable
completion receipts; reporting and publication are intentionally separate.
"""
from __future__ import annotations

from copy import deepcopy
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml

from . import t5bc_execution as execution
from . import t5bc_preparation as preparation
from . import t5bc_runtime as runtime
from .t5bc_calibration import calibration_bin_report
from .sequence_paths import load_sequence_paths, REGISTRY, CALIBRATED_CONTRACT

CONTRACT = Path('configs/paper_rebuild/hext/T5BC_CONTRACT_V1.yaml')
ENTRYPOINT = Path('scripts/paper_rebuild/t5bc_execute.py')
CASES = ['C00_clean_normal'] + [f'D{i:02d}_seed_00' for i in range(1,61)]
SEQUENCES = ('BY2','BY2H','BY2O')


def resolve_aliases(value, roots):
    if isinstance(value,dict):return {key:resolve_aliases(item,roots) for key,item in value.items()}
    if isinstance(value,list):return [resolve_aliases(item,roots) for item in value]
    if isinstance(value,str):
        for key,path in roots.items():value=value.replace('<'+key.upper()+'>',str(path))
    return value


def git_freeze_receipt(code_root, code_freeze, *, required_paths=()):
    """Actual read-only Git commands at invocation time; no supplied fake PASS."""
    code=runtime._safe(code_root)
    if not re.fullmatch(r'[0-9a-f]{40}',code_freeze):raise ValueError('Full code freeze SHA required')
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=code,text=True,
            env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()
    head=git('rev-parse','HEAD')
    remote=git('ls-remote','origin','refs/heads/stage/clean3-math-repair').split()
    if head!=code_freeze or not remote or remote[0]!=code_freeze:
        raise RuntimeError('HARD_STOP_T5BC_CODE_FREEZE_NOT_CURRENT_AND_PUSHED')
    if git('diff','--name-only') or git('diff','--cached','--name-only'):
        raise RuntimeError('HARD_STOP_T5BC_TRACKED_WORKTREE_NOT_FROZEN')
    blobs={line.split('\t',1)[1]:line.split('\t',1)[0].split()[2]
           for line in git('ls-tree','-r',code_freeze).splitlines() if '\t' in line}
    paths=execution._source_files() | {code/CONTRACT,code/ENTRYPOINT,code/REGISTRY,code/CALIBRATED_CONTRACT}
    paths.update(runtime._safe(path) for path in required_paths)
    paths.update(code/name for name in blobs if name.startswith("src/legsa_gins/paper_rebuild/hext/t5bc_") and name.endswith(".py"))
    paths.add(code/"src/legsa_gins/paper_rebuild/publication/style.py")
    paths.update(code/name for name in blobs if name.startswith("scripts/paper_rebuild/t5bc_") and name.endswith(".py"))
    paths.update(code/name for name in blobs if name.startswith('cpp/legsa_v23_port_core/')
                 and (name.endswith(('.cpp','.h','.hpp')) or name.endswith('CMakeLists.txt')))
    pins={}
    for path in sorted(paths):
        path=runtime._safe(path)
        if not runtime._within(path,code):raise RuntimeError('HARD_STOP_T5BC_IMPORTED_WRONG_CHECKOUT')
        relative=path.relative_to(code).as_posix();payload=path.read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
        if blobs.get(relative)!=blob:raise RuntimeError('HARD_STOP_T5BC_UNFROZEN_SOURCE: '+relative)
        pins[relative]=hashlib.sha256(payload).hexdigest()
    return dict(status='PASS_CODE_FREEZE_PUSHED',code_freeze=code_freeze,head_commit=head,
        remote_commit=remote[0],tracked_worktree_clean=True,source_sha256=pins)


def planned_provider_refs(scratch, sequence, case=None):
    root=Path(scratch)/'03_PROVIDER_TABLES'/('SUBSET61/'+case if case else sequence)
    refs={variant:{'path':str(root/variant/'GNSS18.txt'),'sha256':None}
          for variant in ('R5','R5SIGMA','R5W')}
    refs.update(B3_GNSS={'path':str(root/'B3/GNSS18.txt'),'sha256':None},
                B3={'path':str(root/'B3/baseline3d.csv'),'sha256':None},
                prepared_raw_manifest={'path':str(root/'PREPARED_RAW_MANIFEST.json'),'sha256':None})
    return refs


def build_registered_contract(contract, index, contexts, *, scratch_root, code_freeze,
                              selections, raw_hashes, subset_metadata, execution_control,
                              provider_bundles=None, calibration_pins=()):
    """Pure final 261-spec construction; no case selection or calibration inference."""
    if contract.get('execution_ready') is not True or contract.get('preregistered') is not True:
        raise PermissionError('T5BC_DRAFT_NOT_AUTHORIZED_FOR_EXECUTION')
    if contract['matrix']['subset']['case_ids']!=CASES or set(index['subset_sources'])!=set(CASES):
        raise ValueError('T5bc requires the exact frozen 61-case seed-zero registry')
    result=deepcopy(contract);result['code_freeze']=code_freeze
    result['budget']['matrix_evaluator']=result['budget']['evaluator']
    result['execution_control']=deepcopy(execution_control)
    result['execution_control']['calibration_pins']=list(calibration_pins)
    result['applied_calibrations']=deepcopy(selections)
    runs={}
    slots=[(seq,cfg,var,None) for seq in SEQUENCES for var in ('R5SIGMA','R5W','B3')
           for cfg in (('F02','A04','F04') if var=='B3' else ('F04',))]
    slots += [('BY2','F04',var,case) for case in CASES for var in ('R5','R5SIGMA','R5W','B3')]
    slots += [('BY2',cfg,'IDENTITY',None) for cfg in ('F02','F04')]
    for seq,cfg,var,case in slots:
        source=index['subset_sources'][case] if case else index['runtime_sources'][seq+'_'+cfg]
        context=contexts[seq]
        run_id='__'.join((seq,cfg,var,case or 'SEQUENCE'))
        roles=dict(data_mode='semisynthetic' if case not in (None,'C00_clean_normal') else 'real_clean' if case else 'real_raw',
                   synthetic_data_used=False,semisynthetic_data_used=case not in (None,'C00_clean_normal'))
        spec=dict(run_id=run_id,sequence_id=seq,configuration_id=cfg,variant=var,subset_case_id=case,
            frozen_config=deepcopy(source['frozen_config']),frozen_echo=deepcopy(source['frozen_echo']),
            frozen_providers=deepcopy(source['frozen_providers']),raw_source_hashes=deepcopy(raw_hashes[seq]),data_roles=roles,
            baseline_median_m=contract['frozen']['baseline_median_m'][seq],
            evaluation={'window':list(context.window),'base_time':context.base_time,
                        'trace':{'path':str(context.trace),'sha256':context.trace_sha256}})
        if 'frozen_echo_witness' in source:spec['frozen_echo_witness']=deepcopy(source['frozen_echo_witness'])
        if case:
            spec.update(source_registry_row=deepcopy(subset_metadata[case]['source_registry_row']),
                        case_meta=deepcopy(subset_metadata[case]['case_meta']))
        if var!='IDENTITY':
            key=case or seq
            refs=provider_bundles[key] if provider_bundles is not None else planned_provider_refs(scratch_root,seq,case)
            expected=planned_provider_refs(scratch_root,seq,case)
            for role,reference in refs.items():
                if role in expected and reference['path']!=expected[role]['path']:
                    raise ValueError('T5bc generated provider path differs from frozen plan')
            spec.update(prepared_gnss=deepcopy(refs['B3_GNSS' if var=='B3' else var]),
                prepared_raw_manifest=deepcopy(refs['prepared_raw_manifest']),
                r5_reference=deepcopy(index['t5a_r']['r5_providers'][seq]))
            if var=='B3':
                spec.update(sidecar=deepcopy(refs['B3']),baseline3d=dict(dual_antenna_measurement_model='baseline3d',
                    baseline3d_path=refs['B3']['path'],baseline3d_length_m=.35,baseline3d_k_b=selections[seq]['k_b']))
        spec['output_relpath']=runtime._native_relative(spec);runs[run_id]=spec
    result['registered_runs']=runs
    result['registered_evaluator_ids']=[key+'__'+version for key,spec in runs.items()
        if spec['variant']!='IDENTITY' for version in ('v3','v2')]
    runtime.validate_registration(result,code_commit=code_freeze)
    return result


def calibration_summary_rows(scalar, vector):
    """Six exact sequence/lag rows; preserve all main/check scalar and vector statistics."""
    rows=[]
    for seq in SEQUENCES:
        for lag in (1000,200):
            a=[row for row in scalar[seq]["reports"] if row["lag_ms"]==lag]
            b=[row for row in vector[seq]["reports"] if row["lag_ms"]==lag]
            if len(a)!=1 or len(b)!=1:raise ValueError("Calibration summary exact lag support missing")
            z=a[0].get("z",{})
            row={"sequence_id":seq,"lag_ms":lag,"applied":seq=="BY2" and lag==1000,
                "sigma_deg":z.get("sigma_deg"),"k":z.get("k"),"k_b":b[0].get("k_b"),
                "scalar_status":a[0].get("status"),"vector_status":b[0].get("status")}
            for family,record in (("scalar",a[0]),("vector",b[0])):
                for key,value in record.items():
                    if isinstance(value,dict):
                        for subkey,item in value.items():row[family+"_"+key+"_"+subkey]=item
                    else:row[family+"_"+key]=value
            rows.append(row)
    return rows


def render_calibration_snapshot(rows_path, output_root, *, code_root):
    """Dedicated plotting child reads only the already written six-row summary."""
    root=runtime._safe(output_root)
    if root.exists():raise FileExistsError("Calibration figure directory already exists")
    root.mkdir(parents=True)
    program=("import csv,json,sys;from pathlib import Path;"
        "from legsa_gins.paper_rebuild.hext.t5bc_figures import _calibration_figure;"
        "from legsa_gins.paper_rebuild.publication import style;"
        "rows=list(csv.DictReader(open(sys.argv[1])));fig=_calibration_figure(rows);"
        "saved=style.save_figure(fig,Path(sys.argv[2]),'T5BC_CALIBRATION');style.plt.close(fig);"
        "print(json.dumps(saved,sort_keys=True))")
    result=subprocess.run([sys.executable,"-c",program,str(rows_path),str(root)],cwd=code_root,
        env={**os.environ,"PYTHONPATH":str(Path(code_root)/"src"),"PYTHONDONTWRITEBYTECODE":"1",
             "MPLCONFIGDIR":str(root/"MPL_CACHE")},capture_output=True,text=True,check=True)
    saved=json.loads(result.stdout)
    for extension in ("png","pdf","svg"):
        runtime._pin({"path":saved[extension],"sha256":saved[extension+"_sha256"]})
    receipt={"status":"CALIBRATION_FIGURE_COMPLETE","outputs":saved,"summary_csv":execution._reference(rows_path),
             "plotting_process_count":1,"native_invocations":0,"evaluator_invocations":0,"trace_open_count":0}
    return preparation._document(root/"CALIBRATION_FIGURE_MANIFEST.json",receipt)


class Context:
    def __init__(self, code_freeze, *, local_config, contract_path=None):
        self.code=Path(__file__).resolve().parents[4]
        self.contract_path=runtime._safe(contract_path or self.code/CONTRACT)
        raw_contract=yaml.safe_load(self.contract_path.read_text())
        if raw_contract.get('execution_ready') is not True or raw_contract.get('preregistered') is not True:
            raise PermissionError('T5BC_DRAFT_NOT_AUTHORIZED_FOR_EXECUTION')
        if self.contract_path!=self.code/CONTRACT:raise ValueError('Only frozen tracked T5bc contract is admitted')
        local=yaml.safe_load(Path(local_config).read_text())['paths']
        self.roots={key:runtime._safe(local[key]) for key in ('code_root','clean_root','raw_root','handoff_root','t5bc_scratch')}
        if self.roots['code_root']!=self.code:raise RuntimeError('HARD_STOP_T5BC_WRONG_CODE_ROOT')
        self.freeze=code_freeze
        self.clean=self.roots["clean_root"]
        sys.dont_write_bytecode=True
        source_index=self.code/raw_contract['frozen']['source_index']['path']
        self.git_receipt=git_freeze_receipt(self.code,code_freeze,required_paths=[source_index])
        self.contract=resolve_aliases(raw_contract,self.roots)
        self.contract['code_freeze']=code_freeze
        self.scratch=self.roots['t5bc_scratch'];self.archive=runtime._safe(self.contract['output_root'])
        if self.scratch.name!=runtime.STAGE or any(runtime._within(self.scratch,self.roots[key])
                for key in ('code_root','clean_root','raw_root')):
            raise ValueError('Independent exact T5bc scratch root required')
        self.active_phase='metadata'
        self._install_guard()
        self.contexts={seq:load_sequence_paths(seq,local_config=Path(local_config),
            registry_path=self.code/REGISTRY,calibrated_contract_path=self.code/CALIBRATED_CONTRACT) for seq in SEQUENCES}
        for seq,context in self.contexts.items():
            if context.baseline_median_m!=self.contract['frozen']['baseline_median_m'][seq]:
                raise RuntimeError('HARD_STOP_T5BC_FROZEN_EVALUATION_BASELINE')
        index_ref={'path':str(source_index),'sha256':raw_contract['frozen']['source_index']['sha256']}
        self.index=resolve_aliases(yaml.safe_load(self._read(index_ref)),self.roots)
        self.source_index=self.index
        self.source_index_ref=index_ref
        self.evaluator={'path':self.contract['frozen']['evaluator_path'],'sha256':self.contract['frozen']['evaluator_sha256']}
        self.raw_hashes={}
        for seq,context in self.contexts.items():
            payload=self._read({'path':str(context.hash_lock),'sha256':context.hash_lock_sha256})
            prefix=context.gnss1_raw.parent.relative_to(context.raw_root).as_posix()+'/'
            entries=list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
            mapping={str(context.raw_root/row['relative_path']):row['sha256'] for row in entries
                     if row['relative_path'].startswith(prefix) or context.raw_root/row['relative_path']==context.go2_body}
            for path in (context.gnss1_raw,context.gnss2_raw):
                if str(path) not in mapping:raise RuntimeError('HARD_STOP_T5BC_RAW_LOCK_SOURCE_MISSING')
            self.raw_hashes[seq]=mapping
        self.metadata={}
        for case,source in self.index['subset_sources'].items():
            terminal=json.loads(self._read(source['terminal']))
            registry=terminal['source_registry_row']
            if registry['case_id']!=case or registry['method_id']!='F04':
                raise RuntimeError('HARD_STOP_T5BC_FROZEN_SUBSET_REGISTRY_METADATA')
            self.metadata[case]={'source_registry_row':registry,'case_meta':terminal['case_meta']}
        self.control=self._control(index_ref)

    def _install_guard(self):
        def guard(event,args):
            if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
            path=Path(os.fsdecode(args[0])).absolute()
            flags=args[2] if len(args)>2 and isinstance(args[2],int) else 0
            writing=flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
            if writing and path!=Path('/dev/null') and not any(runtime._within(path,root) for root in (self.scratch,self.archive)):
                raise PermissionError('T5bc parent write outside dedicated roots: '+str(path))
            if not writing and runtime._within(path,self.roots['raw_root']):
                if self.active_phase!='calibration' or path.name not in ('gnss1-raw.csv','gnss2-raw.csv'):
                    raise PermissionError('T5bc parent raw/trace access denied: '+str(path))
            if path.suffix.lower() in ('.bag','.fpl') or path.name.lower().startswith('trace_'):
                raise PermissionError('T5bc trace/bag/fpl parent access denied')
        sys.addaudithook(guard)

    def _read(self,reference):
        reference={key:reference[key] for key in ('path','sha256')}
        runtime._pin(reference);return Path(reference['path']).read_bytes()

    def _control(self,index_ref):
        root=self.roots['clean_root']/'stages/CLEAN6_PUBLICATION_FIGURES/figures/v21'
        render={'path':str(root/'RENDER_MANIFEST.json'),'sha256':self.contract['frozen']['original_render_manifest_sha256']}
        self._read(render)
        groups={}
        for directory in sorted(root.iterdir()):
            path=directory/'FIGURE_MANIFEST.json'
            if not directory.is_dir() or directory.name.startswith(('HEXT','FIG02S')) or not path.is_file():continue
            record=json.loads(path.read_text())
            if record.get('protocol_version')!='v2.1' or record.get('status')!='RENDERED':continue
            references=[execution._reference(path)]
            for item in record['outputs'].values():
                ref={'path':str(root/item['path']),'sha256':item['sha256']};runtime._pin(ref);references.append(ref)
            groups[directory.name]=references
        if len(groups)!=28:raise RuntimeError('HARD_STOP_T5BC_FROZEN_FIGURE_COUNT')
        comparators={}
        for cfg in ('F02','F04'):
            source=self.index['runtime_sources']['BY2_'+cfg]
            path=Path(source['frozen_config']['path']).with_name('NAV_10HZ.csv.gz')
            comparators['BY2__'+cfg+'__IDENTITY__SEQUENCE']={'path':str(path),
                'sha256':self.contract['frozen']['identity_nav_10hz_sha256']['BY2_'+cfg]}
        extra={'source_index':index_ref}
        def collect(value,prefix):
            if isinstance(value,dict):
                if 'path' in value and 'sha256' in value:
                    path=Path(value['path'])
                    if not path.is_absolute():path=self.code/path
                    extra[prefix]={'path':str(path),'sha256':value['sha256']}
                else:
                    for key,item in value.items():collect(item,prefix+'__'+key)
        collect(self.index,'source_index_member')
        return dict(identity_comparators=comparators,frozen_figures=groups,render_manifest=render,extra_frozen_pins=extra)

    def _checkpoint(self):
        latest=git_freeze_receipt(self.code,self.freeze,required_paths=[self.code/self.contract['frozen']['source_index']['path']])
        if latest!=self.git_receipt:raise RuntimeError('HARD_STOP_T5BC_SOURCE_GRAPH_CHANGED')
        unique={}
        for reference in self.control['extra_frozen_pins'].values():
            if reference['path'] in unique and unique[reference['path']]!=reference['sha256']:
                raise RuntimeError('HARD_STOP_T5BC_CONFLICTING_CHECKPOINT_SHA')
            unique[reference['path']]=reference['sha256']
        for path,digest in unique.items():runtime._pin({'path':path,'sha256':digest})
        for reference in (self.contract['frozen']['executable'],self.contract['candidate'],self.evaluator,self.control['render_manifest']):
            runtime._pin({key:reference[key] for key in ('path','sha256')})
        for group in self.control['frozen_figures'].values():
            for reference in group:runtime._pin(reference)

    def calibration(self):
        self.active_phase='calibration';path=self.scratch/'01_CALIBRATION/CALIBRATION_SUMMARY.json'
        if path.is_file():return self._verified_calibration()
        self._checkpoint();reports={};vectors={};observations={};pins=[]
        for seq,context in self.contexts.items():
            source=self.index['runtime_sources'][seq+'_F04']['frozen_providers']
            obs,obs_ref=preparation.decode_observations(context,scratch_root=self.scratch,
                output_root=self.scratch/f'01_CALIBRATION/{seq}/RAW_OBSERVATIONS')
            cache=self.scratch/f'01_CALIBRATION/{seq}/OBSERVATIONS.json'
            cache_ref=preparation._document(cache,obs);observations[seq]=cache_ref;pins.extend([cache_ref,obs_ref])
            common=dict(imu_reference=source['imupath'],rp_reference=source['go2_attitude_prior_path'],scratch_root=self.scratch)
            reports[seq],ref=preparation.calibrate_scalar(context,obs,**common,
                output_root=self.scratch/f'01_CALIBRATION/{seq}/SCALAR',denominator_policy='PAIR_ENDPOINTS_WITH_MULTIPLICITY')
            pins.append(ref)
            vectors[seq],ref=preparation.calibrate_vector(context,obs,**common,
                output_root=self.scratch/f'01_CALIBRATION/{seq}/VECTOR');pins.append(ref)
            self._checkpoint()
        scalar=preparation.select_scalar_calibration(reports,sigma_application='BY2_UNIFIED')
        vector=preparation.select_vector_calibration(vectors)
        selected={seq:{**scalar[seq],**vector[seq]} for seq in SEQUENCES}
        rows=calibration_summary_rows(reports,vectors)
        csv_path=path.parent/'CALIBRATION_SUMMARY.csv'
        fields=list(dict.fromkeys(key for row in rows for key in row))
        with csv_path.open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            writer.writerows({key:runtime._json(value) if isinstance(value,(list,dict)) else value for key,value in row.items()} for row in rows)
            stream.flush();os.fsync(stream.fileno())
        bins=[]
        for lag in (1000,200):
            try:
                report=calibration_bin_report(reports,vectors,lag_ms=lag)
                for row in report['rows']:
                    values=row['pair_mean_S_m2'];mean_s=sum(values)/len(values) if values else None
                    row.update(applied_k=selected['BY2']['k'],applied_k_b=selected['BY2']['k_b'],mean_S_bin_m2=mean_s,
                        applied_k_sqrt_S_m=selected['BY2']['k']*math.sqrt(mean_s) if mean_s is not None else None,
                        applied_heading_equivalent_deg=math.degrees(selected['BY2']['k']*math.sqrt(mean_s)/.35) if mean_s is not None else None,
                        applied_k_b_sqrt_S_m=selected['BY2']['k_b']*math.sqrt(mean_s) if mean_s is not None else None)
                bins.append(report)
            except ValueError as error:bins.append({'lag_ms':lag,'status':'UNAVAILABLE','reason':str(error)})
        pins.append(preparation._document(path.parent/'CALIBRATION_S_BINS.json',{'reports':bins}))
        pins.append(execution._reference(csv_path))
        pins.append(render_calibration_snapshot(csv_path,path.parent/'FIGURES',code_root=self.code))
        self._checkpoint()
        value=dict(status='CALIBRATION_COMPLETE' ,code_freeze=self.freeze,selections=selected,
            observations=observations,pins=pins,files=execution._inventory(path.parent),native_invocations=0,evaluator_invocations=0,trace_open_count=0)
        execution._write_or_verify(path,value)
        execution.archive_tree_bounded(path.parent,self.archive/'01_CALIBRATION',audit_root=self.scratch/'09_HANDOFF/ARCHIVE_IO')
        return self._verified_calibration()

    def _verified_calibration(self):
        path=self.scratch/'01_CALIBRATION/CALIBRATION_SUMMARY.json';value=execution._read(path)
        if value['status']!='CALIBRATION_COMPLETE' or value['code_freeze']!=self.freeze:
            raise RuntimeError('HARD_STOP_T5BC_CALIBRATION_FREEZE')
        actual=execution._inventory(path.parent);actual.pop(path.name,None)
        if actual!=value['files']:raise RuntimeError('HARD_STOP_T5BC_CALIBRATION_HASHES')
        for ref in value['pins']:runtime._pin(ref)
        return value

    def registered(self,*,prepared=False):
        calibration=self._verified_calibration();bundles=None
        if prepared:
            bundles={}
            for seq,case in [(seq,None) for seq in SEQUENCES]+[('BY2',case) for case in CASES]:
                root=self.scratch/'03_PROVIDER_TABLES'/('SUBSET61/'+case if case else seq)
                manifest=execution._read(root/'PROVIDER_MANIFEST.json')
                for ref in manifest['providers'].values():runtime._pin(ref)
                bundles[case or seq]=manifest['providers']
        return build_registered_contract(self.contract,self.index,self.contexts,scratch_root=self.scratch,
            code_freeze=self.freeze,selections=calibration['selections'],raw_hashes=self.raw_hashes,
            subset_metadata=self.metadata,execution_control=self.control,provider_bundles=bundles,
            calibration_pins=[*calibration['pins'],execution._reference(self.scratch/'01_CALIBRATION/CALIBRATION_SUMMARY.json')])

    def _arguments(self,contract):
        receipt={**self.git_receipt,'scientific_contract_sha256':runtime.scientific_contract_sha256(contract),
                 'resolved_contract_sha256':execution._digest(contract)}
        return dict(contract=contract,contexts=self.contexts,evaluator=self.evaluator,scratch_root=self.scratch,
                    archive_root=self.archive,code_freeze_receipt=receipt)

    def identity(self):
        self.active_phase='identity';self._checkpoint()
        return execution.execute_identities(**self._arguments(self.registered()))

    def providers(self):
        self.active_phase='providers';planned=self.registered();self._checkpoint()
        execution.verify_identity_receipt(planned,scratch_root=self.scratch,code_commit=self.freeze)
        calibration=self._verified_calibration();observations={}
        for seq,ref in calibration['observations'].items():
            value=json.loads(self._read(ref))
            for key in ('pacc1_m','pacc2_m','pvt_flags1','pvt_flags2'):value[key]={int(k):v for k,v in value[key].items()}
            observations[seq]=value
        manifests={}
        previous_seq=None
        work=[(seq,case) for seq in SEQUENCES for case in ([None,*CASES] if seq=='BY2' else [None])]
        for seq,case in work:
            if previous_seq!=seq:
                self._checkpoint();previous_seq=seq
            source=self.index['subset_sources'][case] if case else self.index['runtime_sources'][seq+'_F04']
            root=self.scratch/'03_PROVIDER_TABLES'/('SUBSET61/'+case if case else seq)
            if root.exists():
                manifest=execution._read(root/'PROVIDER_MANIFEST.json')
                for ref in manifest['providers'].values():runtime._pin(ref)
                manifests[case or seq]=execution._reference(root/'PROVIDER_MANIFEST.json');continue
            config=yaml.safe_load(self._read(source['frozen_config']))
            _,ref=preparation.write_provider_bundle(self.contexts[seq],observations[seq],calibration['selections'][seq],
                frozen_gnss=source['frozen_providers']['gnsspath'],r5_reference=self.index['t5a_r']['r5_providers'][seq],
                output_root=root,scratch_root=self.scratch,data_mode='semisynthetic' if case not in (None,'C00_clean_normal') else 'real_clean' if case else 'real_raw',
                subset_case_id=case,f04_yaw_std_min_deg=config['yaw_std_min_deg'],allow_unmatched_times=case=='D57_seed_00')
            manifests[case or seq]=ref
            print('T5bc provider '+(case or seq)+' COMPLETE',flush=True)
        self._checkpoint()
        value=dict(status='PROVIDERS_COMPLETE',code_freeze=self.freeze,manifests=manifests,
            scientific_contract_sha256=runtime.scientific_contract_sha256(planned))
        execution._write_or_verify(self.scratch/'03_PROVIDER_TABLES/PROVIDERS_COMPLETE.json',value)
        execution.archive_tree_bounded(self.scratch/'03_PROVIDER_TABLES',self.archive/'03_PROVIDER_TABLES',audit_root=self.scratch/'09_HANDOFF/ARCHIVE_IO')
        return value

    def matrix(self):
        self.active_phase='matrix';self._checkpoint()
        return execution.execute_registered(**self._arguments(self.registered(prepared=True)))

    def verify_layout(self):
        """Read-only freeze, metadata, roots and protected-pin check; no launch/reservation."""
        self.active_phase='verification';self._checkpoint()
        if self.archive!=self.clean/'stages'/runtime.STAGE:
            raise RuntimeError('HARD_STOP_T5BC_ARCHIVE_LAYOUT')
        return dict(status='PASS_READ_ONLY_LAYOUT_AND_FROZEN_PINS',code_freeze=self.freeze,
            scratch=str(self.scratch),archive=str(self.archive),sequence_count=3,subset_case_count=len(self.metadata),
            planned_native_count=261,planned_evaluator_count=518,
            native_invocations=0,evaluator_invocations=0,raw_payload_reads=0,trace_open_count=0,
            remaining_admission='Calibration, two identities, provider gates, exact registration before matrix')

    def execute(self,phase):
        if phase not in ('verify','calibration','identity','providers','matrix','all'):raise ValueError('Unknown phase')
        if phase=="verify":return {"verify":self.verify_layout()}
        result={}
        for name in ('calibration','identity','providers','matrix') if phase=='all' else (phase,):
            print('T5bc phase '+name,flush=True);result[name]=getattr(self,name)()
        return result
