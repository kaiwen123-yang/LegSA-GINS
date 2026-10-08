# Persistent standing support: whole-arc release diagnosis

**Status: the current release models do not meet the objective of stable shared-state navigation improvement.** Fully nonlinear conditional histories do not overturn the completed separator controller's decision. Keep the existing engineering edit cost; do not attribute the nonselection to Gaussian freezing or add combinations to force a win.

## Exact experiment identity

- Completed source: `b5adc7a6b5557b106950733296de2e593842870f`, cohort `cohort_separator_20261008_seed6100801`, duration 90 s, seed 6100801.
- Every imported joint-navigation module came from that cohort's verified `SOURCE_SNAPSHOT`; the current working tree navigator was not imported. All source hashes are recorded in the adjacent JSON and original `run_status.json` / `IMPORTED_SOURCE_IDENTITY.json`.
- Two runs only: `U3`, `monitor_support=False`, one complete `common_translation_release` policy or one complete `relative_release` policy. The completed U3 was fixed throughout and supplies H0; H0 and the all-model controller were not rerun.
- The actual complete support tuple at 65 s is `force_0_0091`, `force_1_0092`, `force_2_0092`, `force_3_0091`. Their first observations are 64.8, 65.0, 65.0, 64.8 s. Each conditional policy applies through those source histories from their first use; the navigator receives no truth fault time.
- Execution: session `96421`, PID `12869`, exit 0; common 121.564 s and relative 97.071 s wall time. Each produced 1,287 causal rows and 4,435 scored external scalar rows at 90 s.
- Before the earliest affected observation (64.8 s), p, v, rpy and predictive score are **exactly equal** to H0. Every actual predictive row identity, cumulative count and reconstructed reference fingerprint matched; all integer lineages matched. The original H0 CSV did not save fingerprints: its reference is explicitly reconstructed from identical events and the pinned persistent-ambiguity rule, not falsely presented as an original logged hash.

Artifacts: `/home/kaiwen/research/LegSA-GINS-SCRATCH/SUPPORT_CARRIER_JOINT_20261008/PINNED_STANDING_GROUP_NL_01/`. Each model has `predictive_trace.jsonl`, `score_comparison.csv`, causal navigation, decisions, summary, metrics and offline error series. `DIAGNOSTIC_READOUT.json` is the compact offline readout. The exact executed runner is also archived as `scripts/paper_rebuild/diagnose_joint_standing_policy.py` in this repository. Reproduce with `--repo <REPO> --cohort <COMPLETED_B5_COHORT> --output-root <NEW_OUTPUT>`. The local offline readout script is `summarize_pinned_standing_group_nl.py`; its complete derived values are preserved in the adjacent JSON.

## Same-frontier score result

Score is negative twice conditional predictive log density, including the normalization constant. Lower is better. Every delta below is `conditional minus fixed`. The engineering cost remains κ = `2 ln(100) = 9.210340371976184`; it is not a posterior probability.

| Time (s) | Common raw Δ | Common Δ+κ | Relative raw Δ | Relative Δ+κ | Cumulative scalar rows |
|---:|---:|---:|---:|---:|---:|
| 65 | −0.002671 | +9.207670 | −0.002661 | +9.207679 | 3,101 |
| 67 | −0.517772 | +8.692568 | −0.512804 | +8.697536 | 3,201 |
| 70 | −2.157834 | +7.052506 | −2.233563 | +6.976778 | 3,351 |
| 77 | +3.819942 | +13.030283 | +3.661655 | +12.871995 | 3,707 |
| 78 | +7.214783 | +16.425124 | +7.110616 | +16.320956 | 3,763 |
| 90 | −4.293790 | +4.916551 | −4.265260 | +4.945080 | 4,435 |

Neither policy wins after κ at any event; the minimum penalized deficits are +2.838327 and +2.744611. This is not only a terminal-time failure.

The original Gaussian controller publishes these exact identities only in its supported subset at 82–90 s (107 rows per model). Within that available interval, the maximum absolute nonlinear-minus-Gaussian raw score differences are 0.155011 and 0.130968, both reached at 90 s. At 90 s the original Gaussian penalized deficits are +5.071561 and +5.076047; full nonlinear histories give +4.916551 and +4.945080. Earlier Gaussian scores are not present in the saved CSV and are not inferred. The available comparison does not support a Gaussian-freezing explanation for the missing selection.

## Physical navigation result

Metrics below are time-weighted RMSE of the same causal rows against the same synthetic reference, used only by the offline evaluator. Intervals are the existing input-defined scene intervals, not error-selected windows. Entries are **3D position m / 3D velocity m/s / yaw deg**.

| Interval | Fixed H0 | Common release | Relative release |
|---|---|---|---|
| Full 0–90 s | .075066 / .026658 / 2.145714 | .183018 / .043396 / 2.145709 | .179874 / .043751 / 2.145709 |
| Standing support 65–78 s | .140358 / .043265 / .120317 | .462517 / .099160 / .119656 | .453897 / .100201 / .117494 |
| Actual common slide 67–70 s | .106766 / .077582 / .170005 | .233869 / .053404 / .169416 | .233125 / .053035 / .167711 |
| Receiver PV absent 65–77 s | .140418 / .045018 / .124011 | .480752 / .101978 / .123307 | .471762 / .102989 / .120921 |
| Receiver return 77–90 s | .094281 / .017401 / .060119 | .081388 / .026271 / .060254 | .081417 / .026708 / .064426 |

There is a narrow velocity benefit during the actual slide and some position benefit after receiver return. These do not establish the desired stable benefit: releasing the entire source arc also removes useful translation information before and after the short slide, and both p and v deteriorate over the PV outage. Yaw barely changes because the carrier already supplies direction in this segment. Decreasing κ would not repair that physical loss.

This experiment diagnoses one actual source group by conditional reconstruction. It does not demonstrate that an online algorithm finds the true failure or retracts it successfully. Its role is to decide the next model change before spending more computation on combinations.

See [TIME_LOCAL_SUPPORT_MODEL_PLAN.md](TIME_LOCAL_SUPPORT_MODEL_PLAN.md) for the smallest proposed physical change. No implementation or new navigation run is part of that plan.
