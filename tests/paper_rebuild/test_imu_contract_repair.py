from types import SimpleNamespace
from pathlib import Path
import pytest
from legsa_gins.paper_rebuild.imu_contract_repair import body_digest, clone_fields


def test_historical_raw_pin_shapes_resolve_to_exact_same_body():
    seq=SimpleNamespace(raw_root=Path('/raw'),go2_body=Path('/raw/robot/body.txt'))
    digest='a'*64
    for value in ({'body':digest},{'robot/body.txt':digest},
                  {'body':{'path':'/raw/robot/body.txt','sha256':digest}}):
        assert body_digest({'raw_source_hashes':value},seq)==digest
    with pytest.raises(ValueError):
        body_digest({'raw_source_hashes':{'body':{'path':'/raw/other.txt','sha256':digest}}},seq)


def test_config_edit_preserves_nested_looking_values_and_whitespace():
    source=b'# preserved\r\nstarttime: 1\r\ninitatt: [0, 0, 12]\r\npolicy:\r\n  gain: 0.1\r\n'
    result,changes=clone_fields(source,{'starttime':2,'initatt':[0,0,22]})
    assert b'policy:\r\n  gain: 0.1\r\n' in result
    assert len(changes)==2 and result.startswith(b'# preserved\r\n')


def test_restart_inverse_lever_has_correct_physical_point_and_sign():
    from legsa_gins.paper_rebuild.imu_contract_repair import imu_position_from_antenna
    import numpy as np
    imu=imu_position_from_antenna([0,0,10],[0,0,0],[0,0,-.3])
    assert np.allclose(imu,[0,0,9.7],rtol=0,atol=1e-7)
    imu=imu_position_from_antenna([0,0,10],[0,0,90],[1,0,0])
    assert abs(imu[0])<1e-12 and imu[1]<0
    assert np.isclose(np.deg2rad(imu[1])*6378147,-1.,atol=1e-7)


def test_virtual_free_space_cannot_substitute_for_actual_host_volume(tmp_path):
    from legsa_gins.paper_rebuild.imu_contract_repair import prepare
    target=tmp_path/'stage'
    args=SimpleNamespace(stage=str(target),code=str(tmp_path),prior_v3=str(tmp_path),physical_free_bytes=None)
    with pytest.raises(RuntimeError,match='ACTUAL_HOST_VOLUME_FREE_BYTES_REQUIRED'):
        prepare(args)
    assert not target.exists()
