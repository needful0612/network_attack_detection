#!/bin/bash

mkdir -p data
cd data

BASE_URL="https://archive.ics.uci.edu/ml/machine-learning-databases/00516"

echo "Downloading OS_Scan (Reconnaissance) Dataset..."
curl -L -O "$BASE_URL/os_scan/OS%20Scan_dataset.csv.gz"
curl -L -O "$BASE_URL/os_scan/OS%20Scan_labels.csv.gz"

echo "Downloading Mirai (Botnet Scanning) Dataset..."
curl -L -O "$BASE_URL/mirai/Mirai_dataset.csv.gz"
curl -L -O "$BASE_URL/mirai/Mirai_labels.csv.gz"

echo "Downloading Testing(Mirai) Dataset..."
curl -L -O "$BASE_URL/mirai/Mirai_pcap.pcap.gz"

echo "Download complete. Files located in ./data"