"""Causal reference scheduling; no source-selection accuracy claim."""
import unittest

import numpy as np
from gtsam.symbol_shorthand import X

from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator
from test_joint_shared_chart import stationary_event


class JointSharedReferenceTest(unittest.TestCase):
    def test_nonlinear_reference_updates_other_models_and_can_return_to_fixed(self):
        metadata = dict(baseline_body=[0., -.35, 0.], lag_s=.25,
                        support_inference="shared_linearization")
        navigator = JointNavigator(metadata, "U3")
        events = [stationary_event(index, range(4)) for index in range(3)]
        for foot in events[1]["feet"]:
            foot["point_body"] += np.array([.03, .02, 0.])
        saved = {}

        def observe(index, event, output, policy, integers):
            if index == 0:
                # Supply an already reconstructed reference to isolate the
                # scheduling mechanism from physical-model selection. Choosing
                # the second track requires reordering the next event's work.
                identity = next(key for key in navigator.support_tracks
                                if key.endswith(":relative_release"))
                track = navigator.support_tracks[identity]
                navigator._expand_support_history(track, index, event["time_s"])
                navigator.linearization_reference_identity = identity
                saved.update(identity=identity, tracks=set(navigator.support_tracks),
                             past=navigator.anchor_history[0], background=navigator.branches[0])
                return

            identity = saved["identity"]
            reference = navigator.support_tracks[identity]
            charts = navigator.anchor_history[index]
            self.assertEqual(set(charts), {"step", "conditioned"})
            self.assertEqual(set(navigator.support_tracks), saved["tracks"])
            self.assertIs(navigator.branches[0], saved["background"])
            self.assertIs(navigator.anchor_history[0], saved["past"])
            common = next(track for key, track in navigator.support_tracks.items()
                          if key.endswith(":common_translation_release"))
            self.assertTrue(common.navigator.branches[0].window.gaussian_only)
            branches = [navigator.branches[0],
                        *[track.navigator.branches[0] for track in navigator.support_tracks.values()]]
            self.assertTrue(all(branch.predictive_frontier == index
                                and branch.predictive_row_count == 9 * index for branch in branches))
            self.assertTrue(all(navigator._same_predictive_rows(track.navigator)
                                for track in navigator.support_tracks.values()))
            self.assertFalse(any(decision["kind"] == "PREDICTIVE_SUPPORT_MODEL_SELECTED"
                                 for decision in navigator.decisions))

            if index == 1:
                self.assertTrue(all(anchor["reference_support_identity"] == identity
                                    for phase in charts.values() for anchor in phase))
                np.testing.assert_allclose(charts["step"][0]["values"].atPose3(X(index)).matrix(),
                                           reference.navigator.branches[0].pose.matrix(), atol=1e-12)
                self.assertEqual(common.navigator.branches[0].linearization_scope["reference_support_identity"],
                                 identity)
                distance = np.linalg.norm(charts["step"][0]["values"].atPose3(X(index)).translation()
                                          - navigator.branches[0].pose.translation())
                self.assertGreater(distance, 1e-6)
                self.assertEqual(output["common_linearization_reference_used"], identity)
                # This event actually used the supplied reference even though
                # the published nominal state chooses fixed for the NEXT one.
                self.assertEqual(output["selected_support_model"], "fixed")
                self.assertEqual(output["next_common_linearization_reference"], "fixed")
            else:
                self.assertEqual(output["common_linearization_reference_used"], "fixed")
                self.assertEqual(common.navigator.branches[0].linearization_scope["reference_support_identity"], "fixed")
                np.testing.assert_allclose(charts["step"][0]["values"].atPose3(X(index)).matrix(),
                                           navigator.branches[0].pose.matrix(), atol=1e-12)

        navigator.run(events, output_callback=observe)
        self.assertEqual(navigator.linearization_reference_switches, 1)


if __name__ == "__main__":
    unittest.main()
