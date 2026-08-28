"""Bundle model + calibrator + feature schema + thresholds into one artifact,
so inference can never accidentally run against a mismatched feature order
or a stale threshold config loaded from a different place."""
import json
import platform
from pathlib import Path

import joblib
import lightgbm
import sklearn

ROOT = Path(__file__).parent.parent.parent

lgbm_bundle = joblib.load(ROOT / "models/lightgbm_v1.joblib")
calib_bundle = joblib.load(ROOT / "models/calibrator_v1.joblib")
with open(ROOT / "configs/threshold_policy.json") as f:
    policy = json.load(f)

assert lgbm_bundle["feature_cols"] == calib_bundle["feature_cols"]

final_bundle = {
    "model": lgbm_bundle["model"],
    "calibrator": calib_bundle["calibrator"],
    "feature_cols": lgbm_bundle["feature_cols"],
    "feature_schema_version": "phase4_unified_v1",
    "excluded_artifact_features": ["reference_missing_settlement"],
    "model_params": lgbm_bundle["params"],
    "calibration_method": calib_bundle["method"],
    "threshold_policy": policy,
    "random_seed": lgbm_bundle["random_seed"],
    "lightgbm_version": lightgbm.__version__,
    "sklearn_version": sklearn.__version__,
    "python_version": platform.python_version(),
    "dataset_version": "reconlens_synthetic_v1_seed42_n600",
}
joblib.dump(final_bundle, ROOT / "models/reconlens_phase4_final.joblib")
print(f"Saved final bundle with {len(final_bundle['feature_cols'])} features, "
      f"threshold policy {policy}, calibration={calib_bundle['method']}")
