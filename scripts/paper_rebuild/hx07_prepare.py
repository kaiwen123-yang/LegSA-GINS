#!/usr/bin/env python3
"""Register HX-07 inputs/configurations without executing scientific programs."""
from pathlib import Path
import csv
import difflib
import hashlib
import json
import subprocess
import datetime
import yaml

W = Path(__file__).resolve().parents[2]
PATHS = yaml.safe_load((W / 'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
C = Path(PATHS['clean_root'])
H = C / 'stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY'
D = C / 'stages/CLEAN10_GNSS_RAW_DIAGNOSTIC/DG01R'
O = C / 'stages/CLEAN9_EXTERNAL_COMPARISON/HX07'
R = W / 'docs/paper_rebuild/hext/HX07'
EXT = Path(PATHS['horizontal_literature_rtklib_root'])
S = Path(PATHS['hx02_scratch']).parent / 'HX07'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def dump(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def alias(p):
    value = str(p)
    for root, name in [(W, '<W>'), (C, '<CLEAN_ROOT>'), (EXT, '<RTKLIB>'), (S, '<SCRATCH>'), (EXT.parent, '<EXTERNAL>')]:
        if value == str(root) or value.startswith(str(root) + '/'):
            return name + value[len(str(root)):]
    return value


def resolve(p):
    for root, name in [(W, '<W>'), (C, '<CLEAN_ROOT>'), (EXT, '<RTKLIB>'), (S, '<SCRATCH>'), (EXT.parent, '<EXTERNAL>')]:
        if p.startswith(name):
            return Path(str(root) + p[len(name):])
    return Path(p)


def main():
    pins = {}
    def pin(p, expected=None):
        digest = sha(p)
        assert expected is None or digest == expected, str(p)
        pins[alias(p)] = {'sha256': digest, 'bytes': p.stat().st_size}
        return digest
    contract = yaml.safe_load((W / 'configs/paper_rebuild/hext/HX02_CONTRACT_V1.yaml').read_text())
    for name, digest in contract['code_sha256'].items():
        pin(W / name, digest)
    pin(W / 'src/legsa_gins/paper_rebuild/hext/hx05_tables.py')
    pin(EXT / 'app/consapp/rnx2rtkp/gcc/rnx2rtkp', '3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda')
    dpins = json.loads((D / 'OUTPUT_SHA256.json').read_text())
    seqs = {}
    configs = None
    for seq, count, expected in [('BY2',1370,153), ('BY2H',1350,179), ('BY2O',1885,112)]:
        run = next((H / 'RUNS').glob(seq + '__RTKLIB__NONE__*'))
        files = [run / x for x in ['native/RTKLIB_PREPARED.json', 'native/RTKLIB_RUN.json',
                                  'native/RTKLIB_UNMODIFIED_MOVING_BASE.conf', 'eval/HEADING/SPEC.json']]
        for p in files:
            pin(p)
        conf = files[2].read_text()
        assert sha(files[2]) == '97f0fe4157ce31909538e696184a7faadad059c3099ab912cbe2e97b0fc9e14f'
        if configs is None:
            v1 = conf.replace('pos1-navsys        =33', 'pos1-navsys        =57')
            # Preserve all formatting, including variable spacing, except the registered value.
            import re
            v1, n = re.subn(r'(?m)^(pos1-navsys\s*=)33\b', r'\g<1>57', conf)
            assert n == 1
            v2, n = re.subn(r'(?m)^(pos2-armode\s*=)continuous\b', r'\g<1>fix-and-hold', v1)
            assert n == 1
            configs = {'V0': conf, 'V1': v1, 'V2': v2}
        spec = json.loads(files[3].read_text())
        start = json.loads(files[1].read_text())['argv']
        start = start[start.index('-ts'):start.index('-ts')+3] if '-ts' in start else []
        obs, nav = [], []
        for rx in (1,2):
            p = D / f'CONVBIN/{seq}_R{rx}.obs'
            pin(p, dpins[str(p.relative_to(D))]['sha256']); obs.append(alias(p))
            p = run / f'native/SOURCE_BACKEND/gnss{rx}.nav'
            prepared = json.loads(files[0].read_text())
            pin(p, prepared['files'][f'gnss{rx}']['nav_sha256']); nav.append(alias(p))
        seqs[seq] = {'obs': obs, 'nav_v0': nav, 'hx02_run': alias(run),
                     'start_argv': start, 'paired_denominator': count, 'expected_v0_fixed': expected,
                     'base_time': spec['base_time'], 'window': spec['window'],
                     'reference_sha256_registered_not_opened': spec['trace_sha256']}
    (O / 'CONFIGS').mkdir(exist_ok=False)
    for variant, text in configs.items():
        p = O / f'CONFIGS/{variant}.conf'; p.write_text(text); pin(p)
        base = configs['V0'] if variant != 'V2' else configs['V1']
        diff = ''.join(difflib.unified_diff(base.splitlines(True), text.splitlines(True),
                    fromfile='HX02_original.conf' if variant != 'V2' else 'V1.conf', tofile=f'{variant}.conf'))
        (R / f'HX07_{variant}_CONFIG.diff').write_text(diff or '# V0 configuration is byte-identical to HX-02; output-only argv adds -y 1.\n')
    dl = json.loads((O / '00_INPUTS/DOWNLOAD.json').read_text())
    assert dl['nav_record_counts'].get('E',0) > 0
    brdc = O / '00_INPUTS/BRDC00WRD_R_20260650000_01D_MN.rnx'
    pin(brdc, dl['rnx_sha256']); pin(brdc.with_suffix('.rnx.gz'), dl['compressed_sha256'])
    source_files = subprocess.check_output(['git','-C',str(EXT),'ls-files'], text=True).splitlines()
    dump(O / 'RTKLIB_SOURCE_SHA256.json', {p: sha(EXT/p) for p in source_files if (EXT/p).is_file()})
    plan = {'sequences': seqs, 'variants': ['V0','V1','V2'], 'external_nav': alias(brdc),
            'executable': alias(EXT/'app/consapp/rnx2rtkp/gcc/rnx2rtkp'), 'status_argv': ['-y','1'],
            'run_order': [f'{s}_{v}' for v in ['V0','V1','V2'] for s in seqs],
            'gate': 'stop immediately at first V0 sequence whose associated window Q1 differs by >2; no evaluations until all V0 pass',
            'data_mode': 'recorded_raw_gnss', 'synthetic_data_used': False, 'semisynthetic_data_used': False}
    dump(O/'PLAN.json', plan);dump(R/'HX07_INPUT_SHA256.json', pins)
    dump(R/'HX07_DOWNLOAD.json', dl)
    metadata = {}
    for root in [C/'stages/CLEAN8_PROTOCOL_V3', H, C/'stages/CLEAN9_EXTERNAL_COMPARISON/HX03',
                 C/'stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2', C/'stages/CLEAN9_EXTERNAL_COMPARISON/HX05', D]:
        if root.exists():
            for p in root.rglob('*'):
                if p.is_file():
                    st = p.stat();metadata[str(p)] = [st.st_size, st.st_mtime_ns]
    dump(O/'PROTECTED_METADATA.json', metadata)
    print(f'Prepared {len(pins)} input/code pins; {len(source_files)} RTKLIB tracked entries; {len(metadata)} protected file metadata entries')


if __name__ == '__main__':
    main()
