from fastapi import FastAPI, Body
from scripts.svm.predictor import BotFilterPredictor
from scripts.svm.PacketFeatures import PacketFeatures
import uvicorn
import time
import os
import math

app = FastAPI()

# Retry logic: The server waits for the trainer to finish saving the model
predictor = None
while predictor is None:
    try:
        predictor = BotFilterPredictor(
            model_path="models/svm_bot_filter.onnx", 
            config_path="models/preprocessor_config.json"
        )
        print("Model and Config loaded successfully!")
    except Exception as e:
        print(f"Waiting for model files... {e}")
        time.sleep(10) # Check every 10 seconds

@app.post("/predict")
async def predict(data: PacketFeatures):
    # Expecting {"column_1": 1.2, ... "column_115": 0.5}
    try:
        res = predictor.predict(data.features)
        
        prob = res.get("probability")
        is_attack = res.get("is_attack")

        # 3. FORENSIC CHECK: If probability is NaN, find out why
        if prob is None or (isinstance(prob, float) and not math.isfinite(prob)):
            # Look for NaNs in the input features provided by the sniffer
            bad_inputs = {k: v for k, v in data.features.items() if not math.isfinite(v)}
            actual_input = {k: v for k, v in data.features.items()}
            
            print("--- NAN DETECTION REPORT ---")
            print(f"Toxic Input Columns: {bad_inputs}")
            print(f"Actual Input Columns: {actual_input}")
            
            # Fallback so the JSON encoder doesn't crash
            return {"probability": 0.0, "label": 0, "status": "nan_detected", "culprits": list(bad_inputs.keys())}

        return {"probability": float(prob), "label": bool(is_attack)}
    except Exception as e:
        print(f"CRITICAL: Prediction failed: {e}")
        print(f"BAD DATA: {data.features}")
        return {"probability": 0.0, "label": 0, "status": "error_exception"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4000)