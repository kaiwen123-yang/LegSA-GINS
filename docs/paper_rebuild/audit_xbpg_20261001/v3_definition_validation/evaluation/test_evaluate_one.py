#!/usr/bin/env python3
"""Synthetic helper/contract checks only; never call run_one or frozen evaluation."""
import ast
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('evaluation_singleton_helpers',HERE/'evaluate_one.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
checks=[]


def check(name,ok):
    checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL'))


def refuses(name,call):
    try:call()
    except (ValueError,FileExistsError):check(name,True)
    else:check(name,False)


def main():
    for filename in ('SYNTHETIC_CHECKS.csv','SYNTHETIC_TEST_RECEIPT.json'):
        if (HERE/filename).exists():raise RuntimeError('retain prior test artifacts explicitly before a new test process')
    import numpy as np
    import pandas as pd
    for name,a,b,kind,status in [
        ('metric_equal','2.25',2.25,'numeric','MATCH'),
        ('metric_within_fixed_tolerance','2.25',2.25+1e-10,'numeric','MATCH'),
        ('metric_outside_fixed_tolerance','2.25',2.25+1e-8,'numeric','MISMATCH'),
        ('zero_absolute_tolerance','0.0',5e-11,'numeric','MATCH'),
        ('time_within_1ns','200',200+5e-10,'time','MATCH'),
        ('time_outside_1ns','200',200+2e-9,'time','MISMATCH'),
        ('count_exact',4,4,'exact','MATCH'),
        ('count_no_float_coercion',4,4.,'exact','MISMATCH'),
        ('boolean_not_integer',False,0,'exact','MISMATCH'),
        ('missing_not_zero',None,0,'numeric','MISSING_VALUE'),
        ('two_missing_explicit',None,None,'numeric','MATCH_NULL'),
        ('nan_not_pass','1',float('nan'),'numeric','NONFINITE_NOT_COMPARABLE')]:
        check(name,mod.field_check(name,a,b,kind)['status']==status)
    good={'audit':{'passed':True,'exit_code':0,'trace_open_count':1,'raw_open_count':1,
          'instrumented':True,'trace_read_role':'archived_evaluator_child_only','bag_open_count':0,'fpl_open_count':0,'write_scope':{'pass':True}},
          'capture':{'trace_handle_hash_count':1,'trace_sha256':mod.TRACE_SHA,'evaluator_sha256':mod.EVALUATOR_SHA,
          'selected_columns':dict(mod.SELECTED),'window':list(mod.WINDOW),'consistency':{
          'passed':True,'policy':mod.POLICY,'position_threshold_m':.01,'yaw_threshold_deg':.01,
          'time_offset_applied':0.,'observation_only':True}},'process_resources':{'status':'AVAILABLE'}}
    check('all_evaluator_gates_accept_valid_synthetic_receipt',all(mod.gate_result(good).values()))
    for path,value,key in [
        (('audit','passed'),False,'audit_passed'),(('audit','exit_code'),1,'exit_zero'),
        (('audit','trace_open_count'),2,'one_reference_open'),(('audit','raw_open_count'),2,'one_raw_reference_only'),
        (('audit','instrumented'),False,'instrumented_child_role'),(('audit','bag_open_count'),1,'no_bag_fpl'),
        (('audit','write_scope','pass'),False,'write_scope'),(('capture','trace_handle_hash_count'),0,'same_handle_hash'),
        (('capture','evaluator_sha256'),'bad','capture_evaluator_identity'),(('capture','selected_columns'),{},'selected_columns'),
        (('capture','window'),[66.,341.],'fixed_window'),(('capture','consistency','passed'),False,'D12_passed'),
        (('capture','consistency','policy'),'other','D12_policy'),(('capture','consistency','position_threshold_m'),.1,'D12_fixed_thresholds'),
        (('capture','consistency','time_offset_applied'),1.,'D12_no_offset'),(('capture','consistency','observation_only'),False,'D12_observation_only'),
        (('process_resources','status'),'UNAVAILABLE','resources_available')]:
        altered=copy.deepcopy(good);target=altered
        for part in path[:-1]:target=target[part]
        target[path[-1]]=value
        check('refuse_'+key,mod.gate_result(altered)[key] is False)
    with tempfile.TemporaryDirectory(prefix='.singleton_fixture_',dir=HERE) as name:
        tmp=Path(name);roots={'<FIXTURE>':name}
        check('alias_resolves',mod.resolve('<FIXTURE>/out',roots)==tmp/'out')
        refuses('refuse_parent_traversal',lambda:mod.resolve('<FIXTURE>/../out',roots))
        refuses('refuse_unregistered_absolute',lambda:mod.resolve('/fixture/out',roots))
        (tmp/'real').mkdir();(tmp/'link').symlink_to(tmp/'real',target_is_directory=True)
        refuses('refuse_symlink_parent',lambda:mod.resolve('<FIXTURE>/link/out',roots))
        once=tmp/'exclusive.json';mod.write_json(once,{'first':True})
        refuses('refuse_output_overwrite',lambda:mod.write_json(once,{'second':True}))
        check('first_output_preserved',json.loads(once.read_text())=={'first':True})
        fake=tmp/'strace';evaluator=Path('/fixture/evaluate.py')
        fake.write_text('1 execve("/usr/bin/time", ["time", "python3", "/fixture/evaluate.py"], []) = 0\n'
                        '2 execve("/bad/python3", ["python3", "/fixture/evaluate.py"], []) = -1 ENOENT\n'
                        '2 execve("/usr/bin/python3", ["python3", "/fixture/evaluate.py"], []) = 0\n')
        check('exec_counter_one_actual_python_not_time_or_failed_exec',mod.actual_child_count(fake,evaluator)==1)
        check('missing_strace_unknown',mod.actual_child_count(tmp/'absent',evaluator)=='UNKNOWN')
        item={'original_config_sha256':'config','baseline_run_id':'RUN_TEST'}
        ready={'candidate_id':'N09_RP_ONLY','native_tests_passed':True,'binary_sha256':'a'*64}
        native={'status':'COMPLETED','exit_code':0,'access_passed':True,'native_exec_count':'1',
            'config_sha256':'config','candidate_id':'N09_RP_ONLY','baseline_run_id':'RUN_TEST',
            'binary_sha256':'a'*64,'ready_sha256':'ready_pin',
            'data_role_manifest_check':{str(i):{'present':True,'same':True} for i in range(99)},
            'output_hashes':[{'filename':'NAV','candidate_sha256':'nav'}]}
        receipt_path=tmp/'CANDIDATE_RECEIPT.json';receipt_path.write_text(json.dumps(native))
        check('candidate_closed_native_receipt',mod.native_gate(tmp,item,'N09_RP_ONLY',ready,'ready_pin')[1]=={'NAV':'nav'})
        for key,value in [('status','COMPLETED_REVIEW_REQUIRED'),('exit_code',1),('access_passed',False),
                          ('native_exec_count','2'),('config_sha256','other'),('candidate_id','N12_ONLY'),('baseline_run_id','OTHER'),
                          ('binary_sha256','b'*64),('ready_sha256','other'),('data_role_manifest_check',{})]:
            bad={**native,key:value};receipt_path.write_text(json.dumps(bad))
            refuses('native_refuse_'+key,lambda:mod.native_gate(tmp,item,'N09_RP_ONLY',ready,'ready_pin'))
        for flag in ('present','same'):
            bad=copy.deepcopy(native);bad['data_role_manifest_check']['0'][flag]=False;receipt_path.write_text(json.dumps(bad))
            refuses('native_refuse_role_'+flag,lambda:mod.native_gate(tmp,item,'N09_RP_ONLY',ready,'ready_pin'))
        bad=copy.deepcopy(native);bad['data_role_manifest_check'].pop('0');receipt_path.write_text(json.dumps(bad))
        refuses('native_refuse_role_count_98',lambda:mod.native_gate(tmp,item,'N09_RP_ONLY',ready,'ready_pin'))
        receipt_path.write_text(json.dumps(native))
        refuses('native_refuse_missing_READY',lambda:mod.native_gate(tmp,item,'N09_RP_ONLY'))
        refuses('native_refuse_unpassed_READY',lambda:mod.native_gate(tmp,item,'N09_RP_ONLY',{**ready,'native_tests_passed':False},'ready_pin'))
        baseline={**native,'status':'COMPLETED_BYTE_IDENTICAL','binary_sha256':mod.BASELINE_BINARY_SHA,
            'output_comparisons':[{'filename':'NAV','replay_sha256':'nav'}]}
        baseline_path=tmp/'REPLAY_RECEIPT.json';baseline_path.write_text(json.dumps(baseline))
        check('baseline_fixed_binary_pass',mod.native_gate(tmp,item,'BASELINE')[1]=={'NAV':'nav'})
        baseline['binary_sha256']='c'*64;baseline_path.write_text(json.dumps(baseline))
        refuses('baseline_wrong_binary_refused',lambda:mod.native_gate(tmp,item,'BASELINE'))
    queue=list(csv.DictReader((HERE.parent/'CANDIDATE_QUEUE.csv').open()))
    manifest=list(csv.DictReader((HERE/'EVAL_MANIFEST.csv').open()))
    slot='BASELINE__RUN_00004'
    check('complete_17_slot_manifest_accepts',mod.validate_manifest(queue,manifest,slot)['slot_id']==slot)
    refuses('manifest_missing_slot_refused',lambda:mod.validate_manifest(queue,manifest[:-1],slot))
    refuses('manifest_duplicate_slot_refused',lambda:mod.validate_manifest(queue,manifest[:-1]+[manifest[0]],slot))
    for field,value in [('status','STARTED'),('evaluator_invocation_attempts','1'),('evaluator_child_execs','UNKNOWN'),('method_id','wrong')]:
        bad=copy.deepcopy(manifest);row=next(r for r in bad if r['slot_id']==slot);row[field]=value
        refuses('manifest_refuse_'+field,lambda:mod.validate_manifest(queue,bad,slot))
    times=np.array([66.,196.199,196.2,216.199,216.2,340.])
    errors=pd.DataFrame({'time':times});nav=np.zeros((6,11));nav[:,1]=times
    masks=[]
    def fake_metrics(err,native,identity,window,reference_count):
        masks.append((err.time.tolist(),native[:,1].tolist(),reference_count))
        return dict(identity,matched_epoch_count=len(err),output_epoch_count=len(native))
    views=mod.window_views(fake_metrics,errors,nav,{},'A1')
    check('fixed_half_open_masks',[(v['window'],v['matched_epoch_count']) for v in views]==[('before',2),('fault',2),('after',2)])
    check('matched_and_nav_masks_identical',all(a==b for a,b,_ in masks))
    check('segment_reference_counts_unknown',all(r is None for _,_,r in masks))
    check('C00_no_invented_fault_window',mod.window_views(fake_metrics,errors,nav,{},'C00')==[])
    finite=mod.numeric_diagnostics(np,nav,np.ones((6,4)))
    check('native_all_columns_checked',len(finite)==15 and all(r['nonfinite_count']==0 for r in finite))
    nav[2,6]=np.nan
    finite=mod.numeric_diagnostics(np,nav,np.ones((6,4)))
    check('nonfinite_not_deleted',finite[6]['nonfinite_count']==1 and finite[6]['count']==6 and finite[6]['minimum'] is None)
    tree=ast.parse((HERE/'evaluate_one.py').read_text())
    eval_calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='evaluate']
    check('single_frozen_evaluate_call_site',len(eval_calls)==1)
    keywords={k.arg for k in eval_calls[0].keywords}
    check('no_outage_argument',not any('outage' in k for k in keywords))
    check('export_matched_truth_explicit_false',any(k.arg=='export_matched_truth' and isinstance(k.value,ast.Constant) and k.value.value is False for k in eval_calls[0].keywords))
    check('no_Context_constructor',not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Context' for n in ast.walk(tree)))
    check('import_did_not_import_project',not any(k.startswith('legsa_gins') for k in sys.modules))
    with (HERE/'SYNTHETIC_CHECKS.csv').open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=['check','status'],lineterminator='\n');w.writeheader();w.writerows(checks)
    receipt={'status':'PASS' if all(r['status']=='PASS' for r in checks) else 'FAIL',
        'checks':len(checks),'passed':sum(r['status']=='PASS' for r in checks),'new_test_script_processes':1,
        'test_invocation':2,'prior_test_receipt':'test_history/SYNTHETIC_TEST_RECEIPT_001.json',
        'cumulative_test_script_processes':2,'cumulative_failed_test_processes':0,
        'native_fixture_processes':0,'real_native_calls':0,'evaluator_calls':0,'mock_evaluator_calls':0,
        'reference_payload_reads':0,'source_NAV_STD_payload_reads':0,'frozen_metric_function_calls':0,
        'synthetic_data_used':True,'semisynthetic_data_used':False,'data_mode':'synthetic_helper_validation_only',
        'script_sha256':hashlib.sha256((HERE/'evaluate_one.py').read_bytes()).hexdigest(),
        'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits':'Helper and source-contract checks only; no whole evaluator invocation or scientific agreement assertion.'}
    (HERE/'SYNTHETIC_TEST_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt));return 0 if receipt['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
