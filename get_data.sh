#!/bin/bash

mkdir -p data
cd data

BASE_URL_KIT="https://archive.ics.uci.edu/ml/machine-learning-databases/00516"

FILES=(
    "os_scan/OS%20Scan_dataset.csv.gz"
    "os_scan/OS%20Scan_labels.csv.gz"
    "mirai/Mirai_dataset.csv.gz"
    "mirai/Mirai_labels.csv.gz"
    "mirai/Mirai_pcap.pcap.gz"
)

echo "Download complete. Files located in ./data"