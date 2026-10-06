"""Strict threshold and all-comparison formula tests; no new decision is generated."""
from legsa_gins.paper_rebuild.clean5_calibrated.robustness import compare_segments


def fixture():
    rows=[]
    for ds,segment in [('BY2H','full'),('BY2O','full'),('BY2O','outside')]:
        for method in ['A04','F04']:
            for metric in ['horizontal','up','yaw']:
                rows.append({'dataset_id':ds,'segment_id':segment,'method_id':method,'metric_name':metric,'count':'5',
                    'rmse':'1' if method=='A04' else '1.1','p95_abs':'4' if method=='A04' else '2','source_row':'mock.csv:'+str(len(rows)+2)})
    old={'tests':{'heading':{'status':'FAIL','executable':True,'branches':{k:{'strict_pass':False} for k in ['yaw_rmse_deg','yaw_p95_deg']}},
        'position':{'status':'FAIL','windows':{ds+'_'+segment:{k:{'strict_pass':False} for k in ['horizontal_rmse_m','up_rmse_m']} for ds,segment in [('BY2H','full'),('BY2O','full'),('BY2O','outside')]}}}
    }
    return rows,old


def test_equality_is_not_pass_and_no_new_outcome():
    rows,old=fixture()
    result=compare_segments(rows,rule={'sha256':'fixture'},old=old)
    assert result['heading_branches']['yaw_p95_deg']['threshold_equal']
    assert not result['heading_branches']['yaw_p95_deg']['strict_pass']
    assert all(v['threshold_equal'] and not v['strict_pass'] for checks in result['position_comparisons'].values() for v in checks.values())
    assert len(result['individual_comparisons'])==8
    assert result['outcome_changed'] is False and result['new_outcome_created'] is False
    assert 'proposed_method' not in result


def test_exact_decimal_tiny_strict_change_and_or_heading_and_six_position():
    rows,old=fixture()
    for r in rows:
        if r['method_id']=='F04' and r['metric_name']!='yaw':r['rmse']='1.09999999999999999999999999999999999999999'
        if r['method_id']=='F04' and r['metric_name']=='yaw':r['p95_abs']='1.99999999999999999999999999999999999999999'
    result=compare_segments(rows,rule={},old=old)
    assert not result['heading_branches']['yaw_rmse_deg']['strict_pass']
    assert result['aggregate_formula_checks']['heading']['formula_check_status']=='PASS'
    assert result['aggregate_formula_checks']['position']['formula_check_status']=='PASS'
    assert result['aggregate_formula_checks']['heading']['comparison_to_frozen']=='REVERSED'
    next(r for r in rows if r['dataset_id']=='BY2O' and r['segment_id']=='outside' and r['method_id']=='F04' and r['metric_name']=='up')['rmse']='1.1'
    result=compare_segments(rows,rule={},old=old)
    assert result['aggregate_formula_checks']['position']['formula_check_status']=='FAIL'


def test_csv_projection_copies_all_existing_comparisons_without_recomputation():
    from legsa_gins.paper_rebuild.clean5_calibrated.robustness import comparison_csv_rows
    rows,old=fixture();check=compare_segments(rows,rule={},old=old)
    result={'classification':'NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL','versions':{'v2':check,'v3':check}}
    flat=comparison_csv_rows(result)
    assert len(flat)==20 and sum(r['record_type']=='individual' for r in flat)==16
    item=next(r for r in flat if r['version']=='v3' and r['test']=='heading/yaw_rmse_deg')
    assert all(item[k]==v for k,v in check['heading_branches']['yaw_rmse_deg'].items())
    assert all(r['outcome_changed'] is False for r in flat)
