# ReconLens — Architecture Notes

Living document, updated at the end of each build phase with what was built and why.
This is what you'll draw from for the 5-minute video and for interview follow-ups.

## Phase 1 — Synthetic data generation (done)

**What:** `ml/data_generation/generate.py` produces `data/raw/ledger.csv` and
`data/raw/settlement.csv` from one internally-generated ground-truth transaction set.

**Key decisions and why:**

- **Split assigned before corruption, at the ground-truth level.** If you split after
  generating corrupted variants, two noisy versions of the same underlying transaction
  can land in different splits — the model would then be implicitly evaluated on
  transactions it has effectively already seen. Assigning `train`/`val`/`test` to the
  ground-truth transaction *first*, then deriving all corrupted variants from that
  labeled transaction, makes leakage structurally impossible rather than something
  you have to remember to check for later.

- **Batched settlements (many ledger records -> one settlement line) are grouped
  within the same split only.** A batch spanning train and test would reintroduce
  exactly the leak the split-first rule exists to prevent — one settlement line would
  effectively hand the model test-set information during training.

- **Genuine unmatched records exist by construction** (`ledger_only` = pending
  settlement, `settlement_only` = unrelated bank line such as a fee reversal), at
  roughly 5.5% combined. This means "no match" is a real, learnable outcome, not an
  edge case bolted on afterward — necessary for precision/recall on the negative
  class to mean anything.

- **Public CSVs never carry the ground-truth transaction ID.** It lives only in
  `_hidden_ledger_truth.csv`, `_hidden_settlement_truth.csv`, and
  `_hidden_match_map.json` — files that only the evaluation code should ever open.
  Phase 4 will add a test that fails the build if any feature-extraction code
  imports these.

**Current dataset (seed=42, n=600 ground-truth transactions):**
586 ledger records, 608 settlement records — 481 one-to-one, 50 batched, 36 split,
19 ledger-only exceptions, 14 settlement-only exceptions. Train/val/test = 407/109/84
ground-truth transactions.

**Open question carried into Phase 2:** the corruption severities (0.15 for ledger,
0.55 for settlement) were chosen to be "hard enough to need ML, not so hard that even
a human couldn't reconcile it." Worth revisiting once precision/recall numbers come
back from the baseline — if precision is suspiciously high, severity is too low.
