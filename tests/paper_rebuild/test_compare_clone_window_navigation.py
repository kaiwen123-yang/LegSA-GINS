"""One registered pure synthetic attribution scenario; no real artifacts."""
import importlib.util
from pathlib import Path
import numpy as np

SOURCE=Path(__file__).resolve().parents[2]/"scripts/paper_rebuild/carrier_phase/compare_clone_window_navigation.py"
spec=importlib.util.spec_from_file_location("clone_compare_test",SOURCE)
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

def test_three_arm_attribution_and_all_skip_identity():
    # Original/old-fallback -> NULL improves due to backend only.
    # PAIR with no update has exactly NULL errors; A can pass but foot attribution cannot.
    times=np.arange(7,dtype=float)*.2
    def errors(yaw):
        return c.base.errors_from_rows([{"time":t,"yaw_err_deg":yaw,
            "horizontal_err_m":.1,"err_u_m":-.2} for t in times])
    original,previous,null=errors(10),errors(10),errors(9)
    def item(e):
        return {"errors":e,"row":c.metrics(e),"has_error_series":True}
    v3=c.metrics(original);foot=[];comparisons=[];coverage=[]
    for sid in c.SEQUENCES:
        comparisons.append(c.base.comparison_row(sid,"PAIR_YOUNG","FULL_AVAILABLE_FROZEN",c.metrics(null),v3,len(times)))
        coverage.append({"sequence_id":sid,"arm":"PAIR_YOUNG","coverage_nondegraded":True})
        foot.extend(c.paired_effects(sid,item(null),item(null),"FOOT_PAIR_CONDITIONAL_EFFECT",
                                    "PAIR_YOUNG","NULL_CLONE","COMMON_PAIR_NULL_EXACT_KEYS"))
    gate=c.attribution_gate(comparisons,coverage,foot)
    assert gate["A_original_V3_contract"] is True
    assert gate["A_qualifying_sequences_with_positive_PAIR_vs_NULL_yaw_effect"]==[]
    assert gate["recommend_for_human_review_under_this_contract"] is False
    assert all(r["delta_yaw_rmse_deg"]==0 and r["all_nine_zero_tolerance_nondegraded"] for r in foot)
    backend=c.delta_row("BY2","COMMON","BACKEND_RESET_AND_EVENT_EFFECT",c.metrics(null),c.metrics(previous),"NULL_CLONE","PREVIOUS")
    assert backend["delta_yaw_rmse_deg"]==-1

    # Independently assign one further unit of foot effect; additive decomposition stays -2=-1+-1.
    pair=errors(8);foot=[];comparisons=[]
    for sid in c.SEQUENCES:
        comparisons.append(c.base.comparison_row(sid,"PAIR_YOUNG","FULL_AVAILABLE_FROZEN",c.metrics(pair),v3,len(times)))
        foot.extend(c.paired_effects(sid,item(pair),item(null),"FOOT_PAIR_CONDITIONAL_EFFECT",
                                    "PAIR_YOUNG","NULL_CLONE","COMMON_PAIR_NULL_EXACT_KEYS"))
    gate=c.attribution_gate(comparisons,coverage,foot)
    assert gate["recommend_for_human_review_under_this_contract"] is True
    assert c.metrics(pair)["yaw_rmse_deg"]-c.metrics(previous)["yaw_rmse_deg"]==backend["delta_yaw_rmse_deg"]+foot[0]["delta_yaw_rmse_deg"]
    assert gate["B"] is None

    # Losing a real key cannot turn common-only improvement into a full-support claim.
    reduced=c.base.subset_errors(pair,times[1:])
    lost=c.paired_effects("BY2",item(reduced),item(null),"FOOT_PAIR_CONDITIONAL_EFFECT",
                         "PAIR_YOUNG","NULL_CLONE","COMMON_PAIR_NULL_EXACT_KEYS")[1]
    assert lost["matched_count"]==6 and lost["missing_control_error_keys"]==1
    assert lost["same_complete_error_keys"] is False
    na=c.delta_row("BY2","COMMON","FOOT_PAIR_CONDITIONAL_EFFECT",c.metrics(c.base.empty_errors()),
                   c.metrics(null),"PAIR_YOUNG","NULL_CLONE")
    assert na["delta_yaw_rmse_deg"] is None and na["all_nine_zero_tolerance_nondegraded"] is None
