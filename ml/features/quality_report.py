"""
ReconLens — feature quality report.

Per-feature descriptive stats only. Deliberately does NOT import anything
from _hidden_*: per spec, feature selection in Phase 2 must be justified by
domain reasoning, not by peeking at which features correlate with the
hidden labels. That comparison is reserved for supervised evaluation in a
later phase, using a clearly separate script.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def generate_report(feature_df: pd.DataFrame, metadata: dict) -> dict:
    id_cols = {"ledger_public_id", "settlement_public_id"}
    report = {"metadata": metadata, "n_rows": len(feature_df), "features": {}}

    for col in feature_df.columns:
        if col in id_cols:
            continue
        s = feature_df[col]
        entry = {
            "dtype": str(s.dtype),
            "missing_pct": round(100 * s.isna().mean(), 3),
            "unique_count": int(s.nunique()),
        }
        if pd.api.types.is_numeric_dtype(s):
            entry.update({
                "min": float(s.min()),
                "max": float(s.max()),
                "mean": round(float(s.mean()), 6),
                "median": round(float(s.median()), 6),
                "std": round(float(s.std()), 6),
            })
        report["features"][col] = entry

    return report


def write_report(report: dict, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "feature_quality_report.json", "w") as f:
        json.dump(report, f, indent=2)

    lines = [f"# Feature Quality Report\n", f"Rows: {report['n_rows']}\n",
             f"Embedding backend: `{report['metadata']['embedding_backend']}` "
             f"(dim={report['metadata']['embedding_dim']})\n"]
    if report["metadata"]["embedding_backend"] != "sentence-transformers/all-MiniLM-L6-v2":
        lines.append(
            "\n> **Note:** this run used the fallback n-gram hashing embedder, not the "
            "real semantic model — see `ml/features/embeddings.py` docstring. Vendor "
            "and description embedding similarity numbers below are lexical-overlap "
            "proxies, not true semantic similarity, and should not be quoted as final "
            "model-quality evidence until re-run with network access to the real model.\n"
        )
    lines.append("\n| Feature | Type | Missing % | Unique | Min | Max | Mean | Median | Std |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for name, e in report["features"].items():
        if "mean" in e:
            lines.append(f"| {name} | {e['dtype']} | {e['missing_pct']} | {e['unique_count']} | "
                          f"{e['min']:.4g} | {e['max']:.4g} | {e['mean']:.4g} | {e['median']:.4g} | {e['std']:.4g} |")
        else:
            lines.append(f"| {name} | {e['dtype']} | {e['missing_pct']} | {e['unique_count']} | - | - | - | - | - |")

    with open(out_dir / "feature_quality_report.md", "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    ROOT = Path(__file__).parent.parent.parent
    feature_df = pd.read_parquet(ROOT / "data/processed/features.parquet")
    with open(ROOT / "data/processed/features.metadata.json") as f:
        metadata = json.load(f)
    report = generate_report(feature_df, metadata)
    write_report(report, ROOT / "reports")
    print(f"Report written to reports/feature_quality_report.md ({len(report['features'])} features)")
