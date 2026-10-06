import pytest
from legsa_gins.paper_rebuild.body_velocity import parse_sample

def message(v="1.2",err="0"):
    return ("stamp:\n  sec: 1772784100\n  nanosec: 200000000\nerror_code: "+err+
            "\nvelocity:\n- "+v+"\n- 0.4\n- -0.7\nimu_state:\n  rpy:\n  - 90\n")
def parse(m):
    return parse_sample(m,base_time_s=1772784000,input_frame="dataset_supported_body_flu")
def test_physical_basis_and_source_timestamp():
    s=parse(message())
    assert (s.time,s.forward,s.right,s.valid)==(100.2,1.2,-.4,True)
    assert s.csv_row(.2)["std_forward_mps"]==.2
def test_attitude_and_future_do_not_enter_velocity():
    assert parse(message())==parse(message().replace("  - 90","  - -987"))
@pytest.mark.parametrize("raw,reason",[(message("nan"),"nonfinite_velocity"),
    (message(err="8"),"source_error_code"),(message().replace("error_code: 0\n",""),"missing_error_code"),
    (message().replace("- -0.7\n",""),"missing_velocity")])
def test_invalid_retained(raw,reason):
    s=parse(raw);assert not s.valid and s.reason==reason
    assert s.csv_row(.2)["v_forward_mps"]==""
def test_explicit_frame_required():
    with pytest.raises(ValueError):parse_sample(message(),base_time_s=0,input_frame="odom")
def test_timestamp_not_invented():
    with pytest.raises(ValueError):parse(message().replace("stamp:","missing:"))
