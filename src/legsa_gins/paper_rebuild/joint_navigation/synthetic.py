"""Continuous synthetic input for the joint support--carrier navigator.

NED world; body forward/right/down. Accelerometers measure R.T @ (a-g).
The estimator receives only events and metadata; truth and
evaluation_metadata are separate evaluation-only products. A diagonal trot
transitions to standing. Common contact motion later contradicts fixed-world
support without changing pair geometry. Force identities do not disclose it.
This is a continuous kinematic sensor simulation, not rigid-body dynamics.
The IMU uses the repository's recovered Go2 continuous noise profile, including
nonzero bias random walks. Initial bias values and priors are engineering inputs;
Allan bias-instability diagnostics are not used as initial bias uncertainty.
"""
from __future__ import annotations
from functools import lru_cache
import math
import numpy as np
from scipy.integrate import quad
from ..carrier_phase.temporal import EpochBlock

BASELINE_BODY_M = np.array([0.0, -0.35, 0.0])
GRAVITY_N = np.array([0.0, 0.0, 9.81])
FOOT_SIGMA_M = 0.01
FOOT_CORRELATION_S = 0.08
CODE_SD_SIGMA_M = 0.30
PHASE_SD_SIGMA_M = 0.003
L1_WAVELENGTH_M = 299792458.0 / 1575420000.0
GO2_IMU_PROFILE_PATH = (
    "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/"
    "04_METHOD_CONTRACTS/GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml")
# Source profile lines 32-72: continuous amplitudes, never per-sample sigmas.
GYRO_WHITE_DENSITY = 2.865130e-04    # rad/s/sqrt(Hz), lines 33-42
ACCEL_WHITE_DENSITY = 1.285395e-03   # m/s^2/sqrt(Hz), lines 43-52
GYRO_BIAS_RW_DENSITY = 2.996871e-05  # rad/s^2/sqrt(Hz), lines 53-62
ACCEL_BIAS_RW_DENSITY = 1.594412e-04 # m/s^3/sqrt(Hz), lines 63-72
# The profile supplies no initial bias covariance (lines 94-104 explicitly
# exclude its instability diagnostics). Use the existing NavigationBranch
# engineering defaults, not the Allan bias-instability magnitudes.
INITIAL_ACCEL_BIAS_PRIOR_SIGMA = .03
INITIAL_GYRO_BIAS_PRIOR_SIGMA = .003
GAIT_PERIOD_S = 0.72
STANCE_FRACTION = 0.64
FOOT_PHASE_S = np.array([0.0, 0.36, 0.36, 0.0])  # FR FL RR RL
FOOT_NOMINAL_BODY_M = np.array([
    [0.20, 0.10, 0.42], [0.20, -0.10, 0.42],
    [-0.20, 0.10, 0.42], [-0.20, -0.10, 0.42],
])


def _motion_clock(t: float) -> tuple[float, float, float]:
    """Smoothly stop at 65 s, stand to 78 s, resume by 83 s."""
    if t < 60.0:
        return t, 1.0, 0.0
    if t < 65.0:
        u = (t - 60.0) / 5.0
        return (60.0 + (t - 60.0)/2 + 2.5/math.pi*math.sin(math.pi*u),
                (1 + math.cos(math.pi*u))/2, -math.pi/10*math.sin(math.pi*u))
    if t < 78.0:
        return 62.5, 0.0, 0.0
    if t < 83.0:
        u = (t - 78.0) / 5.0
        return (62.5 + (t - 78.0)/2 - 2.5/math.pi*math.sin(math.pi*u),
                (1 - math.cos(math.pi*u))/2, math.pi/10*math.sin(math.pi*u))
    return t - 18.0, 1.0, 0.0


def _base_motion(s: float):
    yaw = 0.018*s + 0.32*math.sin(0.21*s)
    yaw_rate = 0.018 + 0.0672*math.cos(0.21*s)
    speed = 0.24*(1 - math.exp(-0.5*s*s))
    speed_rate = 0.24*s*math.exp(-0.5*s*s)
    forward = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    side = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
    v = speed*forward
    a = speed_rate*forward + speed*yaw_rate*side
    v[2] = 0.0048*math.sin(0.6*s)
    a[2] = 0.00288*math.cos(0.6*s)
    return yaw, yaw_rate, v, a


@lru_cache(maxsize=32768)
def _base_position(s: float) -> np.ndarray:
    north = quad(lambda q: _base_motion(q)[2][0], 0., s,
                 epsabs=1e-10, epsrel=1e-10)[0]
    east = quad(lambda q: _base_motion(q)[2][1], 0., s,
                epsabs=1e-10, epsrel=1e-10)[0]
    return np.array([north, east, -0.42 + 0.008*(1 - math.cos(0.6*s))])


def _kinematics(t: float, *, position: bool = True) -> dict:
    s, rate, rate_dot = _motion_clock(t)
    yaw, yaw_rate, base_v, base_a = _base_motion(s)
    roll, pitch = 0.07*math.sin(0.7*s), 0.06*math.sin(0.5*s)
    roll_rate = 0.049*math.cos(0.7*s)*rate
    pitch_rate = 0.03*math.cos(0.5*s)*rate
    yaw_rate *= rate
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    R = np.array([
        [cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
        [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
        [-sp, cp*sr, cp*cr]])
    omega = np.array([roll_rate-yaw_rate*sp,
                      pitch_rate*cr+yaw_rate*sr*cp,
                      -pitch_rate*sr+yaw_rate*cr*cp])
    result = dict(R=R, v=base_v*rate,
                  acceleration=base_a*rate*rate+base_v*rate_dot,
                  omega_body=omega)
    if position:
        result["p"] = _base_position(float(s)).copy()
    return result


def _stance(t: float, foot: int) -> bool:
    if 65.0 <= t < 78.0:
        return True
    gait_time = t if t < 65.0 else t - 78.0
    phase = (gait_time + float(FOOT_PHASE_S[foot])) % GAIT_PERIOD_S
    if GAIT_PERIOD_S-phase < 1e-9:
        phase = 0.0
    return phase < STANCE_FRACTION*GAIT_PERIOD_S - 1e-9


def _contact_translation(t: float) -> np.ndarray:
    u = float(np.clip((t-67.0)/3.0, 0., 1.))
    fraction = 10*u**3 - 15*u**4 + 6*u**5
    return np.array([0.18*fraction, 0., 0.])


def _event_times(duration: float, key_dt: float) -> list[float]:
    times = {0., round(duration, 10)}
    for step in (key_dt, .2, 1.):
        times.update(round(float(t), 10) for t in np.arange(0., duration+1e-10, step))
    for lo, hi, origin in ((0., min(duration, 65.), 0.), (78., duration, 78.)):
        if hi < lo:
            continue
        for phase in set(FOOT_PHASE_S):
            for k in range(-2, int((hi-origin)/GAIT_PERIOD_S)+3):
                for edge in (0., STANCE_FRACTION*GAIT_PERIOD_S):
                    t = origin + k*GAIT_PERIOD_S - phase + edge
                    if lo <= t <= hi:
                        times.add(round(t, 10))
    for t in (25., 35., 40., 55., 60., 65., 67., 70., 77., 78., 83.):
        if t <= duration:
            times.add(t)
    return sorted(t for t in times if 0. <= t <= duration)


def _on_grid(t: float, step: float) -> bool:
    return abs(t/step-round(t/step)) < 1e-8


def generate_scene(duration_s: float = 90.0, seed: int = 6100801,
                   key_dt: float = .1, imu_dt: float = .01) -> dict:
    """Return causal events, separate truth, and known sensor settings.

    Event fields: time_s; imu Nx7 [dt, ax,ay,az,gx,gy,gz] between previous
    event and this event; optional carrier EpochBlock; stance feet; optional
    gnss_position and gnss_velocity. IMU uses interval midpoints and t0 has
    an empty packet. Carrier rows are code DD then observed phase DD, metres.
    Shared-pivot DD covariance is sigma_SD^2 (I+11.T). Code-only epochs have
    A.shape=(5,0). Lost phase relations receive new physical labels on return.

    White sensor rate samples use density/sqrt(dt). Bias endpoints follow
    b_next = b + density*sqrt(dt)*z; their interval mean is sampled jointly
    with the endpoint using the independent Brownian-bridge mean term. This
    preserves both the registered bias random walk and its rate contribution.

    Foot body noise is stationary OU/AR(1), independently begun per observed
    force arc. Its sigma/tau must be used to avoid counting repeated points
    as IID. No true integers, world contacts, state, fault labels or
    truth-triggered revocation notice occurs in an event.
    """
    if not (math.isfinite(duration_s) and duration_s > 0 and
            math.isfinite(key_dt) and key_dt > 0 and
            math.isfinite(imu_dt) and imu_dt > 0):
        raise ValueError("duration, key_dt and imu_dt must be positive and finite")
    # Appending a sixth child preserves the original five stream identities;
    # bias draws do not change code, feet, GNSS, phase, or IMU-white draws.
    streams = np.random.SeedSequence(seed).spawn(6)
    imu_rng, foot_rng, code_rng, phase_rng, gnss_rng, bias_rng = [
        np.random.default_rng(stream) for stream in streams]
    # Fixed engineering initial sensor errors, not recovered Allan fit values.
    bias = np.array([.015, -.012, .010, 2e-5, -1.5e-5, 3e-5])
    bias_density = np.r_[np.full(3, ACCEL_BIAS_RW_DENSITY),
                         np.full(3, GYRO_BIAS_RW_DENSITY)]
    accel_density, gyro_density = ACCEL_WHITE_DENSITY, GYRO_WHITE_DENSITY
    gnss_p_sigma = np.array([.05, .05, .08])
    gnss_v_sigma = np.array([.04, .04, .04])
    azimuth = np.radians([5., 65., 125., 195., 250., 315.])
    elevation = np.radians([62., 35., 52., 27., 71., 42.])
    los = np.column_stack((np.cos(elevation)*np.cos(azimuth),
                           np.cos(elevation)*np.sin(azimuth), -np.sin(elevation)))
    design = los[0]-los[1:]
    # Simulator-private values; none are returned.
    initial_integers = np.array([8, -5, 12, 3, -9])
    reopened_integers = np.array([8, -5, -7, 14, 5])
    reacquired_integers = np.array([-11, 7, 4, -8, 13])
    contacts: dict[int, dict] = {}
    arc_counter = [0]*4
    events, truth = [], []
    previous_time = 0.
    for t in _event_times(float(duration_s), float(key_dt)):
        state = _kinematics(t)
        rows = []
        interval = t-previous_time
        if interval > 0:
            pieces = max(1, math.ceil(interval/imu_dt-1e-10))
            dt = interval/pieces
            for j in range(pieces):
                midpoint = previous_time+(j+.5)*dt
                source = _kinematics(midpoint, position=False)
                specific_force = source["R"].T@(source["acceleration"]-GRAVITY_N)
                step_bias = bias_density*math.sqrt(dt)*bias_rng.normal(size=6)
                # Conditional on endpoint increment db, Brownian mean is
                # b + db/2 + density*sqrt(dt/12)*z_independent.
                mean_bias = (bias + .5*step_bias +
                             bias_density*math.sqrt(dt/12.)*bias_rng.normal(size=6))
                accel = specific_force+mean_bias[:3]+accel_density/math.sqrt(dt)*imu_rng.normal(size=3)
                gyro = source["omega_body"]+mean_bias[3:]+gyro_density/math.sqrt(dt)*imu_rng.normal(size=3)
                bias += step_bias
                rows.append(np.r_[dt, accel, gyro])
        imu = np.asarray(rows, dtype=float).reshape((-1, 7))
        foot_observations = []
        for foot in range(4):
            force = 120.+8.*math.sin(1.5*t+foot) if _stance(t, foot) else 0.
            observed_support = force > 60.
            if not observed_support:
                contacts.pop(foot, None)
                continue
            if foot not in contacts:
                arc_counter[foot] += 1
                world_point = state["p"]+state["R"]@FOOT_NOMINAL_BODY_M[foot]
                world_point[2] = 0.
                contacts[foot] = dict(
                    arc_id=f"force_{foot}_{arc_counter[foot]:04d}",
                    world=world_point, started=t, last_time=t,
                    error=foot_rng.normal(0., FOOT_SIGMA_M, size=3),
                    long_stance_member=False)
            contact = contacts[foot]
            if 65. <= t < 67.:
                contact["long_stance_member"] = True
            elapsed = t-contact["last_time"]
            if elapsed > 0:
                rho = math.exp(-elapsed/FOOT_CORRELATION_S)
                contact["error"] = (rho*contact["error"] +
                    FOOT_SIGMA_M*math.sqrt(-math.expm1(-2*elapsed/FOOT_CORRELATION_S))*
                    foot_rng.normal(size=3))
            contact["last_time"] = t
            displacement = _contact_translation(t) if contact["long_stance_member"] else np.zeros(3)
            point_body = state["R"].T@(contact["world"]+displacement-state["p"])
            foot_observations.append(dict(arc_id=contact["arc_id"], foot_id=foot,
                                           point_body=point_body+contact["error"],
                                           force=float(force)))
        carrier = None
        if _on_grid(t, .2):
            phase_indices = (np.arange(2) if 25. <= t < 35. else
                             np.empty(0, dtype=int) if 40. <= t < 55. else np.arange(5))
            integers = (initial_integers if t < 35. else
                        reopened_integers if t < 55. else reacquired_integers)
            generations = [0 if t < 55. else 2 for _ in range(5)]
            if 35. <= t < 55.:
                generations[2:] = [1]*3
            labels = tuple(f"G01_G{int(i)+2:02d}_L1_arc{generations[int(i)]}" for i in phase_indices)
            nphase = len(phase_indices)
            B = np.vstack((design, design[phase_indices]))
            A = np.zeros((5+nphase, nphase))
            A[5:] = L1_WAVELENGTH_M*np.eye(nphase)
            baseline = state["R"]@BASELINE_BODY_M
            code_sd = code_rng.normal(0., CODE_SD_SIGMA_M, 6)
            phase_sd = phase_rng.normal(0., PHASE_SD_SIGMA_M, 6)
            y = B@baseline+np.r_[code_sd[1:]-code_sd[0],
                                  phase_sd[phase_indices+1]-phase_sd[0]]
            y[5:] += L1_WAVELENGTH_M*integers[phase_indices]
            Q = np.zeros((5+nphase, 5+nphase))
            Q[:5, :5] = CODE_SD_SIGMA_M**2*(np.eye(5)+np.ones((5, 5)))
            Q[5:, 5:] = PHASE_SD_SIGMA_M**2*(np.eye(nphase)+np.ones((nphase, nphase)))
            carrier = EpochBlock(t, y, A, B, Q, labels, metadata=dict(
                baseline_frame="NED", row_units="m", code_rows=5,
                phase_dd_indices=phase_indices.tolist(),
                covariance_model="shared_pivot_DD_from_independent_SD_code_and_phase",
                source="synthetic_raw_dual_antenna"))
        gnss_position = gnss_velocity = None
        if _on_grid(t, 1.) and not 65. <= t < 77.:
            gnss_position = state["p"]+gnss_p_sigma*gnss_rng.normal(size=3)
            gnss_velocity = state["v"]+gnss_v_sigma*gnss_rng.normal(size=3)
        events.append(dict(time_s=t, imu=imu, carrier=carrier, feet=foot_observations,
                           gnss_position=gnss_position, gnss_velocity=gnss_velocity))
        truth.append(dict(time_s=t, R=state["R"].copy(), p=state["p"].copy(),
                          v=state["v"].copy(), bias_acc=bias[:3].copy(), bias_gyro=bias[3:].copy()))
        previous_time = t
    metadata = dict(
        schema="joint_navigation.synthetic.v2", data_mode="synthetic",
        carrier_label_mode="synthetic_scalar",
        duration_s=float(duration_s), seed=int(seed), key_dt_s=float(key_dt),
        imu_max_dt_s=float(imu_dt), baseline_body=BASELINE_BODY_M.copy(),
        gravity_n=GRAVITY_N.copy(), body_frame="FRD", world_frame="NED",
        imu_accel_convention="specific_force_R_transpose_acceleration_minus_gravity",
        imu_row_order=("dt", "ax", "ay", "az", "gx", "gy", "gz"),
        imu_sampling="interval_midpoint_average_rate_approximation",
        accel_noise_density=accel_density, gyro_noise_density=gyro_density,
        accel_bias_prior_sigma=INITIAL_ACCEL_BIAS_PRIOR_SIGMA,
        gyro_bias_prior_sigma=INITIAL_GYRO_BIAS_PRIOR_SIGMA,
        accel_bias_random_walk=ACCEL_BIAS_RW_DENSITY,
        gyro_bias_random_walk=GYRO_BIAS_RW_DENSITY,
        imu_noise_source=dict(
            profile_id="GO2_IMU_ALLAN_90MIN_RECOVERED_V1",
            repository_file=GO2_IMU_PROFILE_PATH,
            parameter_lines=dict(gyro_noise_density="33-42", accel_noise_density="43-52",
                                 gyro_bias_random_walk="53-62", accel_bias_random_walk="63-72"),
            stochastic_model_lines="25-30",
            units=dict(gyro_noise_density="rad/s/sqrt(Hz)",
                       accel_noise_density="m/s^2/sqrt(Hz)",
                       gyro_bias_random_walk="rad/s^2/sqrt(Hz)",
                       accel_bias_random_walk="m/s^3/sqrt(Hz)"),
            evidence="THESIS_AND_CONTEMPORANEOUS_TERMINAL_RECORD_CROSS_CONFIRMED",
            original_static_csv_available=False, original_fitting_script_available=False,
            bias_instability_used_as_initial_sigma=False),
        imu_bias_process="continuous_random_walk_with_joint_endpoint_and_interval_mean",
        initial_bias_prior_source=dict(
            role="ENGINEERING_PRIOR_NOT_ALLAN_MEASUREMENT",
            source="existing_NavigationBranch_defaults",
            accel_sigma_unit="m/s^2", gyro_sigma_unit="rad/s",
            profile_has_initial_bias_covariance=False,
            profile_excludes_instability_as_initial_covariance_lines="94-104"),
        foot_sigma=FOOT_SIGMA_M, foot_correlation_tau_s=FOOT_CORRELATION_S,
        foot_noise_model="stationary_body_frame_AR1_per_force_arc",
        force_support_threshold=60., force_units="uncalibrated_SDK_proxy",
        contact_identity="causal_rising_edge_of_observed_force_proxy",
        code_sigma=CODE_SD_SIGMA_M, phase_sigma=PHASE_SD_SIGMA_M,
        carrier_sigma_convention="single_difference_before_shared_pivot_DD",
        carrier_period_s=.2, gnss_period_s=1.,
        gnss_position_sigma=gnss_p_sigma, gnss_velocity_sigma=gnss_v_sigma,
        source_noise_assumption="independent_synthetic_streams_except_DD_and_foot_time_correlations",
        scenario_kind="continuous_kinematic_sensor_scene_not_rigid_body_dynamics",
        online_truth_used=False)
    evaluation_metadata = dict(
        evaluation_only=True,
        stages=[
            dict(interval_s=(0., 25.), description="tilted_turning_and_support_changes"),
            dict(interval_s=(25., 35.), description="two_of_five_phase_relations_remain"),
            dict(interval_s=(40., 55.), description="all_carrier_phase_absent_code_remains"),
            dict(interval_s=(55., 65.), description="fresh_physical_carrier_arcs"),
            dict(interval_s=(65., 78.), description="persistent_standing_support"),
            dict(interval_s=(67., 70.), description="all_four_contacts_translate_together"),
            dict(interval_s=(65., 77.), description="receiver_navigation_products_absent"),
            dict(interval_s=(77., float(duration_s)), description="receiver_corroboration_and_resume")],
        common_contact_displacement_n_m=np.array([.18, 0., 0.]),
        detection_policy="no_injected_revocation_estimator_uses_observed_inconsistency",
        contact_geometric_assumption="fixed_world_except_evaluation_only_common_sliding",
        validity_note="stages_beyond_requested_duration_are_not_executed")
    return dict(events=events, truth=truth, metadata=metadata,
                evaluation_metadata=evaluation_metadata)
