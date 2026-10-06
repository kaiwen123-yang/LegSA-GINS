"""Read-only all-nine saved-payload compatibility audit; no solver/eval/rawGT."""
from pathlib import Path
import csv,gzip,hashlib,json,math,datetime,sys,xml.etree.ElementTree as ET
import numpy as np
CODE=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
ROOT=Path('/mnt/g/LegSA-GINS-project/修复_20261004')
OLD=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/EXT_REPRODUCTION_V2_TECH_RETRY_2_20261004T054256Z')
CLAIM=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/IMU_V3_CLAIM_SUBSET_20261004T064538Z')
sys.path.insert(0,str(CODE/'src'))
from legsa_gins.paper_rebuild.horizontal_literature import ext01_clambda as cl
from legsa_gins.paper_rebuild.horizontal_literature import ext03_yang2024 as yang

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as s:
        for b in iter(lambda:s.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def put(p,d):
    with p.open('x') as s:json.dump(d,s,ensure_ascii=False,indent=2);s.write('\n')
change_path=ROOT/'EXT_HEADING_POST_RESULT_SOURCE_CHANGE.json'
change=json.loads(change_path.read_text());new=change['new_sources'];old=change['old_sources']
assert all(sha(CODE/k)==v for k,v in new.items())
red=ET.parse(ROOT/'EXT_HEADING_GUARD_RED.xml').getroot().find('testsuite')
green=ET.parse(ROOT/'EXT_HEADING_BOUNDED_REGRESSION.xml').getroot().find('testsuite')
assert int(red.attrib['tests'])==19 and int(red.attrib['failures'])==11
assert int(green.attrib['tests'])==75 and int(green.attrib['failures'])==0 and int(green.attrib['errors'])==0 and int(green.attrib['skipped'])==0
runrows=[];pins={};total=valid=internal=invalid=0;min_h=math.inf;min_fraction=math.inf;max_error=0.;triggered=[]
for run in sorted((OLD/'runs').iterdir()):
    manifest=run/'RUN.json';m=json.loads(manifest.read_text());rid=run.name
    assert sha(manifest)==change['old_nine_runs'][rid]['manifest_sha256']
    pins[str(manifest)]=sha(manifest)
    for relative,pin in m['source_snapshot_hashes'].items():
        snap=run/'SOURCE_SNAPSHOT'/relative
        assert sha(snap)==pin
        pins[str(snap)]=pin
    for relative,pin in old.items():assert m['source_hashes'][relative]==pin
    for name,spec in m['outputs'].items():
        f=run/name;assert f.stat().st_size==spec['bytes'] and sha(f)==spec['sha256'];pins[str(f)]=spec['sha256']
    count=ok=extra=bad=0;rh=math.inf;rf=math.inf;delta=0.;nobaseline=0
    with gzip.open(run/'EPOCH_EVIDENCE.jsonl.gz','rt') as stream:
        for raw in stream:
            d=json.loads(raw);assert d['epoch_index']==count;count+=1
            if not d['valid']:
                bad+=1;assert d['body_yaw_deg'] is None
                if d.get('baseline_ned_m') is None:nobaseline+=1
                continue
            ok+=1;baseline=np.asarray(d['baseline_ned_m'],float)
            assert baseline.shape==(3,) and np.isfinite(baseline).all()
            scale=float(np.max(np.abs(baseline)));n=baseline/scale
            fraction=float((n[0]**2+n[1]**2)/np.dot(n,n))
            rh=min(rh,math.hypot(float(baseline[0]),float(baseline[1])));rf=min(rf,fraction)
            predicted=(yang.ned_attitude(baseline).body_yaw_deg if m['method']=='EXT03' else cl.body_yaw_from_ned_baseline(baseline))
            diff=abs(float(predicted)-float(d['body_yaw_deg']));delta=max(delta,diff)
            assert diff<=1e-12
            if m['method']=='EXT03':
                for key,attkey in [('float_baseline_ned_m','float_attitude'),('fixed_baseline_ned_m','fixed_attitude')]:
                    if d.get(key) is not None:
                        extra+=1;att=yang.ned_attitude(d[key]);saved=d[attkey]
                        assert att.baseline_heading_deg==saved['baseline_heading_deg']
                        assert att.body_yaw_deg==saved['body_yaw_deg']
                        assert att.pitch_deg==saved['pitch_deg']
    assert count==m['completed_epochs']==m['planned_paired_epochs'] and ok==m['valid_epochs']
    assert nobaseline==bad
    runrows.append({'run_id':rid,'sequence':m['sequence'],'method':m['method'],'all_payload_records':count,'valid_published_baselines':ok,'invalid_records_no_published_baseline':bad,'additional_EXT03_float_fixed_attitudes_checked':extra,'heading_guard_triggered_on_valid':0,'min_horizontal_m':rh,'min_dimensionless_horizontal_fraction_squared':rf,'max_saved_new_heading_abs_difference_deg':delta,'all_old_source_snapshot_and_output_pins_unchanged':True})
    total+=count;valid+=ok;invalid+=bad;internal+=extra;min_h=min(min_h,rh);min_fraction=min(min_fraction,rf);max_error=max(max_error,delta)
assert len(runrows)==9 and total==15669 and valid==9100 and invalid==6569
assert all(sha(Path(p))==v for p,v in pins.items())
assert all(sha(CODE/k)==v for k,v in new.items())
pr=json.loads((CLAIM/'PREREGISTRATION.json').read_text());diffs=[]
for relative,pin in pr['source_snapshot_sha256'].items():
    assert sha(CLAIM/'SOURCE_SNAPSHOT'/relative)==pin
    current=sha(CODE/relative)
    if current!=pin:diffs.append({'path':relative,'accepted_claim_snapshot_sha256':pin,'post_result_current_sha256':current})
assert {d['path'] for d in diffs}==set(new) and len(diffs)==3
with (ROOT/'EXT_HEADING_POST_RESULT_PAYLOAD_COMPATIBILITY.csv').open('x',newline='') as s:
    w=csv.DictWriter(s,fieldnames=list(runrows[0]));w.writeheader();w.writerows(runrows)
result={'schema':'ext_projected_heading_post_result_repair.v1','captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_checks_passed':True,'scope':'POST_RESULT_SOURCE_REPAIR; never rerun old9EXT or135claim; no execution identity rebound','source_freeze_release_receipt_sha256':change['source_freeze_release_receipt_sha256'],'old_executed_source_pins':old,'new_post_result_source_pins':new,'source_change_receipt_sha256':sha(change_path),'tests':{'red_tests':19,'red_failures':11,'green_new_boundary_tests':19,'full_bounded_regression_tests':75,'green_failures':0,'green_skipped':0,'red_xml_sha256':sha(ROOT/'EXT_HEADING_GUARD_RED.xml'),'green_xml_sha256':sha(ROOT/'EXT_HEADING_GUARD_GREEN.xml'),'bounded_xml_sha256':sha(ROOT/'EXT_HEADING_BOUNDED_REGRESSION.xml'),'test_source_sha256':sha(CODE/'tests/paper_rebuild/test_ext_projected_heading_guard.py')},'raw_selected_saved_payload_machine_audit':True,'semantic_full_read_of15669_claim':False,'all_payload_records':total,'valid_published_baselines':valid,'invalid_records_without_published_baseline':invalid,'additional_EXT03_float_fixed_attitudes_checked':internal,'valid_payload_heading_guard_trigger_count':0,'min_published_horizontal_m':min_h,'min_published_dimensionless_horizontal_fraction_squared':min_fraction,'fixed_dimensionless_threshold_squared':cl.MIN_HORIZONTAL_PROJECTION_FRACTION_SQUARED,'max_saved_new_heading_abs_difference_deg':max_error,'old_nine_runs_manifest_snapshot_heading_and_epoch_pins_before_after_unchanged':True,'claim928_saved_snapshot_remains_exact':True,'claim928_current_intentional_delta':diffs,'old_completed_run_source_pins_not_rewritten':True,'solver_calls':0,'evaluator_calls':0,'raw_reference_open_count':0,'audit_helper_sha256':sha(Path(__file__)),'payload_csv_sha256':sha(ROOT/'EXT_HEADING_POST_RESULT_PAYLOAD_COMPATIBILITY.csv'),'run_checks':runrows,'old_readonly_asset_pins_before_after':pins,'interpretation':{'quantity':'Fixed lateral projected-baseline heading; generally not Euler yaw at nonzero roll/pitch','gate':'rho_squared=(b_N^2+b_E^2)/||b||^2 dimensionless, not actual baseline metres squared; zero mathematically undefined, <=1e-12 rejected as numerical near-singularity only','accuracy':'No independently calibrated practical heading threshold or uncertainty established; positive projection/fixed ambiguities/std do not prove practical accuracy','failure':'Independent runner heading conversion failure returns valid=false, solution_state=INVALID and body_yaw=null, preserving candidate/certificate/computed3D baseline; EXT03 existing fail-closed adapter remains','nontrigger_scope':'All9100 published valid final baselines and every additional published EXT03 float/fixed attitude were passed through new pure conversion functions and matched saved angles. All15669 payloads enumerated;6569 old invalid rows have no published current baseline, so this does not establish counterfactual internal computation of failed epochs under a new solver run. No old metadata/metric/result/sourcepins changed.'}}
put(ROOT/'EXT_HEADING_POST_RESULT_REPAIR_RECEIPT.json',result)
print(json.dumps({k:result[k] for k in ('all_checks_passed','all_payload_records','valid_published_baselines','additional_EXT03_float_fixed_attitudes_checked','valid_payload_heading_guard_trigger_count','min_published_horizontal_m','min_published_dimensionless_horizontal_fraction_squared','max_saved_new_heading_abs_difference_deg')},indent=2))