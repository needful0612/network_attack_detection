import os
import pickle
import sys
import numpy as np
from scapy.utils import PcapReader
from scripts.feature_extractor.feature_extractor import feature_extractor # Ensure this is importable
from scripts.kitnet.engine import KitNetWorker
from scapy.utils import PcapReader
# Configuration
PCAP_PATH = "STREAM"
MODEL_PATH = "models/kitnet_warmed.pkl"
# Total warmup = FM_grace + AD_grace (5,000 + 50,000 = 55,000)
LIMIT = 60000 

def run_warmup():
    print(f"[*] Starting Warmup. Target: {LIMIT} packets from {PCAP_PATH}")
    
    # 1. Initialize your Worker
    worker = KitNetWorker()
    count = 0

    # 2. Stream the PCAP (Memory Efficient)
    try:
        # PcapReader can take a file-like object
        with PcapReader(sys.stdin.buffer) as pcap_stream:
            for pkt in pcap_stream:
                try:
                    fe = feature_extractor(pkt)
                    vector = fe.process_pkt_and_return_features_vector()
                    _ = worker.handle_request(vector)
                    
                    count += 1
                    if count % 1000 == 0:
                        print(f"[>] Processed {count} packets...")

                    if count >= LIMIT:
                        print(f"[!] Target reached. Closing stream...")
                        sys.stdin.close()
                        break
                except Exception as e:
                    break

        print(f"[*] Warmup complete. Saving state to {MODEL_PATH}")
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(worker.engine, f)
            
        print("[+] Success!")

    except FileNotFoundError:
        print(f"[!] Error: {PCAP_PATH} not found. Run get_data.sh first.")

run_warmup()