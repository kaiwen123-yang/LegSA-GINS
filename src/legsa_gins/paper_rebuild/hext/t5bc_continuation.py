"""Explicit T5bc-R control continuation; old evidence is immutable and never relaunched."""
from copy import deepcopy
from collections import Counter
import fcntl
import json
from pathlib import Path

from . import t5bc_execution as ex
from . import t5bc_runtime as rt
from .t5bc_context import Context

PRIOR = 'b0a9230f0711c7b81af9d868a98d0eb537ad6eb9'
REGISTRY_SHA256 = 'd1430d458c0cc7e77ef1edcef3d871d001c5b1cb796c81f45989914be838d6ec'
D57 = 'BY2__F04__B3__D57_seed_00'
NOT_APPLICABLE = 'B3_NOT_APPLICABLE_NO_HEADING_EPOCHS'


def verify_sealed_hard_stop(reference):
    """Integrity verification only. Does not make a historical hard stop executable."""
    rt._pin(reference)
    root = Path(reference['path']).parent
    record = ex._read(reference['path'])
    files = record['file_hashes']
    actual = ex._inventory(root)
    if set(actual) != set(files) | {'T5BC_NATIVE_SUMMARY.json'}:
        raise RuntimeError('HARD_STOP_T5BCR_OLD_MEMBER_SET')
    if any(actual[name]['sha256'] != digest for name, digest in files.items()):
        raise RuntimeError('HARD_STOP_T5BCR_OLD_MEMBER_HASH')
    seal = ex._read(root/'OUTPUT_SEAL.json')
    if seal != {'status':'SEALED', 'same_native_invocation':True,
                'files':{k:v for k,v in files.items() if k!='OUTPUT_SEAL.json'}}:
        raise RuntimeError('HARD_STOP_T5BCR_OLD_SEAL')
    return record


def remaining_ids(allowed, registry):
    old = set(registry['native'])
    if len(old)!=62 or not old <= set(allowed['identity_native']) | set(allowed['matrix_native']):
        raise RuntimeError('HARD_STOP_T5BCR_OLD_NATIVE_SCOPE')
    remaining = set(allowed['matrix_native']) - old
    if len(remaining)!=199 or not set(allowed['identity_native']) <= old:
        raise RuntimeError('HARD_STOP_T5BCR_REMAINING_BUDGET')
    return remaining


class Continuation(Context):
    def __init__(self, code_freeze, *, local_config):
        super().__init__(code_freeze, local_config=local_config)
        if code_freeze == PRIOR:
            raise PermissionError('T5bc-R requires a separate pushed control freeze')
        self.state = self.scratch/'09_HANDOFF/CONTINUATION_R'
        self.execution_summary_path = self.state/'FINAL_EXECUTION_SUMMARY.json'
        self.registry_ref = {'path':str(self.state/'OLD_EVIDENCE_REGISTRY.json'), 'sha256':REGISTRY_SHA256}
        rt._pin(self.registry_ref)
        self.registry = ex._read(self.registry_ref['path'])
        self.new_contract = self.registered(prepared=True)
        self.old_contract = deepcopy(self.new_contract)
        self.old_contract['code_freeze'] = PRIOR
        self.old_digest = rt.scientific_contract_sha256(self.old_contract)
        self.new_digest = rt.scientific_contract_sha256(self.new_contract)
        self.allowed, self.budgets = rt.validate_registration(self.new_contract,code_commit=self.freeze)
        self.remaining = remaining_ids(self.allowed, self.registry)
        self.adjudication = None

    def _verified_calibration(self):
        path = self.scratch/'01_CALIBRATION/CALIBRATION_SUMMARY.json'
        value = ex._read(path)
        if value['status']!='CALIBRATION_COMPLETE' or value['code_freeze']!=PRIOR:
            raise RuntimeError('HARD_STOP_T5BCR_OLD_CALIBRATION')
        for ref in value['pins']: rt._pin(ref)
        return value

    def verify_old(self):
        """Check old pins, reservations, seals, and the existing identity PASS; zero launches."""
        for ref in self.registry['controls'].values(): rt._pin(ref)
        for kind, ref in self.registry['ledgers'].items(): rt._pin(ref)
        if ex._read(self.scratch/'09_HANDOFF/EXECUTION/MATRIX_RESOLVED_CONTRACT.json') != {
                'resolved_contract_sha256':ex._digest(self.old_contract),
                'scientific_contract_sha256':self.old_digest}:
            raise RuntimeError('HARD_STOP_T5BCR_SCIENCE_CONTRACT_CHANGED')
        records = {}
        for category, filename in (('native','T5BC_NATIVE_SUMMARY.json'),('evaluations','T5BC_EVALUATION_SUMMARY.json')):
            for run_id, ref in self.registry[category].items():
                rt._pin(ref)
                record = verify_sealed_hard_stop(ref) if run_id==D57 else ex.verify_terminal(Path(ref['path']).parent,filename)
                if record['run_id']!=run_id or record['code_commit']!=PRIOR or record['contract_sha256']!=self.old_digest:
                    raise RuntimeError('HARD_STOP_T5BCR_OLD_TERMINAL_BINDING')
                if category=='native':
                    if record['run_spec_sha256']!=ex._digest(self.old_contract['registered_runs'][run_id]):
                        raise RuntimeError('HARD_STOP_T5BCR_OLD_RUN_SPEC')
                    if record['trace_open_count']!=0: raise RuntimeError('HARD_STOP_T5BCR_OLD_TRACE')
                elif record['evaluation_invoked'] and record['audit']['trace_open_count']!=1:
                    raise RuntimeError('HARD_STOP_T5BCR_OLD_EVALUATOR_TRACE')
                records[run_id] = record
        for kind, ref in self.registry['ledgers'].items():
            rows = [json.loads(line) for line in Path(ref['path']).read_text().splitlines()]
            if len(rows)!={'identity_native':2,'matrix_native':60,'evaluator':116}[kind] or len({r['run_id'] for r in rows})!=len(rows):
                raise RuntimeError('HARD_STOP_T5BCR_OLD_RESERVATIONS')
            for row in rows:
                category = 'evaluations' if kind=='evaluator' else 'native'
                ref2 = self.registry[category][row['run_id']]
                if ex._read(Path(ref2['path']).parent/'LAUNCH_RESERVATION.json')!=row or row['contract_sha256']!=self.old_digest:
                    raise RuntimeError('HARD_STOP_T5BCR_RESERVATION_BINDING')
        ex.verify_identity_receipt(self.old_contract,scratch_root=self.scratch,code_commit=PRIOR)
        old = records[D57]
        if (self.registry['native'][D57]['sha256']!=self.registry['adjudicated_summary_sha256']
                or old['status']!='HARD_STOP' or old.get('effective_echo_gate') is not None):
            raise RuntimeError('HARD_STOP_T5BCR_ADJUDICATION_SCOPE')
        root = Path(self.registry['native'][D57]['path']).parent
        evidence = rt.classify_heading_failure(root,rt._runtime_mapping((root/'T5BC_RUNTIME_CONFIG.yaml').read_bytes()),variant='B3')
        if not evidence['passed'] or evidence['classification']!=NOT_APPLICABLE:
            raise RuntimeError('HARD_STOP_T5BCR_D57_NOT_POSITIVELY_CLASSIFIED')
        self.adjudication = {'status':'APPEND_ONLY_ADJUDICATION','code_freeze':self.freeze,
            'original_summary':self.registry['native'][D57], 'original_status':'HARD_STOP',
            'classification':NOT_APPLICABLE,'evidence':evidence,'D6_effective_echo':'UNAVAILABLE_NOT_EMITTED',
            'native_invocations':0,'evaluator_invocations':0,'old_evidence_modified':False}
        ex._write_or_verify(self.state/'D57_ADJUDICATION.json',self.adjudication)
        return records

    def read_terminal(self, reference, root, filename):
        """Read-only report view preserves original provenance and terminal on disk."""
        rt._pin(reference)
        record = ex._read(reference['path'])
        run_id = record['run_id']
        old_category = 'native' if filename=='T5BC_NATIVE_SUMMARY.json' else 'evaluations'
        old_ref = self.registry[old_category].get(run_id)
        if old_ref is not None:
            if reference!=old_ref or record['code_commit']!=PRIOR or record['contract_sha256']!=self.old_digest:
                raise RuntimeError('HARD_STOP_T5BCR_REPORT_OLD_BINDING')
        elif record['code_commit']!=self.freeze or record['contract_sha256']!=self.new_digest:
            raise RuntimeError('HARD_STOP_T5BCR_REPORT_NEW_BINDING')
        if Path(reference['path'])!=root/filename:
            raise RuntimeError('HARD_STOP_T5BCR_REPORT_SLOT')
        if filename=='T5BC_NATIVE_SUMMARY.json':
            spec=self.new_contract['registered_runs'][run_id]
            if any(record[key]!=spec[key] for key in rt.IDENTITY_KEYS) or record['run_spec_sha256']!=ex._digest(spec):
                raise RuntimeError('HARD_STOP_T5BCR_REPORT_RUN_SPEC')
        if run_id==D57:
            ref = ex._reference(self.state/'D57_ADJUDICATION.json')
            adjudication = ex._read(ref['path'])
            if adjudication['original_summary']!=reference or adjudication['classification']!=NOT_APPLICABLE:
                raise RuntimeError('HARD_STOP_T5BCR_REPORT_ADJUDICATION')
            record = {**record,'status':NOT_APPLICABLE,'failure_classification':NOT_APPLICABLE,
                'historical_runtime_status':'HARD_STOP','adjudication':ref,'effective_echo_status':'UNAVAILABLE_NOT_EMITTED'}
        return record

    def _checkpoint_new(self,label):
        self._checkpoint()
        receipt = {**self.git_receipt,'scientific_contract_sha256':self.new_digest,
                   'resolved_contract_sha256':ex._digest(self.new_contract)}
        pins = ex._protected_pins(self.new_contract,self.contexts,self.evaluator,receipt)
        for path,digest in pins.items(): rt._pin({'path':str(path),'sha256':digest})
        return ex._write_or_verify(self.state/'CHECKPOINTS'/f'{label}.json',
            {'status':'PASS','code_freeze':self.freeze,'pins':{str(k):v for k,v in pins.items()}})

    def execute_remaining(self):
        hard = self.state/'CONTROLLER_HARD_STOP.json'
        if hard.exists(): raise RuntimeError('HARD_STOP_T5BCR_NO_AUTOMATIC_RETRY')
        with (self.state/'CONTROLLER.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            try:
                self.verify_old()
                checkpoints = {'PRE':self._checkpoint_new('PRE')}
                ex._write_or_verify(self.state/'CODE_FREEZE_RECEIPT.json',self.git_receipt)
                ex._write_or_verify(self.state/'RESOLVED_CONTRACT.json',self.new_contract)
                nrefs = dict(self.registry['native']); erefs = dict(self.registry['evaluations'])
                new_native = new_eval = 0
                statuses = Counter()
                pending = {}
                def archive(relative):
                    value = ex.archive_tree_bounded(self.scratch/relative,self.archive/relative,audit_root=self.state/'ARCHIVE_IO')
                    if value['status']!='ARCHIVE_VERIFIED': pending[relative]=value
                    else: pending.pop(relative,None)
                def ledger_count(kind):
                    path=self.state/'LAUNCH_LEDGERS'/f'{kind}.jsonl'
                    rows=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
                    maximum=199 if kind=='matrix_native' else 398
                    if len(rows)>maximum or len({r['run_id'] for r in rows})!=len(rows):
                        raise RuntimeError('HARD_STOP_T5BCR_REMAINING_BUDGET')
                    for r in rows:
                        rid=r['run_id'] if kind=='matrix_native' else r['run_id'].rsplit('__',1)[0]
                        if rid not in self.remaining or r['contract_sha256']!=self.new_digest:
                            raise RuntimeError('HARD_STOP_T5BCR_OLD_SLOT_RELAUNCH')
                    return len(rows)
                for seq in ('BY2','BY2H','BY2O'):
                    for run_id in sorted(self.allowed['matrix_native']):
                        spec=self.new_contract['registered_runs'][run_id]
                        if spec['sequence_id']!=seq: continue
                        root=self.scratch/spec['output_relpath']
                        if run_id in self.registry['native']:
                            record=self.read_terminal(nrefs[run_id],root,'T5BC_NATIVE_SUMMARY.json')
                            record['native_summary']=nrefs[run_id]
                        else:
                            if root.exists():
                                record=ex.verify_terminal(root,'T5BC_NATIVE_SUMMARY.json')
                                self.read_terminal(record['native_summary'],root,'T5BC_NATIVE_SUMMARY.json')
                            else:
                                if ledger_count('matrix_native')>=199: raise RuntimeError('HARD_STOP_T5BCR_NATIVE_BUDGET')
                                print('T5bc-R native START '+run_id,flush=True)
                                record=rt.run_native(self.contexts[seq],contract=self.new_contract,run_spec=spec,
                                    output_root=root,scratch_root=self.scratch,code_commit=self.freeze,
                                    launch_ledger=self.state/'LAUNCH_LEDGERS/matrix_native.jsonl')
                            nrefs[run_id]=record['native_summary'];new_native+=1
                            archive(spec['output_relpath'])
                        statuses[record['status']]+=1
                        for version in ('v3','v2'):
                            eid=run_id+'__'+version
                            if eid in self.registry['evaluations']:continue
                            eroot=self.scratch/'06_EVAL'/version/run_id
                            if eroot.exists():
                                value=ex.verify_terminal(eroot,'T5BC_EVALUATION_SUMMARY.json')
                                self.read_terminal(value['evaluation_summary'],eroot,'T5BC_EVALUATION_SUMMARY.json')
                            elif record['status']=='COMPLETED':
                                if run_id not in self.remaining or ledger_count('evaluator')>=398:
                                    raise RuntimeError('HARD_STOP_T5BCR_EVALUATOR_BUDGET')
                                value=rt.evaluate_native(self.contexts[seq],self.evaluator['path'],contract=self.new_contract,
                                    run_spec=spec,native_summary=record,version=version,output_root=eroot,
                                    scratch_root=self.scratch,code_commit=self.freeze,
                                    launch_ledger=self.state/'LAUNCH_LEDGERS/evaluator.jsonl')
                            else:
                                eroot.mkdir(parents=True,exist_ok=False)
                                status='NOT_APPLICABLE' if record['status']==NOT_APPLICABLE else 'NOT_RUN_ALGORITHM_FAILURE'
                                row={**{k:spec[k] for k in rt.IDENTITY_KEYS},**spec['data_roles'],
                                    'code_commit':self.freeze,'status':status,'evaluation_status':status,
                                    'failure_classification':record['failure_classification'],
                                    'evaluator_contract':'evaluator_contract_'+version,'metrics_admitted':False,
                                    'reason':record['status'],**rt.PROVENANCE_FLAGS}
                                value=rt._seal(eroot,{'status':status,'run_id':eid,'code_commit':self.freeze,
                                    'contract_sha256':self.new_digest,'native_summary':record['native_summary'],
                                    'evaluation_invoked':False,'row':row},filename='T5BC_EVALUATION_SUMMARY.json')
                            if value['evaluation_invoked']:new_eval+=1
                            erefs[eid]=value['evaluation_summary']
                            archive('06_EVAL/'+version+'/'+run_id)
                        print(f'T5bc-R {run_id} {record["status"]} continuation={new_native}/199 evaluator={ledger_count("evaluator")}/398',flush=True)
                    checkpoints[seq+'_POST']=self._checkpoint_new(seq+'_POST')
                if new_native!=199 or ledger_count('matrix_native')!=199 or ledger_count('evaluator')!=new_eval:
                    raise RuntimeError('HARD_STOP_T5BCR_FINAL_COUNTS')
                self.verify_old()
                for relative in list(pending): archive(relative)
                batches=[ex._read(p) for p in (self.state/'ARCHIVE_IO').glob('BATCH_*.json')]
                attempted=sum(row['attempted_file_count'] for row in batches)
                failed=sum(row['failed_file_count'] for row in batches)
                summary={'status':'COMPLETE_REGISTERED_EXECUTION_ARCHIVE_PENDING' if pending else 'COMPLETE_REGISTERED_EXECUTION','code_freeze':self.freeze,
                    'original_code_freeze':PRIOR,'contract_sha256':self.new_digest,
                    'original_contract_sha256':self.old_digest,'registry':self.registry_ref,
                    'native_terminals':nrefs,'evaluation_terminals':erefs,'checkpoints':checkpoints,
                    'budget_reserved':{'identity_native':2,'matrix_native':259,'evaluator':116+new_eval},
                    'budget_authorized':self.budgets,'continuation_native':199,'continuation_evaluator':new_eval,
                    'native_status_counts':dict(statuses),'trace_open_count_native':0,
                    'trace_open_count_evaluator':116+new_eval,'retry_count':0,'archive_pending':pending,
                    'data_mode':'mixed_registered_frozen_data_modes','synthetic_data_used':False,
                    'semisynthetic_data_used':True,'historical_hard_stop_preserved':True,
                    'archive_attempted_file_count':attempted,'archive_failed_file_count':failed,
                    'archive_failure_fraction':failed/attempted if attempted else 0,
                    'not_applicable_excluded_from_algorithm_failures':True}
                ex._write_or_verify(self.execution_summary_path,summary)
                archive('09_HANDOFF/CONTINUATION_R')
                return summary
            except Exception as error:
                if not hard.exists(): rt._write(hard,{'status':'HARD_STOP','error':str(error),'code_freeze':self.freeze,'automatic_retry':False})
                raise
