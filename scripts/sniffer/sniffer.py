import os
import redis
import json
import numpy as np
import traceback
from scapy.all import sniff

from scripts.feature_extractor.feature_extractor import feature_extractor
from scripts.DTO.object.PacketInfo import PacketInfo

redis_host = os.getenv('REDIS_HOST', 'broker') 
R = redis.Redis(host=redis_host, port=6379)
R_Q = "triage_queue"

def process_and_push(pkt):
    try:
        f = feature_extractor(pkt)
        vector = f.process_pkt_and_return_features_vector()
        
        if vector is not None:
            packet = PacketInfo(
                src_ip=f.sIP,
                dst_ip=f.dIP,
                src_port=int(f.sProto) if f.sProto.isdigit() else None,
                dst_port=int(f.dProto) if f.dProto.isdigit() else None,
                features=vector.tolist() if hasattr(vector, "tolist") else list(vector)
            )
            
            # R.lpush(R_Q, packet.to_redis())
            R.xadd("nids_stream", {"data": packet.to_redis()})
            
    except Exception as e:
        print(f"--- [Sniffer Error] ---")
        traceback.print_exc()

print(F"Starting Sniffer. Pushing to Redis {R_Q}...")
sniff(
    iface="eth0", 
    filter="(tcp or udp) and not port 6379 and not port 8000", 
    prn=process_and_push, 
    store=0
)