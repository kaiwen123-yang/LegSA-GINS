# Causal fixed-candidate tracking trial

Status: registered before real tracking. This extends the experimental carrier frontend; it does not change the V3 default or claim navigation improvement.

## Question and fixed inputs

Can an already admitted integer candidate deliver more useful heading updates while its exact selected receiver/signal/arc support survives? The original V1 support-only inspection found 1, 15, 33, 31, 20, 6 and 1 additional model epochs for seven original partial candidates. Those are upper support lifetimes, not accepted fixes. The V2 trial instead uses all 1200 repaired causal models at 100.198--339.998 s and the completed V2 full/partial acquisition records, without new integer searches.

Retain all completed V1 and V2 acquisition outcomes, including rejections. V2 uses advancing causal broadcast prefixes and explicit pivot changes; tracking must not borrow V1 candidates or transfer an integer across a changed pivot/arc. No reference data, PVT heading, new ambiguity search or observation-dependent threshold change enters tracking.

## State and ownership

Start from a fully qualified original acquisition. Bind its original primary and competitor, selected_at, source identity, integer mappings, original five validation models, admission, phase diagnosis and exported measurement. Recompute that admission/diagnosis once before starting. Never rewrite candidate selection time.

For each next 0.2 s slot (tolerance 0.01 s), keep the most recent five models. Require every originally selected active arc, at least four retained phase rows of rank three, and the same full within-epoch covariance. Recompute the original primary/competitor residual and baseline-length gates and the persistent single-SD phase-fault diagnostic. Use the unchanged 0.35 m physical length, alpha=0.01, diagnostic family alpha=0.01 and 1.5 degree engineering covariance floor.

Any missing model, timing mismatch, selected arc change, unsupported geometry, failed primary gate, unresolved competitor or fault diagnostic releases the track permanently. Returning old labels do not restore it. No subset shrinkage or N modification is allowed.

Each full/partial arm owns at most one active track. If a track is active at entry to an epoch, it alone is evaluated; all new acquisitions at that epoch are recorded as suppressed, including when that incumbent fails in the same epoch. If no track was active, a fresh qualified acquisition available at that exact epoch may start. No queued acquisition, retrospective start or resurrection is allowed. The initial acquisition measurement is output once; later outputs use only their current model. Missing/inactive epochs remain explicit invalid rows.

## Verification and trial

Synthetic checks cover rotating baselines with known N, full covariance, missing/duplicate/future slots, arc resets, wrong candidates, model/receipt mutation, persistent faults, configuration mismatch, terminal release and overlapping acquisition ownership. No real reference tuning is allowed.

After implementation checks and a Git checkpoint, perform one tracking replay over the complete V2 prepared domain for both full and partial arms. Report origins admitted/suppressed, each release cause/time, current-epoch valid outputs and source identities. Reuse the saved integer searches. Then run the same body-velocity-enabled four navigation arms over 66--340 s using the existing native binary, providers, initialization and evaluation contract. Seal all native outputs before offline reference evaluation. Compare all-span heading, horizontal and vertical errors and actual vector acceptance counts; retained-window-only metrics cannot establish navigation gain.

## Limits

Overlapping rolling windows and survival selection invalidate any interpretation as independent repeated validation. The per-window thresholds do not provide lifetime false-fix or false-alarm control. Current fixed-N baseline covariance omits discrete wrong-integer risk and selection conditioning. Data-time causal replay still does not account for the wall-clock CILS acquisition latency. The Fixposition-derived reference is not independent ground truth. Physical FIX truth and production validation remain unavailable.
