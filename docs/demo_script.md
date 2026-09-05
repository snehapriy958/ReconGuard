# ReconGuard — 5-Minute Demo Script

Exact things to say are in *italics*. Actions are plain text. Keep the
tone matter-of-fact and evidence-driven — the project's own strength is
that every claim below can be clicked into and verified live.

---

### 0:00–0:30 — Problem

*"Financial reconciliation means matching your internal ledger against
what actually landed from a payment processor or bank. It sounds like a
simple join — it isn't. References get truncated or dropped. Amounts
drift because of processor fees. Vendor names get corrupted differently
by every upstream system. And it's not even always one-to-one — one
ledger transaction can be split across several settlement lines, or
several ledger transactions get batched into one settlement line. A
system that's confidently wrong here doesn't just misclassify a row —
it silently corrupts a company's books."*

### 0:30–1:00 — Product

*"This is ReconGuard. It takes raw ledger and settlement records and
decides, with a measured, calibrated probability, whether each pair or
group represents the same transaction. High-confidence matches
auto-reconcile. Genuinely uncertain ones go to a human. Everything is
logged as an immutable audit trail. No LLM agents, no RAG, no
chatbot — the learned reconciliation model is the AI here; everything
around it is deterministic orchestration and governance."*

Show the home page (`/`) — the batch list.

### 1:00–2:00 — Upload / data

*"Let's submit a batch."*

Trigger `POST /batches` with a real ledger + settlement CSV (or via the
demo script). Open the resulting batch dashboard.

*"This just ran the entire pipeline synchronously: ingestion,
normalization, candidate generation, feature extraction, ML ranking,
calibration, and the confidence policy — for every candidate in this
batch. Here's the summary: total records, candidates generated,
auto-matched, needs review, likely no match, and structural matches
called out separately — one-to-many and many-to-one."*

Point at the outcome-distribution chart.

### 2:00–3:00 — Matching

Open a `HIGH_CONFIDENCE_MATCH` decision.

*"This candidate scored above our high threshold — 0.85 — so it
auto-matched. You can see the calibrated probability, the raw model
score, and the top evidence features that drove this decision, ranked
by contribution. Nothing here is a black box."*

Open a decision flagged `one_to_many` or `many_to_one`.

*"This is a structural match — one ledger transaction split across
multiple settlement lines. We don't collapse this into a fake one-to-one
pair; the candidate schema natively represents groups, and amounts are
aggregated as combined sums across the whole group."*

### 3:00–4:00 — Exceptions / review

Open the exceptions queue, pick one.

*"This candidate fell below our low threshold, or had no viable match
at all. It's not just discarded — it gets a root-cause category,
computed in a fixed priority order, plus a deeper analysis: which
evidence dimension was weak — amount, date, vendor, or reference — and
investigation guidance for a human."*

Switch to the review queue, open an open review, approve it.

*"This candidate landed between our thresholds, so it's a review task,
not an automatic decision. I'll approve it."*

Click approve. Reload the decision.

*"Here's the important part: the original ML decision and its
calibrated probability are unchanged — I'm looking at the same numbers
as before. Only the workflow state advanced, to
`APPROVED_BY_REVIEWER`, and a new audit event was recorded with my
identity as the reviewer. The model's output is never rewritten by a
human action — it's permanent history."*

### 4:00–4:30 — Auditability

Open the decision's audit timeline.

*"Every meaningful state change is one immutable, append-only event —
model evaluation, auto-match, review creation, my approval just now.
There's no update or delete path anywhere in this table. This merges
two separate event namespaces — the model's events and the human
review's events — into one traceable history, from the first model
score through my approval."*

### 4:30–5:00 — Engineering / results

*"Under the hood: FastAPI and PostgreSQL on the backend, Next.js on the
frontend, LightGBM as the ranking model, calibrated with sigmoid
scaling. On our held-out test set — evaluated exactly once, no tuning
afterward — we measured precision 1.0, recall 0.961, ROC-AUC 0.998.

But the honest number is this: one-to-many recall measured 66.7% on
that same held-out test, versus 98.6% for one-to-one. We don't hide
that — it's a known, tracked limitation, surfaced as a risk flag called
`KNOWN_LOW_GENERALIZATION`, precisely because we didn't have enough
structural examples to tune a separate threshold safely. That's the
whole point of this system's design: the ML model ranks candidates, but
it never gets unchecked authority. A fixed threshold policy, a separate
risk layer, mandatory human review for anything uncertain, and a full
audit trail are what make it safe to actually rely on — not the
model's accuracy number alone."*
