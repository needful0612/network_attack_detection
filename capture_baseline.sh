#!/bin/bash

PCAP_PATH="/app/data/kitnet_cold_start.pcap"
PACKET_COUNT=50000
INTERFACE="eth0"

if [ -s "$PCAP_PATH" ]; then
    echo "[!] $PCAP_PATH already exists and is not empty. Skipping capture."
    exit 0
fi

mkdir -p "$(dirname "$PCAP_PATH")"

echo "[*] Starting Tshark capture ($PACKET_COUNT packets) on $INTERFACE..."

# Tshark execution
# Note: Use -f 'not port 22' if you're SSH'ing in to avoid capturing your own traffic
tshark -i "$INTERFACE" -c "$PACKET_COUNT" -w "$PCAP_PATH" > /dev/null 2>&1 &
TSHARK_PID=$!

echo "[*] Generating traffic to accelerate capture..."
wget -q -O /dev/null https://speed.cloudflare.com/__down?bytes=100000000 &

wait $TSHARK_PID

# perhaps chown to the process that use this? 
chmod 644 "$PCAP_PATH"

echo "[+] Capture complete! PCAP saved to $PCAP_PATH"