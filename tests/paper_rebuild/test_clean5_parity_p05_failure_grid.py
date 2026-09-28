"""Mock early gates: all nine cells recorded without evaluator calls."""
import csv
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from legsa_gins.paper_rebuild.clean5_parity_p05 import runner as rr
from legsa_gins.paper_rebuild.clean5_parity_p05.runtime import GRID

@pytest.mark.parametrize('failure',['FAILED_NATIVE_SOLVER','FAILED_ORIGIN_IDENTITY_GATE_EXCEPTION','POST_CHECKPOINT'])
def test_solver_origin_checkpoint_failure_reports_nine_unavailable_cells(tmp_path,monkeypatch,failure):
    code=tmp_path/'code';cfg=code/'configs/paper_rebuild/clean5';cfg.mkdir(parents=True)
    exe=tmp_path/'exe';exe.write_text('not executed');sha=rr.sha256_file(exe)
    bundle=tmp_path/'bundle.json';bundle.write_text(json.dumps({'baseline_median_m':.3}))
    stage=tmp_path/'stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/13_NOISE_MODEL_SENSITIVITY'
    spec={'cells':[{'cell_id':f'N{i:02d}','abstd_mGal':a,'vrw_mps_sqrt_hour':v} for i,(a,v) in enumerate(GRID)],'executable_sha256':sha,
          'stage_root':str(stage),'provider_bundle':{},'source_pins':[],'evaluator':{},'trace':{},'baseline_median_m':.3}
    (cfg/'CLEAN5_PARITY_P05_CONTRACT.yaml').write_text(yaml.safe_dump({'p05':spec}))
    registry=SimpleNamespace(code_root=code,clean_root=tmp_path,raw_root=tmp_path)
    monkeypatch.setattr(rr,'EXE_SHA',sha);monkeypatch.setattr(rr,'load_registry',lambda *a:registry)
    monkeypatch.setattr(rr,'replace',lambda r,**kw:r);monkeypatch.setattr(rr,'execution_state',lambda *a:{})
    monkeypatch.setattr(rr,'pinned',lambda *a:bundle);monkeypatch.setattr(rr,'verify_bundle',lambda *a:None)
    monkeypatch.setattr(rr,'validate_seal',lambda *a:{})
    calls=[]
    monkeypatch.setattr(rr,'evaluate_grid',lambda **kw:calls.append('forbidden evaluation'))
    def checkpoint(*args):
        if args[-1]=='post_run' and failure=='POST_CHECKPOINT':raise RuntimeError('post checkpoint gate failure')
        return {'pass':True}
    monkeypatch.setattr(rr,'checkpoint',checkpoint)
    def run(**kw):
        record={'variant_id':'N00','terminal_status':failure if failure!='POST_CHECKPOINT' else 'COMPLETED'}
        seal=stage/'04_PARITY_SEAL';seal.mkdir()
        (seal/'PARITY_OUTPUT_SEAL.json').write_text(json.dumps({'records':[record]}))
        return [record]
    monkeypatch.setattr(rr,'run_ladder',run)
    with pytest.raises(RuntimeError):rr.main(['--code-root',str(code),'--paths-config',str(tmp_path/'local'),'--executable',str(exe),'--code-freeze-commit','test_fixture'])
    assert calls==[]
    for version in ['v2','v3']:
        target=stage/'08_AGGREGATE' if version=='v2' else stage/'08_AGGREGATE/v3'
        rows=list(csv.DictReader((target/'SENSITIVITY_GRID.csv').open()))
        assert len(rows)==9 and all(r['evaluation_status']=='UNAVAILABLE' for r in rows)
        assert all(r['up_rmse_m']=='UNAVAILABLE' and r['evaluation_invoked'].lower()=='false' for r in rows)
        assert all(r['solver_terminal_status']=='NOT_EXECUTED' for r in rows[1:])
    receipt=json.loads((stage/'P05_FAILURE.json').read_text())
    assert receipt['failure_grid']['evaluator_invocation_count_from_receipts']==0
    assert receipt['failure_grid']['record_source'].endswith('PARITY_OUTPUT_SEAL.json')


def test_failure_grid_never_overwrites_existing_results(tmp_path):
    target=tmp_path/'08_AGGREGATE';target.mkdir();existing=target/'SENSITIVITY_GRID.csv';existing.write_bytes(b'existing evidence\n')
    contract={'p05':{'cells':[{'cell_id':f'N{i:02d}','abstd_mGal':a,'vrw_mps_sqrt_hour':v} for i,(a,v) in enumerate(GRID)]}}
    result=rr.failure_grid(stage=tmp_path,contract=contract,records=[],code_commit='mock',reason='injected')
    assert existing.read_bytes()==b'existing evidence\n'
    assert str(existing) in result['preserved_tables']
