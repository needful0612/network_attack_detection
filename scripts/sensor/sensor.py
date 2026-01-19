import os
import requests
from scapy.all import sniff, IP, Ether
from kitsune.FeatureExtractor import FE
from kitsune.netStat import netStat

# CONFIGURATION
MODE = os.getenv("SENSOR_MODE", "PCAP") # Default to PCAP
SVM_URL = os.getenv("SVM_URL", "http://svm-container:8000/predict")
KITNET_URL = os.getenv("KITNET_URL", "http://kitnet-container:8001/predict")
INTERFACE = os.getenv("INTERFACE", "eth0")
PCAP_PATH = "/app/data/Mirai_pcap.pcap.gz"

ns = netStat()

def handle_vector(features):
    """Common logic for sending features to the Waterfall"""
    try:
        feature_list = features.tolist()
        res = requests.post(SVM_URL, json={"features": feature_list}, timeout=0.5)
        if res.status_code == 200:
            prediction = res.json()
            prob = prediction.get("probability", 0)

            # 2. THE WATERFALL DECISION
            if 0.2 < prob < 0.8:
                # Grey Zone: The SVM is confused. Escalate to the Autoencoder.
                print(f"[?] Grey Zone ({prob:.2f}) -> Escalating to KitNET...")
                kn_res = requests.post(KITNET_URL, json={"features": feature_list}, timeout=1.0)
                if kn_res.status_code == 200:
                    anom_score = kn_res.json().get("rmse", 0)
                    print(f"    [KitNET Result] Anomaly Score: {anom_score}")
            
            elif prob >= 0.8:
                # SVM is confident it's an attack
                print(f"[!] ATTACK DETECTED by SVM (Prob: {prob:.2f})")
        # ... add request to kitsune
    except Exception as e:
        print(f"Error: {e}")

if MODE == "LIVE":
    print(f"[*] LIVE MODE: Sniffing on {INTERFACE}...")
    def live_callback(pkt):
        if IP in pkt:
            # Manually extract metadata since we aren't using FE.py
            features = ns.updateGetStats(2048, pkt[Ether].src, pkt[Ether].dst, 
                                         pkt[IP].src, pkt[IP].dst, 
                                         pkt.sport if hasattr(pkt, 'sport') else 0,
                                         pkt.dport if hasattr(pkt, 'dport') else 0, 
                                         len(pkt), pkt.time)
            handle_vector(features)
    sniff(iface=INTERFACE, prn=live_callback, store=0)

else:
    print(f"[*] PCAP MODE: Processing {PCAP_PATH}...")
    fe = FE(PCAP_PATH, limit=float('inf'))
    while True:
        pkt_info = fe.get_next_vector()
        if pkt_info[7] == []: break # EOF
        features = ns.updateGetStats(*pkt_info)
        handle_vector(features)