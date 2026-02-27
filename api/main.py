import json
import os
from contextlib import asynccontextmanager
from typing import Annotated, Literal, Union
from uuid import UUID

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DATABASE_URL = os.environ["DATABASE_URL"]

pool: asyncpg.Pool


class SleepJobCreate(BaseModel):
    job_type: Literal["sleep"] = "sleep"
    sleep_seconds: int = 3
    message: str | None = None


class IngestDatasetJobCreate(BaseModel):
    job_type: Literal["ingest_dataset"]
    csv_path: str | None = None  # defaults to /app/spotify-2023.csv in worker


class FindComparablesJobCreate(BaseModel):
    job_type: Literal["find_comparables"]
    track_name: str


JobCreate = Annotated[
    Union[SleepJobCreate, IngestDatasetJobCreate, FindComparablesJobCreate],
    Field(discriminator="job_type"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)


@app.post("/jobs", status_code=201)
async def create_job(body: JobCreate):
    data = body.model_dump()
    job_type = data.pop("job_type")

    if job_type == "sleep":
        sleep_seconds = data.get("sleep_seconds", 3)
        message = data.get("message")
        payload = None
    else:
        sleep_seconds = 0
        message = None
        payload = json.dumps(data)

    row = await pool.fetchrow(
        "INSERT INTO jobs (job_type, sleep_seconds, message, payload) "
        "VALUES ($1, $2, $3, $4) RETURNING id, status, job_type",
        job_type, sleep_seconds, message, payload,
    )
    return {"id": str(row["id"]), "status": row["status"], "job_type": row["job_type"]}


@app.get("/jobs/{job_id}")
async def get_job(job_id: UUID):
    row = await pool.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _row_to_dict(row)


@app.get("/jobs")
async def list_jobs():
    rows = await pool.fetch("SELECT * FROM jobs ORDER BY created_at DESC")
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: asyncpg.Record) -> dict:
    d = dict(row)
    d["id"] = str(d["id"])
    d["created_at"] = d["created_at"].isoformat()
    d["updated_at"] = d["updated_at"].isoformat()
    if d["result"] is not None:
        d["result"] = json.loads(d["result"])
    if d.get("payload") is not None:
        d["payload"] = json.loads(d["payload"])
    return d
