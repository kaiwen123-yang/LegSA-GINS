# LC02 candidate history

LC01 remains the completed Pavlasek two-position-receiver IEKF. It was not opened, executed, or modified by this audit.

The intended LC02 slot is still vacant. Yin 2023 remains a source-under-specified, paper-derived policy baseline and was not promoted. Chang 2021 was audited as the next candidate because its one-receiver INS/GNSS, 15-state error-filter, strong-tracking, and fuzzy-adaptation structure is scientifically distinct from LC01.

Chang 2021 is not admitted as the formal LC02 primary. Its printed 6-by-15 observation matrix has no ordinary inverse for Eq. 12; no source uniquely specifies a generalized inverse or lift into all 15 states; the two fuzzy smoothing factors are not uniquely mapped to all 15 fading coefficients; and the Takagi-Sugeno firing, normalization, aggregation, and clipping semantics are absent. The exact terminal is `NO_GO_LC02_CHANG2021_FSTCKF_AS_FORMAL_PRIMARY`.

This is an audit closure, not a filter implementation, C00 authorization, comparison result, or performance judgment.
