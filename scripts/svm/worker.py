from scripts.svm.predictor import BotFilterPredictor
from scripts.svm.PacketFeatures import PacketFeatures

import redis
import json
import time
import math

R = redis.Redis(host='broker', port=6379, decode_responses=True)
R_Q = "triage_queue"
DEEP_INSPEC_Q = "deep_inspection_queue"

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

print(f"SVM Worker is live. Listening to {R_Q}...")
while True:
    try:
        # BRPOP blocks until data is available
        _, task_json = R.brpop(R_Q)
        task = json.loads(task_json)
        
        features = task['features']
        source_ip = task.get('src_ip', 'unknown')

        res = predictor.predict(features)
        prob = res.get("probability")
        is_attack = res.get("is_attack")

        if prob is None or not math.isfinite(prob):
            print(f"--- NAN DETECTION REPORT for {source_ip} ---")
            continue 

        # --- THE WATERFALL LOGIC ---
        
        if 0.2 <= prob <= 0.8:
            print(f"[GREY ZONE] Prob: {prob:.4f} | IP: {source_ip} -> Routing to KitNET")
            R.lpush(DEEP_INSPEC_Q, json.dumps(task))
        
        elif prob > 0.8:
            print(f"!!! [ATTACK] !!! Prob: {prob:.4f} | IP: {source_ip}")
            R.lpush("alerts", json.dumps({"ip": source_ip, "prob": prob, "type": "SVM_DETECTION"}))

        # else:
            # BENIGN
            # print(f"[CLEAN] Prob: {prob:.4f} | IP: {source_ip}")

    except Exception as e:
        print(f"Worker Loop Error: {e}")
