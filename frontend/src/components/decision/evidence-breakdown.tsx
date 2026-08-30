import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  interpretAmount,
  interpretDate,
  interpretVendor,
  interpretReference,
  interpretCompetition,
  type EvidenceStrength,
} from "@/lib/evidence-interpretation";
import { humanizeFeatureName } from "@/lib/feature-labels";

const strengthTone: Record<EvidenceStrength, "success" | "warning" | "neutral"> = {
  strong: "success",
  moderate: "warning",
  weak: "neutral",
};

function CategoryBlock({
  title,
  strength,
  label,
  technical,
}: {
  title: string;
  strength: EvidenceStrength;
  label: string;
  technical: { feature: string; value: number }[];
}) {
  return (
    <div className="border-t border-slate-100 py-4 first:border-t-0 first:pt-0">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-medium text-slate-800">{title}</h4>
        <Badge variant={strengthTone[strength]}>{strength}</Badge>
      </div>
      <p className="mt-1 text-sm text-slate-600">{label}</p>
      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-600">
          Technical evidence
        </summary>
        <ul className="mt-2 space-y-1 pl-3 text-xs text-slate-500">
          {technical.map((t) => (
            <li key={t.feature} className="flex justify-between gap-4">
              <span>{humanizeFeatureName(t.feature)}</span>
              <span className="tabular-nums text-slate-700">
                {Number.isInteger(t.value) ? t.value : t.value.toFixed(4)}
              </span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

/**
 * LAYER 2 — EVIDENCE QUALITY (full category breakdown).
 * Every value here comes from `all_features`, the real feature vector
 * recomputed server-side (see backend/app/api/main.py). The strength/label
 * for each category comes from src/lib/evidence-interpretation.ts's
 * documented, deterministic rules — never an LLM, never invented per-case.
 */
export function EvidenceBreakdown({
  features,
}: {
  features: Record<string, number>;
}) {
  const amount = interpretAmount(features.relative_amount_diff);
  const date = interpretDate(features.date_diff_days);
  const vendor = interpretVendor(features.vendor_token_set_similarity);
  const reference = interpretReference(
    features.reference_exact_match,
    features.reference_substring_overlap,
    features.reference_similarity,
    features.reference_both_missing
  );
  const competition = interpretCompetition(features.competing_candidate_count);

  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-2 text-sm font-medium text-slate-700">
          Evidence breakdown
        </CardTitle>
        <CategoryBlock
          title="Amount Evidence"
          strength={amount.strength}
          label={amount.label}
          technical={[
            { feature: "abs_amount_diff", value: features.abs_amount_diff },
            { feature: "relative_amount_diff", value: features.relative_amount_diff },
            { feature: "amount_ratio", value: features.amount_ratio },
          ]}
        />
        <CategoryBlock
          title="Date Evidence"
          strength={date.strength}
          label={date.label}
          technical={[{ feature: "date_diff_days", value: features.date_diff_days }]}
        />
        <CategoryBlock
          title="Vendor Evidence"
          strength={vendor.strength}
          label={vendor.label}
          technical={[
            { feature: "vendor_levenshtein_similarity", value: features.vendor_levenshtein_similarity },
            { feature: "vendor_jaro_winkler_similarity", value: features.vendor_jaro_winkler_similarity },
            { feature: "vendor_token_sort_similarity", value: features.vendor_token_sort_similarity },
            { feature: "vendor_token_set_similarity", value: features.vendor_token_set_similarity },
            { feature: "vendor_embedding_cosine_similarity", value: features.vendor_embedding_cosine_similarity },
          ]}
        />
        <CategoryBlock
          title="Reference Evidence"
          strength={reference.strength}
          label={reference.label}
          technical={[
            { feature: "reference_exact_match", value: features.reference_exact_match },
            { feature: "reference_substring_overlap", value: features.reference_substring_overlap },
            { feature: "reference_similarity", value: features.reference_similarity },
            { feature: "reference_both_missing", value: features.reference_both_missing },
          ]}
        />
        <CategoryBlock
          title="Candidate Competition"
          strength={competition.strength}
          label={competition.label}
          technical={[
            { feature: "candidate_count_for_ledger", value: features.candidate_count_for_ledger },
            { feature: "candidate_count_for_settlement", value: features.candidate_count_for_settlement },
            { feature: "competing_candidate_count", value: features.competing_candidate_count },
          ]}
        />
      </CardContent>
    </Card>
  );
}
