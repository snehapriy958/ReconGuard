import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ModelEvaluationPage from "../page";
import type { ModelEvaluationResponse } from "@/lib/api-types";

vi.mock("@/lib/api-client", () => ({
  getModelEvaluation: vi.fn(),
}));

import { getModelEvaluation } from "@/lib/api-client";

const mockEvaluationData: ModelEvaluationResponse = {
  model: {
    name: "LightGBM Classifier",
    model_type: "Gradient Boosted Decision Trees (LightGBM)",
    version: "1.0.0",
    features_count: 22,
    bundle_file: "models/reconciliation_model.pkl",
    threshold_policy: {
      low_threshold: 0.5,
      high_threshold: 0.85,
      fp_cost: 100,
      fn_cost: 10,
      review_cost: 1,
    },
    top_features: [
      { feature: "amount_abs_diff", importance_gain: 1250.4, split_count: 85 },
      { feature: "description_similarity", importance_gain: 980.2, split_count: 64 },
    ],
  },
  dataset: {
    name: "Held-Out Test Split",
    split: "Held-Out Test Split",
    sample_count: 100,
    positive_count: 77,
    negative_count: 23,
    positive_rate: 0.77,
    by_relationship_type: {
      "1:1": { total: 83, positive: 64, negative: 19 },
      "1:N": { total: 11, positive: 8, negative: 3 },
      "N:1": { total: 6, positive: 5, negative: 1 },
    },
    training_samples: 598,
    validation_samples: 100,
  },
  metrics: {
    accuracy: 0.97,
    precision: 1.0,
    recall: 0.961038961038961,
    f1: 0.9801324503311258,
    roc_auc: 0.9983117614980248,
    pr_auc: 0.999494438827098,
  },
  confusion_matrix: {
    true_positive: 74,
    true_negative: 23,
    false_positive: 0,
    false_negative: 3,
    total: 100,
  },
  class_metrics: {
    "1:1": { n: 83, positive: 64, precision: 1.0, recall: 0.96875 },
    "1:N": { n: 11, positive: 8, precision: 1.0, recall: 0.875 },
    "N:1": { n: 6, positive: 5, precision: 1.0, recall: 1.0 },
  },
  routing_policy_results: {
    n_auto_match: 67,
    n_review: 8,
    n_no_match: 25,
    auto_match_precision: 1.0,
    auto_match_recall: 0.8701298701298701,
    review_positive_rate: 0.875,
    likely_no_match_error_rate: 0.12,
  },
  calibration: {
    method: "sigmoid",
    val_fit_samples: 50,
    val_eval_samples: 50,
    brier_score_before: 0.00355,
    brier_score_after: 0.00714,
    brier_improved: false,
    notes: "Platt scaling (sigmoid) chosen over isotonic to avoid step-function collapse.",
    methodology_note: "Platt scaling (sigmoid) chosen over isotonic to avoid step-function collapse.",
    reliability_before: [],
    reliability_after: [
      { bin: "0.0-0.2", n: 23, mean_predicted: 0.042, observed_rate: 0.0 },
      { bin: "0.8-1.0", n: 72, mean_predicted: 0.954, observed_rate: 0.986 },
    ],
  },
  notes: [
    "Held-out test split of 100 candidate groups evaluated under deterministic ground truth.",
    "Zero false positive rate achieved at default 0.85 auto-match threshold.",
  ],
};

describe("ModelEvaluationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renders loading state initially", () => {
    vi.mocked(getModelEvaluation).mockReturnValue(new Promise(() => {}));
    render(<ModelEvaluationPage />);
    expect(screen.getByText(/Loading model evaluation metrics/i)).toBeInTheDocument();
  });

  it("2. Renders error state on API failure", async () => {
    vi.mocked(getModelEvaluation).mockRejectedValue(new Error("Network failed to load"));
    render(<ModelEvaluationPage />);
    expect(await screen.findByText(/Network failed to load/i)).toBeInTheDocument();
  });

  it("3. Renders page title, header badges, and bundle metadata", async () => {
    vi.mocked(getModelEvaluation).mockResolvedValue(mockEvaluationData);
    render(<ModelEvaluationPage />);

    expect(await screen.findByRole("heading", { level: 1, name: "Model Evaluation" })).toBeInTheDocument();
    expect(screen.getByText("Held-Out Test Set")).toBeInTheDocument();
    expect(screen.getByText("models/reconciliation_model.pkl")).toBeInTheDocument();
  });

  it("4. Displays core metric highlight cards accurately", async () => {
    vi.mocked(getModelEvaluation).mockResolvedValue(mockEvaluationData);
    render(<ModelEvaluationPage />);

    expect(await screen.findByText("97.0%")).toBeInTheDocument(); // Accuracy
    expect(screen.getAllByText("100.0%").length).toBeGreaterThan(0); // Precision
    expect(screen.getByText("96.1%")).toBeInTheDocument(); // Recall
    expect(screen.getByText("0.9801")).toBeInTheDocument(); // F1
    expect(screen.getByText("0.9983")).toBeInTheDocument(); // ROC-AUC
    expect(screen.getByText("0.9995")).toBeInTheDocument(); // PR-AUC
  });

  it("5. Displays model architecture details and threshold policy rules", async () => {
    vi.mocked(getModelEvaluation).mockResolvedValue(mockEvaluationData);
    render(<ModelEvaluationPage />);

    expect(await screen.findByText("Gradient Boosted Decision Trees (LightGBM)")).toBeInTheDocument();
    expect(screen.getByText("22 engineered")).toBeInTheDocument();
    expect(screen.getByText("Production Decision Policy")).toBeInTheDocument();
    expect(screen.getByText(/Cost: FP=100, FN=10/i)).toBeInTheDocument();
    expect(screen.getByText("amount_abs_diff")).toBeInTheDocument();
  });

  it("6. Displays dataset split counts and relationship distribution", async () => {
    vi.mocked(getModelEvaluation).mockResolvedValue(mockEvaluationData);
    render(<ModelEvaluationPage />);

    expect(await screen.findByText("598")).toBeInTheDocument(); // Training
    expect(screen.getByText("83 samples")).toBeInTheDocument(); // 1:1 total
    expect(screen.getByText("11 samples")).toBeInTheDocument(); // 1:N total
    expect(screen.getByText("6 samples")).toBeInTheDocument(); // N:1 total
  });

  it("7. Displays confusion matrix cells correctly", async () => {
    vi.mocked(getModelEvaluation).mockResolvedValue(mockEvaluationData);
    render(<ModelEvaluationPage />);

    expect(await screen.findByText("True Positive (TP)")).toBeInTheDocument();
    expect(screen.getByText("74")).toBeInTheDocument();
    expect(screen.getByText("False Negative (FN)")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("False Positive (FP)")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("True Negative (TN)")).toBeInTheDocument();
    expect(screen.getAllByText("23").length).toBeGreaterThan(0);
  });

  it("8. Renders performance by relationship class table", async () => {
    vi.mocked(getModelEvaluation).mockResolvedValue(mockEvaluationData);
    render(<ModelEvaluationPage />);

    expect(await screen.findByText("Performance by Relationship Class")).toBeInTheDocument();
    expect(screen.getAllByText("1:1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1:N").length).toBeGreaterThan(0);
    expect(screen.getAllByText("N:1").length).toBeGreaterThan(0);
  });

  it("9. Renders probability calibration analysis and Brier scores", async () => {
    vi.mocked(getModelEvaluation).mockResolvedValue(mockEvaluationData);
    render(<ModelEvaluationPage />);

    expect(await screen.findByText("Probability Calibration Analysis")).toBeInTheDocument();
    expect(screen.getByText("0.00355")).toBeInTheDocument(); // Before
    expect(screen.getByText("0.00714")).toBeInTheDocument(); // After
    expect(screen.getByText(/Method: sigmoid/i)).toBeInTheDocument();
    expect(screen.getByText(/Platt scaling \(sigmoid\) chosen over isotonic/i)).toBeInTheDocument();
  });

  it("10. Renders governance notes and operational caveats", async () => {
    vi.mocked(getModelEvaluation).mockResolvedValue(mockEvaluationData);
    render(<ModelEvaluationPage />);

    expect(await screen.findByText("Model Governance & Operational Considerations")).toBeInTheDocument();
    expect(screen.getByText(/Held-out test split of 100 candidate groups/i)).toBeInTheDocument();
  });

  it("11. Gracefully handles empty or missing optional sections", async () => {
    const minimalData: ModelEvaluationResponse = {
      ...mockEvaluationData,
      model: {
        ...mockEvaluationData.model,
        top_features: [],
      },
      routing_policy_results: undefined,
      notes: [],
      calibration: {
        ...mockEvaluationData.calibration,
        methodology_note: undefined,
        reliability_after: [],
      },
    };

    vi.mocked(getModelEvaluation).mockResolvedValue(minimalData);
    render(<ModelEvaluationPage />);

    expect(await screen.findByRole("heading", { level: 1, name: "Model Evaluation" })).toBeInTheDocument();
    expect(screen.queryByText("Model Governance & Operational Considerations")).not.toBeInTheDocument();
    expect(screen.queryByText("Top Predictive Features (by gain):")).not.toBeInTheDocument();
  });

  it("12. Renders bottom navigation links pointing to batches and upload", async () => {
    vi.mocked(getModelEvaluation).mockResolvedValue(mockEvaluationData);
    render(<ModelEvaluationPage />);

    const batchesLink = await screen.findByRole("link", { name: /View Reconciliation Batches/i });
    expect(batchesLink).toHaveAttribute("href", "/batches");

    const uploadLink = screen.getByRole("link", { name: /Upload New CSV Batch/i });
    expect(uploadLink).toHaveAttribute("href", "/upload");
  });
});
