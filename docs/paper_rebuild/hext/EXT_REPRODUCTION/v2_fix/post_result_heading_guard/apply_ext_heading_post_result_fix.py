from pathlib import Path
import json,hashlib,datetime
CODE=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
ROOT=Path('/mnt/g/LegSA-GINS-project/修复_20261004')
EXT=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/EXT_REPRODUCTION_V2_TECH_RETRY_2_20261004T054256Z')
PREFIX=Path('src/legsa_gins/paper_rebuild/horizontal_literature')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
release=ROOT/'IMU_CLAIM_135_FINAL_DELIVERY_RECEIPT.json'
assert sha(release)=='9120b27ef47cf5a97fceba439287eca8c78774062024c21ea10957d10f8b5669'
assert json.loads(release.read_text())['source928_last_current_matches_saved_snapshot']
before=ROOT/'EXT_HEADING_POST_RESULT_SOURCE_BEFORE';before.mkdir(exist_ok=False)
files=['ext01_clambda.py','ext03_yang2024.py','reproduction_runner.py']
texts={name:(CODE/PREFIX/name).read_text() for name in files}
oldpins={str(PREFIX/name):sha(CODE/PREFIX/name) for name in files}
for name in files:(before/name).write_bytes((CODE/PREFIX/name).read_bytes())
oldruns={}
for run in sorted((EXT/'runs').iterdir()):
    manifest=run/'RUN.json';d=json.loads(manifest.read_text())
    assert d['status']=='COMPLETED'
    for key,pin in oldpins.items():assert d['source_hashes'][key]==pin
    oldruns[run.name]={'manifest_sha256':sha(manifest),'executed_source_pins':{k:d['source_hashes'][k] for k in oldpins}}
old_cl='''def body_yaw_from_ned_baseline(baseline_ned_m: Sequence[float]) -> float:
    baseline = np.asarray(baseline_ned_m, dtype=float)
    if baseline.shape != (3,) or np.any(~np.isfinite(baseline)):
        raise CLambdaError("baseline must be a finite NED vector")
    beta = math.degrees(math.atan2(baseline[1], baseline[0]))
    return wrap_degrees(beta + 90.0)
'''
new_cl='''class BaselineHeadingUndefined(CLambdaError):
    code = "BASELINE_HEADING_UNDEFINED"


# Dimensionless rho^2=(b_N^2+b_E^2)/||b||^2; this is a numerical
# projection-singularity gate, not a calibrated practical accuracy threshold.
MIN_HORIZONTAL_PROJECTION_FRACTION_SQUARED = 1e-12


def baseline_heading_degrees(baseline_ned_m: Sequence[float]) -> float:
    """Projected baseline bearing, rejecting zero/near-vertical directions.

    Scaling first prevents overflow/underflow and preserves unit/scale
    invariance.  A defined projection is still not generally Euler yaw.
    """
    baseline = np.asarray(baseline_ned_m, dtype=float)
    if baseline.shape != (3,) or np.any(~np.isfinite(baseline)):
        raise CLambdaError("baseline must be a finite NED vector")
    scale = float(np.max(np.abs(baseline)))
    if scale == 0.0:
        raise BaselineHeadingUndefined("zero baseline has undefined projected heading")
    normalized = baseline / scale
    fraction_squared = float((normalized[0]**2 + normalized[1]**2) /
                             np.dot(normalized, normalized))
    if fraction_squared <= MIN_HORIZONTAL_PROJECTION_FRACTION_SQUARED:
        raise BaselineHeadingUndefined("vertical/near-vertical baseline has undefined projected heading")
    return math.degrees(math.atan2(baseline[1], baseline[0]))


def body_yaw_from_ned_baseline(baseline_ned_m: Sequence[float]) -> float:
    return wrap_degrees(baseline_heading_degrees(baseline_ned_m) + 90.0)
'''
old_yang='''    if horizontal == 0.0 and down == 0.0:
        raise Yang2024Error("zero baseline has undefined attitude")
    heading = math.degrees(math.atan2(east, north)) % 360.0
'''
new_yang='''    try:
        heading = baseline_heading_degrees(baseline) % 360.0
    except BaselineHeadingUndefined as exc:
        raise Yang2024Error(str(exc), code=exc.code) from exc
'''
old_import='from .ext01_clambda import LambdaBridgeError, RTKLIBLambdaBridge'
new_import='from .ext01_clambda import (BaselineHeadingUndefined, LambdaBridgeError,\n                            RTKLIBLambdaBridge, baseline_heading_degrees)'
old_runner='''            result.update(baseline_ecef_m=baseline,baseline_ned_m=ned,baseline_length_m=np.linalg.norm(ned),
                          body_yaw_deg=cl.body_yaw_from_ned_baseline(ned))
    except (raw.RawBackendError,ValueError,np.linalg.LinAlgError) as exc:
        result["failure_code"]=getattr(exc,"code",type(exc).__name__)
'''
new_runner='''            result.update(baseline_ecef_m=baseline,baseline_ned_m=ned,baseline_length_m=np.linalg.norm(ned))
            result["body_yaw_deg"]=cl.body_yaw_from_ned_baseline(ned)
    except (raw.RawBackendError,ValueError,np.linalg.LinAlgError) as exc:
        # Candidate/certificate and any computed 3D baseline remain evidence;
        # a failed heading conversion never leaves a stale valid flag or yaw.
        result.update(valid=False,solution_state="INVALID",body_yaw_deg=None)
        result["failure_code"]=getattr(exc,"code",type(exc).__name__)
'''
assert texts['ext01_clambda.py'].count(old_cl)==1
assert texts['ext03_yang2024.py'].count(old_yang)==1 and texts['ext03_yang2024.py'].count(old_import)==1
assert texts['reproduction_runner.py'].count(old_runner)==1
texts['ext01_clambda.py']=texts['ext01_clambda.py'].replace(old_cl,new_cl)
texts['ext03_yang2024.py']=texts['ext03_yang2024.py'].replace(old_import,new_import).replace(old_yang,new_yang)
texts['reproduction_runner.py']=texts['reproduction_runner.py'].replace(old_runner,new_runner)
for name in files:(CODE/PREFIX/name).write_text(texts[name])
d={'schema':'post_result_ext_heading_source_change.v1','captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_freeze_release_receipt_sha256':sha(release),'old_sources':oldpins,'new_sources':{str(PREFIX/name):sha(CODE/PREFIX/name) for name in files},'old_nine_runs':oldruns,'old_results_not_modified':True,'no_solver_or_evaluator':True,'new_identity_role':'POST_RESULT_SOURCE_REPAIR_NOT_EXECUTED_FOR_OLD_9_OR_135'}
(ROOT/'EXT_HEADING_POST_RESULT_SOURCE_CHANGE.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps(d['new_sources'],indent=2))