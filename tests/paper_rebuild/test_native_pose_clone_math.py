"""Four scientific algebra checks for the shared-state support displacement factor."""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    directory = tmp_path_factory.mktemp("pose_clone_math")
    binary = directory / "pose_clone_math"
    cpp = ROOT / "cpp/legsa_v23_port_core"
    sources = [cpp / "src" / p for p in (
        "common/types.cpp", "common/earth.cpp", "common/rotation.cpp",
        "factors/attitude_clone.cpp", "factors/pose_clone.cpp")]
    subprocess.run(["g++", "-std=c++17", "-O2", "-I", str(cpp / "include"),
                    str(Path(__file__).with_name("native_pose_clone_math_harness.cpp")),
                    *map(str, sources), "-o", str(binary)], check=True, capture_output=True, text=True)

    def call(op, *arrays):
        payload = " ".join(format(float(x), ".17g") for a in arrays for x in np.asarray(a).reshape(-1))
        result = subprocess.run([str(binary), op], input=payload, text=True, capture_output=True, check=True)
        return {k: np.asarray(v, float) for k, v in json.loads(result.stdout).items()}
    return call


def exp(v):
    return Rotation.from_rotvec(v).as_matrix()


def skew(v):
    x, y, z = v
    return np.array([[0, -z, y], [z, 0, -x], [-y, x, 0.]])


def ned(q):
    lat, lon, _ = q
    s, c, sl, cl = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    return np.array([[-s * cl, -sl, -c * cl], [-s * sl, cl, -c * sl], [c, 0, -s]])


def ecef(q):
    lat, lon, h = q
    rn = 6378137. / np.sqrt(1 - .0066943799901413156 * np.sin(lat) ** 2)
    return np.array([(rn + h) * np.cos(lat) * np.cos(lon),
                     (rn + h) * np.cos(lat) * np.sin(lon),
                     (rn * (1 - .0066943799901413156) + h) * np.sin(lat)])


def dri(q):
    a, e = 6378137., .0066943799901413156
    t = 1 - e * np.sin(q[0]) ** 2
    rn, rm = a / np.sqrt(t), a * (1 - e) / t ** 1.5
    return np.diag([1 / (rm + q[2]), 1 / ((rn + q[2]) * np.cos(q[0])), -1.])


def geometry(horizontal=True):
    q = np.array([.6, 1.3, 35.])
    f0 = np.array([[.3, -.2, .35], [-.25, .21, .38]])
    f1 = np.array([[.25, -.14, .34], [-.28, .27, .37]])
    c0, cbn = ned(q) @ exp([.2, -.15, .3]), exp([.27, -.12, .42])
    p0 = ecef(q) - ned(q) @ np.array([.12, -.04, .02])
    rng = np.random.default_rng(7701)
    l = .004 * rng.normal(size=(12, 12)) + .01 * np.eye(12)
    return [2, int(horizontal), f0, f1, p0, c0, cbn, q, l @ l.T, np.array([.01, -.02, .015])]


def latent(n):
    rng = np.random.default_rng(610727)
    f = .025 * rng.normal(size=(n, n)) + .2 * np.eye(n)
    return f, f @ f.T, np.linspace(-.012, .015, n)


def qr_posterior(f, mean, h, residual, r):
    l = np.linalg.cholesky(r)
    a = np.vstack([np.eye(f.shape[1]), np.linalg.solve(l, h @ f)])
    b = np.r_[np.zeros(f.shape[1]), np.linalg.solve(l, residual - h @ mean)]
    q, u = np.linalg.qr(a, mode="reduced")
    v = np.linalg.solve(u, np.eye(len(u)))
    return mean + f @ np.linalg.solve(u, q.T @ b), f @ v @ v.T @ f.T


def test_two_foot_model_nonzero_residual_jacobian_and_gauge(native):
    g = geometry(False)
    _, _, f0, f1, p0, c0, cbn, q, sigma, lever = g
    out = native("model", *g)
    delta = ecef(q) - p0
    expected = np.array([c0.T @ (delta + ned(q) @ cbn @ (b - lever) - c0 @ (a - lever))
                         for a, b in zip(f0, f1)]).reshape(-1)
    np.testing.assert_allclose(out["residual"], expected, atol=2e-15)
    assert np.linalg.norm(expected) > .05  # Exercise the essential nonzero-residual frame term.

    def perturbed(error):
        h = list(g)
        h[4] = p0 - error[21:24]
        h[5] = exp(error[24:27]) @ c0
        h[6] = exp(error[6:9]) @ cbn
        h[7] = q - dri(q) @ error[:3]
        return native("model", *h)["residual"]

    jacobian = np.zeros((6, 27))
    for j in [0, 1, 2, 6, 7, 8, 21, 22, 23, 24, 25, 26]:
        step = 1e-2 if j in [0, 1, 2, 21, 22, 23] else 1e-6
        direction = np.eye(27)[j] * step
        jacobian[:, j] = -(perturbed(direction) - perturbed(-direction)) / (2 * step)
    np.testing.assert_allclose(out["H"], jacobian, atol=8e-8, rtol=2e-7)
    np.testing.assert_allclose(out["R"], out["A"] @ sigma @ out["A"].T, atol=2e-18)

    # A rigid rotation of both poses about p0 cannot change a body0 residual.
    connection = np.zeros((3, 3))
    connection[0, 0] = np.sin(q[1]) * dri(q)[0, 0]
    connection[1, 0] = -np.cos(q[1]) * dri(q)[0, 0]
    connection[2, 1] = dri(q)[1, 1]
    gauge = np.zeros((27, 3))
    gauge[:3] = ned(q).T @ skew(delta)
    gauge[6:9] = ned(q).T @ (np.eye(3) + connection @ gauge[:3])
    gauge[24:27] = np.eye(3)
    np.testing.assert_allclose(out["H"] @ gauge, 0, atol=2e-16)
    horizontal = native("model", *geometry(True))
    selected = [0, 1, 3, 4]
    np.testing.assert_array_equal(horizontal["H"], out["H"][selected])
    np.testing.assert_array_equal(horizontal["R"], out["R"][np.ix_(selected, selected)])
    np.testing.assert_array_equal(horizontal["residual"], out["residual"][selected])


def test_deterministic_pose_augmentation_and_joint_propagation(native):
    f, p, mean = latent(21)
    q = np.array([.6, 1.3, 35.])
    out = native("augment", q, p, mean)
    j = out["J"]
    a = np.vstack([np.eye(21), j])
    np.testing.assert_allclose(j[:3, :3], ned(q), atol=0)
    np.testing.assert_allclose(out["P"], (a @ f) @ (a @ f).T, atol=8e-17)
    np.testing.assert_allclose(out["mean"], a @ mean, atol=1e-17)
    null = np.c_[-j, np.eye(6)]
    np.testing.assert_allclose(null @ out["P"] @ null.T, 0, atol=8e-17)
    assert np.linalg.matrix_rank(out["P"]) == 21
    phi = np.eye(21)
    phi[:3, 3:6] = .1 * np.eye(3)
    phi[6:9, 9:12] = -.1 * np.eye(3)
    noise = np.diag(np.linspace(1e-8, 2e-7, 21))
    propagated = native("propagate", 27, out["P"], out["mean"], phi, noise)
    transition, process = np.eye(27), np.zeros((27, 27))
    transition[:21, :21], process[:21, :21] = phi, noise
    np.testing.assert_allclose(propagated["P"], transition @ out["P"] @ transition.T + process, atol=3e-17)
    np.testing.assert_array_equal(propagated["P"][21:, 21:], out["P"][21:, 21:])
    np.testing.assert_array_equal(propagated["mean"][21:], out["mean"][21:])


def test_ordinary_and_foot_update_match_independent_latent_qr(native):
    f, p, mean = latent(27)
    model = native("model", *geometry())
    out = native("foot", 27, p, mean, *geometry())
    mm, pp = qr_posterior(f, mean, model["H"], model["residual"], model["R"])
    np.testing.assert_allclose(out["mean"], mm, atol=3e-15)
    np.testing.assert_allclose(out["P"], pp, atol=5e-16)
    assert np.linalg.norm(out["mean"][3:6] - mean[3:6]) > 1e-4
    assert np.linalg.norm(out["mean"][:3] - mean[:3]) > 1e-3
    h = np.zeros((2, 27))
    h[:, :2] = np.eye(2)
    r, z = np.diag([.002, .003]), np.array([.04, -.02])
    ordinary = native("ordinary", 27, p, mean, 2, h, r, z)
    mm, pp = qr_posterior(f, mean, h, z, r)
    np.testing.assert_allclose(ordinary["mean"], mm, atol=2e-15)
    np.testing.assert_allclose(ordinary["P"], pp, atol=3e-16)
    assert np.linalg.norm(ordinary["mean"][21:] - mean[21:]) > 1e-4


def test_complete_feedback_reset_and_retire_marginal(native):
    _, p, mean = latent(27)
    mean[6:9], mean[24:27] = [.25, -.17, .35], [-.2, .1, .3]
    gp = np.diag([1.00003, .99997, 1.])
    out = native("reset", 27, p, mean, gp)

    def reset_error(error):
        result = error.copy()
        result[:3] = gp @ error[:3]
        for k in (6, 24):
            result[k:k + 3] = (Rotation.from_rotvec(mean[k:k + 3] + error[k:k + 3]) *
                                Rotation.from_rotvec(-mean[k:k + 3])).as_rotvec()
        return result

    step = 1e-7
    g = np.column_stack([(reset_error(step * e) - reset_error(-step * e)) / (2 * step)
                         for e in np.eye(27)])
    np.testing.assert_allclose(out["P"], g @ p @ g.T, atol=1e-10, rtol=1e-8)
    np.testing.assert_array_equal(out["mean"], np.zeros(27))
    np.testing.assert_array_equal(out["P"][21:24, 21:24], p[21:24, 21:24])
    retired = native("marginal", 27, p, mean)
    np.testing.assert_array_equal(retired["P"], p[:21, :21])
    np.testing.assert_array_equal(retired["mean"], mean[:21])
