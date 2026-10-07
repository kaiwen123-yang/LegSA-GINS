# NED-HV reported-time policy: bounded real comparison proposal

Status: **DRAFT_PROPOSAL_ONLY_NOT_EXECUTION_REGISTRATION**. No provider, raw, reference, phase DETAILS, prior or old native payload was opened while writing this proposal; no build, native, evaluator or numerical diagnostic was run. This proposal follows the root's final timestamp-watermark contract as conveyed by the implementation author. It supersedes an earlier index-set/no-fallback suggestion.

## Question and smallest valid comparison

Can an explicitly enabled NED-HV selection policy prevent use of a reported source time later than the update and prevent repeated consumption, while the unmodified default reproduces all existing native outputs? This is a scheduling/provenance qualification, not a navigation-accuracy or phase-information experiment.

Use one newly qualified binary for six native calls: first BY2/BY2H/BY2O **legacy**, then the same three **causal_unique_latest**. All six keep ARC telemetry enabled. The three old ARC_TELEMETRY output seals from registered native run `9c0641beea49e541fc4d64cde5446e4f052e74cc` are reused as immutable byte-identity targets, without rerunning the old binary or rereading old payloads. The prior NULL/TELEMETRY identity proof is inherited with its recorded limits; repeating two telemetry arms would add calls without isolating this policy better.

Run and seal all three new legacy controls and pass their old-output identity gates before any causal call. A first failure stops remaining calls and preserves all partial output. There is no automatic retry, alternative sequence, shortened window or parameter revision.

|Sequence|Frozen window (s)|Blocks / endpoints|Old covered END priors|Old accepted HV updates|Old source-after-update rows|
|---|---:|---:|---:|---:|---:|
|BY2|66–340|274 / 548|273|1369|553|
|BY2H|413–683|270 / 540|269|1348|540|
|BY2O|3186–3563|377 / 754|376|1883|787|
|All|unchanged three windows|921 / 1842|918|4600|1880|

Counts above come from the previous small sealed native COMPLETE. Reported source-after-update is not measured late/early arrival. Previous repeated-vector-index counts were zero; that does not qualify timestamp uniqueness, physical sample identity or independence.

## Frozen selection and consumption semantics

Current NED code (`gi_engine.cpp`, original lines 1686–1766) runs at the GNSS auxiliary-update point. Its legacy loop considers `update_flag` rows, minimizes absolute time distance within the existing tolerance, and uses `<=`, so the last vector row wins a distance tie. Source validity/truth/diagnostic guards and source-aware weighting follow selection. The default must keep this loop, guard order and arithmetic intact.

The root-author contract for the opt-in policy is:

1. Only rows with `update_flag=true`, a finite reported source time, `source_time<=update_time`, `source_time<=pvacur_.time`, `0<=trigger_age<=old_tolerance` and `source_time>last_attempted_source_time` are eligible.
2. Select the maximum eligible source time; equal-time ties select the last original vector index. Preserve the vector order and use the original index as provenance.
3. Reserve the selected source **timestamp** before the existing provider-validity/source-aware guards. A rejected candidate remains consumed. Do not retry another candidate at the same update.
4. The watermark resets only on initialization or explicit source-vector replacement, with a recorded generation boundary. The three real runs must have one initialized generation and no mid-run reset/replacement. Per generation, strictly increasing attempted times rule out repeated timestamps, repeated selected indices and older-sample backfill.

The timestamp watermark is stronger than an accepted-index set. Do not present a two-arm result as separately identifying the effect of no-future selection versus no-reuse: this comparison identifies their **combined registered policy**. Unknown actual arrival remains NA. Time causality of the original SDK-to-NED construction/rotation and its cross-correlation is not established by this selector.

Retain the original NED 2D mode, tolerance 0.08 s, standard-deviation scale 1.0, minimum-std rules, source-aware policy, source caps, guard thresholds, H/R construction, GNSS/RP/Doppler order and ARC schedule. No interpolation, de-skew, covariance/noise tuning, valid-row fallback, heading substitution, frame conversion or new physical claim belongs in this step. The policy must be explicitly rejected outside its qualified NED scope rather than silently changing the body-FRD path.

## Configurations and default identity

Legacy calls should use the exact three already prepared config bytes, with the new key omitted so the default itself is tested. Create three causal config copies in the new stage; the only algorithmic difference is the explicitly named selection-policy key. Keep original run/source/initialization identities, provider paths, source-event CSV/manifest and all old science lines unchanged. The external runner distinguishes arms and output directories. Both arms use the same binary, numeric environment, telemetry flag and source inputs.

Default instrumentation must not change pre-existing log columns, manifest serialization, counter semantics or floating-point order. Compare every pre-existing new-legacy output SHA and size to the old TELEMETRY seal, including NAV/STD, heading/source traces, lifecycle, conditioning ledger, IMU segments, joint priors and RUN_MANIFEST. Added diagnostics should be opt-in separate artifacts. Do not waive a legacy byte mismatch by comparing only RMSE, selecting columns, rounding arrays or accepting an unexplained new manifest field.

For legacy versus causal, fixed input/schedule identity is required, but NAV/STD, conditioning U/R counters and P24/P6 values may legitimately change downstream of a different HV selection. Do not require unchanged filter results or accepted decisions from other state-dependent guards. The current `recordArcImuSegment` call precedes `insPropagation`/IMU compensation: its recorded input segments should remain byte-identical under the same joint-event schedule, and a mismatch requires investigation rather than an automatic state-change exemption.

Preserve every fixed source block, including all 61 blocks with missing phase models. Each causal lifecycle must retain all 921 blocks/1842 source endpoints across the three windows and the same 918 covered END block identities plus three terminal blocks. Compare exact source/replay/state time bits and dispatch phases/ownership. Do not require the old conditioning ordinal or information ID after HV updates change. If state health or support fails, keep the failed output and report the comparison as incomplete; do not select a surviving subwindow.

## Observability of the policy itself

An opt-in NED selection event log should identify update ordinal, update time and actual state timestamp, policy, vector generation, selected index/source bits, signed age, watermark before/after, whether the timestamp was reserved, whether the existing filter update was accepted, and one terminal reason. Preserve NA when no candidate is selected. Distinguish no finite/past/in-tolerance/newer candidate, provider invalid, source-aware rejection and accepted. Log any caller-level auxiliary veto separately if claiming a denominator over all scheduled GNSS updates; function-entry logs alone support only an invocation denominator.

Hard policy checks apply to **all reserved attempts**, not just accepted updates: nonfuture source against both logged trigger and `pvacur_.time`, trigger-age in [0,0.08], nonnegative separately reported state-age, increasing consumed timestamps, at-most-once indices within the one generation, no refund on rejection and no hidden fallback. The opt-in CSV uses `state_time=pvacur_.time`; the existing ARC conditioning ledger uses the engine `timestamp_`; the trigger is the GNSS argument time. The real exact-event path should align them at accepted updates, and the real gate must verify that relationship. General/synthetic paths need not have equal trigger and state clocks. Do not invent a state-age <=0.08 requirement: the unchanged old tolerance applies to trigger age. Generation labels may exceed 1 after initialization/source loading; require one observed generation across every real log row, not a literal label of 1.

Report per window: scheduled GNSS opportunities where available, selection invocations, eligible/reserved/accepted counts, terminal reason counts, acceptance denominator, accepted source-age min/median/P95/max and signed future/reuse counts. Use an explicitly declared standard-library quantile convention, not a fitted threshold. Preserve negative results and unmatched opportunities. Legacy accepted ages and source identities can be summarized from its new sealed conditioning ledger; legacy preselection/rejection reasons absent from existing logs remain **NA**. Do not infer them from accepted rows. New native metadata/diagnostic readout is allowed once for these fields; no source provider needs to be decoded by the readout.

## Draft finite budget and registration gates

Local implementation, build and synthetic/default-regression tests require their own source freeze and explicit budget before this real comparison. The real phase consumes the already qualified new binary and does not compile, run standalone loaders or repeat local tests.

|Operation|Real-phase ceiling|
|---|---:|
|Config derivation|3 copied configs; metadata only, one frozen policy key difference|
|Native processes|6, legacy3 first then causal3, zero retry|
|Native wall time|1200 s per call; bounded process-group timeout|
|Provider hash passes|2 total: one pre/one post over the same 18 unique files|
|Provider bytes per hash pass|120,200,614 B; total 240,401,228 B|
|Scientific provider input paths|Exactly the old six per sequence, 18 unique overall|
|New native output sealing|Every file retained and hashed once; prior 4 GiB per-run safety cap can be retained|
|New field-only diagnostic summary|One bounded pass over registered small output logs; exact row/byte ceilings frozen before execution|
|Old native/phase payload rereads|0; identity targets taken from pinned old seals|
|Evaluator / reference / phase residual / phase information|0 / 0 / 0 / 0|
|NPZ/raw-source reconstruction / integer search / scientific retries|0 / 0 / 0|

The native input opens themselves remain required and authorized only by the future registration. The hash byte ceiling does not pretend to include native provider reads. Source closure must pin the complete C++/CMake build inputs, new binary/build/test receipts, runner/helpers and config derivation. Metadata closure must pin old prepared inputs, all three old TELEMETRY seals, prior identity/access audit and old global seal, including their large-output audit limitation. Exact causal-config bytes, event/manifest identities and provider pin closure are checked before launch.

Use the already successful trace arrangement: outer runner trace without `-f`, with one `-f` child trace per native invocation; do not nest two ptrace owners on the same child. Independently classify all actual scientific opens against the per-sequence six-input closure plus its config/events; writes belong only to the new stage. Record invocation, environment, timeout/return code, input hash receipts, per-run output seals, default identity gates, full lifecycle support and a final completion/failure receipt. Retain full outputs even if there is no accuracy or phase analysis.

## Decision and remaining interpretation

A successful result can establish: the default remained byte-identical on these three frozen windows; the opt-in selector enforced its registered reported-time/watermark semantics; any resulting trajectory difference is attributable to that combined policy under the fixed implementation and inputs. It cannot establish improved accuracy, calibrated covariance, trustworthy heading, independent source information or real-time arrival feasibility.

Only after this policy result is sealed should a separate proposal decide whether to re-examine phase working information or add evaluation. Neither is automatically authorized by this proposal.

## Read-only sources used

The proposal used current native/config/loader source and existing small prepared configs/PLAN and native COMPLETE/seals. The original NED implementation source hashes at review were `gi_engine.cpp=654024e4085373d78606de8af9ce571c311aed5d8415062221fa9552609b922f`, `port_config_loader.cpp=1938b73db0caf8a3d18f5133348e77a3112ac8dc686ee61cf2e4f23ce2f4540a`, `go2_weak_prior_types.hpp=a0b781a519a1bd3b1a1e2340b3369fbb49f27074a8c9aeb1ca6adf161da5a60f`. These document the reviewed baseline, not a future production freeze.


### Implementation-alignment note

The final producer header logs `trigger_age_s`, `state_age_s`, `source_time_bits_hex`, `vector_index`, `generation`, `generation_reset_reason`, `source_present`, `consumed`, `accepted` and candidate-skip counters. It has no `ledger_time`, `tolerance_s` or explicit watermark-before/after columns. `source_present` equals a newly reserved candidate and must equal `consumed`; all candidates rejected by the existing provider/weight guards remain consumed. The execution readout should verify all consumed source times are strictly increasing and indices unique, and directly match accepted source/index/state triples to the existing ARC ledger. Do not claim to independently inspect a watermark field that is not serialized. Generation is recorded even when no source is selected, so an all-skipped negative result can still pass the provenance audit.
