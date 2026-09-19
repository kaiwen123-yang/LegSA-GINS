#!/usr/bin/env python3
"""H03 D11 provenance and full-rate error sources; no raw or evaluator access."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import subprocess
import zipfile

import yaml

from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths, alias_path
from legsa_gins.paper_rebuild.manifest import sha256_file

PACKAGE_SHA = '98a77b4601b897956a6d87f5bfa92e008b584add35e48e2b22a9088ddec07585'
NAV_SHA = {
    ('BY2H', 'A04'): 'c1556deb85f55d4311321e56a01f2731025ff6048c711d8190bdfa1afa77e548',
    ('BY2H', 'F04'): '1edd454c8a687ec2bc941281966d42c745ceeacf47a69a84dad88748c4a08257',
    ('BY2O', 'A04'): '4f060dd8dc8dbecb53ef97bde96f4a4ac4c002198e2e8198ba0f6e0b8b945ccf',
    ('BY2O', 'F04'): 'cfa7a97b0f77560b30de24dc1e3a97e20a86768e726d167fbedb0ce1f4057263',
}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def resolve_sources():
    seq = load_sequence_paths('BY2')
    local = yaml.safe_load((seq.code_root / 'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
    package = Path(local['handoff_root']) / 'c541_v21_handoff.zip'
    if package.is_symlink() or sha256_file(package) != PACKAGE_SHA:
        raise RuntimeError('HARD_STOP_V21_PACKAGE_IDENTITY')
    v21 = seq.clean_root / 'stages/CLEAN6_SENSOR_MODEL_V21'
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        nav_members = [n for n in names if 'Navresult' in n]
        manifest_name = 'sequence_error_series_subset/SUBSET_MANIFEST.csv'
        manifest_bytes = archive.read(manifest_name)
        subset = list(csv.DictReader(io.StringIO(manifest_bytes.decode('utf-8-sig'))))
    finalize_nav = [str(f.relative_to(v21)) for f in (v21 / '20_FINALIZE').rglob('*Navresult*')]
    if nav_members or finalize_nav:
        raise RuntimeError('D11 source availability changed; verify new full-rate members before use')
    diagnostics, descriptors = [], []
    for (dataset, method), expected in NAV_SHA.items():
        run = f'SEQUENCE_{dataset}_{method}'
        attempt = v21 / 'RETAINED_RUNS' / run / 'P13_cycle010_attempt01'
        receipt_path = attempt / 'ARCHIVE_RECEIPT.json'
        receipt = json.loads(receipt_path.read_text())
        sealed = [r for r in receipt['sealed_not_retained_full_files']
                  if r['role'] == 'solver' and r['relative_path'] == 'KF_GINS_Navresult.nav']
        if len(sealed) != 1 or sealed[0]['sha256'] != expected:
            raise RuntimeError('HARD_STOP_NATIVE_SEAL_IDENTITY')
        nav = attempt / 'solver/KF_GINS_Navresult.nav'
        if nav.exists() or nav.is_symlink():
            raise RuntimeError('D11 native availability changed; verify before diagnostic')
        diagnostics.append(dict(sequence_id=dataset, method_id=method, status='UNAVAILABLE',
            reason='FULL_RATE_NAV_SEALED_NOT_RETAINED_ABSENT_FROM_FINALIZE_AND_VERIFIED_PACKAGE',
            native_nav_path=alias_path(nav, seq), expected_native_nav_sha256=expected,
            archive_receipt=alias_path(receipt_path, seq), archive_receipt_sha256=sha256_file(receipt_path)))
        if dataset != 'BY2O':
            continue
        for version in ('v3', 'v2'):
            relative = version + '/FROZEN_EVALUATOR/error_series.csv.gz'
            source = attempt / relative
            match = [r for r in subset if r['run_id'] == run and r['evaluator_version'] == version]
            digest = sha256_file(source)
            if (source.is_symlink() or len(match) != 1 or digest != match[0]['source_sha256']
                    or digest != receipt['retained_files'][relative]['sha256']):
                raise RuntimeError('HARD_STOP_FULL_RATE_ERROR_IDENTITY')
            descriptors.append(dict(sequence_id=dataset, method_id=method, version=version,
                path=alias_path(source, seq), sha256=digest,
                provenance=dict(package='<HANDOFF_ROOT>/c541_v21_handoff.zip', package_sha256=PACKAGE_SHA,
                    member=manifest_name, rows_full=int(match[0]['rows_full']),
                    archive_receipt=alias_path(receipt_path, seq), archive_receipt_sha256=sha256_file(receipt_path),
                    display_projection_used=False, role='READ_ONLY_DERIVED_EXACT_WINDOW_FROZEN_FULL_RATE_ERRORS')))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=seq.code_root, text=True).strip()
    result = dict(status='SOURCE_RESOLUTION_COMPLETE_WITH_EXPLICIT_UNAVAILABLE', code_commit=commit,
        data_mode='frozen_v21_read_only', synthetic_data_used=False, semisynthetic_data_used=False,
        solver_invocation_count=0, evaluator_invocation_count=0, trace_open_count=0,
        package_sha256=PACKAGE_SHA, package_member_count=len(names), package_full_nav_matches=nav_members,
        finalize_full_nav_matches=finalize_nav, diagnostics=diagnostics, frozen_error_sources=descriptors,
        A10_source='<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/03_CALIBRATED_RUNS/CLEAN5_CALIBRATED_BY2H_A04/KF_GINS_Navresult.nav',
        A10_sha256='9da51135029a5f54fb1e387c5df8b20c6e364458731644239332ee5f36710b01',
        A10_role='EARLIER_CALIBRATED_CHAIN_NOT_V21_NOT_SUBSTITUTED',
        frozen_segment_window_note='Existing v21 primary window 3369.943066596985..3411.951585292816 differs; exact H03 closed windows are derived from full-rate errors, not relabeled frozen rows.')
    scratch = seq.hext_scratch / 'H_EXT_03'
    write(scratch / '09_LEGSA_GAP_DIAGNOSTIC/H_EXT_03/SOURCE_RESOLUTION.json', result)
    original = seq.output_root / '09_LEGSA_GAP_DIAGNOSTIC/LEGSA_GAP_DIAGNOSTIC.json'
    gap = json.loads(original.read_text())
    gap.update(code_commit=commit, continuation_source_resolution=result,
               prior_diagnostic_sha256=sha256_file(original), source_audit_task='H-EXT-03')
    write(scratch / '09_LEGSA_GAP_DIAGNOSTIC/H_EXT_03/LEGSA_GAP_DIAGNOSTIC.json', gap)
    output = scratch / '09_LEGSA_GAP_DIAGNOSTIC/H_EXT_03/LEGSA_GAP_DIAGNOSTIC.csv'
    with output.open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(diagnostics[0]))
        writer.writeheader()
        writer.writerows(diagnostics)
    return result


if __name__ == '__main__':
    result = resolve_sources()
    print(json.dumps(dict(status=result['status'], diagnostic_items=len(result['diagnostics']),
                          full_rate_error_sources=len(result['frozen_error_sources'])), indent=2))
