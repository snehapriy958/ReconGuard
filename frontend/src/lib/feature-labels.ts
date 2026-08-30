// Human-readable labels for raw feature names, used only in technical
// evidence displays — purely cosmetic, never changes the underlying value.
export const FEATURE_LABELS: Record<string, string> = {
  abs_amount_diff: "Absolute amount difference",
  relative_amount_diff: "Relative amount difference",
  amount_ratio: "Amount ratio",
  date_diff_days: "Date difference (days)",
  vendor_levenshtein_similarity: "Levenshtein similarity",
  vendor_jaro_winkler_similarity: "Jaro-Winkler similarity",
  vendor_token_sort_similarity: "Token sort similarity",
  vendor_token_set_similarity: "Token set similarity",
  vendor_exact_normalized_match: "Exact normalized match",
  vendor_embedding_cosine_similarity: "Embedding similarity",
  description_embedding_cosine_similarity: "Description embedding similarity",
  reference_exact_match: "Exact match",
  reference_substring_overlap: "Substring overlap",
  reference_similarity: "Reference similarity",
  reference_missing_ledger: "Missing on ledger side",
  reference_missing_settlement: "Missing on settlement side",
  reference_both_missing: "Missing on both sides",
  candidate_count_for_ledger: "Candidates for ledger record",
  candidate_count_for_settlement: "Candidates for settlement record",
  competing_candidate_count: "Competing candidates",
  group_size: "Group size",
  is_potential_one_to_many: "Potential one-to-many",
  is_potential_many_to_one: "Potential many-to-one",
};

export function humanizeFeatureName(feature: string): string {
  return FEATURE_LABELS[feature] ?? feature;
}
