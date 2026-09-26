"""The R2 scientific identity gate uses exact bytes and exact numeric values."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[2]/'scripts/paper_rebuild/hx03r2_execute.py'
spec = importlib.util.spec_from_file_location('hx03r2_gate_test', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_raw_output_whitespace_change_fails_byte_gate(tmp_path):
    summary=tmp_path/'summary.json';errors=tmp_path/'error_series.csv'
    summary.write_bytes(b'{"rmse": 1.0}\n');errors.write_bytes(b'time,error\n0,1\n')
    a,b=module.sha(summary),module.sha(errors)
    assert module.science_identity(a,b,summary,errors)['passed']
    summary.write_bytes(b'{"rmse":1.0}\n')
    assert not module.science_identity(a,b,summary,errors)['passed']


def test_numeric_gate_rejects_tiny_change_but_ignores_audit_status():
    old={'yaw_rmse_deg':1.0,'horizontal_rmse_m':2.0,'status':'COMPLETED'}
    assert module.numeric_identity(old,{**old,'status':'NEW_AUDIT'})['passed']
    result=module.numeric_identity(old,{**old,'yaw_rmse_deg':1.0+1e-14})
    assert not result['passed'] and 'yaw_rmse_deg' in result['differences']


def test_only_proven_preexec_failure_is_excluded_from_call_budget():
    c=module.Controller.__new__(module.Controller)
    c.events=[{'event':'RESERVED'},{'event':'HARD_STOP'}]
    assert c.call_count()==1
    c.events.append({'event':'PREEXEC_NOT_STARTED'})
    assert c.call_count()==0
    c.events.append({'event':'RESERVED'})
    assert c.call_count()==1
