# Experimental carrier-integrated LegSA-GINS

This is an executable research variant on research/ar-tim-exploration-20261006.
It does not replace default V3. A qualified integer candidate is an engineering
decision under the working noise model, not known physical FIX truth.

## Causal pipeline

1. Decode paired receiver RAWX and available broadcast navigation. Qualify full
   signal identities, phase units, half-cycle flags and per-receiver phase arcs.
   Baseline direction is GNSS2 minus GNSS1; the platform body-FRD vector is
   (0,-0.35,0) metres.
2. Form code and phase double differences separately within compatible
   constellation/frequency groups. Propagate the shared-pivot covariance and
   retain arc identities. Build geometry at the current raw-code anchor.
3. At five selection epochs, choose either every current integer or a stable
   subset with phase rank three, at least four ambiguities and at most eight.
   The partial rule sees geometry/covariance/selection arc continuity only.
4. Solve the original full-dimensional integer problem with a fixed-length
   baseline at every selection epoch. Unselected and historical integers remain
   integer nuisance parameters. A partial result needs two distinct selected
   classes and a global search certificate; seed quality cannot replace it.
5. Freeze both candidates before loading the next five validation epochs.
   Reject incomplete arc support, inadequate residual/length evidence or
   unresolved competition. Diagnose persistent phase directions on exactly
   the accepted support with the original covariance. A rejected observation
   stays absent from navigation.
6. Export the last validation epoch's ECEF baseline and complete 3x3 working
   covariance at that epoch's decision time. The mean is constrained to the
   physical length. Covariance is conditional fixed-N GLS plus the registered
   isotropic 1.5-degree angular floor; it excludes wrong-integer risk.
7. The native EKF consumes events in chronological order, splits measured IMU
   increments proportionally, rotates the full vector/covariance to current
   NED, and applies the body-vector attitude observation. An invalid-only
   carrier event does not split inertial propagation. Commercial yaw is not
   parsed in the external-carrier arms.
8. RD/RP use past samples at most once. Optional body-HV uses source-local
   forward/right velocity and a state-dependent attitude Jacobian, at a
   separate 0.20-second timer. This removes the former GNSS-yaw rotation in
   the online HV provider; shared-source correlations remain unmodelled.

## Executable entrypoints

- carrier_phase/real_trial.py prepare: raw observation models and lineage.
- carrier_phase/integration_frontend.py: full/partial integer selection,
  chronological future validation, failure records, 15-column ECEF output.
- carrier_phase/body_velocity_provider.py: dataset-qualified raw FLU velocity
  to body-FRD xy, no GNSS/attitude interpolation.
- carrier_phase/navigation_trial.py prepare/native/evaluate: four common-input
  navigation arms, --hv-mode off or body; reference is used by evaluate only.
- cpp/legsa_v23_port_core: full-covariance baseline and optional body-HV factors.

The Python entrypoints are under scripts/paper_rebuild and run with PYTHONPATH=src
inside Ubuntu 22.04 WSL. The actual commands, input paths and binaries for this
trial are retained in the scratch CARRIER_INTEGRATION_20261006 stage plans and
invocation records. The source modules live under src/legsa_gins/paper_rebuild.

## Fixed first-integration comparison

All arms use the same 66–340 second navigation interval, IMU, GNSS P/V, RD, RP,
initialization, timing scheduler and evaluation support. Within each HV group:
C0 is scalar dual-PVT yaw, C1 dual-PVT vector, C2 full carrier integer class,
C3 preselected partial carrier class. Both carrier methods use the same
100–340 second raw scope; no missing carrier is filled with receiver yaw.

Body-HV uses scale 1 and 0.20 m/s engineering standard deviation in both observed
axes, with .08-second maximum source age. Native NED-HV defaults remain unchanged.
The raw-body frame assumption is specific to these audited recordings; it is not
a universal vendor API assumption. Shared initialization is not an AR cold start.

## Current limitations requiring further development

The first frontend produces one full-class and seven partial-class measurements
in 120 registered windows. GPS-only SPP failures suppress 57 complete window
models; the first preparation also holds broadcast ephemeris at the available
100-second prefix. Causal anchor maintenance and advancing ephemeris reception
are the next input-availability improvements.

This initial implementation re-acquires per non-overlapping two-second window;
it does not yet hold admitted ambiguities as a continuous tracking state.
Persistent fault identification is diagnostic, not unique satellite attribution.
RAWX working covariance is not a field-calibrated temporal error model. The
receiver-derived evaluation reference is not independent ground truth.
