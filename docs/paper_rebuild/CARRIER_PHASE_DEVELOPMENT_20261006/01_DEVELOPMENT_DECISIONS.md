# Decisions made from initial carrier development evidence

## Active ambiguity classes

In the first fixed 80–82 s trial, every family produced globally optimal full-integer candidates. But at the five-epoch decision the best two differed only on obsolete arcs. All three comparisons then gave exactly equal cost on the five future epochs. This is not useful ambiguity discrimination for a current measurement.

The solver now optionally profiles all historical integers while finding the two lowest-cost classes on the explicitly selected current-epoch ambiguity labels. The full historical objective is retained. Independent small-domain exhaustive search tests verify both classes, including nontrivial integer basis transformations. Six new real calls use the current labels at prefixes five and ten, with the same 60 s/100000-node limits. This adjustment is about what the certificate compares, not a new integer acceptance guarantee.

Future checking fixes the selected N before consuming future observations; only the per-epoch baseline is estimated. Unknown/reset-arc phase rows are withheld, and the covariance principal submatrix is used. Comparisons require common scored epochs and identical retained rows. Missing support is unavailable, never zero cost.

## Actual Galileo navigation recovery and second fixed window

The raw files contain Galileo phase and SFRBX observations. The old navigation converter wrongly skips all eight-word Galileo I/NAV messages. The official receiver protocol describes eight-word messages; the retained RTKLIB page decoder reads eight words and verifies CRC and issue of data.

Use a separate source-pinned converter build with only this minimum-length guard corrected. Retain the original files and old converter. Filter Galileo to one E1B stream to avoid cross-signal page mixing; keep CRC, page-type, issue-of-data and health checks. All generated navigation must come from real received pages.

Input-only page inspection finds E02/E10/E11/E36 full healthy IOD-matched pages in both receivers by 99.398 s, but not at 80 s. Before solving, choose the new 100–102 s development window and navigation received no later than 100 s. The old 80–82 trial remains GPS/BDS only. The new time window follows navigation availability, not solver performance. This is further development on the same BY2 recording, not a new independent validation dataset.

For the second window use the same three families and 1/5/10-epoch prefixes, length, noise model, arc rules and search budgets. Prefix-only navigation qualification and actual admitted signal groups must be disclosed. Evaluate active-ambiguity classes at prefixes five and ten where useful; retain failures and timeouts.

## Synthetic scope

Ten newly drawn noise instances, reused across prefixes 1/5/10, test free rotating and tilting baselines. Three of those instances are reused for six pressure conditions: modeled integer slip, unmodeled slip, quarter-cycle bias, correlated temporal noise under an independent working covariance, valid RP and biased RP. These 48 calls are not 48 independent datasets and not receiver-integrity calibration.
