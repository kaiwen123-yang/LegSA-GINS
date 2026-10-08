"""Discrete common-motion process and its original correlated foot likelihood."""
import gtsam
import numpy as np
from scipy.linalg import expm
from scipy.special import roots_legendre

from legsa_gins.paper_rebuild.joint_navigation.factors import (
    FootErrorExpression, algebraic_foot_error_factor,
    integrated_ou_factor, integrated_ou_birth_factor,
)
from legsa_gins.paper_rebuild.joint_navigation.support_motion import support_motion_transition


def _central_factor_jacobian(factor, values, pose_keys=(), point_keys=()):
    columns = []
    epsilon = 1e-6
    for key in factor.keys():
        is_pose = key in pose_keys
        value = (values.atPose3(key) if is_pose else
                 values.atPoint3(key) if key in point_keys else values.atVector(key))
        for axis in range(6 if is_pose else len(value)):
            delta = np.zeros(6 if is_pose else len(value))
            delta[axis] = epsilon
            plus, minus = gtsam.Values(values), gtsam.Values(values)
            if is_pose:
                plus.update(key, value.retract(delta))
                minus.update(key, value.retract(-delta))
            else:
                for target, sign in ((plus, 1.), (minus, -1.)):
                    replacement = gtsam.Values()
                    if key in point_keys:
                        replacement.insert_point3(key, value+sign*delta)
                    else:
                        replacement.insert_vector(key, value+sign*delta)
                    target.update(replacement)
            columns.append((factor.whitenedError(plus)-factor.whitenedError(minus))/(2*epsilon))
    return np.column_stack(columns)


def test_integrated_ou_discretization_matches_continuous_noise_integral():
    sigma, tau = .12, .7
    generator = np.array([[0., 1.], [0., -1./tau]])
    abscissa, weights = roots_legendre(48)
    for dt in (1e-10, 1e-5, .13, 5.3):
        transition, covariance = support_motion_transition(dt, sigma, tau)
        expected = np.zeros((2, 2))
        for t, weight in zip(.5*dt*(abscissa+1.), .5*dt*weights):
            response = expm(generator*t)[:, 1]
            expected += weight*(2*sigma*sigma/tau)*np.outer(response, response)
        indices = np.ix_([0, 3], [0, 3])
        np.testing.assert_allclose(transition[indices], expm(generator*dt), rtol=2e-14, atol=1e-16)
        np.testing.assert_allclose(covariance[indices], expected, rtol=8e-14, atol=0.)
        np.linalg.cholesky(covariance)


def test_integrated_ou_irregular_intervals_compose_and_fixed_limit_is_exact():
    first_f, first_q = support_motion_transition(.013, .08, .31)
    second_f, second_q = support_motion_transition(.287, .08, .31)
    full_f, full_q = support_motion_transition(.3, .08, .31)
    np.testing.assert_allclose(full_f, second_f@first_f, rtol=2e-15, atol=1e-16)
    np.testing.assert_allclose(full_q, second_f@first_q@second_f.T+second_q, rtol=2e-15, atol=1e-18)
    np.testing.assert_array_equal(support_motion_transition(.3, 0., .31)[1], np.zeros((6, 6)))
    zero_f, zero_q = support_motion_transition(0., .08, .31)
    np.testing.assert_array_equal(zero_f, np.eye(6))
    np.testing.assert_array_equal(zero_q, np.zeros((6, 6)))


def test_integrated_ou_factors_birth_coordinate_and_jacobians():
    previous, current, initial = (gtsam.symbol("m", 0), gtsam.symbol("m", 1),
                                  gtsam.symbol("j", 0))
    values = gtsam.Values()
    values.insert_vector(previous, np.array([.02, -.01, .03, .08, -.02, .04]))
    values.insert_vector(current, np.array([.04, -.015, .03, .06, -.015, .01]))
    values.insert_vector(initial, np.array([.08, -.02, .04]))
    dt, sigma, tau = .07, .12, .6
    transition, covariance = support_motion_transition(dt, sigma, tau)
    for factor, key, mapping in (
        (integrated_ou_factor(previous, current, dt, sigma, tau), previous, transition),
        (integrated_ou_birth_factor(initial, current, dt, sigma, tau), initial, transition[:, 3:]),
    ):
        linear = factor.linearize(values)
        np.testing.assert_allclose(linear.getA(),
                                   _central_factor_jacobian(factor, values), rtol=2e-10, atol=1e-8)
        residual = values.atVector(current)-mapping@values.atVector(key)
        np.testing.assert_allclose(2*factor.error(values), residual@np.linalg.solve(covariance, residual),
                                   rtol=2e-14)
    # s0 has no coordinate or prior; the only initial uncertainty is finite u0.
    birth_covariance = transition[:, 3:]@(sigma*sigma*np.eye(3))@transition[:, 3:].T+covariance
    np.testing.assert_allclose(birth_covariance[3:, 3:], sigma*sigma*np.eye(3), rtol=2e-15)


def test_finite_motion_foot_jacobian_and_single_original_ar_likelihood():
    x0, x1, contact, motion = (gtsam.symbol("x", 0), gtsam.symbol("x", 1),
                               gtsam.symbol("c", 0), gtsam.symbol("m", 1))
    values = gtsam.Values()
    values.insert(x0, gtsam.Pose3(gtsam.Rot3.RzRyRx(.13, -.23, .81), np.array([1., 2., .6])))
    values.insert(x1, gtsam.Pose3(gtsam.Rot3.RzRyRx(.21, -.18, .9), np.array([1.1, 2.03, .59])))
    values.insert_point3(contact, np.array([1.23, 1.74, .02]))
    values.insert_vector(motion, np.array([.03, -.01, .005, .06, -.02, .01]))
    old = FootErrorExpression(x0, contact, (.1, -.2, -.5))
    current = FootErrorExpression(x1, contact, (.15, -.18, -.51), motion_key=motion)
    rho, sigma = .83, .013
    initial = algebraic_foot_error_factor(old, sigma)
    following = algebraic_foot_error_factor(current, sigma, previous=old, rho=rho)
    linear = following.linearize(values)
    np.testing.assert_allclose(linear.getA(),
                               _central_factor_jacobian(following, values, (x0, x1), (contact,)),
                               rtol=2e-8, atol=2e-7)
    residual = np.r_[old.evaluate(values), current.evaluate(values)]
    covariance = sigma*sigma*np.kron(np.array([[1., rho], [rho, 1.]]), np.eye(3))
    np.testing.assert_allclose(2*(initial.error(values)+following.error(values)),
                               residual@np.linalg.solve(covariance, residual), rtol=3e-15)
    # Zero world motion reduces exactly to the unchanged fixed-contact equation.
    zero_motion = gtsam.Values()
    zero_motion.insert_vector(motion, np.zeros(6))
    values.update(zero_motion)
    np.testing.assert_array_equal(current.evaluate(values),
                                  FootErrorExpression(x1, contact, current.measured_body).evaluate(values))
