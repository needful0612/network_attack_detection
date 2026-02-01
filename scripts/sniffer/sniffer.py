import redis
import json
import numpy as np
import traceback
from scapy.all import sniff
from scripts.feature_extractor.feature_extractor import feature_extractor

R = redis.Redis(host='broker', port=6379)
R_Q = "triage_queue"

def process_and_push(pkt):
    try:
        f = feature_extractor(pkt)
        vector = f.process_pkt_and_return_features_vector()
        sIP = f.get_src_ip()
        
        if vector is not None:
            inner_dict = {f"column_{i+1}": float(v) for i, v in enumerate(vector)}
            
            payload = {
                "src_ip": sIP,
                "features": inner_dict
            }
            
            R.lpush(R_Q, json.dumps(payload))
            
    except Exception as e:
        print(f"--- Error Caught ---")
        traceback.print_exc()

print(F"Starting Sniffer. Pushing to Redis {R_Q}...")
sniff(
    iface="eth0", 
    filter="(tcp or udp) and not port 6379 and not port 8000", 
    prn=process_and_push, 
    store=0
)