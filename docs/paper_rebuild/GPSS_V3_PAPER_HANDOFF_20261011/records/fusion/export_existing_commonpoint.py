from pathlib import Path
import csv,json,gzip,hashlib
R=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
G=Path('/mnt/g/LegSA-GINS-project'); O=G/'V3研究记录梳理_20261011/fusion'
F=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_REPRODUCTION_FIX_20261004/FGO_REPRODUCTION_FINAL_20261004T054410Z')
T=R/'docs/paper_rebuild/hext/FGO_REPRODUCTION_FIX_20261004/COMPARISON_TABLE.csv'
aliases={'<FGO_ROOT>':str(F),'<FGO_EVALUATION_ROOT>':str(F/'evaluation'),'<V3_ROOT>':str(G/'clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3')}
def resolve(s):
    for k,v in aliases.items():s=s.replace(k,v)
    return s
rows=[]; sources=[]
for i,r in enumerate(csv.DictReader(T.open(encoding='utf-8-sig')),2):
    if r['support']!='COMMON_POI_OISAM_V3_TIME':continue
    e=Path(resolve(r['error_path']));b=e.read_bytes();txt=(gzip.decompress(b) if e.suffix=='.gz' else b).decode('utf-8-sig')
    curves=list(csv.DictReader(txt.splitlines()))
    q=dict(r)
    q.update(source_table_absolute=str(T),source_csv_line=i,source_path_absolute=resolve(r['source_path']),error_path_absolute=str(e),error_file_exists=True,error_file_sha256=hashlib.sha256(b).hexdigest(),error_file_rows=len(curves),error_file_columns=';'.join(curves[0].keys()) if curves else '',curve_support_note='This path contains full retained own error series; apply recorded nominal nearest-time gate/intersection to reproduce common curve. No new curve/metric computed in this export.',matching_implementation_absolute=str(R/'src/legsa_gins/paper_rebuild/fgo_comparison/report.py'),matching_implementation_lines='76-101',alias_resolution='actual strict final root, not older FGO_COMPARISON root')
    rows.append(q);sources.append(dict(absolute_path=str(e),read_depth='full retained CSV bytes and column/row inspection',purpose='existing same POI midpoint V3/OiSAM comparison paths; no metric recomputation',bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
with (O/'V3_OISAM_EXISTING_COMMON_POINT.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for p in [T,R/'src/legsa_gins/paper_rebuild/fgo_comparison/report.py',R/'src/legsa_gins/paper_rebuild/fgo_comparison/evaluation.py',R/'src/legsa_gins/reporting/by2_algorithm_runner.py',R/'suanfahengxiangduibi/PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC/02_evidence_consolidation/qa_full_matrix_evidence.csv',G/'legacy_freeze_202607/selected_reports/LEGACY_STAGE_INDEX.md']:
    b=p.read_bytes();sources.append(dict(absolute_path=str(p),read_depth='full text acquired; relevant sections inspected',purpose='bounded historical QA and common-point followup',bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
with (O/'SOURCES_READ.csv').open('a',encoding='utf-8',newline='') as f:csv.DictWriter(f,fieldnames=list(sources[0])).writerows(sources)
print(json.dumps([{'seq':x['sequence_id'],'method':x['method_id'],'matched':x['matched_epoch_count'],'saved_error_rows':x['error_file_rows']} for x in rows]))
