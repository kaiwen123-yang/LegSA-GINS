"""Physical source-interval conservation, independent of event partitioning."""
import unittest

import numpy as np

from legsa_gins.paper_rebuild.joint_navigation.real_data import _imu_packet


class OriginalIncrementSupportTest(unittest.TestCase):
    def test_nonuniform_intervals_preserve_saved_increments_and_availability(self):
        ends = np.array([.003, .010, .012])
        starts = np.r_[0., ends[:-1]]
        # The source writer's rounded timestamp dt differs slightly from the
        # integer-stamp support; both durations have distinct physical roles.
        writer_dt = np.array([.0030001, .0069998, .0020001])
        rates = np.array([[1., 2., -9., .5, -.2, .1],
                          [-3., 1., -10., -.4, .1, .2],
                          [2., -1., -8., .2, -.3, -.1]])
        source_ids = np.array([[10, 100], [11, 101], [12, 102]])
        event_times = [0., .001, .003, .008, .010, .012]
        accumulated = np.zeros(6)
        used_endpoints = []
        for a, b in zip(event_times[:-1], event_times[1:]):
            packet, support, ids = _imu_packet(
                a, b, ends, rates, source_ids, writer_dt, starts)
            accumulated += np.sum(packet[:, :1]*packet[:, 1:], axis=0)
            used_endpoints.append(float(support[:, 2].max()))
            # The source right endpoint is carried through every fractional
            # split. At .001 and .008 the measurement epoch precedes arrival.
            self.assertTrue(np.all(support[:, 2] >= support[:, 1]))
            np.testing.assert_array_equal(ids, source_ids[np.searchsorted(ends, support[:, 2])])
        np.testing.assert_allclose(accumulated, np.sum(writer_dt[:, None]*rates, axis=0), rtol=0., atol=1e-15)
        self.assertEqual(used_endpoints, [.003, .003, .010, .010, .012])
        self.assertGreater(used_endpoints[0], event_times[1])
        self.assertGreater(used_endpoints[2], event_times[3])


if __name__ == "__main__":
    unittest.main()
