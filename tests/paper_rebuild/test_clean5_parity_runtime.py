"""Synthetic transport/counter regression only; no scientific runtime execution."""
import numpy as np
import pytest
from legsa_gins.paper_rebuild.clean5_parity.runtime import bind_config,expected_counts,scheduled_gnss_indices
from legsa_gins.paper_rebuild.clean5_parity.runner import evaluation_gate

def test_path_transport_preserves_scientific_bytes_and_rejects_window_override():
    text='imupath: old\ngnsspath: old2\nstarttime: 66.000000000\nendtime: 340.0\ninitatt: [0, 0, 0.688505]\n'
    new,ledger=bind_config(text,{'gnsspath':'new path'})
    assert new.splitlines()[2:]==text.splitlines()[2:]
    assert [r['key'] for r in ledger]==['gnsspath']
    with pytest.raises(ValueError,match='non-authorized'):bind_config(text,{'starttime':67})

def test_18_column_eligibility_and_profile_aware_attempts(tmp_path):
    gnss=np.zeros((4,18));gnss[:,0]=[66,66.2,67,340]
    gnss[:,15]=1;gnss[:,16]=[1,1,0,1];gnss[:,17]=[1,0,1,1]
    imu=np.zeros((6,7));imu[:,0]=[65.9,66.005,66.3,67.1,339.997,340.1]
    np.savetxt(tmp_path/'g',gnss);np.savetxt(tmp_path/'i',imu)
    cfg={'gnsspath':str(tmp_path/'g'),'imupath':str(tmp_path/'i'),'starttime':66,'endtime':340,
         'enable_receiver_velocity':True,'enable_dual_yaw':True}
    counts=expected_counts(cfg)
    assert counts['eligible_rows']==2
    assert counts['position_update_count']==2
    assert counts['receiver_velocity_update_count']==1
    assert counts['dual_yaw_attempt_count']==1
    cfg['enable_dual_yaw']=False
    assert expected_counts(cfg)['dual_yaw_attempt_count']==0

def test_missing_evaluation_cannot_be_promoted_by_expected_solver_failure():
    records=[{'run_id':'CLEAN5_PARITY_V2e_F01','terminal_status':'FAILED_NATIVE_COUNTER_CONTRACT'}]
    assert not evaluation_gate({'status':'COMPLETED_WITH_UNAVAILABLE'},records)['pass']
    names=['V0_F01','V0_F03','V0_A04','EXT05C','LC01']
    evaluation={'run_gates':[{'version':v,'run_id':r,'status':'COMPLETED'} for v in ['v2','v3'] for r in names],
        'body_frame_bias':{v:[{'run_id':r,'status':'AVAILABLE'} for r in names] for v in ['v2','v3']}}
    assert evaluation_gate(evaluation,records)['pass']
    evaluation['run_gates'][0]['status']='UNAVAILABLE'
    assert not evaluation_gate(evaluation,records)['pass']


def test_schedule_endpoint_tolerance_and_processed_validity_latch():
    # Future IMU beyond end is never offered to the engine. A GNSS within the
    # fixed tolerance can still update; a later row outside tolerance cannot.
    selected,info=scheduled_gnss_indices([1.5,2.9995,3.0],[1.0,1.5,1.5001,2.999,3.01],1.,3.)
    assert selected.tolist()==[0,1]
    assert info['last_processed_imu_time']==2.999
    assert info['first_unprocessed_imu_time']==3.01
    assert info['time_align_error_s']==.001


def test_schedule_one_stale_refresh_not_while_and_initial_start_rule():
    # Initial GNSS selection is >start, so the first loop refreshes exactly one
    # old row instead of skipping the whole backlog to a schedulable future row.
    selected,_=scheduled_gnss_indices([1.01,1.02,1.5],[1.1,1.2,1.6],1.,2.)
    assert selected.tolist()==[2]
    selected,_=scheduled_gnss_indices([1.01,1.02,1.03,1.5],[1.1,1.6],1.,2.)
    assert selected.tolist()==[]
