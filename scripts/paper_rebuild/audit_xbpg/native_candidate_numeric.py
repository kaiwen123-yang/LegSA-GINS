#!/usr/bin/env python3
"""Generate a candidate patch and verify it only in a small isolated cpp copy.

This does not alter the official source or consume real input. It patches only
Matrix element bounds and Rotation wrappers; other numerical findings remain.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import yaml

ROOT=Path(__file__).resolve().parents[3]
DOC=ROOT/'docs/paper_rebuild/audit_xbpg_20261001'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--local-config',type=Path,required=True);args=parser.parse_args()
    paths=yaml.safe_load(args.local_config.read_text())['paths']
    work=Path(paths['audit_scratch'])/'native_candidate_numeric';work.mkdir(parents=True,exist_ok=False)
    output=Path(paths['audit_root'])/'native/native_candidate_numeric';output.mkdir(parents=True,exist_ok=False)
    copied=work/'cpp';shutil.copytree(ROOT/'cpp',copied)
    patches=[];identities=[]
    for relative in ['cpp/legsa_v23_port_core/src/common/types.cpp','cpp/legsa_v23_port_core/src/common/rotation.cpp']:
        original=(ROOT/relative).read_text();updated=original
        if relative.endswith('types.cpp'):
            old='  return data.at(row * cols + col);'
            new='  if (row >= rows || col >= cols) {\n    throw std::out_of_range("AUDIT_MATRIX_INDEX_OUT_OF_RANGE");\n  }\n'+old
            assert updated.count(old)==2;updated=updated.replace(old,new)
        else:
            updated=updated.replace('#include <cmath>','#include <cmath>\n#include <stdexcept>')
            for method in ['wrapRad','wrap2Pi']:
                old=f'double Rotation::{method}(double angle_rad) {{'
                # Preserve historical arithmetic exactly in ordinary angular
                # ranges. A bounded reduction handles large finite arguments.
                new=old+'\n  if (!std::isfinite(angle_rad)) {\n    throw std::domain_error("AUDIT_NONFINITE_ANGLE");\n  }\n  if (std::fabs(angle_rad) > 16.0 * kPi) {\n    angle_rad = std::fmod(angle_rad, 2.0 * kPi);\n  }'
                assert updated.count(old)==1;updated=updated.replace(old,new)
        assert updated!=original
        target=work/relative;target.write_text(updated)
        identities.append(dict(path=relative,original_sha256=sha(ROOT/relative),candidate_sha256=sha(target)))
        # Zero-context diff avoids whitespace-only context lines in the tracked
        # patch artifact. Use git apply --unidiff-zero in an isolated copy.
        patches.extend(difflib.unified_diff(original.splitlines(True),updated.splitlines(True),fromfile='a/'+relative,tofile='b/'+relative,n=0))
    patch=DOC/'NATIVE_CANDIDATE_NUMERIC.patch';patch.write_text(''.join(patches))
    calls=[];env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    def run(label,command,timeout=120):
        t=time.perf_counter()
        try:
            p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=timeout)
            row=dict(label=label,command=command,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
        except subprocess.TimeoutExpired as exc:
            row=dict(label=label,command=command,returncode=None,status='TIMEOUT',stdout=str(exc.stdout or ''),stderr=str(exc.stderr or ''))
        row['elapsed_seconds']=time.perf_counter()-t;calls.append(row)
        (output/'CALLS.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2)+'\n');print(label,row['returncode'],flush=True);return row
    build=work/'build'
    for label,cmd in [('configure',['cmake','-S',str(copied),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release']),('build',['cmake','--build',str(build),'--target','legsa_v23_port_core_demo','-j4'])]:
        if run(label,cmd)['returncode']!=0:raise SystemExit('candidate build failed; retained')
    for version,library in [('old',Path(paths['audit_scratch'])/'native_build/liblegsa_v23_port_core.a'),('candidate',build/'liblegsa_v23_port_core.a')]:
        cmd=['g++','-std=c++17','-O2','-I',str(ROOT/'cpp/legsa_v23_port_core/include'),str(ROOT/'tests/paper_rebuild/audit_xbpg/native_candidate_probe.cpp'),str(library),'-o',str(work/version)]
        if run('compile_'+version,cmd)['returncode']!=0:raise SystemExit('probe compile failed')
    normals={}
    for version in ['old','candidate']:
        p=subprocess.run([str(work/version),'normal'],cwd=ROOT,env=env,capture_output=True,check=True)
        (work/(version+'_normal.txt')).write_bytes(p.stdout);normals[version]=hashlib.sha256(p.stdout).hexdigest()
    probes=[]
    for mode in ['column','const_column']:
        for version in ['old','candidate']:probes.append(run(version+'_'+mode,[str(work/version),mode]))
    for mode in ['wrap','wrap2pi']:
        for value in ['inf','-inf','nan','1e308','-1e308','7']:
            probes.append(run('candidate_'+mode+'_'+value,[str(work/'candidate'),mode,value],0.5))
    comparisons=[]
    for mode in ['synthetic-math','raw-doppler-toy','source-aware-toy','quality-state-toy','go2-weak-prior-toy','qa-fallback-toy']:
        directory=work/mode;res=run('candidate_target_'+mode,[str(build/'legsa_v23_port_core_demo'),'--dry-run-'+mode,'--output-dir',str(directory)])
        for name in ['LegSA_PORT_NAV.nav','LegSA_PORT_STD.csv','EVAL_NAV.csv']:
            retained=Path(paths['audit_scratch'])/'native_initial'/mode/name
            comparisons.append(dict(mode=mode,file=name,byte_identical=retained.read_bytes()==(directory/name).read_bytes()))
    result=dict(data_mode='synthetic',synthetic_data_used=True,semisynthetic_data_used=False,real_data_open_count=0,reference_open_count=0,production_source_modified=False,post_hoc=True,
        patch_sha256=sha(patch),candidate_binary_sha256=sha(build/'legsa_v23_port_core_demo'),files=identities,normal_angle_sample_count=20001,normal_probe_sha256=normals,normal_probes_byte_identical=normals['old']==normals['candidate'],full_target_comparison=comparisons,
        limitations=['candidate only; not installed','Matrix allocation overflow and inverse not repaired','Go2/FGO/runtime duplicate wrappers not repaired','exception classification in higher Python controllers not executed','no real inputs or performance evaluation'],calls=calls)
    (output/'RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for row in result['calls']:row.pop('command',None)
    shared=json.dumps(result,ensure_ascii=False,indent=2)
    # The full local command/stdout receipt stays external. Shared summaries
    # contain aliases, including CMake's otherwise incidental directory echo.
    for actual,alias in [(paths['audit_scratch'],'<AUDIT_SCRATCH>'),(paths['audit_root'],'<AUDIT_ROOT>'),(str(ROOT),'<CODE_ROOT>')]:
        shared=shared.replace(actual,alias)
    (DOC/'NATIVE_CANDIDATE_RESULTS.json').write_text(shared+'\n')

if __name__=='__main__':main()
