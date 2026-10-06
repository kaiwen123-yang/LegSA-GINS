"""Actual upper classifier on complete synthetic traces; no native rerun."""
import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext.t5bc_runtime import classify_heading_failure

REASON = "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch"


@pytest.mark.parametrize("error,accepted", [
    (REASON,True), ("legsa_v23_port_core_demo failed: "+REASON,True),
    ("AUDIT_NONFINITE_ANGLE",False), ("legsa_v23_port_core_demo failed: AUDIT_NONFINITE_ANGLE",False),
    ("legsa_v23_port_core_demo failed: AUDIT_MATRIX_INDEX_OUT_OF_RANGE",False),
    ("unexpected prefix "+REASON,False),
])
def test_real_classifier_does_not_mislabel_candidate_exception(tmp_path,error,accepted):
    imu = np.zeros((3,7));imu[:,0]=[0,.1,.2]
    # Interior epochs isolate classification from same-rate endpoint refresh delay.
    gnss=np.zeros((2,18));gnss[:,0]=[.05,.15];gnss[:,15]=1
    np.savetxt(tmp_path/"imu.txt",imu);np.savetxt(tmp_path/"gnss.txt",gnss)
    (tmp_path/"PORT_RUNTIME_LOOP_TRACE.csv").write_text("loop_index,timestamp_after_process\n0,0.1\n1,0.2\n")
    (tmp_path/"PORT_GNSS_UPDATE_TRACE.csv").write_text("position_update,velocity_update,yaw_update\n1,0,0\n1,0,0\n")
    (tmp_path/"stderr.log").write_text(error)
    config=dict(imupath=str(tmp_path/"imu.txt"),gnsspath=str(tmp_path/"gnss.txt"),starttime=0.,endtime=.2,
                enable_receiver_velocity=False,enable_dual_yaw=True,enable_source_aware=False)
    result=classify_heading_failure(tmp_path,config,variant="R5")
    assert result["counters"]["position_update_count"] == 2
    assert result["full_window_processed"] and result["passed"] is accepted
    assert result["classification"] == ("ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT" if accepted else "UNAVAILABLE_NATIVE_PROCESS_FAILED")
