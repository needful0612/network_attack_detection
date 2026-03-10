import psycopg2
import os
import time
import socket

def test_mirai_detection_exists():
    db_url = os.getenv("DB_URL")
    
    # --- retry----------------
    conn = None
    for i in range(10):
        try:
            print(f"[*] Attempting to connect to DB: {db_url}")
            conn = psycopg2.connect(db_url)
            break
        except (psycopg2.OperationalError, socket.gaierror) as e:
            print(f"[!] DB not reachable yet: {e}. Retrying in 3s...")
            time.sleep(3)
    
    if not conn:
        assert False, "Could not connect to Database after 10 attempts."
    # ------------------------------------

    cur = conn.cursor()
    max_retries = 15 # Mirai traffic takes a few seconds to process
    cnt = 0
    
    for i in range(max_retries):
        cur.execute("SELECT COUNT(*) FROM alerts")
        res = cur.fetchone()
        cnt = res[0]
        if cnt > 0:
            print(f"[+] Found {cnt} alerts!")
            break
        print(f"[*] No alerts yet, waiting for pipeline... ({i+1}/{max_retries})")
        time.sleep(3)

    cur.close()
    conn.close()
    assert cnt > 0, "E2E Failure: No alerts found in database after attack injection."