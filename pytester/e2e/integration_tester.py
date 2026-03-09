import psycopg2
import os
import time

def test_mirai_detection_exists():
    # Get DB connection from env
    db_url = os.getenv("DB_URL", "db")

    max_retries = 5
    cnt = 0

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    for i in range(max_retries):
        cur.execute("SELECT COUNT(*) FROM alerts")
        res = cur.fetchone()
        cnt = res[0]

        if cnt > 0:
            break

        print(f"[*] No alerts yet, retrying ({i+1}/{max_retries})...")
        time.sleep(2)

    cur.close()
    conn.close()

    assert cnt > 0, f"E2E Failure: No alerts found."