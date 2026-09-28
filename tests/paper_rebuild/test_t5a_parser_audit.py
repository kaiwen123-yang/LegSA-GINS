"""A0 synthetic runtime metadata; no real provider, NAV or trace access."""
import csv
import hashlib
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.hext.t5a_parser_audit import run_parser_audit


FREEZE='a'*40


def sha(payload):return hashlib.sha256(payload).hexdigest()


def retained(root,run,config,echo,*,outside=False,receipt=True,bad_receipt=False):
    stage=root.parent/'REUSED_V2' if outside else root
    attempt=stage/'RETAINED_RUNS'/run/'attempt'
    solver=attempt/'solver';solver.mkdir(parents=True)
    config_path=solver/'PROTOCOL_RUNTIME_CONFIG.yaml';config_path.write_bytes(config)
    manifest=solver/'RUN_MANIFEST.json';manifest.write_text(json.dumps(echo))
    if receipt:
        members={str(p.relative_to(attempt)):{'sha256':sha(p.read_bytes())} for p in (config_path,manifest)}
        if bad_receipt:members['solver/PROTOCOL_RUNTIME_CONFIG.yaml']['sha256']='0'*64
        (attempt/'ARCHIVE_RECEIPT.json').write_text(json.dumps({'retained_files':members}))
    return dict(run_id=run,config_hash=sha(config),output_root=str(solver),native_run_manifest=str(manifest),
                archive_receipt=str(attempt/'ARCHIVE_RECEIPT.json') if receipt else '')


def load_csv(path):
    with path.open(newline='') as stream:return list(csv.DictReader(stream))


def test_inventory_inline_blocks_receipts_roundtrip_and_33_profile_gaps(tmp_path,monkeypatch):
    root=tmp_path/'clean/stages/CLEAN6_SENSOR_MODEL_V21';root.mkdir(parents=True)
    inline=b'initpos: [39.9, 116.34312609, 42]\ninitvel: [0, 0, 0]\n'
    good=retained(root,'RUN_00004',inline,{'init_position_geodetic_deg_m':[39.9,116.34312609000001,42],
                                       'init_velocity_ned_mps':[0,0,0]})
    block=b'initpos:\n- 39.9\n- 116.3\n- 42\n'
    bad=retained(root,'SEQUENCE_BY2H_F04',block,{'init_position_geodetic_deg_m':[0,0,0]},bad_receipt=True)
    # These payloads must never be opened by A0.
    forbidden=root/'payload';forbidden.mkdir()
    (forbidden/'trace_fake.csv').write_text('do not read')
    (forbidden/'KF_GINS_Navresult.nav').write_text('do not read')
    opened=[];original=Path.read_bytes
    def observed(path):
        opened.append(path)
        assert path.parent != forbidden
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',observed)
    output=tmp_path/'audit'
    summary=run_parser_audit(root,[dict(good,dataset_id='BY2',method_id='F04'),
                                   dict(bad,dataset_id='BY2H',method_id='F04')],output,FREEZE)
    assert summary['config_count']==2
    assert summary['config_parse_status_counts']=={'COMPATIBLE':1,'MISMATCH':1}
    assert summary['config_receipt_status_counts']=={'PASS':1,'MISMATCH':1}
    assert summary['echo_sample_row_count']==33
    configs=load_csv(output/'A0_CONFIGS.csv');samples=load_csv(output/'A0_ECHO_SAMPLE.csv')
    assert all(row['config_path'].startswith('<CLEAN_ROOT>/') for row in configs)
    by2=next(row for row in samples if row['dataset_id']=='BY2' and row['method_id']=='F04')
    assert by2['status']=='AVAILABLE'
    details=json.loads(by2['rows_json'])
    position=next(row for row in details if row['config_key']=='initpos')
    assert position['exact_equal'] is False and position['max_roundtrip_ulps']==1
    by2h=next(row for row in samples if row['dataset_id']=='BY2H' and row['method_id']=='F04')
    assert by2h['status']=='MISMATCH'
    assert summary['native_invocation_count']==summary['trace_open_count']==summary['raw_open_count']==0
    assert 'config_rows' not in summary
    assert not any('trace_' in p.name or p.suffix=='.nav' for p in opened)
    with pytest.raises(FileExistsError):run_parser_audit(root,[],output,FREEZE)


def test_reused_f01_is_followed_only_via_projected_frozen_metadata(tmp_path):
    root=tmp_path/'clean/stages/CLEAN6_SENSOR_MODEL_V21';root.mkdir(parents=True)
    config=b'initvel: [0, 0, 0]\n'
    f01=retained(root,'RUN_00001',config,{'init_velocity_ned_mps':[0,0,0]},outside=True)
    additional=retained(root,'RUN_00588',config,{'init_velocity_ned_mps':[0,0,0]},outside=True,receipt=False)
    # An unrelated legacy config must never enter this inventory.
    retained(root,'UNREFERENCED',config,{},outside=True)
    table=root/'20_FINALIZE/13_AGGREGATE/v3/UNIQUE_EVALUATION_RESULTS.csv';table.parent.mkdir(parents=True)
    records=[dict(f01,dataset_id='BY2',method_id='F01',yaw_rmse_deg='FORBIDDEN_PERFORMANCE_VALUE'),
             dict(additional,dataset_id='BY2',method_id='F01',yaw_rmse_deg='ANOTHER_METRIC')]
    with table.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    output=tmp_path/'audit'
    summary=run_parser_audit(root,[dict(f01,dataset_id='BY2',method_id='F01')],output,FREEZE)
    assert summary['config_count']==summary['external_runtime_config_count']==2
    assert summary['external_reference_directory_count']==2
    assert summary['metadata_projection_tables'][0]['projected_rows']==2
    assert 'yaw_rmse_deg' not in summary['metadata_projection_tables'][0]['projected_fields']
    sample=next(row for row in load_csv(output/'A0_ECHO_SAMPLE.csv') if row['dataset_id']=='BY2' and row['method_id']=='F01')
    assert sample['status']=='AVAILABLE' and sample['metadata_config_identity']=='PASS'
    assert sample['echo_receipt_status']=='PASS'
    assert 'REUSED_V2' in sample['config_path']
    assert all('FORBIDDEN_PERFORMANCE_VALUE' not in p.read_text() for p in output.iterdir())


def test_symlink_missing_echo_and_incompatible_source_are_reported(tmp_path):
    root=tmp_path/'clean/stages/CLEAN6_SENSOR_MODEL_V21';root.mkdir(parents=True)
    outside=tmp_path/'external';outside.mkdir();(root/'link').symlink_to(outside,target_is_directory=True)
    record=retained(root,'RUN_00002',b'initvel: [0, 0, 0]\n',{},receipt=False)
    Path(record['native_run_manifest']).unlink()
    output=tmp_path/'audit'
    summary=run_parser_audit(root,[dict(record,dataset_id='BY2',method_id='F02')],output,FREEZE)
    assert summary['status']=='REPORT_PARTIAL_INVENTORY'
    assert summary['symlinks_not_followed']==['link']
    sample=next(row for row in load_csv(output/'A0_ECHO_SAMPLE.csv') if row['dataset_id']=='BY2' and row['method_id']=='F02')
    assert sample['status']=='UNAVAILABLE_NATIVE_ECHO'
    assert summary['config_receipt_status_counts']=={'UNAVAILABLE_NO_RECEIPT':1}


def test_output_cannot_write_frozen_root(tmp_path):
    root=tmp_path/'clean/stages/CLEAN6_SENSOR_MODEL_V21';root.mkdir(parents=True)
    with pytest.raises(ValueError,match='protected'):
        run_parser_audit(root,[],root/'output',FREEZE)
