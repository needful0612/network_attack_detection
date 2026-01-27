import gzip
import shutil
import os
import requests
# stream test
GZ_FILE = "data/Mirai_pcap.pcap.gz"
PCAP_FILE = "data/Mirai_pcap.pcap"
API_URL = "http://localhost:8000/upload_pcap"

def unzip_and_stream():
    if not os.path.exists(PCAP_FILE):
        print(f"Opening {GZ_FILE}...")
        with gzip.open(GZ_FILE, 'rb') as f_in:
            with open(PCAP_FILE, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print("Unzipped.")

    print(f"Streaming raw PCAP to {API_URL}...")
    
    with open(PCAP_FILE, 'rb') as f:
        files = {'file': (PCAP_FILE, f, 'application/octet-stream')}
        try:
            response = requests.post(API_URL, files=files)
            print(f"Server Response: {response.json()}")
        except Exception as e:
            print(f"Connection failed: {e}")

if __name__ == "__main__":
    unzip_and_stream()