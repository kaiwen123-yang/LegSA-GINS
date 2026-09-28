# Official-code search

Overall classification: `OFFICIAL_PARTIAL_CODE_ONLY`.

A focused attributable-code search used all six author names, the paper title, DOI `10.3390/rs15174125`, article number `rs15174125`, Shandong University of Science and Technology, supplementary material, GitHub, and GitLab. The paper's data/code statement was inspected. No repository or supplement attributable to Yin et al.'s adaptive/robust modules was located. Generic RAEKF scripts were rejected as non-attributable.

The paper states that data are available on request because of privacy or ethical restrictions. It credits Z.Y. for software and acknowledges Wuhan University's Multi-Source Navigation Intelligence Laboratory for open-sourcing KF-GINS, but it publishes no software URL or supplementary-code package.

KF-GINS at commit `08f9fce66028c65727b3f3c53f34f7dfd5a3c1c3` (11 July 2023) is therefore the paper-attributable acknowledged partial source for the base ESKF. It is used as a `CITED_SOURCE` for the unprinted standard 21-state dynamics, mechanization, position observation, feedback, and signs. It is not classified as official Yin RAEKF implementation. The nested classifications are `yin_specific_implementation=NO_ATTRIBUTABLE_OFFICIAL_IMPLEMENTATION_FOUND` and `yin_adaptive_robust_modules=NOT_FOUND`. Absence of official branch code is a provenance boundary, not by itself a blocker.
