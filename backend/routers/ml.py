import os
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from dependencies import get_current_user_or_agent

router = APIRouter(tags=["Machine Learning & Tests"])
logger = logging.getLogger("trinetra-backend.ml")

MODEL_METADATA_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "agents", "risk-agent", "models", "model_metadata.json"))
TRAINING_STATUS_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "agents", "risk-agent", "models", "training_status.json"))
ACTIVE_MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "agents", "risk-agent", "models", "active_model.json"))
TEST_STATUS_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "agents", "risk-agent", "models", "test_status.json"))
TEST_REPORT_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "agents", "risk-agent", "models", "test_report.json"))

@router.get("/api/ml/metrics")
async def get_ml_metrics(current_user: dict = Depends(get_current_user_or_agent)):
    """Fetch model training evaluation metrics, downsampled curves, and importances."""
    if not os.path.exists(MODEL_METADATA_PATH):
        return {
            "trained": False,
            "message": "No model metadata found. Please trigger model training first."
        }
    try:
        with open(MODEL_METADATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["trained"] = True
            return data
    except Exception as e:
        logger.error(f"Failed to load model metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load model metadata: {e}")

@router.get("/api/ml/status")
async def get_ml_status(current_user: dict = Depends(get_current_user_or_agent)):
    """Retrieve the current training status and logs."""
    if not os.path.exists(TRAINING_STATUS_PATH):
        return {
            "status": "IDLE",
            "progress": 0,
            "logs": [],
            "updated_at": None
        }
    try:
        with open(TRAINING_STATUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load status logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load status logs: {e}")

@router.post("/api/ml/train")
async def trigger_ml_train(current_user: dict = Depends(get_current_user_or_agent)):
    """Starts the model training and tuning pipeline in a background process."""
    if os.path.exists(TRAINING_STATUS_PATH):
        try:
            with open(TRAINING_STATUS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("status") == "TRAINING":
                    return {"status": "ALREADY_TRAINING", "message": "Model training is already in progress."}
        except Exception:
            pass

    os.makedirs(os.path.dirname(TRAINING_STATUS_PATH), exist_ok=True)
    status_data = {
        "status": "TRAINING",
        "progress": 0,
        "logs": [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Triggered training via API."],
        "error": None,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    with open(TRAINING_STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2)

    try:
        script_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "agents", "train_risk_models.py"))
        root_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".."))
        subprocess.Popen([sys.executable, script_path], cwd=root_dir)
        return {"status": "TRAINING_STARTED", "message": "ML training pipeline started in the background."}
    except Exception as e:
        status_data["status"] = "FAILED"
        status_data["error"] = str(e)
        status_data["logs"].append(f"Failed to start training subprocess: {e}")
        with open(TRAINING_STATUS_PATH, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)
        logger.error(f"Could not spawn training process: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not spawn training process: {e}")

@router.get("/api/ml/active-model")
async def get_active_model(current_user: dict = Depends(get_current_user_or_agent)):
    """Fetch the active underwriting model configuration."""
    if not os.path.exists(ACTIVE_MODEL_PATH):
        return {"active_model": "AUTO"}
    try:
        with open(ACTIVE_MODEL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read active model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read active model: {e}")

@router.post("/api/ml/active-model")
async def set_active_model(payload: dict, current_user: dict = Depends(get_current_user_or_agent)):
    """Sets the active model used by the underwriting agents (AUTO, XGBOOST, LGBM, LOGISTIC, TRI_LENS)."""
    model = payload.get("model", "AUTO")
    allowed = {"AUTO", "XGBOOST", "LGBM", "LOGISTIC", "TRI_LENS"}
    if model not in allowed:
        raise HTTPException(status_code=400, detail=f"Model {model} is not allowed. Must be one of {allowed}")
        
    try:
        os.makedirs(os.path.dirname(ACTIVE_MODEL_PATH), exist_ok=True)
        with open(ACTIVE_MODEL_PATH, "w", encoding="utf-8") as f:
            json.dump({"active_model": model}, f, indent=2)
        return {"status": "SUCCESS", "active_model": model}
    except Exception as e:
        logger.error(f"Failed to update active model configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update active model configuration: {e}")

@router.get("/api/test/report")
async def get_test_report(current_user: dict = Depends(get_current_user_or_agent)):
    """Retrieve the latest automated test execution report."""
    if not os.path.exists(TEST_REPORT_PATH):
        return {
            "run": False,
            "message": "No test suite execution report found. Run the test suite first."
        }
    try:
        with open(TEST_REPORT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["run"] = True
            return data
    except Exception as e:
        logger.error(f"Failed to read test report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read test report: {e}")

@router.get("/api/test/status")
async def get_test_status(current_user: dict = Depends(get_current_user_or_agent)):
    """Retrieve current logs and execution state of the test runner."""
    if not os.path.exists(TEST_STATUS_PATH):
        return {
            "status": "IDLE",
            "progress": 0,
            "logs": [],
            "updated_at": None
        }
    try:
        with open(TEST_STATUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read test status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read test status: {e}")

@router.post("/api/test/run")
async def run_test_suite_api(current_user: dict = Depends(get_current_user_or_agent)):
    """Triggers standard pytest suite programmatically in a background task."""
    if os.path.exists(TEST_STATUS_PATH):
        try:
            with open(TEST_STATUS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("status") == "RUNNING":
                    return {"status": "ALREADY_RUNNING", "message": "Test execution is already in progress."}
        except Exception:
            pass

    os.makedirs(os.path.dirname(TEST_STATUS_PATH), exist_ok=True)
    status_data = {
        "status": "RUNNING",
        "progress": 0,
        "logs": [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Automated test run initiated by API request."],
        "error": None,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    with open(TEST_STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2)

    try:
        script_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "agents", "run_tests.py"))
        root_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".."))
        subprocess.Popen([sys.executable, script_path], cwd=root_dir)
        return {"status": "RUNNING_STARTED", "message": "Automated testing framework running in background."}
    except Exception as e:
        status_data["status"] = "FAILED"
        status_data["error"] = str(e)
        status_data["logs"].append(f"Failed to spawn test runner process: {e}")
        with open(TEST_STATUS_PATH, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)
        logger.error(f"Failed to run test suite background task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to run test suite background task: {e}")
