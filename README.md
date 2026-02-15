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

## Usage

### Create a job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"sleep_seconds": 3, "message": "hello"}'
```

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

Jobs sleep for N seconds (default 3), then return `{"slept_seconds": N, "message": "..."}`.

## Project Structure

```
├── api/           # FastAPI service
├── worker/        # Background job processor
├── db/init.sql    # Schema
└── docker-compose.yml
```

## Out of Scope (v1)

- Retries / dead letter queue
- Job cancellation, priorities, timeouts
- Auth, rate limiting, pagination
- AWS/K8s deployment, CI/CD
- Metrics/tracing
