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
   subset with phase rank three, at least four ambiguities and a registered upper cap (default eight; the
   six-cap development trial changes only this limit).
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

See REPRODUCE.md for the opt-in frontend/tracking/serial command sequence and
native integration input contract.

- carrier_phase/real_trial.py prepare: raw observation models and lineage.
- carrier_phase/integration_frontend.py: full/partial integer selection,
  chronological future validation, failure records, 15-column ECEF output.
- carrier_phase/tracking_frontend.py: causal fixed-N tracking of saved qualified
  acquisitions; explicit release, immutable selection identity and one owner.
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

## Continuous fixed-candidate tracking

The optional tracker separates integer discovery from current-epoch measurement
generation. A track starts only from a qualified acquisition whose original
five-model admission, phase diagnosis and measurement reproduce under the same
policies. The original primary/competitor integers, selected_at, active labels
and source fingerprints remain fixed throughout that track.

Each new 0.2-second slot shifts a five-epoch validation window. The fixed-N GLS
still fits a separate moving baseline at every epoch; tracking does not freeze
the baseline direction. The original residual/length/competition gates and
persistent phase diagnostic are recomputed. A distinct tracking receipt binds
the original acquisition, explicit window times, numerical models and physical
SD fault maps. The last model alone generates the current baseline and covariance.

The first timing gap, selected arc break, deficient geometry, failed gate or
fault diagnostic ends the track permanently. The controller uses one incumbent
per raw epoch, including its failure epoch; overlapping new acquisitions are
logged as suppressed and never queued. Initial measurement is emitted once.
No integer search occurs during tracking, and no old candidate is resurrected.

Twenty-five tracking-library tests and ten controller tests cover dynamic
baselines with known integers, full covariance, independent synthetic SD
geometry, wrong-integer aliases, policy/model mutation, time gaps, terminal
release and owner conflicts. The combined affected-library test set contains
121 passing tests. In the alias counterexample both the wrong and true
competitor fit, so the method returns unresolved competition. Consistency
under an assumed model does not establish integer truth.

## Optional preselected-observation likelihood

The selected-support mode chooses the same labels S using the original
selection-window geometry, covariance and arc identities, before evaluating
integer residuals. It retains R: all code rows plus phase rows with exactly zero
coefficients on every unselected integer. The new problem uses y[R], A[R,S],
B[R] and Q[R,R]. Shared-pivot correlations remain; Q is a marginal principal
submatrix, never a Schur conditional covariance. This is a different
observation likelihood, not an equivalent profile of the original full problem.

The actual reduced problem, source-row identities and selected labels are
fingerprinted. The top two globally certified classes are frozen with the
SELECTED_OBSERVATION_MARGINAL_Q_V1 source prefix. Validation and tracking still
consume the original current models, retain only the fixed support, and use
unchanged residual/length/competition/phase gates. Losing a selected arc still
releases the track. The full-nuisance mode remains available for comparison.

integration_frontend.py accepts --likelihood original (default) or
--likelihood selected-support with partial mode. --sphere-library is an
independent opt-in numerical backend; its ABI/kernel/library SHA enters the
certificate and input contract. Omitting it keeps Python. The selected-support
trial deliberately uses Python, while NATIVE_FULL6 keeps the original
likelihood and changes only equivalent numerical implementation.

The complete 120-window native full-likelihood trial certifies all 120 and
matches the original 112 certified candidate pairs, admissions and measurements
within floating-point tolerance. It produces 71 uncharged and 26 serial
measurements. The separate selected-support trial also certifies all 120,
uses exactly six integers, and produces 62 measurements in either replay;
its two 1200-row streams are byte-identical. It launches all 120 scheduled
opportunities without busy drops. Search median/P95 are 0.135904/0.498868 s.
These are recorded-service-time results with zero other processing costs.
Primary selected integers agree in 111/120 windows between the likelihoods;
competitors agree in only 9/120. Physical integer truth is still unavailable.

## Acquisition cadence and failure timing

The registered final dense trial uses the selected-support likelihood and native
sphere kernel together. All 1191 consecutive ten-epoch windows are offered at
the fifth selection epoch, with 0.2-second spacing. Window width remains two
seconds; each candidate still needs five later validation epochs. Cadence is
derived from registered selection times rather than assumed by the controller.

A saved certificate provides its own elapsed time. If an entered search fails
before producing a certificate, its positive whole-call timer is required.
An explicit preselection failure performs no CILS and is counted separately.
Missing attempted-search timing is an error. These cases still obey the same
busy-drop policy; no failed search becomes a free retry. Preparation and all
other processing costs remain idealized as zero in this replay.

The preceding nine-version comparison completes 36 native/evaluation chains
with the same 56,642 time keys and byte-identical C0/C1/C2 controls. Native
full-likelihood serial tracking accepts 25 measurements and yields yaw RMSE
2.282673 degrees. Selected-likelihood ordinary and serial tracking both accept
60 and have byte-identical navigation: yaw RMSE 2.036194 degrees, horizontal
RMSE 0.100087 m and vertical RMSE 0.048783 m. This improves the earlier
2.403444-degree serial arm, but remains worse than the PVT-vector control's
1.620834 degrees and 0.098646 m horizontal RMSE. See
NATIVE_SELECTED_NAVIGATION_READOUT.md. The final dense trial is now complete:
1191 actual searches, all globally certified under the selected likelihood,
116 admitted acquisitions, and 157 tracked measurements from 55 origins.
Serial replay launches 1172 opportunities and drops 19 while busy, with no
pending result at the end. Its 157-measurement stream is equivalent to the
ordinary stream in the completed navigation comparison; both yield 145 native
accepts. Search median/P95 are 0.034646/0.154479 s. These timing figures still
exclude all non-CILS processing.

Dense serial navigation yields yaw RMSE 1.937270 degrees, horizontal RMSE
0.098965 m and vertical RMSE 0.048794 m. Against the preceding selected-support
serial arm, yaw RMSE improves by 0.098924 degrees but maximum absolute yaw
worsens from 7.205476 to 7.993303 degrees. Against the PVT-vector control, yaw
RMSE remains 0.316437 degrees worse and horizontal RMSE 0.000319 m worse.
The 0.000029 m vertical reduction is not evidence of a meaningful vertical gain.
The eleven-version comparison has 44 complete native/evaluation chains with
the same 56,642 time keys and unchanged controls. See DENSE_NAVIGATION_READOUT.md
and DENSE_SELECTED_EQUIVALENCE/SUMMARY.md. Native acceleration plus denser
opportunities are a combined change; their serial improvement is not an
isolated cadence effect.

This completes the bounded implementation/development comparison. The carrier
path remains an opt-in research algorithm; the available evidence does not
justify promoting it over default V3 or claiming calibrated integer reliability.
No further cap, acceptance-threshold or noise sweep is part of this experiment.

## Measured status and remaining limits

The first frontend produced one full-class and seven partial-class measurements
in 120 windows. Its fixed broadcast prefix and GPS-SPP gaps were preserved as
V1. V2 advances broadcast availability causally and handles unavailable pivots
explicitly: all 1200 raw epochs now build models, but full-class acquisition
admits zero windows and partial acquisition admits six of 120. Its body-HV
partial navigation yaw RMSE is 2.557707 degrees versus 1.620834 degrees for the
dual-PVT vector control; input completeness has not produced navigation gain.
The tracking trial reuses those six acquisitions and exports 24 current
measurements, of which the native filter accepts 20. Full-span yaw RMSE becomes
2.249469 degrees, horizontal RMSE 0.101068 m and vertical RMSE 0.048785 m.
This improves the sparse V2 carrier arm (2.557707 degrees, 0.102334 m,
0.048792 m), while remaining worse than the dual-PVT control in heading and
horizontal position. The control arms and all-invalid full-carrier arm have
byte-identical NAV/STD to V2; only the partial tracking stream changes.
Six tracks end at four phase-diagnostic failures and two arc changes. These are
six acquisition sources, not 24 independent correct integer fixes.

The preregistered six-cap trial performs 120 new searches with unchanged
acceptance thresholds. It admits 16 initial candidates; 15 start tracks and one
is suppressed by the incumbent. Tracking exports 70 measurements and native
navigation accepts 68. Full-span yaw RMSE is 1.994934 degrees, H 0.099993 m and
V 0.048782 m. Compared with eight-cap tracking this improves the RMSE point
estimates, but maximum absolute yaw error rises from 6.520854 to 7.258837
degrees. The longest interval without an accepted carrier update remains
45.998 seconds. This remains worse than the PVT-vector control in yaw and H.
All three controls are NAV/STD byte-identical, and all 16 version/arm outputs
share 56,642 evaluation time keys. See PARTIAL6_NAVIGATION_READOUT.md and the
record of the controller-only nominal-end/last-IMU-time correction.

Recorded search latency is a material unresolved limitation. On eight-cap
tracking only 7/24 exported measurements satisfy even the necessary condition
measurement_time >= selected_at + recorded CILS elapsed time. For six-cap
tracking it is 14/70. These counts assume immediate starts and zero queue or
other processing costs; they do not establish that these outputs are actually
schedulable. Earlier navigation RMSEs remain explicitly data-time offline
results, not latency-corrected real-time results.

The single-worker replay now charges those original recorded CILS service times.
Of 120 opportunities, it starts 37 and drops 83 while busy. Three surviving
origins emit 11 current measurements, 10 accepted by the native EKF; all delayed
origins are checked through intervening epochs before any current export.
Full-span yaw RMSE is 2.403444 degrees, H 0.101844 m and V 0.048793 m, with a
121.202-second longest interval without accepted carrier updates. This is worse
than the uncharged six-cap replay and the PVT control. All three controls remain
byte-identical. Preparation, IO, validation, catch-up and scheduling overhead
remain idealized as zero; this is not a hardware real-time result.

Caching sphere factors and pruning with an already-present cheap lower bound
preserves the original objective. A registered 9-problem/18-call paired benchmark
certifies 6 problems in both versions with the same two full integer vectors,
baselines and objective; median speedup on that selected six-pair sample is
1.248. One old timeout becomes certified; two remain timed out. These speed
measurements were not substituted into the original serial replay.

Rolling windows overlap and surviving tracks are selected by earlier tests.
There is no lifetime false-fix or false-alarm guarantee. Persistent phase
identification is diagnostic, not unique satellite attribution. The working
measurement covariance omits discrete integer error and gate conditioning;
RAWX noise is not a field-calibrated temporal model. The receiver-derived
reference is not independent ground truth. The early data-time
replays do not charge search latency. The separately labeled serial replay
charges recorded search service time only, with other costs still idealized.
