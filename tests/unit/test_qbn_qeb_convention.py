import pytest

from legsa_gins.frames.quaternion import (
    quat_inverse,
    quat_multiply,
    quat_normalize,
    quat_rotate_vector,
)


def assert_tuple_close(actual, expected, tol=1e-12):
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        assert got == pytest.approx(want, abs=tol)


def test_quaternion_normalize():
    q = quat_normalize((2.0, 0.0, 0.0, 0.0))

    assert_tuple_close(q, (1.0, 0.0, 0.0, 0.0))


def test_quaternion_inverse_roundtrip_is_identity():
    q = quat_normalize((1.0, 2.0, 3.0, 4.0))
    identity = quat_multiply(q, quat_inverse(q))

    assert_tuple_close(identity, (1.0, 0.0, 0.0, 0.0))


def test_identity_quaternion_rotation_leaves_vector_unchanged():
    v = (1.0, 2.0, 3.0)

    assert_tuple_close(quat_rotate_vector((1.0, 0.0, 0.0, 0.0), v), v)
