"""Build the opt-in scalar sphere library with explicit strict arithmetic flags."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

FLAGS=("-std=c++17", "-O3", "-fPIC", "-shared", "-fno-fast-math", "-ffp-contract=off", "-Wall", "-Wextra")

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build(output_dir: Path, *, compiler="g++") -> Path:
    root=Path(__file__).resolve().parents[3]
    source=root/"cpp/carrier_phase_sphere/sphere_root.cpp"
    output_dir=Path(output_dir).resolve()
    output_dir.mkdir(parents=True,exist_ok=True)
    library=output_dir/"liblegsa_sphere.so"
    manifest=output_dir/"BUILD_MANIFEST.json"
    if library.exists() or manifest.exists():
        raise FileExistsError("use a new output directory; existing builds are immutable")
    command=[compiler,*FLAGS,str(source),"-o",str(library)]
    compiled=subprocess.run(command,capture_output=True,text=True)
    (output_dir/"BUILD.log").write_text(compiled.stdout+compiled.stderr)
    compiled.check_returncode()
    version=subprocess.run([compiler,"--version"],check=True,capture_output=True,text=True).stdout.splitlines()[0]
    manifest.write_text(json.dumps({"schema":"legsa_sphere_build.v1","abi_version":1,
        "kernel_version":"delta_bisection_3d_v1","compiler":version,"command":command,
        "source":str(source),"source_sha256":digest(source),"build_script_sha256":digest(__file__),
        "library":str(library),"library_sha256":digest(library)},indent=2)+"\n")
    return library

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--compiler",default="g++")
    args=parser.parse_args()
    print(build(args.output_dir,compiler=args.compiler))
