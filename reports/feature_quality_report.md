# Feature Quality Report

Rows: 1136

Embedding backend: `fallback_ngram_hash` (dim=256)


> **Note:** this run used the fallback n-gram hashing embedder, not the real semantic model — see `ml/features/embeddings.py` docstring. Vendor and description embedding similarity numbers below are lexical-overlap proxies, not true semantic similarity, and should not be quoted as final model-quality evidence until re-run with network access to the real model.


| Feature | Type | Missing % | Unique | Min | Max | Mean | Median | Std |
|---|---|---|---|---|---|---|---|---|
| abs_amount_diff | float64 | 0.0 | 802 | 0 | 1.199e+04 | 2201 | 992.3 | 2726 |
| relative_amount_diff | float64 | 0.0 | 799 | 0 | 0.04956 | 0.01513 | 0.00972 | 0.01605 |
| amount_ratio | float64 | 0.0 | 809 | 0.9507 | 1.05 | 0.9974 | 1 | 0.02191 |
| date_diff_days | int64 | 0.0 | 8 | 0 | 7 | 2.071 | 1 | 2.296 |
| vendor_levenshtein_similarity | float64 | 0.0 | 152 | 0 | 1 | 0.5597 | 0.3889 | 0.3491 |
| vendor_jaro_winkler_similarity | float64 | 0.0 | 323 | 0 | 1 | 0.707 | 0.611 | 0.2591 |
| vendor_token_sort_similarity | float64 | 0.0 | 161 | 0 | 1 | 0.5503 | 0.382 | 0.3466 |
| vendor_token_set_similarity | float64 | 0.0 | 132 | 0 | 1 | 0.5839 | 0.3944 | 0.363 |
| vendor_exact_normalized_match | int64 | 0.0 | 2 | 0 | 1 | 0.3134 | 0 | 0.4641 |
| vendor_embedding_cosine_similarity | float64 | 0.0 | 181 | -0.3333 | 1 | 0.4086 | 0.1291 | 0.4545 |
| reference_exact_match | int64 | 0.0 | 2 | 0 | 1 | 0.2984 | 0 | 0.4578 |
| reference_substring_overlap | int64 | 0.0 | 2 | 0 | 1 | 0.3697 | 0 | 0.4829 |
| reference_similarity | float64 | 0.0 | 6 | 0 | 1 | 0.4458 | 0.2308 | 0.3785 |
| reference_missing_ledger | int64 | 0.0 | 1 | 0 | 0 | 0 | 0 | 0 |
| reference_missing_settlement | int64 | 0.0 | 2 | 0 | 1 | 0.1576 | 0 | 0.3645 |
| reference_both_missing | int64 | 0.0 | 1 | 0 | 0 | 0 | 0 | 0 |
| candidate_count_for_ledger | int64 | 0.0 | 7 | 1 | 7 | 2.648 | 2 | 1.34 |
| candidate_count_for_settlement | int64 | 0.0 | 8 | 1 | 8 | 2.852 | 3 | 1.506 |
| competing_candidate_count | int64 | 0.0 | 14 | 0 | 13 | 3.5 | 3 | 2.502 |
| is_potential_one_to_many | int64 | 0.0 | 2 | 0 | 1 | 0.8116 | 1 | 0.3912 |
| is_potential_many_to_one | int64 | 0.0 | 2 | 0 | 1 | 0.794 | 1 | 0.4046 |
| description_embedding_cosine_similarity | float64 | 0.0 | 491 | -0.0915 | 0.9228 | 0.3064 | 0.2146 | 0.2618 |