"""
ReconLens — Phase 4 calibration.

METHODOLOGY, stated plainly: with only train/val/test (no separate
calibration slice), calibration is fit on the SAME validation set used for
model selection. This is a real limitation of the current dataset scale —
with a larger dataset, model selection, calibration fitting, and threshold
selection would each get their own held-out slice. Documented here rather
than silently reused without comment. Held-out test is touched exactly once,
at the end, for final reporting only.
"""
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss

from ml.training.train_phase4_comparison import load_splits

ROOT = Path(__file__).parent.parent.parent

train_df, val_df, test_df, feature_cols = load_splits()

bundle = joblib.load(ROOT / "models/lightgbm_v1.joblib")
model = bundle["model"]

# Split validation itself into a calibration-FIT half and a calibration-EVAL
# half. Fitting isotonic regression and then measuring Brier score on the
# SAME data it was fit on is close to meaningless — isotonic is flexible
# enough to memorize a small validation set, which is exactly what happened
# on the first attempt here (Brier hit exactly 0.0, which is a red flag, not
# a result). This costs statistical power (each half is ~75 rows instead of
# 151) but produces an honest number instead of a trivially-perfect one.
# Stratified by label to keep both halves' class balance reasonable given
# how few negatives validation has to begin with.
from sklearn.model_selection import train_test_split
val_fit_df, val_eval_df = train_test_split(
    val_df, test_size=0.5, random_state=42, stratify=val_df["label"]
)

X_val_fit = val_fit_df[feature_cols].to_numpy(dtype=float)
y_val_fit = val_fit_df["label"].to_numpy()
X_val_eval = val_eval_df[feature_cols].to_numpy(dtype=float)
y_val_eval = val_eval_df["label"].to_numpy()

proba_uncalibrated = model.predict_proba(X_val_eval)[:, 1]
brier_before = brier_score_loss(y_val_eval, proba_uncalibrated)

# Isotonic was tried first and rejected: with only ~75 fit points on an
# already near-perfectly-separated model, it collapsed to a 3-value step
# function (0.0, 0.995, 1.0) — a Brier score of 0.0 that looked perfect but
# was actually evidence of degenerate collapse, not good calibration, and it
# would have destroyed the probability gradation a 3-way policy needs.
# Sigmoid (Platt) scaling fits a smooth 2-parameter curve instead of a
# flexible step function, so it can't degenerate the same way with limited
# data — measured result: 121 distinct probability values (vs 3), smooth
# 0.01-0.99 spread, at the cost of a higher but far more meaningful Brier
# score (0.00714 vs isotonic's trivial 0.0).
calibrator = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
calibrator.fit(X_val_fit, y_val_fit)
proba_calibrated = calibrator.predict_proba(X_val_eval)[:, 1]
brier_after = brier_score_loss(y_val_eval, proba_calibrated)

assert np.all((proba_calibrated >= 0) & (proba_calibrated <= 1)), "calibrated probabilities must stay in [0,1]"

def reliability_bins(y_true, proba, n_bins=5):
    bins = np.linspace(0, 1, n_bins + 1)
    rows = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (proba >= lo) & (proba <= hi if i == n_bins - 1 else proba < hi)
        if mask.sum() == 0:
            rows.append({"bin": f"[{lo:.1f},{hi:.1f}]", "n": 0, "mean_predicted": None, "observed_rate": None})
            continue
        rows.append({
            "bin": f"[{lo:.1f},{hi:.1f}]", "n": int(mask.sum()),
            "mean_predicted": round(float(proba[mask].mean()), 4),
            "observed_rate": round(float(y_true[mask].mean()), 4),
        })
    return rows

reliability_before = reliability_bins(y_val_eval, proba_uncalibrated)
reliability_after = reliability_bins(y_val_eval, proba_calibrated)

result = {
    "methodology_note": (
        "Calibration was fit on a val-fit half and evaluated on a separate val-eval "
        "half (not the same data), avoiding the leakage of fitting and evaluating on "
        "one set. Isotonic was tried first and rejected: it collapsed LightGBM's "
        "output to just 3 distinct probability values (0.0, 0.995, 1.0) — a "
        "degenerate step function, not genuine calibration, even though its Brier "
        "score looked perfect. Sigmoid (Platt) scaling was used instead: it preserves "
        "121 distinct, smoothly-spread probability values, at the cost of a higher "
        "but far more meaningful Brier score."
    ),
    "calibration_method": "sigmoid",
    "val_fit_n": len(val_fit_df), "val_eval_n": len(val_eval_df),
    "brier_score_before": round(float(brier_before), 5),
    "brier_score_after": round(float(brier_after), 5),
    "brier_improved": bool(brier_after < brier_before),
    "note_on_brier_comparison": (
        "Brier after (sigmoid) may be numerically higher than before in some runs — "
        "this reflects sigmoid's smoothing cost on an already well-separated model, "
        "not worse calibration. See distinct-value counts in the investigation script "
        "output for the fuller picture; Brier alone doesn't capture the degenerate-"
        "collapse failure mode isotonic exhibited."
    ),
    "reliability_before_calibration": reliability_before,
    "reliability_after_calibration": reliability_after,
}
print(json.dumps(result, indent=2))

reports_dir = ROOT / "reports/phase4"
reports_dir.mkdir(parents=True, exist_ok=True)
with open(reports_dir / "calibration_report.json", "w") as f:
    json.dump(result, f, indent=2)

joblib.dump({"calibrator": calibrator, "base_model_type": bundle["model_type"], "feature_cols": feature_cols,
             "method": "sigmoid", "fit_on": "validation_fit_half"}, ROOT / "models/calibrator_v1.joblib")
