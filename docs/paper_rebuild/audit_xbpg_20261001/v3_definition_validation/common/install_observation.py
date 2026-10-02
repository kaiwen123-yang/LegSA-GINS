#!/usr/bin/env python3
"""Install the new pure diagnostic layer in one isolated candidate source only."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def install(roots_file, candidate):
    roots = json.loads(Path(roots_file).read_text())['aliases']
    root = Path(roots['<VALIDATION_BUILD_ROOT>']) / ('source_' + candidate)
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError('isolated candidate source must already exist')
    core = root / 'cpp/legsa_v23_port_core'
    target = core / 'include/legsa_v23_port_core/kf_gins/covariance_diagnostics.hpp'
    if target.exists():
        raise RuntimeError('refuse reinstall/overwrite')
    engine = core / 'src/kf_gins/gi_engine.cpp'
    observer = core / 'src/kf_gins/gi_observer.cpp'
    resolved_root = root.resolve()
    for key in ['<FROZEN_SOURCE>', '<OBSERVED_SOURCE>', '<MECHANISM_ROOT>', '<V3_ROOT>', '<CODE_ROOT>']:
        protected = Path(roots[key]).resolve()
        if resolved_root == protected or protected in resolved_root.parents:
            raise RuntimeError('candidate source intersects a protected root')
    for path in [root, target, engine, observer]:
        if any(node.is_symlink() for node in [path, *path.parents]):
            raise RuntimeError('refuse symlink in candidate write path')
        resolved = path.resolve()
        if resolved != resolved_root and resolved_root not in resolved.parents:
            raise RuntimeError('candidate write escaped isolated source')
    e = engine.read_text();o = observer.read_text()
    include = '#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"'
    hook = '  if (!checkCov()) {'
    config = '  observerWrite("CONFIGURATION",x);'
    vector = '.add("used_innovation_covariance",i.used_innovation_covariance).add("residual_norm",i.residual_norm)'
    for needle, text in [(include,e),(hook,e),(config,o),(vector,o)]:
        if text.count(needle) != 1:
            raise RuntimeError('source anchor must be unique: ' + needle)
    e = e.replace(include, include + '\n#include "legsa_v23_port_core/kf_gins/covariance_diagnostics.hpp"')
    e = e.replace(hook, '  if (observer_.enabled()) observerWrite("COVARIANCE_HEALTH",candidate_diagnostics::inspect(Cov_).json());\n' + hook)
    statistic = 'conditional_innovation' if candidate == 'N12_ONLY' else 'frozen_raw_residual'
    o = o.replace(config, config + '\n  observerWrite("CANDIDATE_DEFINITION",Json().add("candidate_id","' + candidate + '")'
                  '.add("sa_statistic","' + statistic + '").add("raw_residual_metadata_norm_preserved",true)'
                  '.add("covariance_diagnostic","POST_IMU_COMPLETE_MATRIX_NO_FILTER_WRITE"));')
    o = o.replace(vector, vector + '.add("residual_vector",i.residual)')
    target.write_bytes((HERE / 'covariance_diagnostics.hpp').read_bytes())
    engine.write_text(e);observer.write_text(o)
    return {'candidate_id': candidate, 'source_root': '<VALIDATION_BUILD_ROOT>/source_' + candidate,
            'new_diagnostic_header_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'scientific_matrix_modified': False, 'source_writes': 3,
            'native_calls': 0, 'evaluator_calls': 0}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--roots', required=True)
    p.add_argument('--candidate', choices=['N12_ONLY','N16_ONLY','N09_RP_ONLY'], required=True)
    a = p.parse_args()
    print(json.dumps(install(a.roots,a.candidate), ensure_ascii=False))
