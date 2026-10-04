"""Pinned OB_GINS Earth preintegration as an actual upstream C++ factor.

GTSAM supplies state containers and its local Pose3 chart only. The upstream
class supplies propagation, coning/sculling, Earth rotation/Coriolis, bias
correction, covariance and whitened residual/analytic local Jacobians.
"""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import subprocess
import numpy as np
import gtsam

UPSTREAM_COMMIT = "e96c69ae84d09f0e8c1c69bdd9323eaec020db86"
_DOUBLE = ctypes.POINTER(ctypes.c_double)
_LIBRARY = None


def _ptr(a):
    return a.ctypes.data_as(_DOUBLE) if a is not None else None


def library():
    global _LIBRARY
    if _LIBRARY is None:
        name = os.environ.get("LEGSA_OBGINS_BRIDGE")
        if not name:
            raise RuntimeError("LEGSA_OBGINS_BRIDGE must identify the pinned compiled bridge")
        path = Path(name)
        receipt = json.loads(path.with_suffix(".build.json").read_text())
        if receipt["upstream_commit"] != UPSTREAM_COMMIT:
            raise RuntimeError("OB_GINS upstream commit mismatch")
        from .oisam_inputs import sha256
        if receipt["library_sha256"] != sha256(path):
            raise RuntimeError("OB_GINS bridge binary identity mismatch")
        for source,digest in receipt["source_sha256"].items():
            if sha256(Path(source)) != digest:
                raise RuntimeError("OB_GINS compiled source identity mismatch: "+source)
        lib = ctypes.CDLL(str(path))
        lib.ob_error.restype = ctypes.c_char_p
        lib.ob_create.argtypes = [_DOUBLE,ctypes.c_double,ctypes.c_double,_DOUBLE,_DOUBLE,_DOUBLE,_DOUBLE,ctypes.c_int]
        lib.ob_create.restype = ctypes.c_void_p
        lib.ob_destroy.argtypes = [ctypes.c_void_p]
        lib.ob_predict.argtypes = [ctypes.c_void_p,_DOUBLE]
        lib.ob_diagnostics.argtypes = [ctypes.c_void_p,_DOUBLE,_DOUBLE]
        lib.ob_evaluate.argtypes = [ctypes.c_void_p,_DOUBLE,_DOUBLE,_DOUBLE,_DOUBLE,_DOUBLE,_DOUBLE,_DOUBLE]
        lib.build_receipt = receipt
        _LIBRARY = lib
    return _LIBRARY


def build_bridge(upstream, output):
    """Compile only the unchanged pinned upstream model and our thin ABI."""
    from .oisam_inputs import sha256
    upstream, output = Path(upstream), Path(output)
    commit = subprocess.check_output(["git","rev-parse","HEAD"],cwd=upstream,text=True).strip()
    if commit != UPSTREAM_COMMIT or subprocess.check_output(["git","status","--porcelain"],cwd=upstream,text=True):
        raise RuntimeError("expected clean pinned upstream checkout")
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():
        raise FileExistsError("preserve existing bridge build identity")
    own = Path(__file__).with_name("obgins_bridge.cc")
    sources = [upstream/"src/preintegration/preintegration_base.cc",upstream/"src/preintegration/preintegration_earth.cc",own]
    headers = [upstream/"src/preintegration"/n for n in ("preintegration_base.h","preintegration_earth.h","integration_state.h")]
    headers += [upstream/"src/common"/n for n in ("earth.h","rotation.h","types.h")]
    command = ["g++","-std=c++17","-O2","-DNDEBUG","-fPIC","-shared","-I"+str(upstream),"-I/usr/include/eigen3",*[str(p) for p in sources],"-o",str(output)]
    subprocess.run(command,check=True)
    receipt = {"upstream_commit":commit,"upstream_url":"https://github.com/i2Nav-WHU/OB_GINS","license":"GPL-3.0-or-later",
        "command":command,"compiler":subprocess.check_output(["g++","--version"],text=True).splitlines()[0],
        "source_sha256":{str(p):sha256(p) for p in sources+headers},"library_sha256":sha256(output),
        "upstream_scientific_source_modified":False,"anisotropic_noise_extension":"noise diagonal only; isotropic parameters recover upstream exactly"}
    output.with_suffix(".build.json").write_text(json.dumps(receipt,indent=2)+"\n")
    return receipt


def pack_state(pose, velocity, bias):
    q = pose.rotation().toQuaternion()
    return np.ascontiguousarray(np.r_[pose.translation(),q.x(),q.y(),q.z(),q.w(),velocity,bias.gyroscope(),bias.accelerometer()],dtype=np.float64)


def unpack_state(x):
    pose=gtsam.Pose3(gtsam.Rot3.Quaternion(x[6],x[3],x[4],x[5]),x[:3])
    return pose,x[7:10].copy(),gtsam.imuBias.ConstantBias(x[13:16],x[10:13])


class EarthPreintegration:
    def __init__(self, config, station_llh_deg_m, gravity, pose, velocity, bias,
                 begin_s, pieces, seed_piece):
        self.lib=library()
        self.initial=pack_state(pose,velocity,bias)
        station=np.asarray(station_llh_deg_m,float).copy(); station[:2]=np.deg2rad(station[:2]); station=np.ascontiguousarray(station)
        factor=2./float(config["bias_correlation_time_s"])
        noise=np.ascontiguousarray(np.r_[np.full(3,config["gyro_white_noise_rad_sqrt_s"]**2),
            np.square(config["accel_white_noise_mps_sqrt_s"]),np.full(3,config["gyro_bias_stationary_std_radps"]**2*factor),
            np.square(config["accel_bias_stationary_std_mps2"])*factor])
        dt,theta,vel=seed_piece
        seed=np.ascontiguousarray(np.r_[begin_s,dt,theta,vel],dtype=np.float64)
        samples=[]; current=float(begin_s)
        for dt,theta,vel in pieces:
            current+=float(dt); samples.append(np.r_[current,dt,theta,vel])
        samples=np.ascontiguousarray(samples,dtype=np.float64)
        self.handle=self.lib.ob_create(_ptr(station),float(gravity),float(config["bias_correlation_time_s"]),_ptr(noise),_ptr(self.initial),_ptr(seed),_ptr(samples),len(samples))
        if not self.handle: raise np.linalg.LinAlgError("OB_GINS_CREATE:"+self.lib.ob_error().decode())
        self.end_time=current
        self.last_piece=pieces[-1]
        self.covariance=np.zeros((15,15)); self.preintegration_jacobian=np.zeros((15,15))
        self._check(self.lib.ob_diagnostics(self.handle,_ptr(self.covariance),_ptr(self.preintegration_jacobian)))
        eigenvalues=np.linalg.eigvalsh(self.covariance)
        if not np.isfinite(eigenvalues).all() or eigenvalues[0]<=0:
            raise np.linalg.LinAlgError("OB_GINS_NON_POSITIVE_COVARIANCE")

    def __del__(self):
        if getattr(self,"handle",None):
            self.lib.ob_destroy(self.handle); self.handle=None

    def _check(self, success):
        if not success: raise np.linalg.LinAlgError("OB_GINS:"+self.lib.ob_error().decode())

    def predict(self):
        result=np.zeros(16)
        self._check(self.lib.ob_predict(self.handle,_ptr(result)))
        return unpack_state(result)

    def evaluate(self,pose0,velocity0,bias0,pose1,velocity1,bias1,jacobian=True):
        a=pack_state(pose0,velocity0,bias0); b=pack_state(pose1,velocity1,bias1)
        residual=np.zeros(15)
        raw=[np.zeros((15,7)),np.zeros((15,9)),np.zeros((15,7)),np.zeros((15,9))] if jacobian else [None]*4
        self._check(self.lib.ob_evaluate(self.handle,_ptr(a),_ptr(b),_ptr(residual),*[_ptr(x) for x in raw]))
        if not jacobian: return residual
        # Upstream local pose: [world-position, right-body-rotation].
        # GTSAM Pose3 tangent: [right-body-rotation, body-translation].
        # Upstream mix: [v,bg,ba]; GTSAM ConstantBias: [ba,bg].
        def convert(p,m,pose):
            return np.c_[p[:,3:6],p[:,:3]@pose.rotation().matrix()],m[:,:3],np.c_[m[:,6:9],m[:,3:6]]
        return residual,(*convert(raw[0],raw[1],pose0),*convert(raw[2],raw[3],pose1))

    def factor(self, previous_keys, current_keys):
        all_keys=[*previous_keys,*current_keys]
        def error(_factor,values,jacobians):
            states=[]
            for x,v,b in (previous_keys,current_keys):
                states.extend([values.atPose3(x),values.atVector(v),values.atConstantBias(b)])
            if jacobians is None: return self.evaluate(*states,jacobian=False)
            residual,blocks=self.evaluate(*states)
            for i,block in enumerate(blocks): jacobians[i]=block
            return residual
        return gtsam.CustomFactor(gtsam.noiseModel.Unit.Create(15),all_keys,error)
