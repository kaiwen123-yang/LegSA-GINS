# Next physical model: finite within-arc common slip

**Proposed, not implemented or validated.** The paired b5 nonlinear diagnosis rules out whole-arc translation release as a sufficient recovery mechanism in this scene. The next change should preserve useful translation on the same source arc and allow its shared world displacement to change over time. Do not lower κ, inject the 67–70 s truth interval, or enlarge the all-model search first.

## Model and identifiable claim

The current `FootErrorExpression` in `factors.py:18–52` changes from `Rᵀ(c_i−p)−r_i` to `Rᵀd_i−r_i−q_t` for common release. In `branch.py:_support`, every simultaneous group gets an unconstrained new q. Position therefore drops out of every affected foot equation for the entire arc. Relative release omits those foot factors altogether. Neither representation can express “the same contact geometry translated briefly and then became useful for translation again.”

Use a world-frame common displacement `s_g(t)` and velocity `u_g(t)` instead, retaining each source arc's contact geometry `c_i`:

```
e_i,t = R_tᵀ (c_i + s_g,t − p_t) − r_i,t
ds_g = u_g dt
du_g = −u_g/τ_s dt + sqrt(2 σ_u²/τ_s) dW
```

For elapsed time Δ, ρ = exp(−Δ/τ_s), a = τ_s(1−ρ), and per Cartesian axis:

```
[s_t] = [1 a] [s_previous] + w
[u_t]   [0 ρ] [u_previous]

Q_uu = σ_u² (1−ρ²)
Q_su = σ_u² τ_s (1−ρ)²
Q_ss = σ_u² [2 τ_s Δ − τ_s² (3−4ρ+ρ²)]
```

All process variances are finite. Implement the small-Δ expressions stably, without adding covariance floors. The group-origin displacement `s_g(t0)=0` is an exact coordinate convention: the unknown c_i absorbs the initial world contact location. It is not a zero-slip truth claim or world-position prior. `u_g(t0)` has the finite stationary OU prior. A zero-variance fixed model uses an exact zero displacement/velocity coordinate, not an almost-zero stochastic prior.

The velocity prior relaxes velocity toward zero, while displacement can remain at its changed value. Thus a completed slide need not spring the contact back to its original position. The same actual foot equations keep constraining body translation relative to the inferred contact motion and retain all inter-foot geometry. A constant finite process does not guarantee the strength of a perfectly fixed contact after sliding; that is a limitation to measure, not a claim that healthy periods have already been recovered. A discrete stick/slip regime is a later question only if this minimum model fails.

Use the observed source-policy group identity and actual elapsed observation times. A newly visible member has its own unknown c_i at the current common displacement. A singleton may still inform translation through the existing group process; it cannot invent a relative direction. Missing packets do not end an arc or reset s/u. Actual closure follows the existing complete support-state/new-token rules. No force-count or dwell rule chooses the slip interval. A group's complete history is rebuilt from before its first dependency when its model changes, so earlier navigation contamination can be removed; changing only future R is insufficient.

## Predictive evidence, without counting the foot AR process twice

Current `navigator.py:_score_prediction` intentionally scores only GNSS products and raw code/carrier rows before consumption. In the 65–77 s PV gap, the remaining carrier rows primarily observe orientation, so they provide little evidence about common translational inconsistency. Better source qualification needs a normalized **joint predictive density of future foot measurements and external rows conditioned on the same IMU stream**, not an extra graph-cost comparison.

Keep the current original per-arc foot AR model exactly once:

```
z_i,t = e_i,t − ρ_i e_i,previous
ρ_i = exp(−actual_elapsed/τ_foot)
Q_z = σ_foot² (1−ρ_i²) I
```

Extend the existing algebraic residual with the world displacement key; do not append a second independent foot-error process or re-add σ_foot² as white noise. The predictive mean/covariance must include the complete joint posterior of current navigation state, c_i, s/u, previous foot expression, integer coordinates and physical carrier β as applicable. The new slip-process covariance and actual IMU preintegration covariance enter once. Gaussian branches use the saved common anchor and actual QR δ, including all cross terms.

Score one joint block of all shared eligible original foot and external rows before any of them are consumed. An equivalent ordered conditional factorization is acceptable only if the second block is conditioned on the first with its cross covariance; adding independent NIS scores is not equivalent. Stable row identities/fingerprints and the frontier ensure each raw measurement contributes once. During a PV/carrier gap, continuing foot observations can then test consistency with IMU-predicted motion.

**Do not add a separate “IMU innovation score” for the same preintegration used to predict those rows.** This design conditions on measured IMU as the process input; its uncertainty is already in the predictive covariance. A separate normalized IMU generative likelihood would require a different joint measurement model and careful dependence accounting. It is not necessary for the minimum change. Common constant translation can remain unobservable during weak excitation with no external translation reference; finite dynamics and foot scoring must expose this uncertainty rather than promise detection.

New contact coordinates have no proper prior before their first observation. Do not initialize c_i from that observation and score it as if it were an independent prediction. Condition on source birth consistently across compared models, and score subsequent shared rows once the contact posterior exists; record this source-initialization scope. Keep first-observation factors in the graph. The normalized foot-row comparison is between **fixed and proper finite-process models on identical measured rows**. The old improper q-per-epoch projection and complete foot omission cannot be silently mixed into that full-measurement evidence as different-dimensional likelihoods.

The resulting density remains a local nonlinear/Gaussian predictive approximation under the declared process model. κ remains the unchanged explicit engineering source-model cost. Calling the combined result a calibrated posterior model probability would need additional justification.

## Five implementation locations

1. **`factors.py`**: add the finite integrated-OU `(s,u)` transition and extend `FootErrorExpression` to `Rᵀ(c+s−p)−r`. Reuse `algebraic_foot_error_factor` for the single original foot AR chain. Keep the old projection representation only as a separately scoped diagnostic.
2. **`branch.py:_support` and source bookkeeping**: retain physical c_i for affected arcs, append s/u only at actual group observations with real Δ, seed source birth without using truth, and retain relative geometry. Add snapshot/restore, semantic common-anchor mapping, and latest-state/previous-AR-expression separator retention, following the existing physical β lifecycle pattern.
3. **`branch.py:predict_external`**: generalize to same-frontier foot-plus-external prediction. Include existing-contact AR innovations, full state/contact/slip/previous-expression cross covariance and all process terms; report first-contact omissions explicitly. Keep the existing external-only output as a diagnostic channel, not a second score accumulation.
4. **`navigator.py:_score_prediction` and support comparisons**: permit foot-only informative epochs, select common original rows across all compared lineages/models, accumulate the one normalized joint predictive score once, and retain external-only/foot-conditional decomposition for interpretation. Rebuild full affected history on model commitment; preserve all supported direction hypotheses and existing lineage checks.
5. **Frozen development configuration and one evaluator readout**: choose σ_u and τ_s only from BY2 development raw foot/IMU/GNSS consistency with declared calibration coverage; freeze them before the next synthetic replay. No simulated slip truth or test-set accuracy selects parameters. Compare fixed vs this one proper process on the same existing continuous sequence first, reporting pre-slide, slide, post-slide causal p/v/yaw and predictive evidence. Do not run a matrix or claim improvement from state differences alone.

The existing b5 two-policy traces remain the failed whole-arc reference. The proposed model's first falsifiable question is whether it retains pre/post translation while allowing the measured short inconsistency, and whether its same-row predictive evidence improves before accepting the source explanation. If the covariance is still weakly identifiable or navigation still degrades, report that outcome before adding regimes or combinations.

## BY calibration and the actual information boundary

Use one BY 66--340 s source-only calibration, with reference reads zero. Keep the original per-arc foot AR parameters fixed and profile only isotropic slip-velocity variance and correlation time. Obtain the across-time joint state distribution from a graph using GNSS1 P/V and IMU without any foot factors (raw direction conditioning may be declared). Integrate that state uncertainty together with the foot AR covariance and profile each contact's constant geometry in the conditional foot likelihood. U1 foot-constrained residuals cannot be used to fit the noise of those same feet. A short 96--106 s interval can develop this computation, but cannot establish full parameter identifiability.

For same-source duration L much shorter than tau, the likelihood mainly constrains 2*sigma_u^2/tau and an initial-velocity combination; at sigma_u=0, tau has no data meaning. Inspect the two-parameter likelihood shape rather than choosing a grid point by navigation accuracy. If it has a long ridge, report the identifiable combination and unresolved range. SDK common errors, mounting errors and actual ground slip can remain mixed: this is an effective common-motion process, not a certified distribution of physical sliding.

With no external translation observation, the transformation p'=p+b*t, s'=s+b*t, v'=v+b leaves foot observations and inertial acceleration unchanged. Previous velocity information limits this ambiguity; current foot/IMU data cannot eliminate it merely because a finite prior is present. At constant attitude, acceleration changes can also trade against accelerometer bias. Carrier heading does not directly resolve these translational freedoms.

After BY fitting and freezing, one new configuration on the existing complete 90-second scene must test whether whole-outage 65--77 s position and velocity both improve over the pinned fixed result, while valid pre/post support and relative direction remain useful. Fault labels stay exclusively in offline evaluation. A local 67--70 s velocity gain with worse whole-outage navigation is another failure, not successful retraction.