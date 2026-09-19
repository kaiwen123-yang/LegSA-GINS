# F/G source provenance

Yin prints the 21-state order and `delta_x_dot=F delta_x+G w`, but not every `F/G` block. The paper explicitly acknowledges the open-source KF-GINS code, so the paper-contemporaneous upstream commit `08f9fce66028c65727b3f3c53f34f7dfd5a3c1c3` is the attributable cited completion.

At that commit, `gi_engine.h` sets state rank 21 and noise rank 18. `gi_engine.cpp` provides the full NED local-level linearization: position/velocity Earth-radius and transport terms; gravity-gradient and Coriolis blocks; velocity-to-attitude specific-force coupling; attitude Earth/transport terms; bias and scale couplings; four first-order Gauss–Markov processes; 18-column noise mapping; continuous noise densities; first-order `Phi`; and trapezoidal `Qd`. `insmech.cpp` supplies the two-sample nominal NED mechanization. Source hashes are frozen in `LC02_SOURCE_REGISTRY.csv`.

The cited source also closes signs: predicted antenna minus observed GNSS position, positive lever-arm skew block, subtractive position/velocity feedback, left attitude feedback, and additive bias/scale feedback.

The current clean repository comparison is exactly `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp`, SHA-256 `4d2e329a1f6a11ed232941c3150a5569791f7ac5fceb0362e91e5dd856dc6a50`. Its matrix builder omits upstream `F_rr`, `F_vr`, `F_vv`, `F_phi_r`, and `F_phi_v`. It also applies local initialization/STD floors (position and velocity `1e-6`, attitude `1e-9`, bias/scale bounded by configured driving-noise STD), clamps correlation time to at least `1 s`, and substitutes `dt=0.01 s` when input `dt<=0`. It is a useful static comparison (`PRIOR_PROJECT_CODE`), not permission to reuse the truncated/floored port as a faithful Yin base.

Exact Yin numeric initialization and process-noise values are not printed. Their structure is source-closed; any future BY2 numbers must be a declared `BY2_PHYSICAL_INSTANTIATION`, never selected from trace.
