#!/usr/bin/env python3
"""Pin HX-05 read sources; this entrypoint performs no integration or evaluation."""
import json
from pathlib import Path

from legsa_gins.paper_rebuild.hext.hx05_common import alias,dump,forbid_reference_open,paths,sha


def main():
    forbid_reference_open();p=paths();c=p['HX05']/'00_CONTROL'
    assert json.loads((c/'VERIFY_START.json').read_text())['passed']
    sources=[p['HX02']/'90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv',
             p['HX02E']/'90_AGGREGATE/HARTLEY_OFFICIAL_TABLE.csv',
             p['HX03R2']/'90_AGGREGATE/DEGRADATION_EXTERNAL_TABLE_R2.csv',
             p['HX03R2']/'90_AGGREGATE/DEGRADATION_EXTERNAL_SUMMARY_R2.csv',
             p['HX03R2']/'90_AGGREGATE/DEGRADATION_PAIRED_R2.csv',
             p['HX03R2']/'90_AGGREGATE/STATE_TRANSITIONS_R2.csv',
             p['V3']/'07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv',
             p['V3']/'07_AGGREGATE/BY2O_SEGMENT_TABLE.csv',
             p['V3']/'07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv',
             p['V3']/'07_AGGREGATE/ADDENDUM_TABLE_V3.csv',
             p['HX02']/'01_INPUT_PINS/INPUT_PINS.json',
             p['W']/'configs/paper_rebuild/hext/HX02E/CONTRACT.json',
             p['HX02D']/'EXECUTION_V2/B_REFERENCE_FREE/BY2/OUTPUT/B_ARRAYS.npz',
             p['HX02D']/'EXECUTION_V2/C_REFERENCE/BY2/OUTPUT/C_TABLES.json',
             p['HX02D']/'HX02D_HARTLEY_DIAGNOSTIC.md']
    expected={'EXTERNAL_FIVE_CATEGORY_TABLE.csv':'7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba',
              'HARTLEY_OFFICIAL_TABLE.csv':'30fda253e5fa4f56b829ae9e5184cefc0258c74d57c0e3fadbae98e407cbd888',
              'DEGRADATION_EXTERNAL_TABLE_R2.csv':'17cfce3191231c1631b0b3b1c2d8196a838690e1e9eae83bbcef0621f23d4989'}
    for method in ('EXT01','EXT02','EXT03','EXT04','RTKLIB'):
        cfg='NONE' if method=='RTKLIB' else 'LIT'
        folder=p['HX02']/'RUNS'/f'BY2O__{method}__{cfg}__FILE_START__NA'/'eval/HEADING/OUTPUT'
        sources+=sorted(folder.glob('HEADING_ERROR_SERIES*.csv'))
    for seq,case in [('BY2','C00'),('BY2H','CONTRACT_START'),('BY2O','FILE_START')]:
        sources.append(p['HX02']/'RUNS'/f'{seq}__GINAV__NONE__{case}__NA'/'eval/D8_BOUNDED_GATE.json')
        folder=p['HX02']/'01_INPUT_PINS/HARTLEY'/seq
        sources += [folder/'H5_INPUT_CACHE.bin',folder/'H5_INPUT_CACHE_MANIFEST.json']
        manifest=json.loads((folder/'H5_INPUT_CACHE_MANIFEST.json').read_text())
        sources.append(Path(manifest['source_identity']['source']))
    pins={alias(f,p):sha(f) for f in sources}
    for f in sources:
        if f.name in expected:assert pins[alias(f,p)]==expected[f.name],f.name
    dump(c/'SOURCE_PINS.json',pins)
    dump(c/'PREPARATION.json',{'source_count':len(pins),'solver_calls':0,'reference_opens':0,'leg_dr_integrations':0,
                             'LEG_DR_definition':'PENDING_USER_FORMULA_RULING',
                             'issue':'HX05 direct negative foot_speed versus HX02D C4 negative omega-cross-foot plus foot_speed; no definition silently substituted'})
    print(json.dumps({'source_count':len(pins),'passed':True,'solver_calls':0,'reference_opens':0}))


if __name__=='__main__':main()
