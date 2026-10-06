"""Transport contract tests; no navigation solver, raw records or reference."""
import csv
import importlib.util
from pathlib import Path

import numpy as np
import pytest
import yaml

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/paper_rebuild/carrier_phase/navigation_trial.py"
spec=importlib.util.spec_from_file_location("carrier_navigation_trial",SCRIPT)
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)


def common():
    return {"algorithm_id":"AB1110","ablation_variant":"AB1110",
        "runtime_contract":"research_experiment","enable_go2_horizontal_velocity_prior":False,
        "enable_go2_velocity_prior_diagnostic":False,
        "dual_yaw_prediction_model":"lateral_projection","enable_receiver_velocity":True,
        "enable_raw_doppler":True,"enable_source_aware":True,"enable_go2_roll_pitch_prior":True,
        "imupath":"pinned/imu","gnsspath":"pinned/gnss","initatt":[0,0,.6]}


def test_config_clone_preserves_unmodified_tokens_and_has_single_gap_policy():
    before=b"# original\r\ninitatt: [0,0,0.688505]\r\nalgorithm_id: LegSA_Paper_V1\r\nimu_gap_policy: STOP_AND_REINITIALIZE\r\n"
    payload,changes=trial.clone_config(before,{"algorithm_id":"AB1110","runtime_contract":"research_experiment"})
    assert b"initatt: [0,0,0.688505]\r\n" in payload
    assert payload.count(b"imu_gap_policy:")==1
    assert yaml.safe_load(payload)["runtime_contract"]=="research_experiment"
    assert len(changes)==2


def test_config_duplicate_rejected():
    with pytest.raises(ValueError,match="DUPLICATE_CONFIG_KEY"):
        trial.clone_config(b"algorithm_id: a\nalgorithm_id: b\n",{"algorithm_id":"AB1110"})


def test_only_heading_and_identity_may_differ():
    configs=[dict(common(),case_id=c,run_id=c,run_label=c,outputpath="out/"+c) for c in trial.CASES]
    configs[0]["dual_antenna_measurement_model"]="scalar"
    configs[1].update(dual_antenna_measurement_model="baseline3d",baseline3d_source="dual_pvt",baseline3d_path="pvt")
    configs[2].update(dual_antenna_measurement_model="baseline3d",baseline3d_source="external_carrier",external_carrier_baseline_path="ar")
    configs[3].update(dual_antenna_measurement_model="baseline3d",baseline3d_source="external_carrier",external_carrier_baseline_path="partial_ar")
    assert trial.common_contract(configs)["HV_disabled_in_all_four"]
    configs[2]["initatt"]=[0,0,1]
    with pytest.raises(ValueError,match="NONHEADING_CONFIG_DIFFERENCE"):
        trial.common_contract(configs)


def test_hv_cannot_be_left_enabled_in_common_configs():
    configs=[dict(common(),enable_go2_horizontal_velocity_prior=True) for _ in trial.CASES]
    with pytest.raises(ValueError,match="COMMON_RESEARCH_CONTRACT"):
        trial.common_contract(configs)


def carrier_file(tmp_path, rows):
    p=tmp_path/"carrier.csv"
    with p.open("w",newline="") as f:
        wr=csv.writer(f,lineterminator="\n");wr.writerow(trial.CARRIER_COLUMNS);wr.writerows(rows)
    return p


def valid_row(t=101.998):
    return [t,t,.1,.2,.25,*np.diag([.01,.02,.03]).ravel(),1]


def test_carrier_current_time_full_covariance_and_invalid_rows(tmp_path):
    bad=[103.998,103.998,*[""]*12,0]
    p=carrier_file(tmp_path,[valid_row(),bad])
    audit=trial.carrier_audit(p)
    assert audit["rows"]==2 and audit["valid_rows"]==1 and audit["invalid_rows"]==1


@pytest.mark.parametrize("mutator",[
    lambda r:r.__setitem__(1,r[0]+.2),
    lambda r:(r.__setitem__(0,99.998),r.__setitem__(1,99.998)),
    lambda r:r.__setitem__(5,-1),
    lambda r:r.__setitem__(6,.1),
    lambda r:r.__setitem__(2,float("nan")),
])
def test_carrier_backdating_or_bad_covariance_rejected(tmp_path,mutator):
    row=valid_row();mutator(row)
    with pytest.raises(ValueError):trial.carrier_audit(carrier_file(tmp_path,[row]))


def test_repeated_carrier_measurement_rejected(tmp_path):
    with pytest.raises(ValueError,match="ORDER_OR_DUPLICATE"):
        trial.carrier_audit(carrier_file(tmp_path,[valid_row(),valid_row()]))


def test_zero_accepted_rows_is_retained_not_forced_to_success(tmp_path):
    p=carrier_file(tmp_path,[[101.998,101.998,*[""]*12,0]])
    assert trial.carrier_audit(p)["valid_rows"]==0


def test_native_effective_contract_and_zero_updates_are_distinct():
    m={"runtime_contract":"research_experiment","algorithm_id":"AB1110",
        "run_id":trial.CASES[3],"dual_yaw_prediction_model":"lateral_projection",
        "go2_horizontal_velocity_update_count":0,
        "research_RD_RP_policy":"past_only_each_source_timestamp_attempted_at_most_once",
        "dual_antenna_measurement_model":"baseline3d","baseline3d_scalar_yaw_observation_used":False,
        "baseline3d_source":"external_carrier","external_carrier_valid_is_trusted_FIX":False,
        "external_carrier_k_b_used":False,"baseline3d_accept_count":0}
    assert trial.manifest_checks(m,trial.CASES[3])["baseline3d_accept_count"]==0
    m["baseline3d_scalar_yaw_observation_used"]=True
    with pytest.raises(ValueError,match="EXCLUSIVITY"):
        trial.manifest_checks(m,trial.CASES[3])
