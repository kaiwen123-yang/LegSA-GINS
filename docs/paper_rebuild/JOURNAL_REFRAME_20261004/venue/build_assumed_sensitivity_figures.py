"""Generate declared analytical illustrations, never measurements or V3 results.

No project scientific input/output, reference, native solver, generator or
estimator is read or invoked. This script uses only constants declared below.
It writes CSV + PNG/SVG and a calculation receipt next to itself. CLI has no
input-data option. Unknown physical parameters remain unknown.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "assumed_sensitivity"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.labelsize": 12, "axes.titlesize": 13,
                     "legend.fontsize": 10, "svg.fonttype": "none"})
ASSUMPTIONS = {
 "evidence_type": "ASSUMED_ANALYTICAL_ILLUSTRATION_NOT_CALIBRATION",
 "scientific_or_reference_files_read": 0, "scientific_runs": 0,
 "observed_project_metrics_used": False,
 "fig1": {"receiver_per_axis_sigma_m": 0.001,
          "receiver_N_E_axes_independent": True,
          "receiver_cross_covariance": "rho*sigma^2*I",
          "rho_values": [0.0, 0.5, 0.9],
          "horizontal_projection_r_m": [0.02, 0.35],
          "model": "local first-order heading; u=sqrt(2*(1-rho))*sigma/r",
          "example_target_heading_deg": 1.0,
          "target_is_practical_validity_threshold": False},
 "fig2": {"body_velocity_perpendicular_sigma_mps": 0.05,
          "heading_sigma_deg": 2.0, "speed_values_mps": [0.5, 1.0, 2.0],
          "rho_range": [-0.95, 0.95],
          "model": "horizontal local toy: delta(v_E)=delta(w_E)+V*delta(psi)",
          "model_variance": "sigma_w^2+(V*sigma_psi)^2+2*rho*sigma_w*V*sigma_psi"},
 "fig3": {"constant_translation_perpendicular_to_baseline_mps": 1.0,
          "horizontal_projection_r_values_m": [0.35, 0.10, 0.02],
          "unsigned_time_difference_ms_range": [0, 20],
          "true_baseline": "[r,0]", "asynchronous_difference": "[r,V*delta_t]",
          "angle_difference": "atan2(V*delta_t,r)",
          "is_standard_uncertainty": False,
          "rotation_acceleration_clock_estimation_model": False}
}

def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)

def figbase(title):
    fig, ax = plt.subplots(figsize=(8.8, 5.7))
    fig.subplots_adjust(left=.13, right=.97, bottom=.25, top=.84)
    fig.suptitle(title, y=.96, fontweight="bold")
    fig.text(.5,.89,"ASSUMED EXAMPLE — NOT FIELD CALIBRATION", ha="center", color="#a32524", fontsize=11)
    ax.grid(True, alpha=.23)
    return fig, ax

def save(fig, stem, footer):
    fig.text(.13,.13,footer,fontsize=9,va="top",linespacing=1.4)
    fig.savefig(OUT/(stem+".png"),dpi=180)
    fig.savefig(OUT/(stem+".svg"))
    plt.close(fig)

rows1=[]
fig,ax=figbase("Horizontal projection and shared receiver errors")
sigma=ASSUMPTIONS["fig1"]["receiver_per_axis_sigma_m"]
for rho,c in zip([0.,.5,.9],["#17699a","#cf7521","#39833f"]):
    rr=np.linspace(.02,.35,166)
    u=np.sqrt(2*(1-rho))*sigma/rr*180/np.pi
    ax.plot(rr*100,u,label=f"receiver correlation rho = {rho:.1f}",color=c,lw=2.2)
    for r,y in zip(rr,u):
        rows1.append({"evidence_type":"ASSUMED", "r_m":float(r), "receiver_sigma_m":sigma,
                      "receiver_rho":rho,"heading_u_first_order_deg":float(y)})
ax.axhline(1.,color="#6f6f6f",ls=":",lw=1.3,label="example target = 1 deg (not validated)")
ax.set(xlabel="Horizontal baseline projection r (cm)",ylabel="Local heading standard uncertainty (deg)",ylim=(0,4.3))
ax.legend(loc="upper right")
save(fig,"Fig_U01_projection_correlation", "Each receiver: assumed 1 mm per N/E axis; cross-covariance = rho*sigma^2*I.\nFirst-order circular-angle approximation. No actual receiver accuracy or admission threshold is inferred.")
write_csv("Fig_U01_projection_correlation.csv",rows1)

rows2=[]
fig,ax=figbase("Heading–velocity correlation in a rotated velocity aid")
sw=.05;sp=math.radians(2.)
for speed,c in zip([.5,1.,2.],["#17699a","#cf7521","#39833f"]):
    rho=np.linspace(-.95,.95,191)
    variance=sw**2+(speed*sp)**2+2*rho*sw*speed*sp
    assert np.all(variance>=0)
    u=np.sqrt(variance)
    ax.plot(rho,u,label=f"assumed forward speed = {speed:g} m/s",color=c,lw=2.2)
    for x,y,z in zip(rho,u,variance):
        rows2.append({"evidence_type":"ASSUMED","rho_heading_body_velocity":float(x),
                      "speed_mps":speed,"body_perpendicular_sigma_mps":sw,
                      "heading_sigma_deg":2.,"variance_m2ps2":float(z),"velocity_component_u_mps":float(y)})
ax.axvline(0,color="#6f6f6f",ls=":",lw=1.3)
ax.set(xlabel="Correlation of body lateral-velocity and heading errors",ylabel="Local east-velocity component uncertainty (m/s)")
ax.legend(loc="upper left")
save(fig,"Fig_U02_heading_velocity_cross_term","Horizontal local toy: delta(v_E) = delta(w_E) + V*delta(psi).\nAssumed sigma(w_E)=0.05 m/s and sigma(psi)=2 deg. Omitting the cross term can raise or lower the result.")
write_csv("Fig_U02_heading_velocity_cross_term.csv",rows2)

rows3=[]
fig,ax=figbase("Asynchronous position differencing can rotate a short baseline")
for r,c in zip([.35,.10,.02],["#17699a","#cf7521","#39833f"]):
    ms=np.linspace(0,20,201);dt=ms/1000
    ang=np.arctan2(dt,r)*180/np.pi
    ax.plot(ms,ang,label=f"assumed horizontal projection = {r*100:g} cm",color=c,lw=2.2)
    for x,t,y in zip(ms,dt,ang):
        rows3.append({"evidence_type":"ASSUMED","time_difference_ms":float(x),
                      "r_m":r,"perpendicular_translation_speed_mps":1.,
                      "asynchronous_baseline_E_m":float(t),"deterministic_direction_difference_deg":float(y)})
ax.set(xlabel="Unsigned inter-receiver observation time difference (ms)",ylabel="Deterministic direction difference (deg)",ylim=(0,48))
ax.legend(loc="upper left")
save(fig,"Fig_U03_asynchronous_direction","Exact toy geometry: true b=[r,0], asynchronous b=[r,1 m/s * delta_t].\nNo rotation or acceleration; not a stochastic uncertainty, measured clock offset, or V3 timing error.")
write_csv("Fig_U03_asynchronous_direction.csv",rows3)

# Calculation checks on the declared toy inputs only; not a scientific validation.
checks=[]
for r,rho in [(.35,0),(.10,.5),(.02,.9)]:
    j=np.array([0.,1/r]);ss=sigma*sigma*np.eye(2)
    sb=ss+ss-rho*ss-rho*ss
    matrix=math.sqrt(float(j@sb@j))*180/math.pi
    scalar=math.sqrt(2*(1-rho))*sigma/r*180/math.pi
    checks.append({"kind":"declared covariance matrix versus scalar expression", "r_m":r,"rho":rho,"matrix_deg":matrix,"scalar_deg":scalar,"passed":abs(matrix-scalar)<1e-12})
for rho in [-.95,0,.95]:
    V=1.;cov=np.array([[sw*sw,rho*sw*sp],[rho*sw*sp,sp*sp]])
    eigen=np.linalg.eigvalsh(cov);J=np.array([1.,V])
    val=math.sqrt(float(J@cov@J))
    scalar=math.sqrt(sw*sw+(V*sp)**2+2*rho*sw*V*sp)
    checks.append({"kind":"declared 2-input PSD and propagated variance", "rho":rho,"min_eigenvalue":float(eigen[0]),"matrix_mps":val,"scalar_mps":scalar,"passed":eigen[0]>=0 and abs(val-scalar)<1e-12})
checks.append({"kind":"time toy exact zero difference","passed":math.atan2(0,.35)==0})
checks.append({"kind":"CSV row counts", "counts":[len(rows1),len(rows2),len(rows3)],"passed":[len(rows1),len(rows2),len(rows3)]==[498,573,603]})
assert all(c["passed"] for c in checks)
(OUT/"ASSUMPTIONS_AND_CALCULATION_CHECKS.json").write_text(json.dumps({"assumptions":ASSUMPTIONS,"checks":checks,"all_calculation_checks_passed":True,"visual_review":"PENDING_ACTUAL_PNG_VIEW"},indent=2)+"\n",encoding="utf-8")
print(json.dumps({"csv_rows":[498,573,603],"calculation_checks":len(checks),"all_passed":True,"output_dir":str(OUT)}))
