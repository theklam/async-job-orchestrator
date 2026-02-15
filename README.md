# async-job-orchestrator

A minimal async job processing system with FastAPI, a background worker, and Postgres.

**Goal:** Demonstrate a simple, working job queue without external dependencies like Redis or Celery.

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

- **API**: Accepts job requests, writes to Postgres, returns job status
- **Worker**: Polls Postgres for `queued` jobs, processes them, updates status
- **Postgres**: Single source of truth for job state

## Tech Stack

- Python 3.11+
- FastAPI (API service)
- psycopg (Postgres driver, sync for worker)
- PostgreSQL 15
- Docker Compose

## Project Structure

```
async-job-orchestrator/
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── worker/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── db/
│   └── init.sql
├── docker-compose.yml
└── README.md
```

## Job Schema

| Field        | Type      | Description                          |
|--------------|-----------|--------------------------------------|
| id           | UUID      | Primary key                          |
| status       | TEXT      | `queued`, `running`, `succeeded`, `failed` |
| sleep_seconds| INTEGER   | How long the job sleeps (default: 3) |
| message      | TEXT      | Optional message to echo back        |
| result       | JSONB     | Job output (set on completion)       |
| created_at   | TIMESTAMP | When job was created                 |
| updated_at   | TIMESTAMP | Last status change                   |

## Running Locally

### Prerequisites

- Docker and Docker Compose

### Start Everything

```bash
docker compose up --build
```

This starts:
- Postgres on port 5432
- API on port 8000
- Worker (polling every 2 seconds)

### Verify Services

```bash
# Health check
curl http://localhost:8000/health
```

## API Usage

### Create a Job

```bash
# Basic job (sleeps 3 seconds)
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{}'

# Custom sleep duration
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"sleep_seconds": 5}'

# With message
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"sleep_seconds": 2, "message": "hello world"}'
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "sleep_seconds": 3,
  "message": null,
  "result": null,
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Get Job Status

```bash
curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000
```

**Response (completed):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "succeeded",
  "sleep_seconds": 3,
  "message": "hello world",
  "result": {
    "slept_seconds": 3,
    "message": "hello world"
  },
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:03Z"
}
```

### List Jobs

```bash
curl http://localhost:8000/jobs
```

## Worker Behavior

The worker:
1. Polls Postgres every 2 seconds
2. Claims one `queued` job using `SELECT ... FOR UPDATE SKIP LOCKED`
3. Sets status to `running`
4. Sleeps for `sleep_seconds`
5. Sets status to `succeeded` with result JSON
6. On exception: sets status to `failed` with error in result

The `SKIP LOCKED` pattern allows running multiple worker instances safely.

## Development

### Rebuild after code changes

```bash
docker compose up --build
```

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f worker
```

### Connect to Postgres

```bash
docker compose exec db psql -U postgres -d jobs
```

### Stop everything

```bash
docker compose down

# Include volumes (resets database)
docker compose down -v
```

## Out of Scope for v1

These are intentionally deferred:

- **Retries / Dead Letter Queue**: Failed jobs stay failed
- **Job cancellation**: No way to cancel a running job
- **Job priorities**: FIFO only
- **Job timeouts**: Jobs can run forever
- **Authentication/Authorization**: API is open
- **Rate limiting**: No request limits
- **Pagination**: List endpoint returns all jobs
- **AWS/Kubernetes deployment**: Local Docker only
- **CI/CD pipeline**: Manual builds
- **Observability**: No metrics/tracing (just logs)
- **Multiple job types**: Single job type (sleep)

## Future Enhancements

When extending beyond v1:

1. **Retries**: Add `attempts` column, retry on failure up to N times
2. **DLQ**: Move permanently failed jobs to separate table
3. **Job types**: Add `job_type` column, dispatch to different handlers
4. **Redis**: For faster polling and pub/sub notifications
5. **Timeouts**: Kill jobs exceeding max duration
6. **Auth**: API keys or JWT for job submission
