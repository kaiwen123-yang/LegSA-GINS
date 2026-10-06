# TIM manuscript and carrier-phase development — author scope

Date: 2026-10-06. Parent evidence: AR_TIM_EXPLORATION_20261006 at 4c4604ad002a6b2f4d6e757a628cfee1432ec230.

The author's latest instruction explicitly continues TIM manuscript development and moving-baseline carrier-phase research, delegates ordinary research decisions, and requests clear Git labels for later writing. This opens a new bounded development stage; earlier stop wording applies to its frozen trials, not to all future authorized work.

## Manuscript identities

- MAIN_TEXT_READY: traceable existing V3 outcomes, correctly attributed measurement models, implementation boundaries and synthetic propagation checks. This label means a claim may be written with its limitations, not that the paper is submission-ready.
- SUPPLEMENT_EXPLORATORY: newly frozen carrier-phase mechanism trials and their adverse results. An optimal integer candidate is not a validated FIX measurement.
- PROPOSED / NEEDS_MEASUREMENT: future estimator integration, physical covariance calibration, wrong-fix risk and independent generalization claims without current qualifying evidence.

Original V3, old manuscripts and old experiment directories remain immutable. New manuscript is TIM R4; its original V3 results and later diagnostics retain separate provenance. A better title or the combination of a quadruped, dual antennas and EKF does not establish methodological novelty.

## Current development

Implement and validate D, a bounded roll/pitch-prior penalty using two globally solved hard-length C-ILS branches. This is an adaptation of a standard robust objective, not a claim of a new robust principle. Freeze the exact contract and all observations before the finite validation. Report correct/wrong/unresolved outputs, heading error and common support, including non-improvements.

Algorithm edits, synthetic calculations, solver calls and evidence calculations run only in the E-drive Ubuntu-22.04 WSL environment. Raw sources and fused-reference data may not determine online answers. Manuscript DOCX authoring/rendering is a document-formatting operation.

## Git labels

Use docs(tim-paper) for manuscript and claim mapping; feat(ar-research) for isolated algorithm implementations; experiment(ar-validation) for preregistered tests and their sealed outcomes. Commit bodies identify paper status, dataset/experiment identity and validation. Push each completed milestone; maintain draft PR #65 until the integrated scientific claims qualify for promotion.

The next decision is made from the sealed evidence, without asking the author to choose routine parameters or implementation steps. A negative finding becomes a documented boundary and does not replace the V3 manuscript baseline.
