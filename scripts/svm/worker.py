import os
import socket
import redis
import json
import time
import math
import traceback
import uuid
from prometheus_client import start_http_server, Summary, Counter

from scripts.svm.predictor import BotFilterPredictor
from scripts.DTO.object.PacketInfo import PacketInfo
from scripts.alert.alert import cal_weighted_sum

INFERENCE_TIME = Summary('nids_svm_inference_seconds', 'Time spent on SVM inference')
PACKETS_PROCESSED = Counter('nids_svm_packets_total', 'Total packets processed by SVM')

R = redis.Redis(host='broker', port=6379, decode_responses=True)
# R_Q = "triage_queue"
# DEEP_INSPEC_Q = "deep_inspection_queue"
base_name = os.getenv("HOSTNAME") or socket.gethostname()
worker_name = f"{base_name}_{str(uuid.uuid4())[:4]}"

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
        time.sleep(10)

try:
    R.xgroup_create("nids_stream", "Group_SVM", id="0", mkstream=True)
except: 
    pass

PORT = 8000
start_http_server(PORT)
print(f"Prometheus metrics on SVM available on port {PORT}")
    
while True:
    # NOTE: apparently ">" means newest package
    messages = R.xreadgroup("Group_SVM", worker_name, {"nids_stream": ">"}, count=1, block=0)
    for _, msg_list in messages:
        for msg_id, payload in msg_list:
            
            with INFERENCE_TIME.time():
                packet = PacketInfo.from_redis(payload['data'])
                
                features_dict = {f"column_{i+1}": v for i, v in enumerate(packet.features)}
                res = predictor.predict(features_dict)
                score = res.get("probability")
            PACKETS_PROCESSED.inc()

            # --- SUBMITTION ---
            pipe = R.pipeline()
            pipe.hset(f"pkt:{packet.task_id}", "svm_score", score)
            pipe.hset(f"pkt:{packet.task_id}", "src_ip", packet.src_ip)
            pipe.hincrby(f"pkt:{packet.task_id}", "status", 1)
            pipe.expire(f"pkt:{packet.task_id}", 60)
            results = pipe.execute()

            new_status = results[-2] 
            if new_status == 2:
                full_record = R.hgetall(f"pkt:{packet.task_id}")
                res = cal_weighted_sum(full_record)
                
                if res != None:
                    # print(f"!!! ATTACK DETECTED !!! Score: {res["score"]:.4f} | IP: {res['ip']}")
                    R.xadd("alerts_stream", {"data": json.dumps(res)})
                    
                R.delete(f"pkt:{packet.task_id}")
            
            R.xack("nids_stream", "Group_SVM", msg_id)
    
"""
print(f"SVM Worker is live. Listening to {R_Q}...")
while True:
    try:
        # BRPOP blocks until data is available
        _, task_json = R.brpop(R_Q)
        packet = PacketInfo.from_redis(task_json)
        features_dict = {f"column_{i+1}": v for i, v in enumerate(packet.features)}
        
        res = predictor.predict(features_dict)
        prob = res.get("probability")
        is_attack = res.get("is_attack")

        if prob is None or not math.isfinite(prob):
            print(f"--- NAN DETECTION REPORT for {packet.src_ip} ---")
            continue 

        # --- THE WATERFALL LOGIC ---
        
        if 0.2 <= prob <= 0.8:
            print(f"[GREY ZONE] Prob: {prob:.4f} | IP: {packet.src_ip} -> Routing to KitNET")
            R.lpush(DEEP_INSPEC_Q, packet.to_redis())
        
        elif prob > 0.8:
            print(f"!!! [ATTACK] !!! Prob: {prob:.4f} | IP: {packet.src_ip}")
            R.lpush("alerts", json.dumps({"ip": packet.src_ip, "prob": prob, "type": "SVM_DETECTION"}))

        # else:
            # BENIGN
            # print(f"[CLEAN] Prob: {prob:.4f} | IP: {source_ip}")

    except Exception as e:
        print(f"Worker Loop Error: {e}")
        traceback.print_exc()
        
"""
