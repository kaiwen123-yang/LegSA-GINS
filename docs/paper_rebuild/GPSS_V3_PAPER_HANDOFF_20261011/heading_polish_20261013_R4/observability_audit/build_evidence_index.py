from pathlib import Path
import hashlib,csv,json
P=Path(__file__).parent
ROOT=Path('/mnt/g/LegSA-GINS-project')
S=ROOT/'clean_rebuild_202607/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/07_LSE01_HARTLEY_CONTACT_INEKF'
FO=ROOT/'V3论文组图_20261008/focused_20261011/robot'
R3=ROOT/'V3正文精修_20261012_R3/observability'

small={
 'H5_INPUT_CACHE_MANIFEST.json':S/'08_BY2_NATIVE/00_PROVIDER/H5_INPUT_CACHE_MANIFEST.json',
 'BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json':S/'03_BY2_INPUT_AUDIT/BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json',
 'H5_ATTEMPT_LEDGER.json':S/'08_BY2_NATIVE/00_PROVIDER/SUPERVISOR_ATTEMPT_LEDGER.json',
 'H6_ZERO_PARITY.json':Path('/home/kaiwen/research/LegSA-GINS-RUNS/LSE01_H6_REAL_DATA_GAUGE_OBSERVABILITY_4B25FA6_V1/00_ADMIN/H6_ZERO_DEGREE_RUNNER_PARITY.json'),
 'H5_REPORT.md':S/'11_REPORT/LSE01_H5_BY2_NATIVE_REPORT.md',
 'H6_REPORT.md':S/'11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md',
 'H6R_REPORT.md':S/'11_REPORT/LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md',
 'H6R_STATUS.json':S/'11_REPORT/LSE01_H6R_STATUS.json',
 'profile_robot_20261011.py':FO/'profile_robot.py',
 'build_robot_heading_20261011.py':FO/'build_robot_heading.py',
 'build_observability_R3.py':R3/'build_observability.py',
}
for name,source in small.items():(P/'evidence'/name).write_bytes(source.read_bytes())
items=[]
def add(label,path,start,end,meaning,status='CURRENT_READ'):
    path=Path(path); lines=path.read_text().splitlines();assert 0<start<=end<=len(lines)
    items.append(dict(evidence_id=label,path=str(path),line_start=start,line_end=end,meaning=meaning,status=status,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
def find(label,path,needle,before,after,meaning,status='CURRENT_READ'):
    lines=Path(path).read_text().splitlines(); k=next(i for i,v in enumerate(lines) if needle in v)
    add(label,path,max(1,k+1-before),min(len(lines),k+1+after),meaning,status)

find('E01',P/'evidence/profile_robot_20261011.py',"files=[ROOT",0,8,'Figure source enumeration: H5 zero anchor plus six saved H6 NAVs; plotted yaw read from atan2 of native rotation.')
find('E02',P/'evidence/build_robot_heading_20261011.py',"native_initial_yaw",1,0,'Plot CSV extraction copies native px/py/pz and derives yaw directly; does not rotate one path into seven.')
find('E03',P/'evidence/build_observability_R3.py',"runs={",0,20,'Current panel a plots saved positions; known inverse rotation is applied only for panel b and residual panel c.')
find('E04',P/'evidence/BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json','raw_source_path_alias',1,2,'Same BY2 high-level raw recording dated2026-03-06; raw checksum.')
find('E05',P/'evidence/H5_INPUT_CACHE_MANIFEST.json','cache_sha256',0,0,'Shared immutable provider cache checksum matches all seven native records.')
find('E06',P/'evidence/H6_REPORT.md','The frozen H5',0,13,'H5 zero reused; one extra zero parity replay was temporary; six nonzero native sequences completed.')
find('E07',P/'source_snapshots/H6__configs__paper_rebuild__horizontal_literature__hartley__stage_payload__04_METHOD_CONTRACTS__HARTLEY_H6_EXECUTION_CONTRACT.yaml','gauge_ensemble:',0,17,'Initial-yaw control ensemble; six new nonzero runs plus H5 zero.', 'H6_CLOSURE_SOURCE_NOT_IDENTICAL_TO_RUNTIME_CONTRACT_PIN')
find('E08',P/'source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_inekf__tools__run_h5.cpp','Matrix3 initial_gauge_rotation',0,26,'Native matching-pin C++ applies a known gravity-axis rotation only at initialization, before output loop.', 'EXACT_RUNTIME_SOURCE_PIN_MATCH')
add('E09',P/'source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_inekf__tools__run_h5.cpp',389,430,'Native matching-pin C++ loops through each input record, propagates, performs contact update, and writes actual filter state.', 'EXACT_RUNTIME_SOURCE_PIN_MATCH')
add('E10',P/'source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_inekf__src__backend.cpp',1095,1118,'Initial transformation applies to R/v/p/contacts and covariance; body-frame biases unchanged.', 'EXACT_RUNTIME_SOURCE_PIN_MATCH')
add('E11',P/'source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_h6.py',405,452,'Native argv form and saved stdout/counter checks; read closure wrapper, not assert exact runtime whole-file identity.', 'H6_CLOSURE_WRAPPER_SHA_DIFFERS_FROM_RUNTIME_PIN')
add('E12',P/'source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_h6.py',775,789,'Compact publication copies original native NAV byte-for-byte; no trajectory rotation is performed in this step.', 'H6_CLOSURE_WRAPPER_SHA_DIFFERS_FROM_RUNTIME_PIN')
add('E13',P/'evidence/H6_YAW_M100__RUNTIME.csv',1,2,'Example per-member native runtime ledger:63277 states,63276 propagation/Eq61 calls.')
find('E14',P/'evidence/H6_YAW_M100__NATIVE_CONFIG.yaml','native_stdout:',2,2,'Example saved native process success stdout after a separate call.')
find('E15',P/'evidence/H6_YAW_M100__NATIVE_SUMMARY.json','expected_native_euler_yaw_offset_deg',0,0,'Registered downward-gravity alpha has opposite sign to plotted positive-z Euler yaw.')
find('E16',P/'evidence/H6_REPORT.md','Only the maximum',0,13,'Original H6 full gate failed only due six-digit contact serialization; do not silently mark that stage globally passed.')
add('E17',P/'evidence/H6R_REPORT.md',1,23,'Later independent full-precision contact recovery passed and reused windows; not the NAV source used in figure4.')
find('E18',P/'evidence/H5_REPORT.md','committed H5 implementation',0,2,'H5 archival commit and runtime source context.')
find('E19',P/'COMMIT_DATES.json','2026-08-19T02:15:05',0,4,'Git archival date/author, not exact individual solver launch time.')
find('E20',P/'COMMIT_DATES.json','2026-08-19T23:45:54',0,4,'Git H6 closure archival date/author, not exact individual solver launch time.')
with (P/'EVIDENCE_LOCATIONS.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
lines=['# Evidence locations','', '|ID|File|Lines|Meaning|', '|---|---|---:|---|']
for x in items:
    relative=Path(x['path']).relative_to(P)
    lines.append(f'|{x["evidence_id"]}|[{relative}]({relative.as_posix()})|{x["line_start"]}–{x["line_end"]}|{x["meaning"]}|')
(P/'EVIDENCE_INDEX.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(len(items),'source locations')
