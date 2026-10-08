"""Checks for candidate bookkeeping and retained continuous relation freedom."""
import unittest

import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.candidate import propose_candidates, relation_parameterization


def abstract_block(time, labels, means):
    """An analytic GLS fixture; not a physical navigation performance case."""
    count = len(labels)
    design = np.eye(count + 3)
    return EpochBlock(time, np.r_[means, [.0, .35, .0]], design[:, :count], design[:, count:],
                      np.diag([.2] * count + [.0001] * 3), tuple(labels))


class JointNavigationCandidatesTest(unittest.TestCase):
    def test_capped_active_set_keeps_dormant_enumerated_support(self):
        proposal = propose_candidates([abstract_block(0., ["a", "b"], [.12, -.2])], np.array([0., .35, 0.]), 4)
        self.assertTrue(proposal.metadata["enumeration_complete"])
        self.assertEqual(len(proposal.active), 4)
        self.assertGreater(len(proposal.dormant), 0)
        self.assertFalse(proposal.metadata["active_support_complete"])
        self.assertEqual(proposal.metadata["remaining_count"], len(proposal.dormant))
        self.assertFalse(proposal.metadata["integer_acceptance_defined"])
        costs = [item.raw_cost for item in (*proposal.active, *proposal.dormant)]
        self.assertEqual(costs, sorted(costs))

    def test_partial_epoch_columns_keep_label_identity(self):
        blocks = [abstract_block(0., ["a", "b"], [.12, -.2]), abstract_block(.2, ["b"], [-.18])]
        proposal = propose_candidates(blocks, np.array([0., .35, 0.]))
        self.assertEqual(proposal.metadata["ambiguity_labels"], ("a", "b"))
        self.assertTrue(proposal.active)
        self.assertEqual(set(proposal.active[0].integer_by_label), {"a", "b"})

    def test_underdetermined_carrier_is_unresolved(self):
        block = EpochBlock(0., np.zeros(2), np.eye(2), np.zeros((2, 3)), np.eye(2), ("a", "b"))
        proposal = propose_candidates([block], np.array([0., .35, 0.]))
        self.assertEqual(proposal.metadata["status"], "UNQUALIFIED_NUMERICS")
        self.assertFalse(proposal.active)
        self.assertFalse(proposal.metadata["enumeration_complete"])
        self.assertIsNone(proposal.metadata["remaining_count"])

    def test_partial_relation_keeps_nullspace_and_fractional_freedom(self):
        C = np.array([[1., -1., 0.], [0., 1., -1.]])
        m = np.array([2., -1.])
        n0, Z = relation_parameterization(C, m)
        self.assertEqual(Z.shape, (3, 1))
        np.testing.assert_allclose(C @ n0, m, atol=1e-12)
        np.testing.assert_allclose(C @ Z, 0., atol=1e-12)
        fractional = n0 + Z @ np.array([.173])
        np.testing.assert_allclose(C @ fractional, m, atol=1e-12)
        self.assertGreater(np.max(abs(fractional - np.round(fractional))), .01)


if __name__ == "__main__":
    unittest.main()
