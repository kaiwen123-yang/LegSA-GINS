"""Pure validation fixtures; no native call and no historical payload."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
import analyze_schedule as s


class ScheduleTests(unittest.TestCase):
    def test_original_time_predicate_endpoints(self):
        tol = 1 / 1024
        self.assertEqual(s.time_branch(1, 2, 1, tol), 1)
        self.assertEqual(s.time_branch(1, 2, 2 + tol, tol), 2)
        self.assertEqual(s.time_branch(1, 2, 1 - tol, tol), 0)  # first endpoint is strict
        self.assertEqual(s.time_branch(1, 2, 1.5, tol), 3)

    def test_window_denominators(self):
        self.assertEqual(s.windows(196.2, 'A1'), ['full', 'during'])
        self.assertEqual(s.windows(216.2, 'A2'), ['full', 'after'])
        self.assertEqual(s.windows(340, 'A2'), ['full', 'after'])
        self.assertEqual(s.windows(340.1, 'A2'), [])
        self.assertEqual(s.windows(200, 'C00'), ['full'])

    def test_hv_invalid_flag_is_not_qualified(self):
        row = {'update_flag': False, 'source_status': 'active', 'diagnostic_only': False, 'go2_velocity_truth_claim': False}
        self.assertFalse(s.candidate_quality('go2_horizontal_velocity', {'match_found': True, 'selected_input': row}, {'hv_horizontal_enabled': True}))

    def test_entry_blocked_distinct_from_unavailable_and_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); log = root / 'observer'; log.mkdir(); output = root / 'analysis'; output.mkdir(); public = root / 'public'; public.mkdir()
            counters = dict.fromkeys(['position_update_count', 'receiver_velocity_update_count', 'dual_yaw_accepted_count',
                'raw_doppler_update_count', 'go2_roll_pitch_update_count', 'go2_horizontal_velocity_update_count'], 0)
            (root / 'RUN_MANIFEST.json').write_text(json.dumps(counters))
            ctx = {'gnss_input_seq': 1, 'imu_previous_time': 199.99, 'imu_current_time': 200.005, 'res': 0, 'gnss_time': 200}
            config = {'TIME_ALIGN_ERR': .001, 'raw_doppler_min_sat': 5, 'receiver_velocity_enabled': True, 'dual_yaw_enabled': True, 'hv_horizontal_enabled': True}
            rp = {'match_found': True, 'config_enabled': True, 'solver_enabled': True, 'loaded_rows': 1, 'selected_row_id': 0,
                  'selected_input': {'source_status': 'active', 'std_roll_rad': .01, 'std_pitch_rad': .01}}
            unavailable = {'match_found': False, 'config_enabled': True, 'solver_enabled': True, 'loaded_rows': 2, 'selected_row_id': -1}
            disabled = dict(unavailable, config_enabled=False)
            gnss = {'time': 200, 'has_position': False, 'has_velocity': False, 'has_yaw': False, 'flags_or': False}
            payloads = [('OBSERVER_BEGIN', {}), ('CONFIGURATION', {'context': ctx, 'snapshot': config}),
                        ('GNSS_INPUT', {'context': ctx, 'snapshot': {'effective': gnss, 'auxiliary_candidates': {'raw_doppler': disabled, 'go2_roll_pitch': rp, 'go2_horizontal_velocity': unavailable}}}),
                        ('IMU_OPPORTUNITY', {'context': ctx, 'snapshot': {'initialized': True, 'reason': 'GNSS_ALL_FLAGS_FALSE', 'res': 0, 'gnss': gnss}}),
                        ('OBSERVER_END', {'prior_event_count': 4})]
            rows = [dict(event_seq=i, run_id='FIXTURE', event=name, data=data) for i, (name, data) in enumerate(payloads, 1)]
            path = log / 'events.jsonl'; path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            item = dict(run_id='FIXTURE', group='A1', method_id='A04', data_mode='synthetic_parser_fixture', semisynthetic_data_used='False')
            s.analyze(path, item, output, public)
            with (public / 'FIXTURE_SCHEDULING.csv').open() as stream:
                result = {r['source']: r for r in csv.DictReader(stream) if r['window'] == 'during'}
            self.assertEqual(result['go2_attitude_roll_pitch']['qualified_but_entry_blocked_events'], '1')
            self.assertEqual(result['go2_horizontal_velocity']['qualified_but_entry_blocked_events'], '0')
            self.assertEqual(result['go2_horizontal_velocity']['config_enabled_no_usable_candidate_events'], '1')
            self.assertEqual(result['raw_doppler_velocity']['disabled_by_config_events'], '1')
            self.assertEqual(result['raw_doppler_velocity']['qualified_but_entry_blocked_events'], '0')


if __name__ == '__main__':
    unittest.main()
