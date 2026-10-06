"""Unknown trace opens must never turn into zero in partial handoff accounting."""
import importlib.util
import json
from pathlib import Path


def test_failed_reserved_slots_preserve_unknown_trace_counts(tmp_path):
    path=Path(__file__).parents[2]/'scripts/paper_rebuild/t5a_finalize.py'
    spec=importlib.util.spec_from_file_location('t5a_finalize',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    ledgers={'NATIVE':[{'run_id':'BY2__F02__R1'},{'run_id':'BY2__F02__R5'}],
             'EVALUATOR':[{'run_id':'BY2__F02__R1__v3'}]}
    p=tmp_path/'03_NATIVE/BY2/F02/R1/NATIVE_ACCESS_AUDIT.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'trace_open_count':0}))
    result=m.trace_accounting(tmp_path,ledgers)
    assert result['NATIVE']['trace_open_count']=='UNAVAILABLE'
    assert result['NATIVE']['known_open_count']==0 and result['NATIVE']['unknown_slots']==1
    assert result['EVALUATOR']['trace_open_count']=='UNAVAILABLE'
    p=tmp_path/'03_NATIVE/BY2/F02/R5/NATIVE_ACCESS_AUDIT.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'trace_open_count':2}))
    result=m.trace_accounting(tmp_path,ledgers)
    assert result['NATIVE']['trace_open_count']==2
    assert result['EVALUATOR']['unknown_slots']==1
