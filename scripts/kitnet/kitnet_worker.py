import uuid
import os
import redis
import time
import socket
from scripts.kitnet.kitnet_engine import KitNetWorker 
from scripts.DTO.object.PacketInfo import PacketInfo

R = redis.Redis(host='broker', port=6379, decode_responses=True)

base_name = os.getenv("HOSTNAME") or socket.gethostname()
worker_name = f"{base_name}_{str(uuid.uuid4())[:4]}"

kit_engine = KitNetWorker(model_path="models/kitnet_state.pkl")

try:
    R.xgroup_create("nids_stream", "group_kitnet", id="0", mkstream=True)
except:
    pass

print(f"[*] {worker_name} is live. Waiting for packets...")

while True:
    messages = R.xreadgroup("group_kitnet", worker_name, {"nids_stream": ">"}, count=1, block=5000)
    
    if not messages:
        continue

    for _, msg_list in messages:
        for msg_id, payload in msg_list:
            packet = PacketInfo.from_redis(payload['data'])
            
            rmse_score = kit_engine.process_features(packet.features)
            print(rmse_score)
            
            pipe = R.pipeline()
            pipe.hset(f"pkt:{packet.task_id}", "kitnet_score", float(rmse_score))
            pipe.hincrby(f"pkt:{packet.task_id}", "status", 1)
            pipe.expire(f"pkt:{packet.task_id}", 60)
            results = pipe.execute()

            new_status = results[-2]
            if new_status == 2:
                full_record = R.hgetall(f"pkt:{packet.task_id}")
                
                s_score = float(full_record.get('svm_score', 0))
                k_score = float(full_record.get('kitnet_score', 0))
                
                combined = (s_score * 0.6) + (k_score * 0.4)
                
                if combined >= 0.8:
                    print(f"!!! ATTACK DETECTED !!! Score: {combined:.4f} | IP: {full_record['src_ip']}")
                    # push to persistent storage,might need to isolate the logic here
            
            R.xack("nids_stream", "Group_KitNET", msg_id)