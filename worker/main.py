import json
import os
import time
import traceback

import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]
POLL_INTERVAL = 2


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def process_job(conn, job_id, sleep_seconds, message):
    print(f"Processing job {job_id}: sleep {sleep_seconds}s, message={message!r}")
    time.sleep(sleep_seconds)
    result = {"slept_for": sleep_seconds, "echo": message}
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE jobs SET status = 'succeeded', result = %s, updated_at = now() WHERE id = %s",
            (json.dumps(result), str(job_id)),
        )
    conn.commit()
    print(f"Job {job_id} succeeded")


def poll(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, sleep_seconds, message FROM jobs "
            "WHERE status = 'queued' ORDER BY created_at LIMIT 1 "
            "FOR UPDATE SKIP LOCKED"
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return False

        job_id, sleep_seconds, message = row
        cur.execute(
            "UPDATE jobs SET status = 'running', updated_at = now() WHERE id = %s",
            (str(job_id),),
        )
        conn.commit()

    try:
        process_job(conn, job_id, sleep_seconds, message)
    except Exception:
        traceback.print_exc()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status = 'failed', result = %s, updated_at = now() WHERE id = %s",
                (json.dumps({"error": traceback.format_exc()}), str(job_id)),
            )
        conn.commit()
        print(f"Job {job_id} failed")

    return True


def main():
    print("Worker starting...")
    conn = get_connection()
    try:
        while True:
            if not poll(conn):
                time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("Worker shutting down")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
