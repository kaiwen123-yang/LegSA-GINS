"""Registry routing does not inspect the reference payload."""
from pathlib import Path
import yaml
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths


def test_trace_path_is_derived_from_registry_without_payload_access(tmp_path):
    local=tmp_path/'local.yaml';registry=tmp_path/'registry.yaml';contract=tmp_path/'contract.yaml'
    local.write_text(yaml.safe_dump({'paths':{k:str(tmp_path/k) for k in ('raw_root','clean_root','code_root','hext_scratch')}}))
    registry.write_text(yaml.safe_dump({'sequences':{'BY2H':{'fix_prefix':'changed_receiver_dir','trace_name':'registry_selected.csv','go2_body':'body.txt'}}}))
    contract.write_text(yaml.safe_dump({'sequences':{'BY2H':{'base_time':1772784000.,'window_seconds':[413,683],
        'baseline_median_m':.35418777593777223,'trace':{'path':'<RAW_ROOT>/changed_receiver_dir/registry_selected.csv','sha256':'a'*64},
        'raw_lock':{'path':'<CLEAN_ROOT>/01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK_CLEAN5.csv','sha256':'b'*64}}}}))
    result=load_sequence_paths('BY2H',local,registry,contract)
    assert result.trace==tmp_path/'raw_root/changed_receiver_dir/registry_selected.csv'
    assert result.gnss1_raw==tmp_path/'raw_root/changed_receiver_dir/gnss1-raw.csv'
    assert result.go2_body==tmp_path/'raw_root/body.txt'
    assert result.window==(413.,683.)
    assert not (tmp_path/'raw_root').exists()
