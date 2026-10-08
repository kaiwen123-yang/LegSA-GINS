"""Exact relation-space counterexamples; no field or navigation evaluation."""
import unittest

import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.arc_relations import DdArcRelation, SdArcNode
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock, assemble_epochs
from legsa_gins.paper_rebuild.joint_navigation.carrier_relations import (
    CarrierRelationTracker, analyze_relation_transition, reparameterize_epoch_blocks,
)


def node(sv, arc="continuous"):
    return SdArcNode(f"0:{sv}:0:0", arc)


def edge(a, b):
    return DdArcRelation(a, b).label


def analyze(history, current):
    return analyze_relation_transition(history, current, label_mode="physical_sd_arcs")


class CarrierRelationsTest(unittest.TestCase):
    def assert_exact(self, result):
        np.testing.assert_array_equal(result.history_transform @ result.history_incidence,
                                      result.intersection_basis)
        np.testing.assert_array_equal(result.current_transform @ result.current_incidence,
                                      result.intersection_basis)
        np.testing.assert_array_equal(result.current_internal_constraints @ result.current_incidence,
                                      np.zeros((len(result.current_internal_constraints), len(result.nodes)), int))
        for array in (result.current_transform, result.history_transform, result.intersection_basis):
            self.assertEqual(array.dtype.kind, "i")
        self.assertFalse(result.observation_transport_applied)
        self.assertFalse(result.covariance_transformed)
        self.assertFalse(result.integer_acceptance_defined)
        self.assertFalse(result.direction_observability_defined)

    def test_pivot_only_rebase_has_exact_maps_without_integer_values(self):
        a, b, c = (node(k) for k in (1, 2, 3))
        result = analyze([edge(b, a), edge(c, a)], [edge(a, b), edge(c, b)])
        self.assert_exact(result)
        self.assertEqual(result.intersection_rank, 2)
        self.assertEqual(result.continuation_status, "COMPLETE_RELATION_CONTINUATION")
        self.assertTrue(result.pivot_only_change)
        self.assertEqual(len(result.graph_constraints()), 2)
        # The identity also holds for unconstrained float ambiguities, so the
        # transport introduces no integer rounding or false acceptance.
        absolute = np.array([.13, -2.84, 9.91])
        np.testing.assert_allclose(result.current_transform @ (result.current_incidence @ absolute),
                                   result.history_transform @ (result.history_incidence @ absolute))

    def test_new_pivot_leaves_target_difference_but_not_new_integers(self):
        a, b, c, unknown = (node(k) for k in (1, 2, 3, 4))
        result = analyze([edge(b, a), edge(c, a)], [edge(b, unknown), edge(c, unknown)])
        self.assert_exact(result)
        self.assertEqual((result.history_relation_rank, result.current_relation_rank, result.intersection_rank), (2, 2, 1))
        self.assertEqual(result.new_relation_rank, 1)
        self.assertEqual(result.continuation_status, "PARTIAL_HISTORY_CONTINUATION")
        self.assertEqual(np.count_nonzero(result.current_transform[0]), 2)
        self.assertEqual(np.count_nonzero(result.history_transform[0]), 2)
        self.assertFalse(result.pivot_only_change)

    def test_disconnected_gauges_share_a_four_node_contrast(self):
        a, b, c, d = (node(k) for k in (1, 2, 3, 4))
        result = analyze([edge(a, b), edge(c, d)], [edge(a, c), edge(b, d)])
        self.assert_exact(result)
        # Every pair of component intersections is a singleton; simply taking
        # their pairwise difference ranks incorrectly reports zero here.
        self.assertEqual(result.intersection_rank, 1)
        self.assertEqual(np.count_nonzero(result.intersection_basis[0]), 4)

    def test_changed_arc_token_never_inherits_old_integer(self):
        a, b = node(1), node(2)
        result = analyze([edge(a, b)], [edge(node(1, "after_slip"), b)])
        self.assert_exact(result)
        self.assertEqual(result.intersection_rank, 0)
        self.assertEqual(result.continuation_status, "NO_SURVIVING_HISTORY_RELATION")
        self.assertEqual(len(result.new_nodes), 1)
        self.assertFalse(result.graph_constraints())

    def test_redundant_current_rows_get_exact_cycle_identity(self):
        a, b, c = (node(k) for k in (1, 2, 3))
        result = analyze([], [edge(a, b), edge(b, c), edge(a, c)])
        self.assert_exact(result)
        self.assertEqual(result.current_relation_rank, 2)
        self.assertEqual(result.current_internal_constraints.shape, (1, 3))
        self.assertEqual(result.graph_constraints()[0]["kind"], "current_cycle")

    def test_missing_packet_does_not_shrink_history_and_closed_pivot_can_cancel(self):
        a, b, c = (node(k) for k in (1, 2, 3))
        history = [edge(b, a), edge(c, a)]
        tracker = CarrierRelationTracker(label_mode="physical_sd_arcs", history_labels=history)
        missing = tracker.advance([], time_s=1., observation_available=False)
        self.assertEqual(missing.continuation_status, "NO_CURRENT_PHASE_RELATIONS")
        self.assertEqual(tracker.history_labels, tuple(history))
        tracker.retire([("physical_sd_arc", a.signal, a.arc)])
        partial = tracker.advance([edge(c, b)], time_s=2.)
        self.assert_exact(partial)
        self.assertEqual(partial.intersection_rank, 1)
        self.assertEqual(partial.unavailable_history_rank, 1)
        with self.assertRaisesRegex(ValueError, "resurrect"):
            tracker.advance(history, time_s=3.)

    def test_synthetic_adapter_is_explicit_and_does_not_parse_physical_json(self):
        result = analyze_relation_transition(["a", "b"], ["b", "c"], label_mode="synthetic_scalar")
        self.assert_exact(result)
        self.assertEqual((result.history_relation_rank, result.current_relation_rank, result.intersection_rank), (2, 2, 1))
        self.assertFalse(result.graph_constraints())  # b is already the same key
        with self.assertRaises(ValueError):
            analyze_relation_transition([], [edge(node(1), node(2))], label_mode="synthetic_scalar")
        with self.assertRaises(ValueError):
            analyze_relation_transition([], ["a"], label_mode="physical_sd_arcs")

    def test_arrived_pivot_chain_has_one_integer_lattice_and_unchanged_full_Q(self):
        a, b, c, d, e = (node(k) for k in (1, 2, 3, 4, 5))
        epochs = ([edge(b, a), edge(c, a)],
                  [edge(a, b), edge(d, b)],
                  [edge(b, c), edge(d, c), edge(e, c)])
        potentials = {a: -3, b: 11, c: 5, d: -7, e: 17}
        integer = lambda label: potentials[DdArcRelation.from_label(label).target]-potentials[DdArcRelation.from_label(label).pivot]
        blocks = []
        baseline = np.array([.17, -.23, .201])
        for index, labels in enumerate(epochs):
            count = len(labels)
            design = np.arange((3+count)*3).reshape(3+count, 3)*.013 + .07
            ambiguity = np.vstack([np.zeros((3, count)), .19*np.eye(count)])
            root = np.eye(3+count)+.07*np.tril(np.ones((3+count, 3+count)), -1)
            covariance = root @ root.T
            y = design @ baseline + ambiguity @ np.array([integer(label) for label in labels])
            blocks.append(EpochBlock(1.+index*.2, y, ambiguity, design, covariance,
                                     tuple(labels), dict(baseline_frame="NED")))
        result = reparameterize_epoch_blocks(blocks, available_time_s=1.4)
        self.assertEqual(result.basis_labels, (edge(b, a), edge(c, a), edge(d, b), edge(e, c)))
        self.assertEqual(result.actual_label_to_basis.shape, (7, 4))
        self.assertEqual(result.basis_metadata["gauge_variable_count"], 0)
        selected = result.basis_metadata["basis_indices_in_observed_labels"]
        np.testing.assert_array_equal(result.actual_label_to_basis[selected], np.eye(4, dtype=int))
        physical = np.array([integer(label) for label in result.observed_labels])
        basis_integer = np.array([integer(label) for label in result.basis_labels])
        np.testing.assert_array_equal(result.actual_label_to_basis @ basis_integer, physical)
        relations = analyze([], result.observed_labels)
        np.testing.assert_array_equal(relations.current_internal_constraints @ result.actual_label_to_basis,
                                      np.zeros((3, 4), dtype=int))
        for original, changed, mapping in zip(blocks, result.blocks, result.epoch_label_to_basis):
            self.assertIs(changed.y, original.y)
            self.assertIs(changed.B, original.B)
            self.assertIs(changed.Q, original.Q)
            np.testing.assert_allclose(changed.A @ basis_integer + changed.B @ baseline, original.y,
                                       rtol=0., atol=1e-14)
            future_columns = np.array(result.basis_metadata["basis_first_observed_times_s"]) > original.time_s
            self.assertFalse(np.any(mapping[:, future_columns]))
            self.assertFalse(changed.metadata["observation_transport_applied"])
            self.assertFalse(changed.metadata["covariance_transformed"])
        # This is the actual existing propose_candidates assembly interface,
        # not a separate result representation or a numerical solver run.
        assembled = assemble_epochs(result.blocks)
        self.assertEqual(assembled.ambiguity_labels, result.basis_labels)
        np.testing.assert_allclose(assembled.A @ basis_integer + assembled.B @ np.tile(baseline, 3),
                                   assembled.y, rtol=0., atol=1e-14)


if __name__ == "__main__":
    unittest.main()
