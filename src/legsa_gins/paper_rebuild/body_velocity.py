"""Source-local body velocity samples; no GNSS attitudes or time interpolation.

The FLU hypothesis must be supplied explicitly for the particular recording.
It is supported for the BY2-family logs by their internal position/rpy/velocity
audit, not by a universal promise about the vendor SportModeState API.
"""
from dataclasses import dataclass
import math
import re

FIELDS=("time","v_forward_mps","v_right_mps","std_forward_mps",
        "std_right_mps","valid","source_status")
STAMP=re.compile(r"^stamp:\n  sec: (\d+)\n  nanosec: (\d+)\s*$",re.M)
ERROR=re.compile(r"^error_code: ([^\n]+)$",re.M)
VELOCITY=re.compile(r"^velocity:\n((?:- [^\n]*(?:\n|$)){3})",re.M)

@dataclass(frozen=True)
class BodyVelocitySample:
    time: float
    forward: float|None
    right: float|None
    valid: bool
    reason: str

    def csv_row(self,std_mps):
        if not math.isfinite(std_mps) or std_mps<=0:
            raise ValueError("positive engineering standard deviation required")
        return dict(zip(FIELDS,(self.time,self.forward if self.valid else "",
            self.right if self.valid else "",std_mps if self.valid else "",
            std_mps if self.valid else "",int(self.valid),"active" if self.valid else "invalid")))

def iter_messages(path):
    """Stream complete ROS text messages, preserving an incomplete final record."""
    lines=[]
    with open(path,encoding="utf8") as stream:
        for line in stream:
            if line.strip()=="---":
                if lines: yield "".join(lines)
                lines=[]
            else: lines.append(line)
    if lines: yield "".join(lines)

def parse_sample(message,*,base_time_s,input_frame):
    if input_frame!="dataset_supported_body_flu":
        raise ValueError("explicit dataset-supported body-FLU frame required")
    if not math.isfinite(base_time_s):
        raise ValueError("finite time origin required")
    time=STAMP.search(message)
    if time is None:
        raise ValueError("missing source timestamp; no invented sample time")
    sec,nsec=int(time[1]),int(time[2])
    if not 0<=nsec<1000000000:
        raise ValueError("invalid source nanoseconds")
    t=(sec-base_time_s)+nsec*1e-9
    error=ERROR.search(message)
    if error is None:
        return BodyVelocitySample(t,None,None,False,"missing_error_code")
    try: error_code=int(error[1])
    except ValueError:
        return BodyVelocitySample(t,None,None,False,"malformed_error_code")
    if error_code!=0:
        return BodyVelocitySample(t,None,None,False,"source_error_code")
    velocity=VELOCITY.search(message)
    if velocity is None:
        return BodyVelocitySample(t,None,None,False,"missing_velocity")
    try: values=[float(line[2:]) for line in velocity[1].splitlines()]
    except ValueError:
        return BodyVelocitySample(t,None,None,False,"malformed_velocity")
    if len(values)!=3 or not all(math.isfinite(v) for v in values):
        return BodyVelocitySample(t,None,None,False,"nonfinite_velocity")
    # FLU -> FRD is a coordinate basis change; no SDK/GNSS attitude enters.
    return BodyVelocitySample(t,values[0],-values[1],True,"raw_body_FLU_to_FRD")
