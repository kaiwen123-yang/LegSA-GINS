"""Two correlated spheres: numerical witnesses versus exact necessary bounds."""
import unittest
from unittest import mock
import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock,assemble_epochs,joint_float
from legsa_gins.paper_rebuild.joint_navigation.candidate import propose_candidates
from legsa_gins.paper_rebuild.joint_navigation.coupled_length_profile import coupled_length_profile


def correlated_two_spheres(variance):
    q=np.diag([.01,variance,variance,variance])
    a=np.array([[1.],[0.],[0.],[0.]])
    b=np.vstack((np.zeros((1,3)),np.eye(3)))
    blocks=tuple(EpochBlock(t,np.array([0.,1.4,0.,0.]),a,b,q,("integer",)) for t in (0.,.2))
    full=np.block([[q,np.zeros((4,4))],[np.zeros((4,4)),q]])
    full[1:4,5:8]=.8*variance*np.eye(3)
    full[5:8,1:4]=.8*variance*np.eye(3)
    return blocks,full


class CoupledLengthProfileTest(unittest.TestCase):
    def test_full_angle_grid_envelope_and_max_not_sum(self):
        variance=.008
        blocks,full=correlated_two_spheres(variance)
        problem=assemble_epochs(blocks,length_m=1.,temporal_covariance=full)
        floating=joint_float(problem)
        profile=coupled_length_profile(problem,floating,[0])
        az,el=np.meshgrid(np.linspace(-np.pi,np.pi,25)[:-1],np.linspace(-np.pi/2,np.pi/2,13))
        points=np.column_stack((np.cos(el.ravel())*np.cos(az.ravel()),
                                np.cos(el.ravel())*np.sin(az.ravel()),np.sin(el.ravel())))
        delta=points-np.array([1.4,0,0])
        weight=np.linalg.inv(floating.conditional_covariance_b)
        each=np.einsum("ij,jk,ik->i",delta,weight[:3,:3],delta)
        other=np.einsum("ij,jk,ik->i",delta,weight[3:,3:],delta)
        all_angles=each[:,None]+other[None,:]+2*delta@weight[:3,3:]@delta.T
        grid_best=float(all_angles.min())+profile.relaxed_raw_cost
        # For equal exterior centers and positive isotropic correlation, the
        # common radial points globally minimize common and difference modes.
        analytic_best=2*.4**2/(variance*(1+.8))
        self.assertAlmostEqual(grid_best,analytic_best,places=9)
        self.assertLessEqual(profile.raw_cost_lower_bound,grid_best)
        self.assertLessEqual(grid_best,profile.raw_cost_upper_bound+1e-9)
        self.assertAlmostEqual(profile.raw_cost_upper_bound,analytic_best,places=9)
        self.assertAlmostEqual(profile.conditional_cost_lower_bound,max(profile.marginal_sphere_costs),places=12)
        self.assertGreater(sum(profile.marginal_sphere_costs),profile.raw_cost_upper_bound)
        self.assertLess(abs(profile.objective_identity_error),1e-10)
        self.assertLess(abs(profile.relaxed_objective_identity_error),1e-10)
        self.assertLess(profile.maximum_length_error_m,1e-12)
        with mock.patch("legsa_gins.paper_rebuild.joint_navigation.candidate.evaluate_integer",
                        side_effect=AssertionError("separable solver must not see cross Q")):
            proposal=propose_candidates(blocks,np.array([1.,0.,0.]),temporal_covariance=full)
        self.assertTrue(proposal.metadata["enumeration_complete"])
        self.assertTrue(proposal.metadata["length_support_complete"])
        self.assertTrue(proposal.metadata["active_support_complete"])
        self.assertEqual(proposal.active[0].support_status,"FEASIBLE_UPPER_WITHIN_BUDGET")

    def test_straddling_bounds_retain_identity_without_claiming_complete_support(self):
        blocks,full=correlated_two_spheres(.16/24.)
        with mock.patch("legsa_gins.paper_rebuild.joint_navigation.candidate.evaluate_integer",
                        side_effect=AssertionError("separable solver must not see cross Q")):
            proposal=propose_candidates(blocks,np.array([1.,0.,0.]),temporal_covariance=full)
        self.assertTrue(proposal.metadata["enumeration_complete"])
        self.assertFalse(proposal.metadata["length_support_complete"])
        self.assertFalse(proposal.metadata["active_support_complete"])
        self.assertEqual(proposal.metadata["length_unresolved_count"],1)
        self.assertEqual(proposal.metadata["length_rejected_count"],0)
        self.assertEqual(proposal.active[0].integer_by_label,{"integer":0})
        self.assertEqual(proposal.active[0].support_status,"LOWER_UPPER_STRADDLE")
        record=proposal.metadata["candidate_qualifications"][0]
        self.assertIsNone(record["length_qualified"])
        self.assertTrue(record["retained"])
        self.assertLess(record["joint_raw_cost_lower_bound"],proposal.metadata["expanded_working_threshold"])
        self.assertGreater(record["joint_raw_cost_upper_bound"],proposal.metadata["expanded_working_threshold"])
        self.assertFalse(record["global_profile_optimum_certified"])


if __name__ == "__main__":
    unittest.main()
