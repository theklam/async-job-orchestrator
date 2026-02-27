import csv
import json
import math
import os
import time
import traceback

import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]
DATASET_PATH = os.environ.get("DATASET_PATH", "/app/spotify-2023.csv")
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


def safe_int(val):
    if val is None:
        return None
    s = str(val).replace(",", "").strip()
    if s == "" or s == "-":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def handle_ingest_dataset(conn, job_id, payload):
    payload_data = json.loads(payload) if payload else {}
    csv_path = payload_data.get("csv_path") or DATASET_PATH

    print(f"Job {job_id}: ingesting dataset from {csv_path}")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE spotify_tracks RESTART IDENTITY")

    rows_inserted = 0
    rows_skipped = 0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        with conn.cursor() as cur:
            for row in reader:
                track_name = row.get("track_name", "").strip()
                artists = row.get("artist(s)_name", "").strip()
                if not track_name or not artists:
                    rows_skipped += 1
                    continue
                try:
                    cur.execute(
                        """
                        INSERT INTO spotify_tracks (
                            track_name, artists, artist_count,
                            released_year, released_month, released_day,
                            streams,
                            in_spotify_playlists, in_spotify_charts,
                            in_apple_playlists, in_apple_charts,
                            in_deezer_playlists, in_deezer_charts,
                            in_shazam_charts,
                            bpm, key, mode,
                            danceability, valence, energy,
                            acousticness, instrumentalness, liveness, speechiness
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s, %s,
                            %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s
                        )
                        """,
                        (
                            track_name,
                            artists,
                            safe_int(row.get("artist_count")),
                            safe_int(row.get("released_year")),
                            safe_int(row.get("released_month")),
                            safe_int(row.get("released_day")),
                            safe_int(row.get("streams")),
                            safe_int(row.get("in_spotify_playlists")),
                            safe_int(row.get("in_spotify_charts")),
                            safe_int(row.get("in_apple_playlists")),
                            safe_int(row.get("in_apple_charts")),
                            safe_int(row.get("in_deezer_playlists")),
                            safe_int(row.get("in_deezer_charts")),
                            safe_int(row.get("in_shazam_charts")),
                            safe_int(row.get("bpm")),
                            row.get("key", "").strip() or None,
                            row.get("mode", "").strip() or None,
                            safe_int(row.get("danceability_%")),
                            safe_int(row.get("valence_%")),
                            safe_int(row.get("energy_%")),
                            safe_int(row.get("acousticness_%")),
                            safe_int(row.get("instrumentalness_%")),
                            safe_int(row.get("liveness_%")),
                            safe_int(row.get("speechiness_%")),
                        ),
                    )
                    rows_inserted += 1
                except Exception:
                    traceback.print_exc()
                    rows_skipped += 1

    conn.commit()

    result = {"rows_inserted": rows_inserted, "rows_skipped": rows_skipped}
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE jobs SET status = 'succeeded', result = %s, updated_at = now() WHERE id = %s",
            (json.dumps(result), str(job_id)),
        )
    conn.commit()
    print(f"Job {job_id} ingest succeeded: {result}")


def _minmax_normalize(vectors):
    """Normalize a list of equal-length vectors via min-max per dimension."""
    if not vectors:
        return vectors
    n_dims = len(vectors[0])
    mins = [min(v[d] for v in vectors) for d in range(n_dims)]
    maxs = [max(v[d] for v in vectors) for d in range(n_dims)]
    normalized = []
    for v in vectors:
        norm = []
        for d in range(n_dims):
            span = maxs[d] - mins[d]
            norm.append((v[d] - mins[d]) / span if span > 0 else 0.0)
        normalized.append(norm)
    return normalized


def _euclidean(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def handle_find_comparables(conn, job_id, payload):
    payload_data = json.loads(payload) if payload else {}
    track_name = payload_data.get("track_name", "").strip()

    print(f"Job {job_id}: finding comparables for '{track_name}'")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT track_name, artists,
                   danceability, valence, energy, acousticness,
                   instrumentalness, liveness, speechiness, bpm,
                   streams, in_spotify_playlists, in_apple_playlists, in_deezer_playlists
            FROM spotify_tracks
            """
        )
        rows = cur.fetchall()

    if not rows:
        raise RuntimeError("spotify_tracks is empty — run ingest_dataset first")

    # Build records, substituting 0 for NULL numeric fields
    records = []
    for r in rows:
        name, artists = r[0], r[1]
        audio = [float(r[i] or 0) for i in range(2, 10)]   # 8 dims
        market = [float(r[i] or 0) for i in range(10, 14)]  # 4 dims
        records.append({"track_name": name, "artists": artists, "audio": audio, "market": market})

    # Find query track (case-insensitive)
    query_lower = track_name.lower()
    query_record = next(
        (rec for rec in records if rec["track_name"].lower() == query_lower),
        None,
    )
    if query_record is None:
        raise RuntimeError(f"Track '{track_name}' not found in spotify_tracks")

    # Normalize audio and market feature groups independently
    audio_vecs = [rec["audio"] for rec in records]
    market_vecs = [rec["market"] for rec in records]

    norm_audio = _minmax_normalize(audio_vecs)
    norm_market = _minmax_normalize(market_vecs)

    # Locate query index
    query_idx = next(
        i for i, rec in enumerate(records)
        if rec["track_name"].lower() == query_lower
    )
    q_audio = norm_audio[query_idx]
    q_market = norm_market[query_idx]

    # Compute distances for all tracks (50/50 blend)
    scored = []
    for i, rec in enumerate(records):
        if i == query_idx:
            continue
        audio_dist = _euclidean(norm_audio[i], q_audio)
        market_dist = _euclidean(norm_market[i], q_market)
        dist = 0.5 * audio_dist + 0.5 * market_dist
        scored.append((dist, rec["track_name"], rec["artists"]))

    scored.sort(key=lambda x: x[0])
    top10 = scored[:10]

    comparables = [
        {"rank": rank + 1, "track_name": t, "artists": a, "distance": round(d, 6)}
        for rank, (d, t, a) in enumerate(top10)
    ]

    result = {"query": track_name, "comparables": comparables}
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE jobs SET status = 'succeeded', result = %s, updated_at = now() WHERE id = %s",
            (json.dumps(result), str(job_id)),
        )
    conn.commit()
    print(f"Job {job_id} find_comparables succeeded for '{track_name}'")


def poll(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, job_type, sleep_seconds, message, payload "
            "FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1 "
            "FOR UPDATE SKIP LOCKED"
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return False

        job_id, job_type, sleep_seconds, message, payload = row
        cur.execute(
            "UPDATE jobs SET status = 'running', updated_at = now() WHERE id = %s",
            (str(job_id),),
        )
        conn.commit()

    try:
        if job_type == "ingest_dataset":
            handle_ingest_dataset(conn, job_id, payload)
        elif job_type == "find_comparables":
            handle_find_comparables(conn, job_id, payload)
        else:
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
