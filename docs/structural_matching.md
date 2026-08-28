# ReconLens — Structural Matching (Phase 4)

## The gap this closes

Phase 3's Logistic Regression baseline was scoped explicitly to one-to-one
pairwise candidates. Structural (V2) candidates had 100% recall as *candidates*
but no feature vector and no label — meaning no model had ever been trained
or evaluated on split/batch reconciliation at all. Objective 1 required
inspecting this before touching LightGBM, confirming the gap, and fixing it.

## Representation

A candidate is generalized to a `CandidateGroup(ledger_ids: tuple, settlement_ids: tuple)`.
All public IDs are preserved, joined with `|` for storage:

```
one-to-one:   ledger_public_id="LED-000012"              settlement_public_id="STL-000012-0"
many-to-one:  ledger_public_id="LED-000045|LED-000046"    settlement_public_id="STL-BATCH-000045-000046"
one-to-many:  ledger_public_id="LED-000078"               settlement_public_id="STL-000078-0|STL-000078-1"
```

`relationship_type_candidate` (`one_to_one` / `one_to_many` / `many_to_one`)
and `group_size` are derived directly from `len(ledger_ids)` / `len(settlement_ids)`.

## Aggregation rules (every rule, stated explicitly per spec §13)

| Feature type | Rule | Why |
|---|---|---|
| Amount (`abs_amount_diff`, `relative_amount_diff`, `amount_ratio`) | Computed on **combined** amounts — sum of all ledger member amounts vs sum of all settlement member amounts | The business question for a batch is "does the total reconcile," not "does any one component match" |
| Date (`date_diff_days`, generalized to group span) | Max date − min date across **all** member records (ledger and settlement combined) | For a (1,1) candidate this is exactly the original `date_diff_days` |
| String/semantic similarity (vendor, embeddings) | **Max** across every (ledger member, settlement member) pair | A single strongly-matching pair is real evidence even if other cross-pairs look unrelated; averaging would dilute genuine evidence with irrelevant cross-terms |
| Reference (`exact_match`, `substring_overlap`, `similarity`) | Same max-reduction rule | Consistent with string/semantic reasoning |
| `reference_missing_ledger` / `_settlement` | 1 only if **all** members on that side are missing | If even one member has a reference, there's reference evidence to work with |
| `candidate_count_for_ledger` / `_settlement`, `competing_candidate_count` | Recomputed over the **full V1+V2 pool** (not just V1) | Now reflects structural competition, which Phase 2 had no visibility into |

**Verified, not assumed:** `test_group_features_backward_compatible_with_pairwise_core_features`
confirms all 15 non-count features produce bit-identical values to Phase 2's
original pairwise extractor when applied to a (1,1) candidate. The 5
count-based features are *expected* to differ (documented above), and a
separate test confirms genuine many-to-one positives have combined-amount
relative difference under 5% — verifying the aggregation rule actually
produces sane numbers, not just that the code runs.

## Class composition after unified labeling

|  | one_to_one | one_to_many | many_to_one |
|---|---|---|---|
| Train positive/negative | 334 / 279 | 27 / 1,626 | 13 / 1,099 |
| Val positive/negative | 98 / 25 | 3 / 14 | **0 / 11** |
| Test positive/negative | 70 / 13 | 6 / 5 | 1 / 5 |

**Val has zero many-to-one positives** — that relationship type could not be
meaningfully evaluated until the one-time held-out test run, which is itself
a limitation worth naming: model selection and threshold selection happened
with no visibility into many-to-one behavior at all.

## What held-out test revealed (see docs/model_comparison.md for full numbers)

One-to-many recall on test: **66.7%** (2 of 6 true matches missed) — notably
worse than one-to-one's 98.6%. This was invisible during validation (only 3
one-to-many positives there) and is a genuine, currently-unresolved
limitation: structural candidates are harder for this model than one-to-one,
and the current feature aggregation (max-reduction) may be discarding
information that would help — e.g., a true one-to-many match should have
*multiple* reasonably-strong evidence pairs, not just one, and the current
features can't distinguish "one strong pair, rest irrelevant" from "all
pairs moderately strong," which is a real structural difference worth
future feature-engineering work.
