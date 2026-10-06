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


def body_configs():
    configs=[dict(common(),case_id=c,run_id=c,run_label=c,outputpath="out/"+c,
        algorithm_id="AB1111",ablation_variant="AB1111",
        enable_go2_horizontal_velocity_prior=True,
        go2_horizontal_velocity_frame="body_frd",go2_body_velocity_prior_path="body.csv",
        go2_body_velocity_update_period_s=.2,go2_velocity_prior_std_scale=1.,
        go2_horizontal_velocity_prior_std_scale=1.) for c in trial.CASES]
    configs[0]["dual_antenna_measurement_model"]="scalar"
    configs[1].update(dual_antenna_measurement_model="baseline3d",baseline3d_source="dual_pvt",baseline3d_path="pvt")
    for c,path in zip(configs[2:],["full.csv","partial.csv"]):
        c.update(dual_antenna_measurement_model="baseline3d",baseline3d_source="external_carrier",
                 external_carrier_baseline_path=path)
    return configs


def test_body_mode_four_arms_share_input_model_and_preserve_comparison():
    configs=body_configs()
    gate=trial.common_contract(configs,"body")
    assert gate["body_velocity_shared_in_all_four"] and gate["algorithm_id"]=="AB1111"
    assert not gate["HV_disabled_in_all_four"]
    configs[2]["go2_body_velocity_prior_path"]="different.csv"
    with pytest.raises(ValueError,match="NONHEADING_CONFIG_DIFFERENCE"):
        trial.common_contract(configs,"body")


@pytest.mark.parametrize("key,value",[
    ("go2_horizontal_velocity_frame","ned"),
    ("go2_horizontal_velocity_prior_std_scale",2.),
    ("go2_body_velocity_update_period_s",.1),
])
def test_body_mode_rejects_shared_but_wrong_model(key,value):
    configs=body_configs()
    for c in configs:c[key]=value
    with pytest.raises(ValueError,match="COMMON_BODY_VELOCITY_CONTRACT"):
        trial.common_contract(configs,"body")


def test_body_provider_retains_invalid_rows_but_requires_registered_working_noise(tmp_path):
    p=tmp_path/"body.csv"
    with p.open("w",newline="") as f:
        wr=csv.writer(f,lineterminator="\n");wr.writerow(trial.BODY_COLUMNS)
        wr.writerows([[66.1,1.,-.3,.2,.2,1,"active"],[66.2,"","","","",0,"missing"]])
    gate=trial.body_velocity_audit(p)
    assert gate["valid_rows"]==1 and gate["invalid_rows"]==1
    assert gate["physical_frame_verified_by_this_check"] is False
    p.write_text(p.read_text().replace("0.2,0.2","0.1,0.2"))
    with pytest.raises(ValueError,match="FIXED_NOISE"):
        trial.body_velocity_audit(p)


def body_events(tmp_path, rows):
    p=tmp_path/"BODY_VELOCITY_EVENTS.csv"
    with p.open("w",newline="") as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(["state_time","source_time","age_s","source_present","valid","accepted","reason","frame","observed_axes"])
        writer.writerows(rows)
    return p


def test_body_events_only_past_unique_attempts_and_count(tmp_path):
    good=[[66.2,66.19,.01,1,1,1,"accepted","body_frd","forward_right"],
          [66.4,66.39,.01,1,0,0,"invalid","body_frd","forward_right"],
          [66.6,"","",0,0,0,"no_source","body_frd","forward_right"]]
    assert trial.body_event_audit(body_events(tmp_path,good),1,.08)["source_attempts"]==2
    good[1][1]=66.19;good[1][2]=.21
    with pytest.raises(ValueError,match="CAUSAL_AGE"):
        trial.body_event_audit(body_events(tmp_path,good),1,.08)


@pytest.mark.parametrize("row",[
    [66.2,66.21,-.01,1,1,1,"accepted","body_frd","forward_right"],
    [66.2,66.19,.01,1,0,1,"accepted","body_frd","forward_right"],
    [66.2,66.19,.01,1,1,1,"accepted","ned","forward_right"],
])
def test_body_events_reject_future_invalid_or_wrong_frame(tmp_path,row):
    with pytest.raises(ValueError):
        trial.body_event_audit(body_events(tmp_path,[row]),1,.08)


def test_body_events_reject_reuse_even_if_second_attempt_invalid(tmp_path):
    rows=[[66.2,66.19,.01,1,1,1,"accepted","body_frd","forward_right"],
          [66.21,66.19,.02,1,0,0,"invalid","body_frd","forward_right"]]
    with pytest.raises(ValueError,match="REUSED_SOURCE"):
        trial.body_event_audit(body_events(tmp_path,rows),1,.08)


def test_body_manifest_makes_body_z_vs_navigation_down_distinction():
    m={"runtime_contract":"research_experiment","algorithm_id":"AB1111",
        "run_id":trial.CASES[0],"dual_yaw_prediction_model":"lateral_projection",
        "go2_horizontal_velocity_update_count":13,
        "research_RD_RP_policy":"past_only_each_source_timestamp_attempted_at_most_once",
        "go2_horizontal_velocity_frame":"body_frd","body_velocity_measurement_axes":"forward_right",
        "body_velocity_z_observed":False,"body_velocity_nav_down_state_frozen":False,
        "body_velocity_native_uses_GNSS_heading_to_construct_measurement":False,
        "body_velocity_update_period_s":.2,"go2_velocity_prior_std_scale":1.,
        "body_velocity_time_policy":"independent_IMU_boundary_timer_past_latest_unique_attempt_no_interpolation"}
    assert trial.manifest_checks(m,trial.CASES[0],"body")["go2_horizontal_velocity_update_count"]==13
    m["body_velocity_nav_down_state_frozen"]=True
    with pytest.raises(ValueError,match="NATIVE_BODY"):
        trial.manifest_checks(m,trial.CASES[0],"body")
