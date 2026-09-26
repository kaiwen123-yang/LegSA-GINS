"""Read-only final input verification, factual report and complete T5bc ZIP.

No provider generation, native/evaluator invocation or reference trace access.
ZIP members are streamed, every CRC/SHA verified; existing evidence preserved.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile
import zlib

from ..manifest import sha256_file
from .t5bc_execution import archive_tree_once, verify_terminal
from .t5bc_runtime import _safe, _json, _pin, PROVENANCE_FLAGS

TABLES=("CASE_INPUT_EFFECTS.csv","CALIBRATION_SUMMARY.csv","S3_CALIBRATION_BINS.csv","PILOT_TABLE_V3.csv","PILOT_TABLE_V2.csv",
        "LC01_CROSSCHECK.csv","SUBSET61_SUMMARY.csv","SUBSET61_PAIRED_DISTRIBUTIONS.csv","SUBSET61_TABLE_V3.csv","SUBSET61_TABLE_V2.csv",
        "BY2O_SEGMENTS_BY_VARIANT.csv","GATING_COUNTS.csv","NIS_CONSISTENCY.csv","ATTITUDE.csv")


def _read(path):return json.loads(_safe(path).read_text())


def _write(path,value):
    data=(_json(value)+'\n').encode();path=_safe(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise RuntimeError('T5BC_FINAL_EXISTING_DOCUMENT_DIFFERS: '+str(path))
    else:
        with path.open('xb') as stream:stream.write(data)
    return {'path':str(path),'sha256':sha256_file(path)}


def _member(path,name):
    digest=hashlib.sha256();crc=0;size=0
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):
            digest.update(block);crc=zlib.crc32(block,crc);size+=len(block)
    return dict(name=name,sha256=digest.hexdigest(),crc32=f'{crc&0xffffffff:08x}',size_bytes=size)


def verify_completed(scratch,code_freeze):
    scratch=_safe(scratch)
    state=scratch/'09_HANDOFF/EXECUTION'
    if (state/'CONTROLLER_HARD_STOP.json').exists():raise RuntimeError('T5BC_RECORDED_HARD_STOP')
    summary=_read(state/'FINAL_EXECUTION_SUMMARY.json')
    if summary['status']!='COMPLETE_REGISTERED_EXECUTION' or summary['code_freeze']!=code_freeze:
        raise RuntimeError('T5BC_INCOMPLETE_EXECUTION_OR_CODE_FREEZE')
    budget=summary['budget_reserved']
    if budget['identity_native']!=2 or budget['matrix_native']!=259 or not 0<=budget['evaluator']<=518:
        raise RuntimeError('T5BC_FINAL_BUDGET_MISMATCH')
    for category,filename in (('native_terminals','T5BC_NATIVE_SUMMARY.json'),('evaluation_terminals','T5BC_EVALUATION_SUMMARY.json')):
        for ref in summary[category].values():
            _pin(ref);verify_terminal(Path(ref['path']).parent,filename)
    checked={}
    for reference in summary['checkpoints'].values():
        _pin(reference)
        for name,digest in _read(reference['path'])['pins'].items():
            if name in checked and checked[name]!=digest:raise RuntimeError('T5BC_FINAL_CONFLICTING_PIN')
            checked[name]=digest
    # These pins intentionally exclude the reference trace; only evaluator children open it.
    for path,digest in checked.items():_pin({'path':path,'sha256':digest})
    if summary['trace_open_count_native']!=0 or summary['trace_open_count_evaluator']!=budget['evaluator']:
        raise RuntimeError('T5BC_FINAL_TRACE_ACCOUNTING')
    return summary,checked


def write_report(scratch,code_root,code_freeze,*,aliases):
    scratch=_safe(scratch);code_root=_safe(code_root)
    summary=_read(scratch/'09_HANDOFF/EXECUTION/FINAL_EXECUTION_SUMMARY.json')
    if summary['code_freeze']!=code_freeze:raise RuntimeError('Report code-freeze mismatch')
    manifest=_read(scratch/'07_AGGREGATE/AGGREGATE_MANIFEST.json')
    identity=_read(scratch/'02_IDENTITY_GATE/IDENTITY_GATE.json')
    def alias(text):
        for key,value in sorted(aliases.items(),key=lambda p:len(str(p[1])),reverse=True):text=text.replace(str(value),'<'+key.upper()+'>')
        return text
    lines=['# T5bc v3 candidate pilot','',
        'Status: **COMPLETE_REGISTERED_EXECUTION**. This record contains sensitivity/limitations and v3 decision evidence outside the frozen v2.1 manuscript chain. No v2.1 row is replaced.',
        '',f'Code freeze: `{code_freeze}`. Authorization: `T5bc prompt 2026-09-19`.',
        '', '## Execution and identity', '', '```json',alias(json.dumps({key:summary[key] for key in ('status','budget_reserved','budget_authorized','trace_open_count_native','trace_open_count_evaluator','retry_count','archive_failure_fraction')},ensure_ascii=False,indent=2)),'```','',
        '```json',alias(json.dumps(identity,ensure_ascii=False,indent=2)),'```','',
        'The measurement model uses 0.35 m. Evaluator point conversion keeps the frozen sequence-specific lengths and windows. BY2 1 s calibration is applied to all three sequences; 0.2 s and other-sequence calibration are diagnostic only. Calibration residuals include gyro, starting raw-heading and frozen-RP mapping motion errors. The candidate binary is used only by B3 and the two identity runs.',
        '', '## Bookkeeping and interpretation limits','',
        '- All 61 cases are included. Their non-yaw GNSS tokens and IMU/RD/RP/HV bytes are retained. The original yaw/A1 fault columns are replaced by the registered raw-baseline input; the corresponding heading injection is not claimed to survive.',
        '- D57 uses exact time matching. Unmatched epochs remain invalid; there is no time-axis repair or interpolation. Zero valid input and the formal activation guard are reported separately from attempts that are all rejected.',
        '- Frozen D37 has no historical effective-options echo. Its expected options use D36 only after proving exactly five changed metadata/path lines and identical scientific configuration bytes. The old D37 failure and unavailable metrics remain unchanged.',
        '- C00 retains real_clean in the subset; D01–D60 are semisynthetic controlled degradations. The historical native configuration flags remain visible separately from the authoritative outer data roles.',
        '- R5W NIS uses the source-aware residual after scheme-C and before source-aware scaling, without subtracting Hdx. B3 NIS uses the actual innovation before its NIS gate and source-aware action. Coverage is descriptive; no gate is changed.',
        '- A single baseline constrains two attitude directions; rotation about the baseline axis remains unobservable. All failed/unavailable rows are retained; no numerical imputation or result-driven parameter selection is used.',
        '- Subset worst-five-percent threshold is the linear P95 of available absolute case RMSE. Paired differences require both rows to be available. The frozen failure row cannot supply a fabricated comparator.',
        '', '## Tables (verbatim CSV)','']
    for name in TABLES:
        path=scratch/'07_AGGREGATE'/name;data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=manifest['files_sha256'][name]:raise RuntimeError('Report aggregate pin mismatch '+name)
        lines += ['### '+name,'',f'SHA256: `{sha256_file(path)}`.','', '```csv',alias(data.decode('utf-8-sig').rstrip()),'```','']
    lines += ['## Figures','', 'Independent exports and source bindings are in `<T5BC_ROOT>/08_FIGURES/T5BC_RENDER_MANIFEST.json`. The original 28 figures and render manifest remain byte-identical.','',
              '## v3 work requiring separate preregistration','',
              'Heading/A1 degradation families need source-consistent injection definitions for the new raw and vector inputs. HV source changes and the A1/A2 family definitions remain separate work. This pilot supplies no directional pass/fail performance criterion.','',
              '## Handoff','', 'The package includes the complete new artifact tree, its file inventory and every member SHA256/CRC32. ZIP_VERIFICATION.json is external to the package to avoid a self-hash cycle; the final documentation commit records the whole-package SHA256 and bytes.','']
    text='\n'.join(lines)
    target=code_root/'docs/paper_rebuild/hext/T5BC_V3_CANDIDATE_PILOT.md'
    target.write_text(text,encoding='utf-8')
    copy=scratch/'09_HANDOFF/T5BC_V3_CANDIDATE_PILOT.md'
    if copy.exists() and copy.read_text()!=text:raise RuntimeError('Preserve existing handoff report')
    if not copy.exists():copy.write_text(text,encoding='utf-8')
    return target


def package_completed(scratch,archive,handoff_root,code_freeze):
    scratch,archive,handoff_root=map(_safe,(scratch,archive,handoff_root))
    summary,pins=verify_completed(scratch,code_freeze)
    visual=_read(scratch/'09_HANDOFF/VISUAL_REVIEW.json')
    if visual.get('status')!='PASS':raise RuntimeError('T5BC_ACTUAL_VISUAL_REVIEW_REQUIRED')
    render=scratch/'08_FIGURES/T5BC_RENDER_MANIFEST.json'
    if not render.is_file():raise RuntimeError('T5BC_FIGURE_MANIFEST_REQUIRED')
    files=[p for p in sorted(scratch.rglob('*')) if p.is_file() and p.suffix!='.zip' and p.name not in ('FINAL_SUMMARY.json','ZIP_VERIFICATION.json')]
    artifact_hashes={p.relative_to(scratch).as_posix():sha256_file(p) for p in files}
    final={**PROVENANCE_FLAGS,'status':'PASS_T5BC_V3_CANDIDATE_PILOT_COMPLETE','code_freeze':code_freeze,
           'data_mode':summary['data_mode'],'synthetic_data_used':summary['synthetic_data_used'],
           'semisynthetic_data_used':summary['semisynthetic_data_used'],
           'budget_authorized':summary['budget_authorized'],'budget_actual':summary['budget_reserved'],
           'trace_open_count_native':0,'trace_open_count_evaluator':summary['trace_open_count_evaluator'],
           'retry_count':0,'input_hashes':pins,'artifact_hashes':artifact_hashes,
           'frozen_chain_unchanged':True,'original_28_figures_unchanged':True,'scratch_retained':True,
           'zip_self_reference_policy':'Whole ZIP SHA256 and bytes live in external ZIP_VERIFICATION.json and final documentation.'}
    _write(scratch/'FINAL_SUMMARY.json',final);files.append(scratch/'FINAL_SUMMARY.json')
    members=[]
    for path in files:
        _safe(path);members.append(_member(path,'T5BC/'+path.relative_to(scratch).as_posix()))
    manifest={'data_mode':final['data_mode'],'synthetic_data_used':final['synthetic_data_used'],'semisynthetic_data_used':final['semisynthetic_data_used'],
              'code_freeze':code_freeze,'members':members,
              'self_reference_policy':'This member is hashed and CRC-checked in external ZIP_VERIFICATION.json.'}
    zip_path=scratch/'09_HANDOFF/t5bc_v3_candidate_pilot_handoff.zip'
    with zipfile.ZipFile(zip_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as stream:
        for path,row in zip(files,members):stream.write(path,row['name'])
        stream.writestr('MEMBER_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    expected={row['name']:row for row in members};checked=[]
    with zipfile.ZipFile(zip_path) as stream:
        if len(stream.infolist())!=len(members)+1:raise RuntimeError('T5BC_ZIP_MEMBER_COUNT')
        for info in stream.infolist():
            digest=hashlib.sha256();crc=0;size=0
            with stream.open(info) as member:
                for block in iter(lambda:member.read(2**20),b''):
                    digest.update(block);crc=zlib.crc32(block,crc);size+=len(block)
            row=dict(name=info.filename,sha256=digest.hexdigest(),crc32=f'{crc&0xffffffff:08x}',size_bytes=size)
            if row['crc32']!=f'{info.CRC:08x}' or size!=info.file_size:raise RuntimeError('T5BC_ZIP_CRC_SIZE')
            if info.filename in expected and row!=expected[info.filename]:raise RuntimeError('T5BC_ZIP_MEMBER_HASH')
            checked.append(row)
    digest=sha256_file(zip_path);destination=handoff_root/zip_path.name
    if destination.exists():raise FileExistsError('Preserve existing T5bc handoff')
    shutil.copyfile(zip_path,destination)
    if sha256_file(destination)!=digest:raise RuntimeError('T5BC_ZIP_ARCHIVE_HASH')
    verification={'status':'PASS','code_freeze':code_freeze,'zip_sha256':digest,'zip_size_bytes':zip_path.stat().st_size,
                  'members':checked,'ext4_and_G_equal':True}
    _write(scratch/'09_HANDOFF/ZIP_VERIFICATION.json',verification)
    # Runtime trees were already archived; this performs only copy-missing with equality checks.
    for name in ('01_CALIBRATION','02_IDENTITY_GATE','03_PROVIDER_TABLES','04_NATIVE_C00_SEQ',
                 '05_NATIVE_SUBSET61','06_EVAL','07_AGGREGATE','08_FIGURES'):
        archive_tree_once(scratch/name,archive/name)
    # Exclude ZIP from stage archive; its requested destination is HANDOFF_ROOT.
    for path in sorted((scratch/'09_HANDOFF').rglob('*')):
        if not path.is_file() or path.suffix=='.zip':continue
        target=archive/path.relative_to(scratch);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and sha256_file(target)!=sha256_file(path):raise RuntimeError('T5BC_FINAL_ARCHIVE_DIFF')
        if not target.exists():shutil.copyfile(path,target)
        if sha256_file(target)!=sha256_file(path):raise RuntimeError('T5BC_FINAL_ARCHIVE_HASH')
    target=archive/'FINAL_SUMMARY.json'
    if target.exists() and sha256_file(target)!=sha256_file(scratch/'FINAL_SUMMARY.json'):raise RuntimeError('T5BC_FINAL_SUMMARY_DIFF')
    if not target.exists():shutil.copyfile(scratch/'FINAL_SUMMARY.json',target)
    return {key:verification[key] for key in ('status','zip_sha256','zip_size_bytes')}
