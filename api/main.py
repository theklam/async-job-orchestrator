import os
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DATABASE_URL = os.environ["DATABASE_URL"]

pool: asyncpg.Pool


class JobCreate(BaseModel):
    sleep_seconds: int = 3
    message: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)


@app.post("/jobs", status_code=201)
async def create_job(body: JobCreate):
    row = await pool.fetchrow(
        "INSERT INTO jobs (sleep_seconds, message) VALUES ($1, $2) RETURNING id, status",
        body.sleep_seconds,
        body.message,
    )
    return {"id": str(row["id"]), "status": row["status"]}


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
    import json

    d = dict(row)
    d["id"] = str(d["id"])
    d["created_at"] = d["created_at"].isoformat()
    d["updated_at"] = d["updated_at"].isoformat()
    if d["result"] is not None:
        d["result"] = json.loads(d["result"])
    return d
