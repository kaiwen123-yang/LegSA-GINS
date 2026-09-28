import math
from legsa_gins.paper_rebuild.hext.hx05_tables import heading_slice_statistics


def test_slice_keeps_previous_heading_from_before_segment():
    # Both invalid epochs still have archived hold errors from an earlier valid epoch.
    rows=[{'valid':'0','error_valid_deg':'','error_hold_deg':'3','hold_source_epoch_index':'4'},
          {'valid':'0','error_valid_deg':'','error_hold_deg':'4','hold_source_epoch_index':'4'}]
    result=heading_slice_statistics(rows)
    assert result['availability']==0
    assert result['valid_rmse_deg']=='UNAVAILABLE_NO_VALID_EPOCHS'
    assert result['hold_rmse_deg']==math.sqrt(12.5)
    assert result['hold_scored_epochs']==2


def test_missing_reference_does_not_change_native_availability():
    rows=[{'valid':'1','error_valid_deg':'','error_hold_deg':''},
          {'valid':'1','error_valid_deg':'4','error_hold_deg':'4'},
          {'valid':'0','error_valid_deg':'','error_hold_deg':'-2'}]
    result=heading_slice_statistics(rows)
    assert result['availability']==2/3
    assert result['valid_scored_epochs']==1
    assert result['valid_rmse_deg']==4
    assert result['hold_scored_epochs']==2
    assert result['hold_rmse_deg']==math.sqrt(10)


def test_no_valid_heading_is_not_a_zero_error():
    result=heading_slice_statistics([{'valid':'0','error_valid_deg':'','error_hold_deg':''}])
    assert result['valid_epochs']==0 and result['paired_epochs']==1
    assert isinstance(result['valid_rmse_deg'],str)
    assert isinstance(result['hold_rmse_deg'],str)
