"""The 28 v2.1 figures; existing v2 drawings remain immutable."""
from __future__ import annotations

from copy import copy
from functools import wraps

import numpy as np
import pandas as pd

from . import protocol_v2_figures as old
from .protocol_v2_data import ALL, MAIN, EvidenceUnavailable
from .protocol_v21_data import BODY, COMPARISON, GRID, LADDER, RESIDUALS

COLORS, METRICS = old.COLORS, old.METRICS
NEW_METHODS = [method for method in ALL if method != 'F01']
VARIANTS = ['V0', 'V1', 'V2', 'V2i', 'V2s', 'V2is']


def _edition(drawer):
    @wraps(drawer)
    def draw(bundle):
        figure, caption = drawer(bundle)
        caption = caption.replace('protocol-v2 ', 'protocol-v2.1 ').replace('protocol v2 ', 'protocol v2.1 ')
        return figure, caption + ' Protocol v2.1 figure edition.'
    return draw


class _Sources:
    """Explicit edition-only member binding; absence never falls back to v2."""
    def __init__(self, package, mapping):
        self.package, self.mapping = package, mapping

    def table(self, name):
        return self.package.table(self.mapping.get(name, name))

    def __getattr__(self, name):
        return getattr(self.package, name)


def _rebound(drawer, bundle, mapping):
    view = copy(bundle)
    view.p = _Sources(bundle.p, mapping)
    figure, caption = drawer(view)
    # The source reader and mutable notes lists are shared; any scalar source
    # disclosure updated by a reused drawer must also reach the real bundle.
    bundle.controlled_degradation_used |= view.controlled_degradation_used
    return figure, caption


def _failure_pair(bundle, core, failures):
    """Bind the first CORE F04 failure and its F02 control to new native rows."""
    anchor = failures.sort_values(['case_id', 'dataset_id', 'run_id']).iloc[0]
    pair = core[(core.dataset_id == anchor.dataset_id) & (core.case_id == anchor.case_id) &
                core.method_id.isin(['F02', 'F04'])].sort_values('method_id')
    if len(pair) != 2 or set(pair.method_id) != {'F02', 'F04'}:
        raise EvidenceUnavailable('New CORE failure lacks exactly one same-case F02 control')
    manifest = bundle.p.table('supplemental/FAILURE_SERIES/SERIES_MANIFEST.csv')
    required = {'run_id', 'dataset_id', 'case_id', 'method_id', 'effective_configuration_id',
                'evaluation_status', 'evaluator_version', 'terminal_status', 'domain',
                'source_protocol', 'formal_F01_reused', 'member', 'status'}
    if not required <= set(manifest):
        raise EvidenceUnavailable('v2.1 native failure manifest lacks required identity/status fields')
    selected = []
    for _, native in pair.iterrows():
        match = manifest
        for key in ('run_id', 'dataset_id', 'case_id', 'method_id', 'effective_configuration_id', 'evaluation_status'):
            match = match[match[key] == native[key]]
        if len(match) != 1:
            raise EvidenceUnavailable('Native failure timeline does not exactly match the new CORE row: '+native.method_id)
        source = match.iloc[0]
        expected_terminal = ('COMPLETED' if native.evaluation_status == 'COMPLETED'
                             else 'ALGORITHM_FAILURE_ALL_YAW_REJECTED')
        if (source.domain != 'CORE' or source.evaluator_version != 'v3' or source.terminal_status != expected_terminal or
                source.source_protocol != 'SENSOR_MODEL_V2_1' or str(source.formal_F01_reused).lower() != 'false'):
            raise EvidenceUnavailable('Native failure pair must use exact new v2.1 CORE sources')
        if source.status not in ('OK', 'UNAVAILABLE'):
            raise EvidenceUnavailable('Unknown native failure trace availability')
        if source.status == 'OK':
            expected_member = 'supplemental/FAILURE_SERIES/'+native.run_id+'.csv.gz'
            if source.member != expected_member:
                raise EvidenceUnavailable('Native failure trace member does not belong to this run')
            identity = bundle.p.manifest['members'].get(source.member, {})
            if identity.get('source_protocol') != 'SENSOR_MODEL_V2_1':
                raise EvidenceUnavailable('Native failure member is not a new v2.1 source')
        selected.append(match)
    selected = pd.concat(selected).sort_values('method_id')
    selected.attrs = dict(manifest.attrs)
    bundle.p.use(selected)
    bundle.disclose(pair, True)
    return anchor, selected


def _failure_counts(core, failed, *, detail):
    figure, axes = old.canvas(1, 2, 3.5)
    counts = [int(failed.profile.eq(method).sum()) for method in ALL]
    axes[0, 0].bar(range(len(ALL)), counts, color=[COLORS[m] for m in ALL])
    axes[0, 0].set_xticks(range(len(ALL)), ALL, rotation=45, ha='right')
    axes[0, 0].set_ylabel('v2.1 core algorithm failures (count)')
    axes[0, 0].set_ylim(0, max(1, max(counts) * 1.2))
    for i, value in enumerate(counts):
        axes[0, 0].text(i, value + .025, str(value), ha='center', va='bottom', fontsize=7)
    denominator = int(core.profile.eq('F04').sum())
    axes[0, 1].axis('off')
    axes[0, 1].text(.5, .65, 'CORE F04 all-yaw-rejected runs\n'+str(counts[ALL.index('F04')])+' / '+str(denominator),
                    ha='center', va='center', transform=axes[0, 1].transAxes, fontsize=10)
    axes[0, 1].text(.5, .28, detail, ha='center', va='center',
                    transform=axes[0, 1].transAxes, fontsize=8, wrap=True)
    return figure


def mfig14(bundle):
    core = bundle.core(ALL)
    if not core.evaluation_status.isin(['COMPLETED', 'NOT_RUN_ALGORITHM_FAILURE']).all():
        raise EvidenceUnavailable('v2.1 failure accounting contains a technical or missing terminal')
    failed = core[core.evaluation_status == 'NOT_RUN_ALGORITHM_FAILURE']
    f04 = failed[failed.profile == 'F04']
    if not f04.empty:
        anchor, selected = _failure_pair(bundle, core, f04)
        missing = selected[selected.status == 'UNAVAILABLE'].method_id.tolist()
        bundle.notes.append({'scope': 'CORE', 'selected_case_id': anchor.case_id,
            'selected_dataset_id': anchor.dataset_id, 'selected_run_ids': selected.run_id.tolist(),
            'new_F04_failure_count': len(f04), 'old_failure_timeline_reused': False,
            'native_trace_unavailable_methods': missing})
        if missing:
            figure = _failure_counts(core, failed, detail=anchor.case_id+'\nNative failure timeline\nUNAVAILABLE: '+', '.join(missing))
            return figure, ('New v2.1 CORE failure accounting; first F04 failure '+anchor.case_id+
                '. Its native timeline/control is explicitly UNAVAILABLE for '+', '.join(missing)+
                '. The case is not replaced by another example; no old timeline is reused.')
        frames = []
        for _, row in selected.iterrows():
            frame = bundle.p.use(bundle.p.table(row.member))
            if not {'gnss_time', 'yaw_mode'} <= set(frame):
                raise EvidenceUnavailable('Native failure trace lacks its original time/action columns')
            times = pd.to_numeric(frame.gnss_time, errors='coerce').to_numpy(float)
            if not len(times) or not np.isfinite(times).all() or np.any(np.diff(times) < 0):
                raise EvidenceUnavailable('Native failure trace has empty/nonfinite/nonmonotonic times')
            frames.append((row, frame))
        figure, axes = old.canvas(2, 1, 4.6)
        for row, frame in frames:
            accepted = frame.yaw_mode.isin(['NORMAL', 'DOWNWEIGHT'])
            rejected = frame.yaw_mode.eq('REJECT')
            offset = 0 if row.method_id == 'F02' else 2
            for delta, mask, marker in ((0, accepted, 'o'), (1, rejected, 'x')):
                if mask.any():
                    axes[0, 0].scatter(frame.loc[mask, 'gnss_time'], np.full(mask.sum(), offset+delta),
                                      marker=marker, s=6, color=COLORS[row.method_id], label=row.method_id)
            axes[1, 0].step(frame.gnss_time, accepted.astype(int).cumsum(), where='post', **old.linekw(row.method_id))
            axes[1, 0].step(frame.gnss_time, rejected.astype(int).cumsum(), where='post',
                            color=COLORS[row.method_id], ls=':', label=row.method_id+' rejected')
        axes[0, 0].set_yticks([0, 1, 2, 3], ['F02 accepted', 'F02 rejected', 'F04 accepted', 'F04 rejected'])
        axes[0, 0].set(ylim=(-.4, 3.4), xlabel='Time (s)')
        axes[1, 0].set(xlabel='Time (s)', ylabel='Cumulative yaw actions (count)')
        for ax in axes.flat:
            old.legend(ax)
        return figure, (anchor.case_id+': first new v2.1 CORE F04 ALL_YAW_REJECTED case with the exact '
            'same-dataset/case new F02 control. Native yaw_mode defines accepted (NORMAL/DOWNWEIGHT) and '
            'rejected actions. Yaw residuals are not plotted. No pre-correction timeline is reused.')
    figure = _failure_counts(core, failed, detail='Native failure timeline\nNot applicable')
    denominator = int(core.profile.eq('F04').sum())
    bundle.notes.append({'new_F04_failure_count': 0, 'core_F04_run_count': denominator,
                         'old_failure_timeline_reused': False, 'zero_is_failure_count_not_error': True})
    return figure, ('New v2.1 core terminal accounting. F04 has no ALL_YAW_REJECTED run within the 541-case core, so its '
        'failure timeline is not applicable. Zero labels count algorithm failures; they do not '
        'represent navigation-error values. No pre-correction failure timeline is reused.')


def mfig16(bundle):
    for dataset in ('BY2', 'BY2H', 'BY2O'):
        quality = bundle.p.table('supplemental/SEQUENCE_QUALITY/' + dataset + '.csv')
        values = pd.to_numeric(quality.yaw_std_deg, errors='raise').to_numpy(float)
        if not len(values) or not np.all(values == 2.933193):
            raise EvidenceUnavailable('Heading-provider quality does not use v2.1 yaw sigma')
    figure, caption = old.mfig16(bundle)
    return figure, caption.replace('constant 1.5°', 'constant 2.933193°') + (
        ' The scheme-C soft threshold remains 3.0°; the registered sigma is below it.')


def mfig17(bundle):
    frame = bundle.p.table(LADDER)
    if 'evaluator_version' in frame:
        frame = frame[frame.evaluator_version == 'v3']
    expected = {(variant, method) for variant in VARIANTS for method in ('F03', 'A04')}
    if (len(frame) != 12 or set(zip(frame.variant_id, frame.method_id)) != expected or
            set(frame.dataset_id) != {'BY2'} or not frame.evaluation_status.eq('COMPLETED').all()):
        raise EvidenceUnavailable('v2.1 error-budget ladder must contain twelve completed BY2 runs')
    bundle.p.use(frame)
    figure, axes = old.canvas(1, 3, 3.8)
    for ax, (metric, label) in zip(axes[0], METRICS):
        for method, marker in [('F03', 'o'), ('A04', 's')]:
            values = frame[frame.method_id == method].set_index('variant_id').loc[VARIANTS, metric].to_numpy(float)
            if not np.isfinite(values).all():
                raise EvidenceUnavailable('Nonfinite v2.1 ladder metric')
            ax.plot(range(6), values, marker=marker, ms=3, **old.linekw(method))
        ax.set_xticks(range(6), VARIANTS, rotation=35, ha='right')
        ax.set_ylabel(label)
        ax.set_ylim(bottom=0)
        old.legend(ax)
    return figure, ('BY2 error-budget ladder: V0, V1, V2, V2i, V2s and V2is, each for F03 and A04, '
        'under the registered v2.1 HV/RP/yaw-sigma corrections and evaluator v3. Each variant retains '
        'its original IMU processing, noise settings and window. Values are complete-run frozen RMSEs; '
        'steps are not independent additive uncertainty terms. No earlier BY2H/BY2O ladder result is substituted.')


def mfig18(bundle):
    frame = bundle.p.table(BODY)
    selected = frame[frame.method_id.isin(MAIN)]
    if (len(selected) != 15 or selected.duplicated(['dataset_id', 'method_id']).any() or
            set(selected.dataset_id) != {'BY2', 'BY2H', 'BY2O'}):
        raise EvidenceUnavailable('v2.1 body-frame sidecars lack the fifteen displayed sequence/profile rows')
    if 'std_ddof' in frame and not pd.to_numeric(selected.std_ddof).eq(0).all():
        raise EvidenceUnavailable('Body-frame spread no longer uses the frozen population standard deviation')
    figure, caption = _rebound(old.mfig18, bundle, {old.CAL + '08_AGGREGATE/v3/BODY_FRAME_BIAS.csv': BODY})
    return figure, caption + ' The four changed displayed profiles use new v2.1 sidecars; formal F01 uses its unchanged v2 output.'


def mfig19(bundle):
    frame = bundle.p.table(GRID)
    if (len(frame) != 9 or not frame.method_id.eq('A04').all() or
            set(pd.to_numeric(frame.abstd_mGal)) != {77.8, 778., 7780.} or
            set(pd.to_numeric(frame.vrw_mps_sqrt_hour)) != {.077, .77, 7.7}):
        raise EvidenceUnavailable('v2.1 nine-grid identity or frozen noise settings differ')
    return _rebound(old.mfig19, bundle,
        {old.PARITY + '13_NOISE_MODEL_SENSITIVITY/08_AGGREGATE/v3/SENSITIVITY_GRID.csv': GRID})


def residual_pairs(frame, sensor, axis, statistic):
    """Select exact pre/post registered scalar pairs without recomputing them."""
    selected = frame[(frame.sensor == sensor) & (frame.axis == axis) & (frame.statistic == statistic)]
    if selected.empty or set(selected.correction_stage) != {'before', 'v21_final'}:
        raise EvidenceUnavailable('Exact before/final residual scalars unavailable: ' + sensor + '/' + axis)
    keys = ['dataset_id', 'n'] if sensor == 'HV' else ['dataset_id', 'window_id', 'window_start_s', 'window_end_s', 'n']
    if selected.duplicated(keys + ['correction_stage']).any():
        raise EvidenceUnavailable('Duplicate residual source identity')
    paired = selected.pivot(index=keys, columns='correction_stage', values='value').reset_index()
    if not np.isfinite(paired[['before', 'v21_final']].to_numpy(float)).all():
        raise EvidenceUnavailable('Missing or nonfinite residual pair')
    expected = 3 if sensor == 'HV' else 4
    if len(paired) != expected or set(paired.dataset_id) != {'BY2', 'BY2H', 'BY2O'}:
        raise EvidenceUnavailable('Residual sequence/window coverage differs from preregistration')
    if sensor == 'RP':
        identities = set(zip(paired.dataset_id, paired.window_id))
        if identities != {('BY2', 'first_1000'), ('BY2H', 'first_1000'),
                          ('BY2O', 'first_1000'), ('BY2O', 'BY2O_standing')}:
            raise EvidenceUnavailable('RP windows changed or were pooled')
        order = {('BY2', 'first_1000'): 0, ('BY2H', 'first_1000'): 1,
                 ('BY2O', 'first_1000'): 2, ('BY2O', 'BY2O_standing'): 3}
        paired = paired.iloc[sorted(range(len(paired)), key=lambda i:
            order[(paired.iloc[i].dataset_id, paired.iloc[i].window_id)])].reset_index(drop=True)
    return selected, paired


def mfig20(bundle):
    samples = bundle.p.use(bundle.p.table(old.CAL + '00_CALIBRATION/LAG_VARIANCE_FIT.csv'))
    parameters = bundle.p.use(bundle.p.table(old.CAL + '00_CALIBRATION/CALIBRATED_PARAMETERS.csv'))
    residuals = bundle.p.table(RESIDUALS)
    figure, axes = old.canvas(2, 3, 6.5)
    for ax, axis in zip(axes[0], ['north', 'east', 'up']):
        selected, parameter = samples[samples.axis == axis], parameters[parameters.axis == axis]
        if axis == 'up' and (selected.empty or parameter.empty):
            selected, parameter = samples[samples.axis == 'down'], parameters[parameters.axis == 'down']
        if selected.empty or len(parameter) != 1:
            raise EvidenceUnavailable('Frozen IMU regression axis unavailable')
        x = pd.to_numeric(selected.lag_s).to_numpy(float)
        y = pd.to_numeric(selected.variance_m2ps2).to_numpy(float)
        ax.plot(x, y, 'o', color=COLORS['A04'], ms=3, label='Observed')
        endpoints = np.array([x.min(), x.max()])
        row = parameter.iloc[0]
        ax.plot(endpoints, float(row.q_m2ps3)*endpoints+float(row.c_m2ps2),
                color=COLORS['F04'], label='Frozen qτ + c')
        ax.set(xlabel='Lag τ (s)', ylabel=axis.title() + ' residual variance (m²/s²)')
        old.legend(ax)
    specs = [('HV', 'horizontal', 'sigma_HV_mps', 'm/s', 'HV residual scale (m/s)'),
             ('RP', 'roll', 'mean', 'deg', 'Static roll residual mean (°)'),
             ('RP', 'pitch', 'mean', 'deg', 'Static pitch residual mean (°)')]
    for ax, (sensor, axis, statistic, unit, label) in zip(axes[1], specs):
        selected, paired = residual_pairs(residuals, sensor, axis, statistic)
        if set(selected.unit) != {unit}:
            raise EvidenceUnavailable('Residual unit mismatch')
        bundle.p.use(selected)
        x = np.arange(len(paired))
        ax.plot(x-.08, paired.before, 'o', color=COLORS['A04'], ms=4, label='v2 pre-correction')
        ax.plot(x+.08, paired.v21_final, 's', mfc='none', color=COLORS['F04'], ms=4, label='v2.1')
        for index, row in paired.iterrows():
            ax.plot([index-.08, index+.08], [row.before, row.v21_final], color='#aaaaaa', lw=.7)
        if sensor == 'HV':
            labels = paired.dataset_id.tolist()
            ax.set_ylim(bottom=0)
        else:
            labels = [row.dataset_id + ('\nstanding' if row.window_id == 'BY2O_standing' else '\nfirst 1000')
                      for row in paired.itertuples()]
            ax.axhline(0, color='#555555', lw=.7)
        ax.set_xticks(x, labels)
        ax.set_ylabel(label)
    figure.legend(*axes[1, 0].get_legend_handles_labels(), loc='upper center',
                   bbox_to_anchor=(.56, 1.01), ncol=2, fontsize=8)
    return figure, ('Top: unchanged BY2 IMU lag-variance observations and accepted qτ+c coefficients; '
        'no regression is refitted. Bottom: HV residual scale σ_HV from P11b H-C before correction '
        'and the final scaled v2.1 provider on the same mask, followed by roll/pitch mean residuals '
        'against gravity for all four registered static windows. RP pairs preserve each window name, '
        'bounds and sample count; no windows are pooled. HV inverse-scaled H-A statistics belong '
        'to the reproduction gate and do not substitute for the final provider residuals.')


def mfig22(bundle):
    table = bundle.p.table(COMPARISON)
    figure, axes = old.canvas(1, 2, 5.0)
    for ax, metric, label in [(axes[0, 0], 'horizontal_rmse_m', 'Median horizontal RMSE (m)'),
                             (axes[0, 1], 'yaw_rmse_deg', 'Median yaw RMSE (°)')]:
        selected = table[(table.evaluator_version == 'v3') & (table.domain == 'CORE') &
            (table.dataset_id == 'BY2') & (table.scope == 'ALL') & (table.statistic == 'median') &
            (table.metric_name == metric) & table.method_id.isin(NEW_METHODS)]
        if len(selected) != 10 or selected.method_id.duplicated().any():
            raise EvidenceUnavailable('v2 to v2.1 comparison requires all ten exact profile rows')
        bundle.p.use(selected)
        selected = selected.set_index('method_id').loc[NEW_METHODS]
        labels = []
        for i, (method, row) in enumerate(selected.iterrows()):
            count = int(row.paired_finite_count)
            labels.append(method + '  n=' + str(count) + '/' + str(int(row.registered_case_count)))
            values = np.array([row.v2_value, row.v21_value], float)
            if count and np.isfinite(values).all():
                ax.plot(values, [i, i], color='#bbbbbb', lw=1)
                ax.plot(values[0], i, 'o', color=COLORS['A04'], ms=4, label='v2 pre-correction' if i == 0 else None)
                ax.plot(values[1], i, 's', mfc='none', color=COLORS['F04'], ms=4, label='v2.1' if i == 0 else None)
            else:
                ax.text(.02, i, 'Unavailable', transform=ax.get_yaxis_transform(), va='center', fontsize=7)
        ax.set_yticks(range(10), labels)
        ax.set_xlabel(label)
        ax.set_xlim(left=0)
        ax.invert_yaxis()
    figure.legend(*axes[0, 0].get_legend_handles_labels(), loc='upper center',
                   bbox_to_anchor=(.57, 1.02), ncol=2, fontsize=8)
    return figure, ('Protocol v2 pre-correction and v2.1 core medians for all ten rerun configurations, '
        'evaluator v3. Each pair uses identical finite successful case membership in both editions; '
        'n is the paired finite count over the registered core denominator. Algorithm failures and '
        'missing metrics are counted separately and never converted to error values. F01 is unchanged '
        'and omitted from this correction comparison; no direction of change is interpreted.')


FIGURES = {key: (title, _edition(drawer), kind, gps, tim)
           for key, (title, drawer, kind, gps, tim) in old.FIGURES.items() if key != 'MFIG21'}
for key, title, drawer in (
    ('MFIG14', 'All-yaw-rejected accounting and native timeline', mfig14),
    ('MFIG16', 'Yaw errors and corrected heading-provider quality', mfig16),
    ('MFIG17', 'BY2 error-budget ladder under v2.1', mfig17),
    ('MFIG18', 'Three-sequence body-frame bias under v2.1', mfig18),
    ('MFIG19', 'Nine-setting noise sensitivity under v2.1', mfig19),
    ('MFIG20', 'IMU calibration and HV/RP residual corrections', mfig20),
    ('MFIG22', 'Protocol v2 to v2.1 ten-configuration comparison', mfig22),
):
    _, _, kind, gps, tim = FIGURES[key]
    FIGURES[key] = title, _edition(drawer), kind, gps, tim

assert len(FIGURES) == 28 and 'MFIG21' not in FIGURES
