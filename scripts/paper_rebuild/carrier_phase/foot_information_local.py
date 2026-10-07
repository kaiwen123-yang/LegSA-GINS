"""Finite synthetic qualification runner. No real-data or evaluator invocation."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OLD=Path(os.environ["OLD_FOOT_HARNESS"])
OLD_SHA="5a291e41120a44e98de8a921219e563c8408c084e20f8851beea833679c0b6d5"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("--stage",type=Path,required=True);a=p.parse_args();stage=a.stage.resolve()
    scratch=Path(os.environ["LEGSA_SCRATCH_ROOT"]).resolve()
    if not stage.is_relative_to(scratch) or stage.exists():raise RuntimeError("new scratch stage required")
    assert sha(OLD)==OLD_SHA,"old sealed synthetic harness hash mismatch"
    stage.mkdir(parents=True);build=stage/"BUILD"
    plan=ROOT/"docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007/FOOT_INFORMATION_LOCAL_PLAN.json"
    (stage/"LOCAL_PLAN.json").write_bytes(plan.read_bytes())
    sources=list((ROOT/"cpp/legsa_v23_port_core").rglob("*.cpp"))+list((ROOT/"cpp/legsa_v23_port_core").rglob("*.hpp"))
    sources += [ROOT/"tests/paper_rebuild/native_attitude_clone_harness.cpp",ROOT/"tests/paper_rebuild/test_native_attitude_clone.py",ROOT/"tests/paper_rebuild/test_foot_information_diagnostic.py",ROOT/"scripts/paper_rebuild/carrier_phase/foot_information_diagnostic.py"]
    pins={str(x.relative_to(ROOT)):sha(x) for x in sources}
    (stage/"SOURCE_PINS.json").write_text(json.dumps(pins,indent=2)+"\n")
    env=os.environ.copy();env.update(PYTHONPATH=str(ROOT/"src"),OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1",NATIVE_CLONE_TEST_STAGE=str(stage),OLD_FOOT_HARNESS=str(OLD),LEGSA_FOOT_INFORMATION_DIAGNOSTICS="0")
    calls=[]
    def invoke(name,cmd):
        before=time.monotonic()
        with (stage/(name+".log")).open("w") as log:
            result=subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        row=dict(name=name,command=cmd,exit_code=result.returncode,elapsed_s=time.monotonic()-before)
        calls.append(row);(stage/(name+".json")).write_text(json.dumps(row,indent=2)+"\n")
        (stage/"CALLS.json").write_text(json.dumps(calls,indent=2)+"\n")
        print(json.dumps(row),flush=True)
        if result.returncode:raise RuntimeError("preserved first failure: "+name)
    invoke("01_CONFIGURE",["cmake","-S",str(ROOT/"cpp"),"-B",str(build),"-DCMAKE_BUILD_TYPE=Release"])
    invoke("02_BUILD",["cmake","--build",str(build),"--target","legsa_v23_port_core_demo","-j","4"])
    invoke("03_HARNESS_COMPILE",["g++","-std=c++17","-O2","-I"+str(ROOT/"cpp/legsa_v23_port_core/include"),str(ROOT/"tests/paper_rebuild/native_attitude_clone_harness.cpp"),str(build/"liblegsa_v23_port_core.a"),"-o",str(stage/"native_attitude_clone_harness")])
    invoke("04_TESTS",["python3","-m","pytest","-q","tests/paper_rebuild/test_native_attitude_clone.py","tests/paper_rebuild/test_foot_information_diagnostic.py","-k","not test_09 and not test_10","--junitxml="+str(stage/"04_TESTS.xml")])
    assert pins=={k:sha(ROOT/k) for k in pins},"source changed during local qualification"
    receipt=dict(status="PASS_24_SYNTHETIC_CASES",calls=calls,binary_sha256=sha(build/"legsa_v23_port_core_demo"),harness_sha256=sha(stage/"native_attitude_clone_harness"),old_harness_sha256=OLD_SHA,source_pins=pins,raw_reads=0,reference_reads=0,real_navigation_calls=0,evaluator_calls=0)
    (stage/"RECEIPT.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({k:v for k,v in receipt.items() if k not in ("source_pins","calls")}),flush=True)
if __name__=="__main__":main()
