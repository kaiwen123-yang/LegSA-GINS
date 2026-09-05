# Conversation handoff (paper-writing phase)

Every conversation (Claude, ChatGPT, Codex) reads `AGENTS.md` first, then this file,
and appends its own decisions under "Conversation log" before it ends. Nothing in this
file overrides `AGENTS.md`; it only records paper-phase decisions and task ownership.

## 1. Target and page budget

- Target journal: IEEE Transactions on Instrumentation and Measurement (TIM), regular
  paper, free limit 8 pages (IEEE double-column). GPS Solutions is a fallback only.
- Main-text figure budget: about 7 figures + 3-4 tables. Everything else goes to the
  supplementary text file.
- TIM "Important Note" obligations: state the I&M contribution (measurement model,
  uncertainty budget, calibration) in abstract/introduction; compare against I&M
  literature (the three raw-layer comparators are TIM papers).

## 2. Method identities for the manuscript

| Manuscript label | Registry id | Role |
|---|---|---|
| Single | `F01` = `single_antenna_EKF` | baseline (position + receiver velocity, no yaw) |
| Dual-basic | `F02` = `basic_dual_yaw_EKF` | baseline (dual yaw only, fixed 1.5 deg std) |
| Backbone | `F03` = `A02` = `AB0000` | proposed method without RD/RP/HV/SA; ablation row only, never a "strong baseline" |
| Core | `A04` = `AB1011` | candidate proposed method (Source-Aware disabled) |
| Full | `F04` = `A01` = `AB1111` | candidate proposed method (Source-Aware enabled) |

The graduation-design algorithm (`final_v23`, the backbone) has never been published;
the manuscript still adds one sentence declaring reuse of graduation-design material,
as TIM requests for thesis material.

Proposed-method identity: `PROVISIONAL_PENDING_BY2H_BY2O`, decided only by
`docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md` (commit hash: `<fill after commit>`).

## 3. Comparison structure

- Comparison tables/figures (with external methods): Single, Dual-basic, proposed
  (plus the other candidate as "+/- Source-Aware" where space allows).
- Ablation table/figure: Dual-basic -> Backbone -> +RD -> +RP/HV -> +SA, all from the
  frozen Canonical-541 tables (541 x 11 unique configurations).
- Delta convention everywhere: candidate - reference, negative is better; always report
  mean, median, and case win rate together.
- Reference label inside figures follows AGENTS section 13 (`Truth`); prose carries the
  same-source caveat. Risk noted for a metrology journal; the human owns this choice.

## 4. Planned stages and naming

| Purpose | Stage id / dataset id |
|---|---|
| Same-day poor-heading run | `BY2H`, `CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE` |
| Same-day single-antenna occlusion run | `BY2O`, `CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE` |
| C00 input-parity experiment (A04 fed 5 Hz GNSS1 HPPOSECEF; EXT05C single-receiver IEKF) | `CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF` |
| Publication figures | `CLEAN6_PUBLICATION_FIGURES/01_CANONICAL541`, `.../02_HORIZONTAL` |

Rules for BY2H/BY2O: BY2-frozen parameters, own yaw physical gate, occlusion window
defined from input-side flags before evaluation, no Canonical matrix rerun, no tuning.

## 5. Task ownership

| Conversation | Owner | Scope | Status |
|---|---|---|---|
| A | Claude (matrix-figure conversation) | derived tables (A04 vs F03 / F02, F04 vs F02, bootstrap CI, stratified Wilcoxon, bias/random decomposition), publication plotting common layer, Canonical-541 figures, captions, this file | in progress |
| B | new conversation | horizontal publication figures FIG02/FIG03 (FIG04 supplementary), reuses A's common layer | waits for A's common layer |
| C | Codex / execution conversation | BY2H, BY2O, input-parity runs and evaluation | waits for authorization |
| D | new conversation | yaw uncertainty budget, consistency diagnostic, bias/precision wording | after A's decomposition |
| E | new conversation | manuscript | last |
| F | new conversation | clean submission repository, data/code release | last |

## 6. Data handoff locations

- Canonical-541 authoritative attempt: `<CANONICAL541_ATTEMPT>` (see AGENTS section 3).
- Packed subset for conversation A: `~/c541_handoff.zip` produced by `c541_pack_v2.py`
  (aggregates, whitelisted evaluation columns, decimated representative error series,
  C00 NAV files, identity probe). Decimated series are display-only; every metric comes
  from the frozen aggregate tables.
- Horizontal synthesis tables for conversation B: `<CLEAN4 root>/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/`.

## 7. Open items

- [ ] Decision-rule file committed; hash recorded above.
- [ ] AGENTS section 12b (Canonical-541 publication figures) inserted.
- [ ] Stale tracked docs (ACTIVE_CONTEXT, NEXT_STAGE_INSTRUCTIONS, GINav/Hartley BLOCKED reports) synchronised before BY2H/BY2O run.
- [ ] Bias/random decomposition result reported (conversation A) and consumed by C and D.
- [ ] Derived pairwise `A04_vs_F02`, `F04_vs_F02`, `A04_vs_F03` added under the publication namespace.

## Conversation log

- 2026-09-04 (A): file created; decisions in sections 1-4 agreed with the human.
