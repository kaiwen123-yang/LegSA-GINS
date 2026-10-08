"""One physical pivot identity consumed and restored in the common graph."""
import unittest

import gtsam
import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.arc_relations import DdArcRelation, SdArcNode
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch


def edge(target, pivot):
    return DdArcRelation(SdArcNode(f"0:{target}:0:0", "continuous"),
                         SdArcNode(f"0:{pivot}:0:0", "continuous")).label


class CarrierGraphTest(unittest.TestCase):
    def test_pivot_coordinates_survive_lag_and_snapshot_without_integer_fix(self):
        branch = NavigationBranch(dict(baseline_body=[0., -.35, 0.],
            carrier_label_mode="physical_sd_arcs", lag_s=.05), use_foot=False)
        baseline = np.array([0., -.35, 0.])

        def consume(t, labels, ambiguity_means, pose_index):
            pose_key, pose = gtsam.symbol("x", pose_index), gtsam.Pose3()
            count = len(labels)
            design = np.vstack([np.eye(3), np.array([[.2, .5, -.1], [-.4, .1, .3]])[:count]])
            integers = np.vstack([np.zeros((3, count)), .19*np.eye(count)])
            y = design @ baseline + integers @ np.array(ambiguity_means)
            block = EpochBlock(t, y, integers, design, np.diag([.2]*3+[.003]*count)**2,
                               tuple(labels), dict(baseline_frame="NED"))
            values = gtsam.Values()
            values.insert(pose_key, pose)
            factors = [gtsam.PriorFactorPose3(pose_key, pose,
                gtsam.noiseModel.Isotropic.Sigma(6, .01))]
            branch.time = t
            times = {pose_key: t}
            branch._carrier(block, pose, pose_key, values, times, factors)
            branch.window.update(factors, values, times, t, retain_keys=branch._retained_keys())
            return pose_key

        old_labels, new_labels = (edge(2, 1), edge(3, 1)), (edge(1, 2), edge(3, 2))
        old_pose = consume(0., old_labels, [7.25, -1.75], 0)
        # The old pivot is absent in one partial packet: C-B survives first.
        # Adding A-B next must add just one independent new coordinate equation.
        consume(.1, [new_labels[1]], [-9.20], 3)
        self.assertEqual(branch.last_carrier_relations["new_coordinate_factors"], 1)
        before = branch.snapshot()
        new_pose = consume(.2, new_labels, [-7.10, -9.20], 1)
        self.assertFalse(branch.window.values.exists(old_pose))
        self.assertEqual(branch.last_carrier_relations["new_coordinate_factors"], 1)
        self.assertTrue(branch.last_carrier_relations["pivot_only_change"])
        self.assertFalse(branch.fixed)
        self.assertFalse(branch._conditioned_labels)
        keys = [branch.ambiguity_keys[label] for label in (*old_labels, *new_labels)]
        mean = np.array([branch.window.values.atVector(key)[0] for key in keys])
        constraint = np.array([[1., 0., 1., 0.], [1., -1., 0., 1.]])
        np.testing.assert_allclose(constraint @ mean, 0., atol=1e-10)
        self.assertGreater(np.max(abs(mean-np.round(mean))), .05)
        # This exercises the no-foot exact-coordinate QR path. The returned
        # covariance must preserve the same exact relation and all cross terms.
        covariance = branch.joint_covariance(keys)
        np.testing.assert_allclose(constraint @ covariance, 0., atol=1e-10)
        self.assertTrue(branch.window.values.exists(new_pose))
        consume(.4, new_labels, [-7.1, -9.2], 2)
        self.assertEqual(branch.last_carrier_relations["new_coordinate_factors"], 0)
        branch.restore(before)
        self.assertEqual(len(branch._carrier_coordinate_constraints), 1)
        self.assertNotIn(new_labels[0], branch.ambiguity_keys)
        self.assertEqual(branch._carrier_relation_tracker.last_time_s, .1)
        consume(.2, new_labels, [-7.10, -9.20], 1)
        replay = np.array([branch.window.values.atVector(branch.ambiguity_keys[label])[0]
                           for label in (*old_labels, *new_labels)])
        np.testing.assert_allclose(replay, mean, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
