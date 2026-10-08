"""Fixed BY2 first50-epoch source diagnostic; inputs and output paths are supplied by --config."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('--config', type=Path, required=True)
a = parser.parse_args()
config = json.loads(a.config.read_text())
p = Path(config['output_directory'])
s = json.loads((p / 'SUMMARY.json').read_text())
raw = json.loads((p / 'RAW_PHASE_NOISE_CHECK.json').read_text())
rows = json.loads((p / 'ROWS_AND_TRANSITIONS.json').read_text())['rows']
z = np.load(p / 'DIFFERENCE_DIAGNOSTIC.npz')
r, R = z['residual'], z['residual_covariance']
std = np.sqrt(np.diag(R)); rz = r / std
C = R / std[:, None] / std[None, :]
lookup = {(v['relation_id'], v['epoch_index']): i for i,v in enumerate(rows) if v['kind'] == 'phase_time_difference'}

def ratio(lag, group=None):
    pairs = [(i, lookup[v['relation_id'], v['epoch_index'] + lag]) for i,v in enumerate(rows)
             if v['kind'] == 'phase_time_difference' and (group is None or v['group'] == group)
             and (v['relation_id'], v['epoch_index'] + lag) in lookup]
    aa = np.array([v[0] for v in pairs]); bb = np.array([v[1] for v in pairs])
    return {'lag_intervals': lag, 'group': group, 'pairs': len(pairs),
            'uncentered_product_ratio': float((rz[aa] @ rz[bb]) / np.sqrt((rz[aa] @ rz[aa]) * (rz[bb] @ rz[bb]))),
            'nominal_covariance_product_ratio': float(np.mean(C[aa,bb]))}

s['amplitude_normalized_temporal_description'] = {
    'scope': 'Descriptive only. Not invariant to heterogeneous unknown variances and not a significance test.',
    'all_groups': [ratio(lag) for lag in (1,2,3)],
    'group_lag1': [ratio(1,g['group']) for g in s['phase_groups']]}
s['method']['maximal_integer_annihilator_dimension_check'] = {
    'phase_raw_rows': s['scope']['raw_rows'] - s['scope']['code_rows_preserved'],
    'physical_integer_dimension': s['scope']['raw_physical_forest_integer_dimension'],
    'phase_difference_rows': s['scope']['same_arc_phase_difference_rows'],
    'complete_annihilator': s['scope']['same_arc_phase_difference_rows'] == s['scope']['raw_rows'] - s['scope']['code_rows_preserved'] - s['scope']['raw_physical_forest_integer_dimension'],
    'rank_evidence': 'Successful SPD Cholesky of D Q D.T, with D A=0 and correct annihilator dimension.'}
s['interpretation'] = {
    'constant_integer_offset_explains_excess': False,
    'time_varying_error_model_inadequacy_supported': True,
    'temporal_coloring_uniquely_established': False,
    'reason': 'Integer-annihilating differences retain excess phase energy, but underestimated independent phase variance also amplifies mandatory negative adjacent-difference correlations. Original-Q score scales are not calibrated significance after amplitude misspecification.',
    'not_identified': ['absolute constant phase bias', 'a unique physical error source', 'beta amplitude and correlation time suitable for navigation', 'integer acceptance reliability'],
    'ten_second_identifiability': 'No fitted likelihood or information-rank evidence separates white amplitude from beta sigma/tau here. tau far below0.2s is white-like; tau above surviving arc/window duration is constant-like or identifies only sigma^2/tau through small increments. Geometry/synchronization can also remain outside the free-baseline subspace.'}
s['raw_noise_source_check'] = {
    'receiver_signal_samples': raw['raw_samples'],
    'original_csv_to_ubx_selected_payloads_identical': all(all(x['selected_payloads_equal']) for x in raw['sources']),
    'selected_payload_count': sum(len(x['selected_payloads_equal']) for x in raw['sources']),
    'source_hashes_match_registry': all(x['csv_hash_matches_pin'] and x['ubx_hash_matches_pin'] for x in raw['sources']),
    'Q_max_abs_reconstruction_difference': max(x['Q_max_abs_difference'] for x in raw['checks']),
    'unit_policy': raw['interpretation']['phase_sigma_policy'],
    'CNO_policy': raw['interpretation']['CNO_policy'],
    'conclusion': 'No field/unit construction error in this fixed window; receiver-reported precision does not ensure environmental errors are fully represented.',
    'details': 'RAW_PHASE_NOISE_CHECK.json and RAW_PHASE_NOISE_ROWS.json'}
s['next_measurement_model_study_not_run'] = {
    'source_defined_windows_s': {'calibration_BY2': [110.0,170.0], 'validation_BY2': [180.0,240.0], 'interval_semantics': 'left closed, right open'},
    'selection': 'Windows fixed before reading their observations or outcomes. PLAN time coverage exists from100.198 to339.998s. No new windows were analyzed in this diagnostic.',
    'independence_boundary': 'Nonoverlapping held-out time blocks with10s separation. Approximate decorrelation follows only for a finite candidate tau<=2s; physical independence is not presumed and longer dependence invalidates that assumption.',
    'models': ['M0: original source Q.', 'M1: original Q plus additive white variance per identifiable physical SD signal group, mapped to DD with the actual target/pivot incidence.', 'M2: M1 plus zero-mean finite-time stationary beta on each physical SD source signal, independent of integer arc identity and with no automatic beta reset at integer slip, covariance sigma_beta_g^2 exp(-abs(dt)/tau), mapped through the same DD incidence; retain integer N and do not add an unrestricted constant beta.'],
    'identifiable_parameters': 'Fit only covariance combinations identifiable after physical integer and geometry elimination. Two receiver white variances with identical DD structure appear only as a sum; do not claim separate receiver estimates. A common tau and group SD amplitudes are a candidate low-dimensional model, not a validated choice.',
    'restricted_likelihood': 'For fixed integer-annihilator D, Qd(theta)=D Qraw(theta) D.T. Profile free per-epoch geometry B by GLS and minimize logdet(Qd)+logdet(B.T inv(Qd) B)+r.T inv(Qd) r. Check projected covariance-derivative rank/profile curvature. Constant components annihilated by D cannot be estimated.',
    'tau_scope': 'Initially study finite resolvable0.2..2s correlation time only. A bound optimum or flat profile means unresolved parameters, not permission to assert a colored source. Subsample-white and slow-constant limits are explicitly outside a separately identified tau claim.',
    'direct_discriminator': 'Predefine nonoverlapping same-physical-relation endpoint intervals at h=0.2,0.4,0.8,1.6s. For each h use source-index anchored disjoint endpoints, preserve the cross-h and state-projection covariance. Compare variogram shapes after original reported heteroscedastic precision and fitted white SD terms: use a quadratic contrast orthogonal to the identifiable white-amplitude derivative span. A colored covariance contributes an h-dependent1-exp(-h/tau) shape; actual projected expectations must be computed rather than substituting this ideal shape.',
    'variogram_full_null_covariance': 'For quadratic statistics V_h=r.T W_h r on one common projected raw/differenced residual vector with covariance R, E[V_h]=tr(W_h R), Cov(V_h,V_k)=2 tr(W_h R W_k R). Overlapping sources across h and all geometry-fit effects remain in R. Parameter-estimation uncertainty must be propagated for calibrated coverage or assessed on held-out blocks.',
    'validation': 'Freeze source-noise parameters from calibration. Evaluate held-out predictive/restricted likelihood, projected innovation covariance and the registered variogram contrast on the validation block. Use the same complete input likelihood and unchanged integer-domain quantile, not selected passing subsets. No ordinary chi-square likelihood-ratio claim at sigma_beta=0 where tau is unidentified.',
    'success_does_not_establish': ['absolute beta means', 'unique multipath attribution', 'AR reliability or navigation accuracy', 'permission to release arbitrary N integrality']}
s['provenance']['postprocessor_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
s['provenance']['scratch_config_sha256'] = hashlib.sha256(a.config.read_bytes()).hexdigest()
(p / 'SUMMARY.json').write_text(json.dumps(s, indent=2, ensure_ascii=False) + '\n')
lines = ['# BY2 fixed first10s: integer-free phase-time diagnostic', '',
'No navigation, reference, integer search, Q change or acceptance-threshold change was performed. All50 built blocks in100.198..109.998s were used.', '',
'## Measured evidence', '',
'1680 original rows contain840 phase rows and41 physical integer coordinates. Exact same-arc differences yield799 rows, D A=0. Keeping all840 code rows gives1639 observations; free3D baselines at50 epochs have rank150, leaving1489 residual degrees of freedom. Full D Q D.T and the full GLS residual covariance are retained.', '',
f"Joint cost: {s['joint_fit']['cost']:.6f} /1489={s['joint_fit']['cost_over_degrees_of_freedom']:.6f}. Code cost {s['joint_fit']['code_cost']:.6f} vs expected {s['joint_fit']['code_expected_cost']:.6f}; phase cost {s['joint_fit']['phase_difference_cost']:.6f} vs expected {s['joint_fit']['phase_expected_cost_after_baseline_fit']:.6f}.", '',
'| Physical signal group | Difference rows | Phase cost / projected expectation |', '|---|---:|---:|']
for g in s['phase_groups']:
    lines.append(f"| {g['group']} | {g['phase_difference_rows']} | {g['full_temporal_Q_residual_cost']:.3f} / {g['null_expected_cost_after_baseline_fit']:.3f} = {g['cost_over_null_expectation']:.3f} |")
lines += ['', 'The six groups share geometry estimation; these are not six independent votes.', '',
'Original RAWX check:100 selected payloads match the original CSV byte-for-byte;2280 admitted receiver-signal samples were checked. Reconstructing all50 Q matrices from original cpStdev, prStdev, wavelength and DD incidence gives maximum absolute difference0. The0.004*cpStdev phase sigma is in cycles and converted once to meters. The phase floor is inactive here. C/N0 and precision time series are saved.', '',
'## What follows and what does not', '',
'Constant integer offsets cannot explain this excess because they were canceled exactly. Constant phase biases are canceled too and remain unidentifiable. There is source evidence of inadequately modeled time-varying phase error, but this10s calculation does not identify a colored beta source or its time constant. Underestimated white variance also increases compulsory negative adjacent-difference correlation. Lag quadratic scores under the already misspecified original Q are descriptive, not calibrated significance.', '',
'The amplitude-normalized lag products are−0.4407,−0.0817,+0.0092 at0.2,0.4,0.6s; nominal projected covariance values are−0.5005,+0.00014,+0.00011. These descriptive values cannot distinguish heterogeneous white variance, colored source, synchronization effects or geometry-model residuals by themselves.', '',
'## One next bounded study, proposed only', '',
'Use BY2[110,170)s for restricted-likelihood calibration and[180,240)s for frozen-parameter validation. Their source coverage exists; their observations were not analyzed here. Compare original Q; Q plus identifiable signal-group SD white noise; and that model plus finite stationary physical-SD-source beta independent of integer arc tokens. Map both added terms through real DD incidence, including shared pivot and time covariance. Two receiver contributions with identical structure are identifiable only through their sum. Preserve N as integers and leave the existing acceptance quantile unchanged.', '',
'Use same-arc nonoverlapping endpoint variograms at predeclared0.2,0.4,0.8,1.6s intervals as the direct white-versus-colored discriminator. Retain the common full projected covariance and use a shape contrast orthogonal to identifiable white-amplitude directions. Do not infer coloring from lag1 negativity. Start with a bounded0.2..2s tau hypothesis; flat/boundary profiles indicate nonidentifiability. The10s validation separation only gives approximate decorrelation under that finite-tau hypothesis.', '',
'Fit by restricted likelihood after integer elimination and free-baseline GLS. Freeze parameters before evaluating held-out predictive likelihood, covariance and variogram contrast. A supported measurement model does not establish integer acceptance reliability or navigation improvement; those remain subsequent common-state tests. Never use the best-integer residual or a newly nonempty domain as the calibration target.', '',
'## Reproduce', '',
'Edit machine paths in scratch_config.json, then run with OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1:', '',
'```sh', 'python scripts/paper_rebuild/diagnose_by_phase_time_difference.py --config scratch_config.json', 'python scripts/paper_rebuild/inspect_by_raw_phase_precision.py --config scratch_config.json', 'python scripts/paper_rebuild/write_by_phase_diagnostic_readout.py --config scratch_config.json', '```', '',
'SUMMARY.json contains scalar results, source hashes and the proposed next study. ROWS_AND_TRANSITIONS.json and DIFFERENCE_DIAGNOSTIC.npz retain exact physical mappings, full Q and projected covariance. RAW_PHASE_NOISE_ROWS.json retains original precision/C/N0 time series. Machine paths are in the scratch config; repository algorithm files were not changed.', '']
(p / 'READOUT.md').write_text('\n'.join(lines))
print(json.dumps({'summary': str(p/'SUMMARY.json'), 'readout': str(p/'READOUT.md'), 'constant_integer_explanation_removed':True, 'colored_tau_identified':False}))
