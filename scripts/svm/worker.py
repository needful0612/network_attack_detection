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
redis_env = os.getenv("REDIS_ADDR", "broker:6379")

if ":" in redis_env:
    redis_host, redis_port = redis_env.split(":", 1)
    redis_port = int(redis_port)
else:
    redis_host = redis_env
    redis_port = 6379

print(f"[*] Connecting to Redis at: {redis_host}:{redis_port}")

R = None
retry_count = 0
while True:
    try:
        socket.gethostbyname(redis_host)
        
        temp_r = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            decode_responses=False,
            socket_connect_timeout=5
        )
        
        temp_r.ping() 
        
        R = temp_r
        print(f"[+] Successfully connected to Redis at {redis_host}")
        break
    except (socket.gaierror, redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        retry_count += 1
        print(f"[!] Redis at {redis_host} not ready. Retry #{retry_count} in 5s... ({e})")
        time.sleep(5)
# --------------------------------

# R = redis.Redis(host='broker', port=6379, decode_responses=False)
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
    # NOTE: apparently ">" means newest package
    while True:
        messages = R.xreadgroup(b"group_svm", worker_name.encode(), {b"nids_stream": b">"}, count=1, block=0)
        
        if not messages:
            continue

        for _, msg_list in messages:
            for msg_id, payload in msg_list:
                
                with INFERENCE_TIME.time():
                    packet = PacketInfo()
                    packet.ParseFromString(payload[b'data']) 
                    
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