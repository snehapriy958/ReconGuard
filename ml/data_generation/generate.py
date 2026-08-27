"""
ReconLens — Phase 1: Synthetic data generation.

Generates a ground-truth transaction set, then derives two divergent,
independently corrupted source record sets (ledger + settlement) from it,
simulating the real-world disagreement between Razorpay's internal ledger
and a bank settlement file.

Design rules this file exists to enforce (see docs/architecture.md §6):
  1. Ground truth is generated once and never mutated after corruption.
  2. The internal ground-truth transaction id is carried on every derived
     record for evaluation purposes ONLY — it is stripped before features
     are computed and must never reach the model.
  3. Train/val/test splits are assigned at the ground-truth-transaction
     level, BEFORE any corrupted variant is created, so that no two
     variants of the same underlying transaction can land in different
     splits. This is what prevents leakage.
  4. A deliberate fraction of records are genuinely unmatched on one side
     (pending settlements, unrelated bank lines) so "no match" is a real,
     learnable class — not an artifact of a lazy generator.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import string
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

VENDORS = [
    "Reliance Industries Limited", "Tata Consultancy Services", "Infosys Limited",
    "HDFC Bank Limited", "ICICI Bank Limited", "Bharti Airtel Limited",
    "Larsen & Toubro Limited", "Wipro Limited", "Adani Enterprises Limited",
    "Mahindra & Mahindra Limited", "Zomato Limited", "Nykaa E-Retail Private Limited",
    "Swiggy Bundl Technologies Private Limited", "PhonePe Private Limited",
    "Flipkart Internet Private Limited", "BigBasket Innovative Retail Concepts",
    "Ola Cabs Private Limited", "Urban Company Technologies Private Limited",
    "Cred Dreamplug Technologies Private Limited", "Meesho Fashnear Technologies",
]

VENDOR_ABBREV = {
    "Reliance Industries Limited": ["Reliance Ind Ltd", "RIL", "RIL Payment", "Reliance Inds Ltd"],
    "Tata Consultancy Services": ["TCS", "Tata Consult Services", "TCS Ltd"],
    "Infosys Limited": ["Infosys Ltd", "INFY", "Infosys Pvt Ltd"],
    "HDFC Bank Limited": ["HDFC Bank Ltd", "HDFC Bk", "HDFCBANK"],
    "ICICI Bank Limited": ["ICICI Bank Ltd", "ICICI Bk", "ICICIBANK"],
    "Bharti Airtel Limited": ["Airtel Ltd", "Bharti Airtel Ltd", "AIRTEL"],
    "Larsen & Toubro Limited": ["L&T Ltd", "Larsen Toubro Ltd", "L AND T LIMITED"],
    "Wipro Limited": ["Wipro Ltd", "WIPRO", "Wipro Technologies Ltd"],
    "Adani Enterprises Limited": ["Adani Ent Ltd", "Adani Enterprises Ltd", "ADANIENT"],
    "Mahindra & Mahindra Limited": ["M&M Ltd", "Mahindra Mahindra Ltd", "M AND M LIMITED"],
    "Zomato Limited": ["Zomato Ltd", "ZOMATO", "Zomato Online Ordering Ltd"],
    "Nykaa E-Retail Private Limited": ["Nykaa Pvt Ltd", "FSN E-Commerce Nykaa", "NYKAA"],
    "Swiggy Bundl Technologies Private Limited": ["Swiggy Pvt Ltd", "Bundl Technologies", "SWIGGY"],
    "PhonePe Private Limited": ["PhonePe Pvt Ltd", "PHONEPE", "PhonePe Internet Pvt Ltd"],
    "Flipkart Internet Private Limited": ["Flipkart Pvt Ltd", "Flipkart Internet Ltd", "FLIPKART"],
    "BigBasket Innovative Retail Concepts": ["BigBasket Pvt Ltd", "Innovative Retail Concepts", "BIGBASKET"],
    "Ola Cabs Private Limited": ["Ola Cabs Pvt Ltd", "ANI Technologies Ola", "OLACABS"],
    "Urban Company Technologies Private Limited": ["Urban Company Pvt Ltd", "UrbanClap Technologies", "URBANCOMPANY"],
    "Cred Dreamplug Technologies Private Limited": ["Cred Pvt Ltd", "Dreamplug Technologies", "CRED"],
    "Meesho Fashnear Technologies": ["Meesho Pvt Ltd", "Fashnear Technologies Ltd", "MEESHO"],
}

DESC_TEMPLATES = [
    "Payment for invoice {ref}",
    "Order settlement {ref}",
    "Subscription charge {ref}",
    "Vendor payout {ref}",
    "Merchant settlement batch {ref}",
    "Service fee {ref}",
]


@dataclass
class GroundTruthTxn:
    txn_id: str
    vendor: str
    amount: float
    date: str  # ISO date of the underlying transaction
    ref_id: str
    split: str  # train / val / test
    structural_type: str  # one_to_one / split_settlement / batched_settlement / ledger_only / settlement_only


def _make_ref_id(rng: random.Random) -> str:
    return "RZP" + "".join(rng.choices(string.digits, k=10))


def _corrupt_vendor(rng: random.Random, vendor: str, severity: float) -> str:
    """severity in [0,1]: higher = more likely to alter the name."""
    if rng.random() > severity:
        return vendor
    choice = rng.random()
    abbrevs = VENDOR_ABBREV.get(vendor, [vendor])
    if choice < 0.5:
        return rng.choice(abbrevs)
    elif choice < 0.7:
        return vendor.upper()
    elif choice < 0.85:
        return vendor.replace("Limited", "Ltd").replace("Private", "Pvt")
    else:
        # whitespace / minor typo noise
        s = list(vendor)
        if len(s) > 5:
            i = rng.randrange(1, len(s) - 1)
            s[i], s[i + 1] = s[i + 1], s[i]
        return "".join(s)


def _corrupt_amount(rng: random.Random, amount: float, is_settlement: bool) -> float:
    if not is_settlement:
        return round(amount, 2)
    choice = rng.random()
    if choice < 0.55:
        return round(amount, 2)  # exact
    elif choice < 0.75:
        # fee deduction, 0.5%-2.5%
        fee_pct = rng.uniform(0.005, 0.025)
        return round(amount * (1 - fee_pct), 2)
    elif choice < 0.9:
        # paise rounding drift
        return round(amount + rng.uniform(-0.5, 0.5), 2)
    else:
        # small flat deduction (bank charges)
        return round(amount - rng.uniform(1, 25), 2)


def _corrupt_ref(rng: random.Random, ref_id: str) -> str:
    choice = rng.random()
    if choice < 0.70:
        return ref_id
    elif choice < 0.85:
        return ref_id[:6]  # truncated
    else:
        return ""  # missing


def _corrupt_date(rng: random.Random, base_date: datetime, is_settlement: bool) -> str:
    if not is_settlement:
        return base_date.date().isoformat()
    # settlement lag: log-normal-ish via exponential, capped at 5 days
    lag_days = min(5, int(rng.expovariate(1.2)))
    return (base_date + timedelta(days=lag_days)).date().isoformat()


def generate(n_transactions: int, seed: int, out_dir: Path) -> None:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    ground_truth: list[GroundTruthTxn] = []
    base_date = datetime(2026, 1, 1)

    # --- 1. Generate ground truth, assign structural type + split up front ---
    # Split proportions at the ground-truth level (leakage-safe).
    split_choices = (["train"] * 70) + (["val"] * 15) + (["test"] * 15)

    for i in range(n_transactions):
        txn_id = f"GT-{i:06d}"
        vendor = rng.choice(VENDORS)
        amount = round(rng.uniform(150, 250000), 2)
        date = base_date + timedelta(days=rng.randrange(0, 180))
        ref_id = _make_ref_id(rng)
        split = rng.choice(split_choices)

        structural_roll = rng.random()
        if structural_roll < 0.78:
            structural_type = "one_to_one"
        elif structural_roll < 0.86:
            structural_type = "split_settlement"      # one ledger -> many settlement lines
        elif structural_roll < 0.94:
            structural_type = "batched_settlement"    # many ledger -> one settlement line
        elif structural_roll < 0.97:
            structural_type = "ledger_only"            # pending, not yet settled -> genuine exception
        else:
            structural_type = "settlement_only"        # unrelated bank line (reversal/fee) -> genuine exception

        ground_truth.append(GroundTruthTxn(
            txn_id=txn_id, vendor=vendor, amount=amount,
            date=date.date().isoformat(), ref_id=ref_id, split=split,
            structural_type=structural_type,
        ))

    # --- 2. Derive ledger records (internal source — cleaner, minor corruption) ---
    ledger_rows = []
    settlement_rows = []
    match_map = []  # ground-truth mapping: ledger_id <-> settlement_id(s), TEST/EVAL USE ONLY
    pending_batch_items: list[GroundTruthTxn] = []

    for gt in ground_truth:
        base_dt = datetime.fromisoformat(gt.date)

        if gt.structural_type == "settlement_only":
            # no ledger record at all for this ground-truth txn
            pass
        elif gt.structural_type == "batched_settlement":
            # Ledger row deferred to step 2b: batch members need a jointly
            # reassigned, temporally-clustered date (see the fix note there),
            # so creating the ledger row here with the txn's independently
            # -drawn original date would just reintroduce the same bug.
            pass
        else:
            ledger_id = f"LED-{gt.txn_id[3:]}"
            ledger_rows.append({
                "ledger_id": ledger_id,
                "vendor_name": _corrupt_vendor(rng, gt.vendor, severity=0.15),
                "amount": round(gt.amount, 2),
                "txn_date": gt.date,
                "reference_id": gt.ref_id,  # ledger side keeps clean reference
                "description": rng.choice(DESC_TEMPLATES).format(ref=gt.ref_id),
                "_gt_txn_id": gt.txn_id,
                "_split": gt.split,
            })

        if gt.structural_type == "ledger_only":
            # pending — no settlement record yet, genuine exception
            continue

        if gt.structural_type == "one_to_one":
            settlement_rows.append({
                "settlement_id": f"STL-{gt.txn_id[3:]}-0",
                "vendor_name": _corrupt_vendor(rng, gt.vendor, severity=0.55),
                "amount": _corrupt_amount(rng, gt.amount, is_settlement=True),
                "txn_date": _corrupt_date(rng, base_dt, is_settlement=True),
                "reference_id": _corrupt_ref(rng, gt.ref_id),
                "description": rng.choice(DESC_TEMPLATES).format(ref=gt.ref_id[:6]),
                "_gt_txn_id": gt.txn_id,
                "_split": gt.split,
            })
            match_map.append({"gt_txn_id": gt.txn_id, "ledger_ids": [f"LED-{gt.txn_id[3:]}"],
                               "settlement_ids": [f"STL-{gt.txn_id[3:]}-0"], "split": gt.split})

        elif gt.structural_type == "split_settlement":
            n_parts = rng.choice([2, 3])
            remaining = gt.amount
            parts = []
            for p in range(n_parts - 1):
                part_amt = round(remaining * rng.uniform(0.3, 0.5), 2)
                parts.append(part_amt)
                remaining -= part_amt
            parts.append(round(remaining, 2))
            stl_ids = []
            for p_idx, part_amt in enumerate(parts):
                stl_id = f"STL-{gt.txn_id[3:]}-{p_idx}"
                stl_ids.append(stl_id)
                settlement_rows.append({
                    "settlement_id": stl_id,
                    "vendor_name": _corrupt_vendor(rng, gt.vendor, severity=0.55),
                    "amount": _corrupt_amount(rng, part_amt, is_settlement=True),
                    "txn_date": _corrupt_date(rng, base_dt, is_settlement=True),
                    "reference_id": _corrupt_ref(rng, gt.ref_id),
                    "description": rng.choice(DESC_TEMPLATES).format(ref=gt.ref_id[:6]),
                    "_gt_txn_id": gt.txn_id,
                    "_split": gt.split,
                })
            match_map.append({"gt_txn_id": gt.txn_id, "ledger_ids": [f"LED-{gt.txn_id[3:]}"],
                               "settlement_ids": stl_ids, "split": gt.split})

        elif gt.structural_type == "batched_settlement":
            # Deferred: these are grouped into real many-to-one batches below,
            # because a true batch requires >=2 ground-truth txns sharing one
            # settlement line (same vendor, same settlement date), not one
            # settlement row per transaction.
            pending_batch_items.append(gt)

    # --- 2b. Materialize batched settlements: group pending items 2-3 at a time,
    #          by (split, vendor), into a single settlement row covering their
    #          summed amount. Grouping within the same split is required —
    #          a batch line spanning train and test would leak split membership
    #          across the boundary we're trying to keep clean (see module docstring §3).
    #
    #          BUG FOUND, DIAGNOSED, AND FIXED (see docs/architecture.md Phase 3
    #          notes for the full write-up — this is the project's documented
    #          "what broke" story):
    #
    #          Observed: candidate-generation recall on many-to-one batches was
    #          0% even after Phase 3's structural blocking pass was built
    #          specifically to catch them.
    #
    #          Investigation: direct inspection of the hidden match map showed
    #          batch member transactions genuinely months apart (one batch
    #          spanned Jan 24 to Apr 19) — no bounded date window could ever
    #          recover that.
    #
    #          Root cause: the original generator picked each ground-truth
    #          transaction's date independently BEFORE deciding it would be
    #          part of a batch, then grouped whichever same-vendor/same-split
    #          leftovers happened to exist, with no proximity constraint.
    #
    #          First fix attempted: require batch members to already be close
    #          in date before grouping them. This FAILED — with ~600
    #          transactions spread across 20 vendors x 3 splits, most
    #          vendor/split buckets contain fewer than one batch-eligible item
    #          on average, so finding 2+ independently-dated items within a
    #          few days of each other almost never happens by chance (measured:
    #          0 of 50 batch-eligible transactions formed a valid group).
    #
    #          Actual fix: don't search for proximity among independently-dated
    #          transactions after the fact — assign a shared anchor date to
    #          each batch GROUP at formation time, and generate each member's
    #          date as a small, bounded offset from that anchor. This is also
    #          the more realistic model: a real settlement batch is defined by
    #          the processor choosing to batch a set of transactions together
    #          within a short operational window, not by coincidence. ---
    MAX_BATCH_DATE_SPAN_DAYS = 3

    def _make_ledger_row(gt: GroundTruthTxn, override_date: str) -> dict:
        return {
            "ledger_id": f"LED-{gt.txn_id[3:]}",
            "vendor_name": _corrupt_vendor(rng, gt.vendor, severity=0.15),
            "amount": round(gt.amount, 2),
            "txn_date": override_date,
            "reference_id": gt.ref_id,
            "description": rng.choice(DESC_TEMPLATES).format(ref=gt.ref_id),
            "_gt_txn_id": gt.txn_id,
            "_split": gt.split,
        }

    pending_batch_items.sort(key=lambda g: (g.split, g.vendor))
    grouped_chunks: list[list[GroundTruthTxn]] = []
    for _, bucket_iter in itertools.groupby(pending_batch_items, key=lambda g: (g.split, g.vendor)):
        bucket = list(bucket_iter)
        j = 0
        while j < len(bucket):
            size = rng.choice([2, 3])
            grouped_chunks.append(bucket[j:j + size])
            j += size

    for group in grouped_chunks:
        if len(group) < 2:
            # leftover single item: fall back to a normal one-to-one settlement,
            # using its own original date (nothing to synchronize with).
            gt = group[0]
            base_dt = datetime.fromisoformat(gt.date)
            ledger_rows.append(_make_ledger_row(gt, gt.date))
            settlement_rows.append({
                "settlement_id": f"STL-{gt.txn_id[3:]}-0",
                "vendor_name": _corrupt_vendor(rng, gt.vendor, severity=0.55),
                "amount": _corrupt_amount(rng, gt.amount, is_settlement=True),
                "txn_date": _corrupt_date(rng, base_dt, is_settlement=True),
                "reference_id": _corrupt_ref(rng, gt.ref_id),
                "description": rng.choice(DESC_TEMPLATES).format(ref=gt.ref_id[:6]),
                "_gt_txn_id": gt.txn_id, "_split": gt.split,
            })
            match_map.append({"gt_txn_id": gt.txn_id, "ledger_ids": [f"LED-{gt.txn_id[3:]}"],
                               "settlement_ids": [f"STL-{gt.txn_id[3:]}-0"], "split": gt.split})
            continue

        # Real batch: pick one shared anchor date for the group, then give each
        # member a small, bounded offset from it — this is what actually makes
        # the batch temporally realistic and recoverable by a bounded date
        # window, instead of relying on coincidence.
        anchor_date = datetime.fromisoformat(group[0].date)
        member_dates = []
        for g in group:
            offset = rng.randint(0, MAX_BATCH_DATE_SPAN_DAYS)
            member_date = (anchor_date + timedelta(days=offset)).date().isoformat()
            member_dates.append(member_date)
            ledger_rows.append(_make_ledger_row(g, member_date))

        combined_amount = sum(g.amount for g in group)
        # Settlement happens after the LAST member transaction, not the first —
        # a batch can't be settled before all its component transactions occurred.
        latest_member_date = max(datetime.fromisoformat(d) for d in member_dates)
        batch_id = "STL-BATCH-" + "-".join(g.txn_id[3:] for g in group)
        settlement_rows.append({
            "settlement_id": batch_id,
            "vendor_name": _corrupt_vendor(rng, group[0].vendor, severity=0.55),
            "amount": _corrupt_amount(rng, combined_amount, is_settlement=True),
            "txn_date": _corrupt_date(rng, latest_member_date, is_settlement=True),
            # a batched settlement line legitimately carries no single clean reference
            "reference_id": "",
            "description": f"Merchant settlement batch covering {len(group)} transactions",
            "_gt_txn_id": "|".join(g.txn_id for g in group),
            "_split": group[0].split,  # all members share the same split by construction below
        })
        match_map.append({
            "gt_txn_id": "|".join(g.txn_id for g in group),
            "ledger_ids": [f"LED-{g.txn_id[3:]}" for g in group],
            "settlement_ids": [batch_id],
            "split": group[0].split,
        })

    ledger_df = pd.DataFrame(ledger_rows)
    settlement_df = pd.DataFrame(settlement_rows)

    # Public files: strip internal ground-truth columns so features can't see them.
    public_cols_ledger = [c for c in ledger_df.columns if not c.startswith("_")]
    public_cols_settlement = [c for c in settlement_df.columns if not c.startswith("_")]

    ledger_df[public_cols_ledger].to_csv(out_dir / "ledger.csv", index=False)
    settlement_df[public_cols_settlement].to_csv(out_dir / "settlement.csv", index=False)

    # Hidden files: for evaluation ONLY, never fed to feature extraction or model.
    ledger_df[["ledger_id", "_gt_txn_id", "_split"]].to_csv(out_dir / "_hidden_ledger_truth.csv", index=False)
    settlement_df[["settlement_id", "_gt_txn_id", "_split"]].to_csv(out_dir / "_hidden_settlement_truth.csv", index=False)
    with open(out_dir / "_hidden_match_map.json", "w") as f:
        json.dump(match_map, f, indent=2)

    # Summary for sanity-checking the generator itself.
    summary = {
        "n_ground_truth_txns": n_transactions,
        "n_ledger_records": len(ledger_rows),
        "n_settlement_records": len(settlement_rows),
        "structural_type_counts": pd.Series([g.structural_type for g in ground_truth]).value_counts().to_dict(),
        "split_counts": pd.Series([g.split for g in ground_truth]).value_counts().to_dict(),
    }
    with open(out_dir / "_generation_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Generate ReconLens synthetic ledger/settlement data.")
    parser.add_argument("--n", type=int, default=600, help="Number of ground-truth transactions.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="../../data/raw")
    args = parser.parse_args()
    generate(args.n, args.seed, Path(__file__).parent / args.out)


if __name__ == "__main__":
    main()
