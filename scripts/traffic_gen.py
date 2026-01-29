import requests
import time
import random

TARGET_URL = "http://target-web"

def simulate_benign_behavior():
    print("[*] Starting benign traffic generation...")
    while True:
        try:
            choice = random.random()
            
            if choice < 0.7:
                requests.get(TARGET_URL)
                print("Generated: GET /")
            
            elif choice < 0.9:
                for _ in range(5):
                    requests.head(TARGET_URL)
                    time.sleep(0.1)
                print("Generated: HEAD Pings")
            
            else:
                requests.get(f"{TARGET_URL}/50x.html")
                print("Generated: File Download")

            time.sleep(random.uniform(0.5, 2.0))
            
        except Exception as e:
            print(f"Target not ready: {e}")
            time.sleep(2)

if __name__ == "__main__":
    simulate_benign_behavior()