# Serial recorded-CILS latency replay: implementation and verification

Implementation: `scripts/paper_rebuild/carrier_phase/latency_tracking_frontend.py`. Registration: `SERIAL_LATENCY_REPLAY_PLAN.md`, commit `9795895`. No original carrier library, frontend, tracking implementation or saved result is modified. This implementation has not been executed on real model inputs by its author; root controls the registered run.

The service costs come from the original **120 PARTIAL6 saved cases**, field `search.certificate.elapsed_s`. The saved execution chain contains commits `c25a48ed4ddf2ac8748f0a393dcbaa87cba85c3b` and `dbf340afb34fffb35763b63d9a948f7346cbf1cf`; each case is bound to its original tracking SHA pin. The acquisition summary is also pinned. These are the old recorded complete CILS-call durations, including the float/search work inside that timer. They are **not** total frontend-window elapsed times, and **not** the newly measured 18-call cache-optimization benchmark costs. No faster cost is substituted into old cases.

## Implemented timing and ownership

- Opportunities occur at the original fifth selection epoch, every two-second window. An idle worker launches; a busy worker permanently drops that opportunity. Outcome, validity, reference or residual never determines launch/drop. Uncertified and rejected tasks consume their recorded service duration too.
- Completion equals original selected_at plus recorded CILS seconds. The worker is free at that timestamp, even between raw epochs and even if original validation has not finished. Equality at the next selection opportunity permits launch. Finished results waiting for validation are not a search queue.
- Result arrival is the first raw slot at or after both completion and original fifth validation epoch. Results beyond the last raw epoch remain pending; they are not clipped to the endpoint. Simultaneous arrivals use completion, then selection time, then case identity as a deterministic final tie-break.
- The original five-model receipt and immutable integer pair are restored and rechecked. A late candidate then consumes every observed intervening slot, including missing models. First release permanently kills it. If it survives, only its current-epoch measurement can enter the output CSV.
- Historical receipt checks use the existing library's logical data-time API internally. They are marked `INTERNAL_CATCHUP_NOT_EXPORTED`; their internal decision timestamps do not represent past publication. Logs keep original validation end separate from scheduler_acquired_at and record both historical model time and current simulated processing time.
- An incumbent at epoch entry owns its release epoch and suppresses all arrivals at that epoch. With no incumbent, a candidate that dies during catch-up never gains ownership, so the next arrival may be tried. Once one succeeds, all remaining arrivals are permanently suppressed. No candidate resurrection or result queue is introduced.

All 1200 original raw slots produce a CSV row, including inactive or rejected slots. Per-mode schedule and event JSONL files retain launch/drop, arrival, suppression, catch-up failure and release evidence. The partial stream is `CARRIER_LATENCY_TRACKED_PARTIAL.csv`. The original selected_at and integer values are never rewritten, and no delayed historical baseline is injected into a current state.

## Verification already completed

The implementation suite `tests/test_carrier_latency_tracking_frontend.py` passed **16 pure mock tests** in Ubuntu 22.04 WSL. The independent suite `tests/test_carrier_latency_review.py` passed **11 tests**, reported by the independent reviewer. Its interval oracle covers 200 sets of 25 jobs. No additional scientific rerun was used to prepare this note.

The combined 27 checks cover busy-drop/no-queue, exact completion boundaries, completion between raw slots, waiting for validation, rejected service costs, nonfinite/negative/missing durations, endpoint pending results, deterministic arrival ordering, current-only export, unchanged original receipt inputs, late survival, death/missing models during catch-up, no future history, incumbent failure-epoch ownership, multiple arrivals, suppression and no resurrection. No real models, CILS, native navigation or reference evaluation were used by these tests.

Implementation SHA-256: `1a0a48a0839a632cf139a2b08a07191b6b985426bcab6816ac25d54691053929`.

## Run interface and limitations

The runner requires `--trial`, `--summary`, `--original-tracking-summary`, and a fresh `--output` directory; use `--modes partial` for the registered PARTIAL6 experiment. It reads only prepared current/past models during chronological replay. Full saved case JSON is available as **recorded-cost simulation metadata**; its eventual status is not a launch/drop criterion. Original case hashes are checked before reuse. The registered output location is `SERIAL_LATENCY_PARTIAL6` under the current carrier WSL scratch root.

This is **idealized recorded-CILS service-cost replay**, not a wall-clock real-time implementation or hardware qualification. Preparation, model loading, IO, validation, fault diagnostics, catch-up, tracking, export, navigation and task-launch costs are set to zero in simulated time. No queueing or CPU contention cost is estimated. If multiple modes are requested, each is an independent one-worker methodological replay; they do not model simultaneous deployment on one CPU. Recorded durations are single-run observations, not worst-case execution bounds.

The existing necessary-condition readouts remain separate: `LATENCY_NECESSITY_REVIEW_V2` gives 7/24 original outputs passing the optimistic inequality; `LATENCY_NECESSITY_REVIEW_PARTIAL6` gives 14/70. These counts are not the new scheduler's results. The registered replay may change which opportunities launch and which origin owns an epoch; its output must be reported separately. No integer-truth or calibrated false-fix claim follows from either diagnostic.
