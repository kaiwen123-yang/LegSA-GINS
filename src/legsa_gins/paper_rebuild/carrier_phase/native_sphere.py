"""Explicitly selected scalar C++ sphere backend; Python remains the default.

The shared library replaces only the spectral 3D hard-case/secular root kernel.
Covariance validation/factors, frame projections, objective and constraint checks
stay in Python. An explicit missing/incompatible library is an error, never a
silent fallback. No library is searched, compiled or loaded at module import.
"""
from __future__ import annotations
import ctypes
import hashlib
import math
from pathlib import Path
import numpy as np

from ..horizontal_literature.ext01_clambda import (
    BaselineSphereMetric, CLambdaError, ConditionalBaseline,
)

ABI_VERSION=1
KERNEL_VERSION="delta_bisection_3d_v1"

class NativeSphereError(CLambdaError):
    """Requested backend cannot satisfy its ABI or numerical contract."""

class NativeSphereBackend:
    def __init__(self, library: str | Path):
        try:
            self.path=Path(library).resolve(strict=True)
            self.library_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()
            self._library=ctypes.CDLL(str(self.path))
        except (OSError, TypeError, ValueError) as exc:
            raise NativeSphereError("cannot load explicitly requested sphere library") from exc
        try:
            abi=self._library.legsa_sphere_abi_version
            abi.argtypes=[];abi.restype=ctypes.c_uint32
            version=self._library.legsa_sphere_kernel_version
            version.argtypes=[];version.restype=ctypes.c_char_p
            self.abi_version=int(abi())
            encoded=version()
            self.kernel_version=encoded.decode("ascii") if encoded is not None else ""
            if self.abi_version!=ABI_VERSION or self.kernel_version!=KERNEL_VERSION:
                raise NativeSphereError("sphere ABI/kernel version mismatch")
            self._root=self._library.legsa_sphere_root3
            self._pointer=ctypes.POINTER(ctypes.c_double)
            self._root.argtypes=[self._pointer,self._pointer,ctypes.c_double,ctypes.c_double,
                self._pointer,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
            self._root.restype=ctypes.c_int
        except (AttributeError, UnicodeError, TypeError, ValueError) as exc:
            raise NativeSphereError("sphere ABI/kernel version mismatch") from exc

    def from_covariance(self, covariance):
        return _NativeSphereMetric(BaselineSphereMetric.from_covariance(covariance), self)

class _NativeSphereMetric:
    def __init__(self, metric, backend):
        self.metric,self.backend=metric,backend
        # Both metric and pointer retain the readonly owning array for every call.
        self._eigen_pointer=metric.eigenvalues.ctypes.data_as(backend._pointer)

    def solve(self, center, length_m, tolerance=1e-13):
        start=np.asarray(center,dtype=float)
        if start.shape!=(3,) or np.any(~np.isfinite(start)) or not math.isfinite(length_m) or length_m<=0:
            raise CLambdaError("invalid constrained-baseline inputs")
        coordinates=self.metric.vectors.T@start
        out=np.empty(4,dtype=np.float64)
        hard,iterations=ctypes.c_int(),ctypes.c_int()
        backend=self.backend
        status=backend._root(self._eigen_pointer,coordinates.ctypes.data_as(backend._pointer),
            length_m,tolerance,out.ctypes.data_as(backend._pointer),ctypes.byref(hard),ctypes.byref(iterations))
        if status:
            messages={1:"failed to bracket sphere multiplier",2:"unresolved constrained-baseline degeneracy",
                      3:"invalid constrained-baseline inputs"}
            if status not in messages:
                raise NativeSphereError("invalid status from native sphere kernel")
            raise CLambdaError(messages[status])
        if (hard.value not in (0,1) or not 0<=iterations.value<=300 or not np.isfinite(out).all()):
            raise NativeSphereError("invalid result from native sphere kernel")
        baseline=self.metric.vectors@out[:3]
        norm=float(np.linalg.norm(baseline))
        if not hard.value and abs(norm-length_m)>1e-9:
            raise CLambdaError("sphere root failed constraint tolerance")
        delta=baseline-start
        objective=float(delta@self.metric.weight@delta)
        if not np.isfinite(baseline).all() or not math.isfinite(objective):
            raise NativeSphereError("non-finite native sphere result")
        return ConditionalBaseline(baseline,objective,float(out[3]),abs(norm-length_m),bool(hard.value))
