# ReconGuard — Interview / Judge Q&A Prep

**"Explain your project in 60 seconds."**
ReconGuard reconciles a business's internal ledger against payment
processor/bank settlement records. It generates candidate matches with
two deterministic blocking passes, scores them with a calibrated
LightGBM model, and applies a fixed three-way confidence policy:
high-confidence matches auto-reconcile, uncertain ones go to a human
reviewer, and low-confidence ones become exceptions with a root-cause
analysis. It natively handles one-to-many and many-to-one relationships,
not just one-to-one. Every state change is logged as an immutable audit
event. There's no LLM agent or RAG involved — the learned model ranks
candidates; deterministic policy, human review, and audit logging keep
it safe.

**"Explain your architecture."**
Next.js frontend talking to a single FastAPI backend over a typed API
client, backed by PostgreSQL (seven tables: batches, source_records,
decisions, evidence_records, review_tasks, exception_records,
audit_events) via SQLAlchemy + Alembic migrations. Batch processing runs
synchronously inside the API request: candidate generation → feature
extraction → LightGBM scoring + calibration → workflow state machine →
persistence, with an append-only audit log written at every step.

**"Where exactly is AI used?"**
In exactly one place: ranking candidates that a deterministic blocking
step already generated, via a calibrated LightGBM classifier trained on
22 engineered features. It does not decide candidate generation, it
does not decide the confidence thresholds, and it does not make the
final auto-match/review/exception decision alone — that's a fixed
policy applied to its calibrated output.

**"Why LightGBM?"**
It captures non-linear feature interactions a linear model can't (e.g.
weak vendor similarity mattering more when reference similarity is also
weak), and on our validation set it strictly outperformed a Logistic
Regression baseline (precision/recall/F1 all 1.0 vs 0.9806/1.0/0.9902).
It's also fast enough to score a whole batch synchronously within one
API request.

**"Why not use an LLM for matching?"**
Matching here is a structured, numeric classification problem with a
measurable ground truth — amount/date/string-similarity features feed a
probability. An LLM would add latency, cost, and non-determinism without
adding capability: there's no unstructured natural-language
understanding task in this pipeline. It would also make the safety story
harder, not easier — a probability from a well-understood, calibrated
gradient-boosted model is something we can threshold and audit
confidently; an LLM's confidence is not.

**"Why do you need deterministic rules?"**
Because the model's own held-out evaluation shows a real, measurable
generalization gap — one-to-many recall at 66.7% vs 98.6% for
one-to-one — that only became visible on data the model hadn't been
scored against. A fixed threshold policy and a separate risk-flag layer
mean that gap gets caught and routed to a human instead of silently
auto-matching (or silently rejecting) the wrong things.

**"How do you avoid false automatic matches?"**
The HIGH threshold (0.85) was chosen by a cost-sensitive grid search
that weighted false positives 10× a false negative's 3× — explicitly
because a wrong auto-match is far more costly than a missed one — with
a hard floor so the threshold could never drop below 0.85 even if raw
cost-minimization on a small sample suggested lower. On held-out test,
auto-matched candidates had 0 false positives (precision 1.0, n=71).

**"What happens when confidence is low?"**
Below the LOW threshold (0.50, or no candidate at all), the candidate
becomes an `ExceptionRecord` with a root-cause category (chosen in a
fixed priority order: no candidate found → structural ambiguity → high
competition → insufficient evidence → low confidence), plus an on-demand
deeper root-cause analysis identifying which evidence dimension —
amount, date, vendor, or reference — was weakest.

**"How does candidate generation work?"**
Two blocking passes. V1 (pairwise): an amount window (±5%, ₹50 floor)
and a date window (0–7 days after the ledger date) — 100% recall on
one-to-one, but structurally can't represent split/batched settlements.
V2 (structural): a bounded combinatorial search (group size 2–3) over
the same date window, tuned to a 0.025 relative / ₹7 absolute amount
tolerance — the tightest setting that still achieves 100% measured
recall on both structural types. Combined, they generate 10,980
candidates from 586 ledger + 607 settlement records.

**"How do you handle one-to-many transactions?"**
Every candidate is a `CandidateGroup(ledger_ids, settlement_ids)` — both
are lists, even for one-to-one (a 1-element list). One-to-many and
many-to-one candidates go through the exact same feature schema:
amounts as combined sums, dates as the group's full span, string
similarity as the max across every member pair. No fake collapsing to a
single ID.

**"How did you evaluate the model?"**
Ground-truth transactions were split train/val/test before corruption
was applied (so noisy variants of the same transaction can't split
across sets), plus a second leakage rule excluding any candidate whose
members disagree on split. LightGBM was picked over Logistic Regression
on validation, then evaluated exactly once on held-out test with no
further tuning — precision 1.000, recall 0.961, F1 0.9801, ROC-AUC
0.9983, PR-AUC 0.9995 (TN=23, FP=0, FN=3, TP=74).

**"Why is recall important here?"**
A missed match (false negative) becomes an exception a human can still
catch and resolve — recoverable. A wrong match (false positive) can
silently corrupt financial records — much harder to recover from. That
asymmetry is exactly why the threshold policy weights false positives
10× a false negative's 3×, and why the system is tuned to protect
precision at the top end even at some recall cost.

**"What does your false-positive rate mean?"**
On held-out test, auto-matched candidates (the HIGH_CONFIDENCE_MATCH
band) had zero false positives (FP=0 of 74 true positives, precision
1.0) — meaning every candidate the system auto-reconciled without human
involvement was actually correct, on this test set. The overall
confusion matrix's 3 false negatives all fell into the review or
no-match bands, where a human is still in the loop.

**"What happens during reviewer approval?"**
`POST /reviews/{id}/approve` (or `/reject`) looks up the `ReviewTask`,
rejects it with HTTP 409 if already resolved, and otherwise advances
`workflow_state` (e.g. to `APPROVED_BY_REVIEWER`) and records the
reviewer's ID and timestamp. It explicitly does **not** touch
`decision.decision`, `raw_probability`, or `calibrated_probability` —
those are immutable ML output. A new audit event captures the action
alongside the model's original decision and probability as an explicit,
queryable proof nothing was overwritten.

**"How do you maintain an audit trail?"**
One function, `record_event()`, is the only code path anywhere in the
codebase that writes to the audit table — it only ever `INSERT`s; there
is no update or delete function for it. Every meaningful state change
calls it. `GET /audit/{entity_type}/{entity_id}` retrieves the full
ordered history for any entity; `GET /decisions/{id}/audit` merges the
decision's own events with any human-review events (a separate entity
namespace) into one timeline.

**"How do you guarantee idempotency?"**
Every batch submission is hashed (`compute_batch_hash()` over the
ledger + settlement records). If a batch with the same hash already
exists, the pipeline returns the existing batch instead of
reprocessing — verified directly by submitting the same batch twice
over real HTTP against real PostgreSQL and confirming only one row
exists.

**"Why PostgreSQL?"**
A real relational database with ACID transactions and native JSON
column support (used for feature/evidence/risk-flag payloads) — the
project's actual production target. SQLite is only an explicit, opt-in
isolated-test backend, never a silent fallback for real runs.

**"Why FastAPI?"**
Typed request/response validation via Pydantic, auto-generated
interactive docs (`/docs`), and the same language (Python) as the ML
pipeline — no serialization boundary between the model code and the API
layer.

**"What is your biggest limitation?"**
The one-to-many recall gap: 66.7% on held-out test vs 98.6% for
one-to-one. It's real, it's measured, and we chose to surface it
honestly via a `KNOWN_LOW_GENERALIZATION` risk flag rather than
under-report it or paper over it with an untuned type-specific
threshold we don't have enough data to set safely.

**"What would you change for production?"**
Type-aware thresholds once more structural labeled data exists; async
batch processing behind a task queue; authentication and multi-tenant
scoping; guaranteed availability of the real sentence-transformer
embedding model instead of the n-gram-hashing fallback; stronger audit
immutability guarantees (database-level or cryptographic, not just
application-level); and validation against real (not synthetic)
ledger/settlement data.

**"What happens if the ML model is unavailable?"**
Model loading happens inside a try/except in `process_batch()`; if
candidate generation or inference throws, the batch is explicitly
transitioned to `FAILED` with the error recorded (`failure_reason`) and
a `PROCESSING_FAILED` audit event — not silently dropped or left in an
ambiguous state. There's no automatic fallback decision path; a failed
batch is visibly failed.

**"What happens if the data format changes?"**
Pydantic models (`LedgerRecordIn`, `SettlementRecordIn`) validate
incoming records at the API boundary — a genuinely malformed request is
rejected with a 422 before it reaches the pipeline. Within the pipeline,
missing optional fields (e.g. no `description` column in a given
batch's schema) are handled by filling absent feature columns with 0
rather than crashing, though a fully incompatible schema would still
surface as a batch-level failure per the previous answer.

**"How would this scale to millions of transactions?"**
Candidate generation would need indexed blocking (a proper database-
backed windowed query instead of an in-memory combinatorial search) at
that volume, and batch processing would need to move off the
synchronous request path onto an async worker/task queue so a large
batch doesn't hold an HTTP request open. The scoring step itself
(LightGBM inference) is already fast and batches well; it's the
candidate-generation and orchestration layers that would need to change
first — this is an explicitly acknowledged limitation, not something
this codebase already solves.
