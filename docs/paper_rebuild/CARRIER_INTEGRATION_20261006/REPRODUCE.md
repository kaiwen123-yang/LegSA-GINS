# Run the experimental carrier path

All numerical commands run inside Ubuntu 22.04 WSL on the E-drive installation.
The experiment is opt-in; default V3 configuration is unchanged.

## Inputs and entrypoints

Start with the prepared raw model trial described in INPUT_LIFECYCLE.md and
CAUSAL_INPUT_V2_PLAN.md. Its PLAN.json binds the raw/model lineage, wavelength,
broadcast availability, ambiguity arcs and physical baseline length.
REAL_100_340_V2 is the completed trial used here. Do not substitute receiver
heading, reference trajectory or a legacy exported solution for raw models.
Raw preparation uses scripts/paper_rebuild/carrier_phase/real_trial.py.

The optional native sphere library is built with
scripts/paper_rebuild/carrier_phase/build_native_sphere.py --output-dir NEW_DIR.
It requires g++ and writes its compiler/ABI/kernel/source manifest. A new build's
identity must be recorded; it need not have the binary hash of the historical
build. The integer solver also uses the RTKLIB library bound by the prepared
trial. Omitting --sphere-library selects the Python sphere backend.

Set REPO to the WSL checkout, PREPARED to the prepared trial, SPHERE to the
explicit library and OUT to a fresh experiment directory. The example below
reproduces the final dense configuration; running it is new numerical work,
not a read-only way of opening the saved results.

    from pathlib import Path
    import os
    import subprocess

    repo = Path(os.environ["REPO"]).resolve()
    prepared = Path(os.environ["PREPARED"]).resolve()
    sphere = Path(os.environ["SPHERE"]).resolve()
    out = Path(os.environ["OUT"]).resolve()
    out.mkdir(exist_ok=False)
    scripts = repo / "scripts/paper_rebuild/carrier_phase"
    env = os.environ.copy()
    env.update(PYTHONPATH=str(repo / "src"),
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")

    def run(script, *args):
        subprocess.run(["python3", str(scripts / script), *map(str, args)],
                       cwd=repo, env=env, check=True)

    run("integration_frontend.py",
        "--trial", prepared, "--output", out / "FRONTEND",
        "--modes", "partial", "--partial-max-ambiguities", 6,
        "--likelihood", "selected-support", "--sphere-library", sphere,
        "--nodes", 100000, "--timeout", 30,
        "--starts", *(f"{100+i/5:.1f}" for i in range(1191)))
    summary = out / "FRONTEND/SUMMARY_0001.json"
    run("tracking_frontend.py",
        "--trial", prepared, "--summary", summary,
        "--output", out / "TRACKING", "--modes", "partial")
    run("latency_tracking_frontend.py",
        "--trial", prepared, "--summary", summary,
        "--original-tracking-summary", out / "TRACKING/SUMMARY.json",
        "--output", out / "SERIAL", "--modes", "partial")

The output for the latency-accounted integration is
SERIAL/CARRIER_LATENCY_TRACKED_PARTIAL.csv. Invalid rows are intentional:
they preserve absence of a qualified current carrier observation. The ordinary
TRACKING output is a separate data-time result without charged search latency.
The serial replay charges recorded CILS costs only; it is not a deployed
real-time worker. Actual driver records, commands and source freeze remain
with the completed WSL scratch outputs.

## Native navigation integration

navigation_trial.py has prepare, native and evaluate phases. Prepare binds the
existing binary/config checker, prior registration, common GNSS providers,
full/partial carrier CSVs and optional raw body-frame velocity. Its four arms
compare scalar PVT heading, vector PVT baseline, full-class carrier and partial
carrier. For the final experiment use --hv-mode body and the registered
BODY_VELOCITY provider. Clone frozen configurations by line replacement;
do not round-trip them through YAML.

The prepared PLAN records the actual last IMU time 339.997056 s separately
from the nominal evaluation window ending at 340 s. Do not overwrite the
native end time with the nominal window boundary. Complete all four native
runs before invoking evaluate. The reference is available only to evaluation.
Use a fresh stage for each carrier stream. Recorded prepare/native/evaluate
invocations under NAVIGATION_DRIVER_DENSE_SELECTED provide the exact local
paths used in this experiment.

## Meaning of a result

A global certificate proves the searched integer optimum under the registered
likelihood and limits. Subsequent qualification checks future observations;
it does not establish physical integer truth. Tracking preserves both frozen
candidate classes, allows the baseline direction to move, and releases a
failed track permanently. More overlapping windows do not count as independent
correct fixes. The final result must be judged from full-support navigation,
availability, latency and failures together; see ALGORITHM.md and the dense
frontend/navigation readouts.
