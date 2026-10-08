"""Physical SD OU graph equals the complete cross-time DD covariance."""
import math
import unittest

import gtsam
import numpy as np
from scipy import linalg

from legsa_gins.paper_rebuild.carrier_phase.arc_relations import DdArcRelation, SdArcNode
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
from legsa_gins.paper_rebuild.joint_navigation.factors import source_ou_factor
from legsa_gins.paper_rebuild.joint_navigation.source_noise_likelihood import (
    NoiseParameters, assemble_source_noise_covariance, physical_source_incidence)


def pivot_partial_slip_blocks():
    signals = tuple(f"0:{i}:0:0" for i in range(1, 5))
    geometry = np.vstack((np.eye(3), np.zeros(3)))
    baseline = np.array([0., -.35, 0.])
    blocks = []
    for epoch, (time, pivot, targets) in enumerate((
            (0., 3, (0, 1, 2)), (.2, 2, (0, 1, 3)),
            (.5, 2, (0,)), (.9, 2, (0, 1, 3)))):
        d = np.zeros((len(targets), 4)); labels = []
        integers = np.array([12, 25, -8, 3]); integers[0] += int(epoch >= 2)
        for j, target in enumerate(targets):
            d[j, target], d[j, pivot] = 1., -1.
            labels.append(DdArcRelation(
                SdArcNode(signals[target], "new" if target == 0 and epoch >= 2 else "old"),
                SdArcNode(signals[pivot], "old")).label)
        m = len(labels)
        b = np.vstack((d@geometry, d@geometry))
        a = np.vstack((np.zeros((m, m)), .19*np.eye(m)))
        q = linalg.block_diag(.1**2*(d@d.T), .003**2*(d@d.T))
        blocks.append(EpochBlock(time, b@baseline+a@(d@integers), a, b, q, tuple(labels)))
    return blocks


class PhysicalPhaseSourceGraphTest(unittest.TestCase):
    def test_explicit_ou_graph_matches_full_covariance_through_pivot_partial_and_slip(self):
        blocks = pivot_partial_slip_blocks()
        parameters = NoiseParameters(.005, .012, .65)
        covariance = assemble_source_noise_covariance(blocks, parameters)
        self.assertEqual(len(covariance.source_signals), 4)
        values, graph = gtsam.Values(), gtsam.NonlinearFactorGraph()
        beta_keys, histories, local = [], {}, []
        for block in blocks:
            incidence = physical_source_incidence(block)
            keys = []
            for signal in incidence.source_signals:
                key = gtsam.symbol("e", len(beta_keys)); beta_keys.append(key); keys.append(key)
                values.insert_vector(key, np.zeros(1))
                if signal in histories:
                    previous, previous_time = histories[signal]
                    rho = math.exp(-(block.time_s-previous_time)/parameters.tau_s)
                    graph.add(source_ou_factor(previous, key, rho,
                        parameters.beta_sd_sigma_m*math.sqrt(1-rho*rho)))
                else:
                    graph.add(gtsam.PriorFactorVector(key, np.zeros(1),
                        gtsam.noiseModel.Isotropic.Sigma(1, parameters.beta_sd_sigma_m)))
                histories[signal] = key, block.time_s
            local.append((incidence, keys))
        # Drop no observed source across the integer slip. Missing source samples
        # have no artificial reset/node: their next transition spans actual dt.
        self.assertEqual(len(beta_keys), 14)
        ordering = gtsam.Ordering()
        for key in beta_keys:
            ordering.push_back(key)
        process_a, _ = graph.linearize(values).jacobian(ordering)
        process_rows, state_dim = process_a.shape
        total_rows = len(covariance.total)
        square_root = np.zeros((process_rows+total_rows, state_dim+total_rows))
        square_root[:process_rows, :state_dim] = process_a
        key_column = {key:i for i,key in enumerate(beta_keys)}
        for block, (incidence, keys), rows in zip(blocks, local, covariance.row_slices):
            q = block.Q + parameters.white_sd_sigma_m**2*(incidence.D@incidence.D.T)
            chol = linalg.cholesky(q, lower=True)
            beta_design = np.zeros((len(block.y), state_dim))
            for j,key in enumerate(keys):
                beta_design[:,key_column[key]] = -incidence.D[:,j]
            target = slice(process_rows+rows.start, process_rows+rows.stop)
            square_root[target,:state_dim] = linalg.solve_triangular(chol,beta_design,lower=True)
            square_root[target,state_dim+rows.start:state_dim+rows.stop] = \
                linalg.solve_triangular(chol,np.eye(len(block.y)),lower=True)
        # QR, not normal equations: marginal covariance of observation variables.
        _, r = linalg.qr(square_root, mode="economic")
        inverse = linalg.solve_triangular(r,np.eye(len(r)))
        observed = (inverse@inverse.T)[state_dim:,state_dim:]
        np.testing.assert_allclose(observed,covariance.total,atol=2e-16,rtol=2e-12)
        # This cross-slip block has actual same-signal memory, despite new N_1.
        self.assertGreater(np.linalg.norm(observed[covariance.row_slices[0],
                                                  covariance.row_slices[2]]), 0.)

    def test_actual_carrier_source_identity_and_white_component_count(self):
        blocks = pivot_partial_slip_blocks()
        original_q = [block.Q.copy() for block in blocks]
        for beta in (.012, 0.):
            branch = NavigationBranch(dict(
                baseline_body=[0., -.35, 0.], carrier_label_mode="physical_sd_arcs",
                phase_noise_model=dict(white_sd_sigma_m=.005,beta_sd_sigma_m=beta,
                                       tau_s=.65,scope="FIXED_TEST_SOURCE_MODEL")),
                use_foot=False)
            previous_keys = {}
            for index, block in enumerate(blocks):
                pose_key, pose = gtsam.symbol("x",index), gtsam.Pose3()
                values = gtsam.Values(); values.insert(pose_key,pose)
                factors, times = [], {pose_key:block.time_s}
                branch.time = block.time_s
                branch._carrier(block,pose,pose_key,values,times,factors)
                incidence = physical_source_incidence(block)
                np.testing.assert_allclose(factors[-1].noiseModel().covariance(),
                    block.Q + .005**2*(incidence.D@incidence.D.T),atol=1e-18,rtol=1e-13)
                # Values carry the existing graph chart between actual packets;
                # no optimizer or navigation is needed for this construction check.
                branch.window.values.insert(values)
                if beta:
                    self.assertEqual(set(branch.phase_beta_keys),
                                     set(assemble_source_noise_covariance(blocks[:index+1],
                                           NoiseParameters(.005,beta,.65)).source_signals))
                    if index == 2:
                        self.assertEqual(branch.phase_beta_keys["0:2:0:0"],
                                         previous_keys["0:2:0:0"])
                        self.assertEqual(branch.phase_beta_times["0:2:0:0"], .2)
                    previous_keys = dict(branch.phase_beta_keys)
                else:
                    self.assertFalse(branch.phase_beta_keys)
                    self.assertFalse(branch.phase_beta_coordinates)
            if beta:
                self.assertEqual(len(branch.phase_beta_coordinates),14)
                self.assertEqual(len(branch.phase_beta_keys),4)
        for block,q in zip(blocks,original_q):
            np.testing.assert_array_equal(block.Q,q)


if __name__=="__main__":
    unittest.main()
