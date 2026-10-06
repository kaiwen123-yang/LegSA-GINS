# V2 arc-break cause review

One statistics pass read the saved ARC_EVENTS.json once (174,787 events,
1,200 model epochs). Inputs were the existing V2 plan/arc metadata and saved
frontend cases. Only A/B from saved models was opened where needed to check
the six qualified candidates' later support. CILS/native/reference calls: 0.
No algorithm, observation, integer, threshold, Q or arc policy was changed.

## Candidate first breaks

| Mode | Active-arc failures | Metadata only | TDCP only | Mixed | Model qualification only |
|---|---:|---:|---:|---:|---:|
| Full | 104 | 76 | 22 | 5 | 1 |
| Partial | 60 | 44 | 14 | 2 | 0 |

Each case is classified at its FIRST lost original selected DD arc. Endpoint
causes are deduplicated when a pivot affects multiple selected DD labels.
The two method rows share underlying observations and are not independent
experiments. Metadata and TDCP reasons can coexist on different endpoints.

The one qualification-only case is full_0196.00 at 197.598 s:
G22 L1 disappears from the DD model with RAW_CODE_LOCK_OR_CNO_INELIGIBLE while
the original target/pivot arc tokens remain unchanged. The saved reason does
not distinguish code validity, C/N0 or lock subconditions; it is not proof of
a physical cycle slip or a purely interchangeable pivot.

The majority of first breaks are therefore actual input-contract metadata
failures, rather than isolated effects of the 0.5-cycle TDCP criterion.
The classifier does not infer physical fault causes from these flags.

## All saved events

| Reason | RX1 event records | RX2 event records |
|---|---:|---:|
| CARRIER_INVALID | 15,938 | 13,416 |
| HALF_CYCLE_UNRESOLVED | 25,492 | 22,823 |
| LOCKTIME_REGRESSION | 2,024 | 1,953 |
| HALF_CYCLE_CORRECTION_CHANGED | 295 | 314 |
| MISSING | 14,195 | 15,897 |
| TDCP_DOPPLER_INCONSISTENT | 174 | 203 |

Reasons overlap; invalid/missing states may be logged repeatedly. These counts
are NOT counts of independent slips. No TIME_GAP or RECEIVER_CLOCK_RESET reason
appears in this saved interval. Absence of a clock-reset flag does not exclude
other receiver clock behavior.

TDCP is computed only when both endpoints are metadata-continuous. Its
population is selected and must not be treated as all incoming observations.

## TDCP coincidence and metre-domain behavior

The AR signal-family scope below contains GPS/Galileo/BDS components supported
by the frontend, including their saved RAWX tracking checks. It is not an
assertion that every checked signal passed the current NAV/CNO/elevation model
qualification. All-raw counts above additionally include other constellations.

| Receiver | AR-family TDCP checks | >0.5-cycle events | Receiver-epochs with a violation | Maximum simultaneous violations |
|---|---:|---:|---:|---:|
| RX1 | 34,498 | 87 | 80 | 3 |
| RX2 | 33,036 | 98 | 91 | 2 |

There are 180 physical-frequency/receiver/epoch groups with at least one
violation; none has three or more. There is no broad simultaneous gate crossing
across many AR signals in this interval.

Residual metres were computed as residual_cycles times the correct signal
wavelength. The saved tdcp_m is a phase increment, NOT a residual, and was not
used as one. Same-frequency groups combine equal physical carrier frequencies,
including GPS L1 and Galileo E1; unique-SV counts are retained separately.
Multiple signals on the same satellite are not independent samples.

A concrete common-mode example is RX1 at 139.798 s:
30 checked AR signals (20 unique SVs) all have negative residuals, median
-47.91 mm and MAD 9.33 mm. Only three cross the cycle gate. Within that epoch,
B1I's eight signals have median -51.91 mm/MAD 5.60 mm (one violation);
L1/E1's ten signals have median -46.16 mm/MAD 7.58 mm (two violations).
The receiver-level mean accounts for 0.826 of squared residual energy.
Other coincident examples are less common-mode: at 110.998 s RX1 has two
violations but only 0.020 mean-energy fraction and mixed residual signs.

Across 1,199 epochs with at least four common checked AR signals, the two
receivers' median metre residuals have Pearson correlation 0.651. The median
RX2-minus-RX1 residual is -0.74 mm; its per-epoch median has a 5th--95th
percentile range of about -27.4 to 29.1 mm, and the median cross-signal MAD
of the receiver difference is 16.4 mm.

These are descriptive indications of shared temporal effects. They do not
separate receiver-clock behavior, timing alignment, Doppler integration error,
common motion, multipath, or true phase discontinuities. No common-mode
subtraction, alternative continuity labels, revised gate or corrected phase was
computed. In particular, correlation is not permission to retain an integer
through an unresolved half-cycle or carrier-validity loss.

## Six already qualified candidates: support-only lifetimes

| Original case | Export, s | Additional supported epochs | Additional span, s | First stop |
|---|---:|---:|---:|---|
| partial_0148.00 | 149.998 | 6 | 1.2 | 151.398: RX1 E10 E5b carrier/half-cycle/lock invalid |
| partial_0154.00 | 155.998 | 4 | 0.8 | 156.998: RX1 E10 E5b carrier/half-cycle/lock invalid |
| partial_0156.00 | 157.998 | 0 | 0.0 | 158.198: E10 E1 RX1 TDCP plus RX2 metadata invalid |
| partial_0168.00 | 169.998 | 31 | 6.2 | 176.398: RX1 C27 B1I half-cycle unresolved |
| partial_0332.00 | 333.998 | 0 | 0.0 | 334.198: RX2 E11 E1 TDCP inconsistency |
| partial_0334.00 | 335.998 | 8 | 1.6 | 337.798: RX2 pivot G17 L2 carrier/half-cycle/lock invalid |

All original selected labels, phase count >=4 and phase B rank 3 were required;
the traversal stopped at the first failure. These are support-only upper
limits, not newly admitted tracking measurements. At the 334.198 s TDCP-only
stop, RX2 has just one violating signal among 30 checks, so this example does
not support a broad receiver-wide jump explanation.

## Files

- SUMMARY.json: compact aggregate statistics and explicit scope.
- CANDIDATE_FIRST_ARC_BREAKS.csv (full detail JSON retained in scratch):
  original case, first epoch, changed endpoints and saved reasons.
- QUALIFIED_SUPPORT_STOPS.csv: six support-only lifetimes.
- EVENT_REASON_COUNTS.csv / EVENT_STATE_COUNTS.csv: full event denominators.
- TDCP_RECEIVER_EPOCHS.csv / TDCP_FREQUENCY_EPOCHS.csv /
  TDCP_RECEIVER_PAIR_EPOCHS.csv: descriptive rows at anomalous epochs.
- scripts/paper_rebuild/carrier_phase/diagnose_arc_causes.py: the same one-pass diagnostic logic with portable path arguments. The original invocation script remains in scratch; only CLI paths and CSV newlines were adapted for the repository.

The evidence favors retaining the current validity boundaries. It identifies
where separate time/measurement-model investigation could be useful, but does
not establish that changing TDCP thresholds would improve AR or navigation.
