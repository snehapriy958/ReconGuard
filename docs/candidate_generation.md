# ReconLens — Candidate Generation

## V1 (baseline, frozen — `ml/candidate_generation/blocking_v1.py`)

Pairwise blocking: amount window (±5% of ledger amount, floor ₹50) × date window
(0 to 7 days after the ledger transaction date).

**Measured recall (on the corrected dataset — see "Bug found" below):**

| Relationship type | Recall |
|---|---|
| One-to-one | **100%** (502/502 groups) |
| One-to-many (split) | **0%** (0/36 groups) |
| Many-to-one (batched) | **0%** (0/14 groups) |
| Overall (pair-level) | 80.87% |

**Failure mechanism, confirmed by direct inspection, not assumed:** V1 only ever
compares one ledger record against one settlement record, so it structurally
cannot represent "ledger A + ledger B → settlement X" or "ledger A →
settlement X + settlement Y" — a component's individual amount never falls
within a single-record's amount window of the combined total.

## Bug found during V2 development, fixed at the source

**Observed:** even after building V2's structural search specifically for
this, many-to-one recall barely moved (2/14 → 1/14 across debugging attempts).

**Investigation:** direct inspection of the hidden match map showed one true
batch's member transactions dated Jan 24 and Apr 19 — three months apart.

**Root cause:** Phase 1's batch generator grouped same-vendor/same-split
leftover transactions with **no date-proximity constraint** — whichever
transactions happened to exist were chunked together regardless of when they
occurred.

**First fix attempted (rejected):** require batch members to already be
close in date before grouping. This produced **zero** valid batches — with
~600 transactions across 20 vendors × 3 splits, most vendor/split buckets
contain fewer than one batch-eligible transaction on average, so two
independently-dated transactions landing within days of each other by chance
essentially never happens.

**Actual fix:** assign each batch group a shared anchor date at *formation*
time, then give each member a small bounded offset (0-3 days) from that
anchor — synchronizing dates by construction instead of searching for
coincidental proximity. This is also the more realistic model: a real
settlement batch reflects a processor's deliberate choice to batch
transactions within an operational window, not coincidence.

**Verified by test:** `test_batch_members_are_temporally_close` asserts every
many-to-one group spans ≤3 days; regenerating the dataset confirmed max
observed span dropped from >80 days to 3 days.

## V2 (structural — `ml/candidate_generation/blocking_v2.py`)

Bounded combinatorial search (group size 2-3, matching the generator's own
maximum) over same-*date-window* candidates — **not** gated by vendor
similarity. That gate was tried first and rejected: vendor corruption is
applied independently per record, so members of the *same* true group can
normalize to completely different strings (observed: settlement vendor
`ADANIENT` against ledger vendors `Adani Enterprises` / `Adani Enteprrises` —
none matching). A group is only as strong as its weakest corrupted member, so
requiring all members to agree on vendor was silently rejecting genuine
groups. Amount-sum + date window are the features that actually constrain
this problem; vendor similarity is recorded as a per-candidate signal for the
classifier, never a gate that can kill a true candidate.

**Tolerance tuned via a real sweep, not guessed:**

| relative_tol / abs_floor | Structural candidates | One-to-many recall | Many-to-one recall |
|---|---|---|---|
| 0.01 / ₹2 | 3,886 | 88.9% | 71.4% |
| 0.015 / ₹3 | 5,939 | 100% | 78.6% |
| 0.02 / ₹5 | 7,902 | 100% | 85.7% |
| **0.025 / ₹7 (chosen)** | **9,838** | **100%** | **100%** |
| 0.03 / ₹10 | 11,762 | 100% | 100% |

0.025/₹7 was chosen because it's the tightest setting that still achieves
100% recall on both structural types — 16% fewer candidates than the next
looser setting, with zero recall cost. It also has a principled justification
independent of the sweep: it matches the generator's known fee-deduction
ceiling (2.5%) rather than padding past it.

## V1 + V2 combined (final)

| Metric | V1 alone | V1 + V2 |
|---|---|---|
| Candidate pairs/groups | 1,142 | 10,980 (1,142 pairwise + 9,838 structural) |
| Pair-level recall | 80.87% | **100%** (622/622) |
| One-to-one recall | 100% | 100% |
| One-to-many recall | 0% | 100% |
| Many-to-one recall | 0% | 100% |
| Runtime | 0.67s | ~3.06s |

Target from the spec (>95% recall while keeping volume/runtime reasonable):
**met**, with the tradeoff explicit rather than hidden — structural
candidates outnumber true structural groups roughly 200:1, which is an
expected consequence of amount-sum search and is exactly why label assembly
and training treat structural candidates as a distinct, deferred problem
(see `docs/model_baseline.md`) rather than blending them into the pairwise
classifier under time pressure.
