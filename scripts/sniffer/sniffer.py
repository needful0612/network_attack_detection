import redis
import json
from scapy.all import sniff
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import ARP
from scapy.layers.inet import ICMP
from scripts.sniffer.netStat import netStat
import numpy as np
import traceback

# C0 maintains the STATE (netStat)
MAX_HOST = 100000000000
MAX_SESS = 100000000000
# use default(please see in netstat)
NSTAT = netStat(np.nan, MAX_HOST, MAX_SESS)

R = redis.Redis(host='broker', port=6379)
R_Q = "triage_queue"

def process_and_push(pkt):
    # Manually parse the pkt fields (similar to FE.get_next_vector logic)
    # This replaces the need for the FE class to read a file
    try:
        # Extract metadata (timestamp, length, IPs, Ports)
        # This is a condensed version of the FE class logic
        IPtype = 0 if pkt.haslayer(IP) else 1 # Simple check for IPv4/6
        timestamp = float(pkt.time) 

        framelen = len(pkt)
        srcMAC = pkt.src
        dstMAC = pkt.dst
        srcIP = pkt[IP].src if pkt.haslayer(IP) else ""
        dstIP = pkt[IP].dst if pkt.haslayer(IP) else ""
        
        srcproto = ''
        dstproto = ''
        
        if pkt.haslayer(TCP):
            srcproto = str(pkt[TCP].sport)
            dstproto = str(pkt[TCP].dport)
        elif pkt.haslayer(UDP):
            srcproto = str(pkt[UDP].sport)
            dstproto = str(pkt[UDP].dport)
        
        srcMAC = pkt.src
        dstMAC = pkt.dst
        if srcproto == '':  # it's a L2/L1 level protocol
            if pkt.haslayer(ARP):  # is ARP
                srcproto = 'arp'
                dstproto = 'arp'
                srcIP = pkt[ARP].psrc  # src IP (ARP)
                dstIP = pkt[ARP].pdst  # dst IP (ARP)
                IPtype = 0
            elif pkt.haslayer(ICMP):  # is ICMP
                srcproto = 'icmp'
                dstproto = 'icmp'
                IPtype = 0
            elif srcIP + srcproto + dstIP + dstproto == '':  # some other protocol
                srcIP = pkt.src  # src MAC
                dstIP = pkt.dst  # dst MAC
                
        sMAC = str(srcMAC) if srcMAC else ""
        dMAC = str(dstMAC) if dstMAC else ""
        sIP = str(srcIP) if srcIP else ""
        dIP = str(dstIP) if dstIP else ""
        sProto = str(srcproto) if srcproto else ""
        dProto = str(dstproto) if dstproto else ""

        # 2. Get the 115 features from netStat
        # vector = NSTAT.updateGetStats(IPtype, srcMAC, dstMAC, srcIP, srcproto, dstIP, dstproto,
        #                                          int(framelen),
        #                                          float(timestamp))
        
        vector = NSTAT.updateGetStats(
            int(IPtype), 
            sMAC, dMAC, 
            sIP, sProto, 
            dIP, dProto,
            int(framelen),
            float(timestamp)
        )
        
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
# ignore internal ports
sniff(
    iface="eth0", 
    filter="(tcp or udp) and not port 6379 and not port 8000", 
    prn=process_and_push, 
    store=0
)