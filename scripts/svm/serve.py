from fastapi import FastAPI, Body
from predictor import BotFilterPredictor
import uvicorn
import time
import os

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
async def predict(features: dict = Body(...)):
    # Expecting {"column_1": 1.2, ... "column_115": 0.5}
    return predictor.predict(features)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)