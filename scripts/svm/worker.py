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
# from scripts.DTO.object.PacketInfo import PacketInfo
from scripts.DTO import packet_pb2
from scripts.alert.alert import cal_weighted_sum

INFERENCE_TIME = Summary('nids_svm_inference_seconds', 'Time spent on SVM inference')
PACKETS_PROCESSED = Counter('nids_svm_packets_total', 'Total packets processed by SVM')

R = redis.Redis(host='broker', port=6379, decode_responses=False)
PacketInfo = packet_pb2.PacketInfo
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
    R.xgroup_create("nids_stream", "group_svm", id="0", mkstream=True)
except: 
    pass

PORT = 8000
start_http_server(PORT)
print(f"Prometheus metrics on SVM available on port {PORT}")
    
while True:
    """
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
    while True:
        # 1. Use bytes for stream and group names to match decode_responses=False
        messages = R.xreadgroup(b"group_svm", worker_name.encode(), {b"nids_stream": b">"}, count=1, block=0)
        
        if not messages:
            continue

        for _, msg_list in messages:
            for msg_id, payload in msg_list:
                
                with INFERENCE_TIME.time():
                    # 2. Decode the Protobuf binary payload
                    packet = PacketInfo()
                    packet.ParseFromString(payload[b'data']) 
                    
                    # Convert features to the dict format your predictor expects
                    features_dict = {f"column_{i+1}": v for i, v in enumerate(packet.features)}
                    res_pred = predictor.predict(features_dict)
                    score = res_pred.get("probability")
                    
                PACKETS_PROCESSED.inc()

                pkt_key = f"pkt:{packet.task_id}"
                pipe = R.pipeline()
                pipe.hset(pkt_key, "svm_score", float(score))
                pipe.hset(pkt_key, "src_ip", packet.src_ip)
                pipe.hincrby(pkt_key, "status", 1)
                pipe.expire(pkt_key, 60)
                results = pipe.execute()

                current_votes = results[2] 
                
                if current_votes == 2:
                    full_record_raw = R.hgetall(pkt_key)
                    
                    full_record = {k.decode(): v.decode() for k, v in full_record_raw.items()}
                    
                    res_alert = cal_weighted_sum(full_record)
                    
                    if res_alert is not None:
                        R.xadd("alerts_stream", {"data": json.dumps(res_alert)})
                        
                    R.delete(pkt_key)
                
                R.xack(b"nids_stream", b"group_svm", msg_id)