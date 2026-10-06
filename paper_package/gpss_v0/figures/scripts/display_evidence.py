"""Publication-only qualifications for historical diagnostic budget labels.

Retains numerical tokens; no estimator/evaluator/statistical imports.
"""
def publication_budget_rows(rows):
    out=[]
    for original in rows:
        r={k:v for k,v in original.items() if k!='evidence'}
        key=r['row']
        r['type']='resampling statistic' if key in {'9','10'} else 'diagnostic indicator'
        if key=='1':
            r['magnitude']=r['magnitude'].replace('<=1.14 deg','1.14 deg scaled specification indicator').replace('noise <=0.059 deg','disagreement 0.059 deg')
            r['effect']='shared reference contribution; magnitude not independently calibrated'
        elif key=='2':
            r['effect']+='; similar retained components, physical cause not identified'
        elif key=='3':
            r['source']='estimator_heading_bias'
            r['effect']+='; mounting cause not independently identified'
        elif key=='4':
            r['magnitude']=r['magnitude'].replace('lower bound','indicator').replace('upper bound','indicator')
            r['effect']=r['effect'].replace('floor ','historical diagnostic range ')
        elif key=='6':
            r['magnitude']=r['magnitude'].replace('lateral verified <=7 mm','lateral model consistency 7 mm (not installation uncertainty)').replace('bounded by height residual mean','retained height residual mean').replace('leakage <=17 mm','diagnostic leakage 17 mm')
            r['effect']='installation uncertainty not independently established'
        r['cancels_in_paired_comparison']='not generally in squared-error/RMSE differences' if key in {'1','2','4','5','6'} else r['cancels_in_paired_comparison']
        out.append(r)
    return out
