from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import ARP
from scapy.layers.inet import ICMP
from scripts.feature_extractor.netStat import netStat
import numpy as np

MAX_HOST = 100000000000
MAX_SESS = 100000000000
# use default(please see in netstat)
NSTAT = netStat(np.nan, MAX_HOST, MAX_SESS)

class feature_extractor:
    def __init__(self, pkt):
        self.pkt = pkt
        
        self.IPtype = 0 if pkt.haslayer(IP) else 1 # Simple check for IPv4/6
        self.timestamp = float(pkt.time) 

        self.framelen = len(pkt)
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
                
        self.sMAC = str(srcMAC) if srcMAC else ""
        self.dMAC = str(dstMAC) if dstMAC else ""
        self.sIP = str(srcIP) if srcIP else ""
        self.dIP = str(dstIP) if dstIP else ""
        self.sProto = str(srcproto) if srcproto else ""
        self.dProto = str(dstproto) if dstproto else ""
        
    def process_pkt_and_return_features_vector(self):
        vector = NSTAT.updateGetStats(
            int(self.IPtype), 
            self.sMAC, 
            self.dMAC, 
            self.sIP, 
            self.sProto, 
            self.dIP, 
            self.dProto,
            int(self.framelen),
            float(self.timestamp)
        )
        
        return vector
    
    def get_src_ip(self):
        return self.sIP
        