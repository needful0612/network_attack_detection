import time
import json

from scripts.DTO.object.PacketInfo import PacketInfo
def cal_weighted_sum(full_record):
    s_score = float(full_record.get('svm_score', 0))
    k_score = float(full_record.get('kitnet_score', 0))
                
    combined = (s_score * 0.6) + (k_score * 0.4)
    
    alert_data = None
    if combined >= 0.8:
        alert_data = {
            "ip": full_record.get('src_ip', 'unknown'),
            "score": combined,
            "svm": s_score,
            "kitnet": k_score,
            "timestamp": time.time()
        }
    return alert_data