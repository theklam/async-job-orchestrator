# async-job-orchestrator

A minimal async job processing system built with FastAPI, a background worker, and Postgres.

The API enqueues jobs, and a separate worker process polls the database to execute them asynchronously. This project focuses on a simple, working local prototype without external queue systems.

## Architecture

```
┌──────────┐     ┌────────────────┐     ┌────────────┐
│  Client  │────▶│  API (FastAPI) │────▶│  Postgres  │
└──────────┘     └────────────────┘     └────────────┘
                                              ▲
                                              │ polls
                                              │
                                        ┌──────────┐
                                        │  Worker  │
                                        └──────────┘
```

## Quick Start

```bash
docker compose up --build
```

This starts Postgres, API (port 8000), and Worker.

If you are rebuilding after a schema change, drop the DB volume first:

```bash
docker compose down -v && docker compose up --build
```

## Job Types

### `sleep` (default)

Sleeps for N seconds and echoes a message back. Useful for testing the pipeline.

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_type": "sleep", "sleep_seconds": 3, "message": "hello"}'
```

Result: `{"slept_for": 3, "echo": "hello"}`

---

### `ingest_dataset`

Parses `spotify-2023.csv` (953 songs) and loads it into the `spotify_tracks` table. Idempotent — truncates and reloads on each run.

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_type": "ingest_dataset"}'
```

Result: `{"rows_inserted": 953, "rows_skipped": 0}`

Must be run before `find_comparables`.

---

### `find_comparables`

Given a track name, finds the 10 most similar songs in the dataset using weighted Euclidean distance across two feature groups:

- **Audio** (8 dims): danceability, valence, energy, acousticness, instrumentalness, liveness, speechiness, bpm
- **Market** (4 dims): streams, Spotify playlists, Apple playlists, Deezer playlists

Both groups are min-max normalized independently, then blended 50/50.

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_type": "find_comparables", "track_name": "Cruel Summer"}'
```

Result:
```json
{
  "query": "Cruel Summer",
  "comparables": [
    {"rank": 1, "track_name": "Jimmy Cooks (feat. 21 Savage)", "artists": "Drake, 21 Savage", "distance": 0.16062},
    ...
  ]
}
```

## Usage

### Check job status

```bash
curl http://localhost:8000/jobs/{id}
```

### List all jobs

```bash
curl http://localhost:8000/jobs
```

## Job Lifecycle

`queued` → `running` → `succeeded` / `failed`

Jobs are processed asynchronously. `POST /jobs` returns immediately with a job ID; poll `GET /jobs/{id}` to read the result once the worker completes it.

## Project Structure

```
├── api/              # FastAPI service
├── worker/           # Background job processor
├── db/init.sql       # Schema (jobs + spotify_tracks)
├── spotify-2023.csv  # Source dataset (953 tracks)
└── docker-compose.yml
```

## Out of Scope (v1)

- Retries / dead letter queue
- Job cancellation, priorities, timeouts
- Auth, rate limiting, pagination
- AWS/K8s deployment, CI/CD
- Metrics/tracing
