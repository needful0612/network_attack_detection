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

for FILE_PATH in "${FILES[@]}"; do
    FILE_NAME=$(basename "$FILE_PATH")

    if [ -f "$FILE_NAME" ]; then
        echo "$FILE_NAME exists, skipping."
    else
        echo "Downloading $FILE_NAME..."
        curl -L -O "$BASE_URL_KIT/$FILE_PATH"
    fi
done

echo "Download complete. Files located in ./data"