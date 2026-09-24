"""Tests for Phase 4 — Model Evaluation backend API and service.

Covers:
- A. GET /model/evaluation returns structured response
- B. Returned metrics match canonical evaluation artifact
- C. Endpoint is strictly read-only
- D. Arbitrary file path access is prevented
- E. Missing evaluation artifact produces controlled error
- F. Response schema is deterministic
"""

import os
os.environ["RECONLENS_TEST_SQLITE"] = "1"

from unittest.mock import patch
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.api.main import app
from backend.app.model_evaluation import get_model_evaluation_data

client = TestClient(app)


def test_a_model_evaluation_endpoint_returns_200():
    res = client.get("/model/evaluation")
    assert res.status_code == 200
    data = res.json()
    assert "model" in data
    assert "dataset" in data
    assert "metrics" in data
    assert "confusion_matrix" in data
    assert "class_metrics" in data
    assert "calibration" in data
    assert "notes" in data


def test_b_metrics_match_canonical_artifact():
    res = client.get("/model/evaluation")
    assert res.status_code == 200
    data = res.json()

    # Metrics
    metrics = data["metrics"]
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 0.961
    assert metrics["f1"] == 0.9801
    assert metrics["roc_auc"] == 0.9983
    assert metrics["pr_auc"] == 0.9995
    assert metrics["accuracy"] == 0.97

    # Confusion matrix
    cm = data["confusion_matrix"]
    assert cm["true_positive"] == 74
    assert cm["true_negative"] == 23
    assert cm["false_positive"] == 0
    assert cm["false_negative"] == 3
    assert cm["total"] == 100

    # Class metrics
    cm_classes = data["class_metrics"]
    assert "one_to_one" in cm_classes
    assert cm_classes["one_to_one"]["precision"] == 1.0
    assert cm_classes["one_to_one"]["recall"] == 0.9857
    assert cm_classes["one_to_many"]["recall"] == 0.6667
    assert cm_classes["many_to_one"]["recall"] == 1.0

    # Calibration
    calib = data["calibration"]
    assert calib["method"] == "sigmoid"
    assert calib["brier_score_before"] == 0.00355
    assert calib["brier_score_after"] == 0.00714
    assert calib["brier_improved"] is False


def test_c_endpoint_is_read_only():
    # POST, PUT, DELETE must be rejected with 405 Method Not Allowed
    post_res = client.post("/model/evaluation", json={"train": True})
    assert post_res.status_code == 405

    put_res = client.put("/model/evaluation", json={})
    assert put_res.status_code == 405

    delete_res = client.delete("/model/evaluation")
    assert delete_res.status_code == 405


def test_d_arbitrary_filesystem_paths_cannot_be_accessed():
    # Providing path traversal or arbitrary path queries has no effect
    res = client.get("/model/evaluation?path=/etc/passwd")
    assert res.status_code == 200
    data = res.json()
    # It strictly returns the fixed evaluation artifact, not arbitrary files
    assert data["model"]["name"] == "LightGBM Classifier (Calibrated)"


def test_e_missing_artifact_produces_controlled_404():
    with patch("backend.app.model_evaluation.REPORTS_DIR", Path("/non/existent/path")):
        res = client.get("/model/evaluation")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


def test_f_response_schema_is_deterministic():
    res1 = client.get("/model/evaluation")
    res2 = client.get("/model/evaluation")
    assert res1.json() == res2.json()
