import uuid
import os
import redis
import time
import socket
import json
from prometheus_client import start_http_server, Summary, Counter

from scripts.kitnet.kitnet_engine import KitNetWorker 
from scripts.DTO.object.PacketInfo import PacketInfo
from scripts.alert.alert import cal_weighted_sum

INFERENCE_TIME = Summary('nids_kitnet_inference_seconds', 'Time spent on kitnet inference')
PACKETS_PROCESSED = Counter('nids_kitnet_packets_total', 'Total packets processed by kitnet')

R = redis.Redis(host='broker', port=6379, decode_responses=True)

base_name = os.getenv("HOSTNAME") or socket.gethostname()
worker_name = f"{base_name}_{str(uuid.uuid4())[:4]}"

kit_engine = KitNetWorker(model_path="models/kitnet_state.pkl")

try:
    R.xgroup_create("nids_stream", "group_kitnet", id="0", mkstream=True)
except:
    pass

PORT = 8000
start_http_server(PORT)
print(f"Prometheus metrics ON KITNET available on port {PORT}")

print(f"[*] {worker_name} is live. Waiting for packets...")

while True:
    messages = R.xreadgroup("group_kitnet", worker_name, {"nids_stream": ">"}, count=1, block=5000)
    
    if not messages:
        continue

    for _, msg_list in messages:
        for msg_id, payload in msg_list:
            
            with INFERENCE_TIME.time():
                packet = PacketInfo.from_redis(payload['data'])
                
                rmse_score = kit_engine.process_features(packet.features)
            PACKETS_PROCESSED.inc()
            
            pipe = R.pipeline()
            pipe.hset(f"pkt:{packet.task_id}", "kitnet_score", float(rmse_score))
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
            
            R.xack("nids_stream", "Group_KitNET", msg_id)