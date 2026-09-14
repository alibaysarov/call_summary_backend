"""Lightweight infrastructure API. Audio ingestion arrives in spec 03."""

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from call_summary.db.session import get_engine
from call_summary.storage import S3Storage

app = FastAPI(title="call_summary")


@app.get("/health")
def health():
    return {"status": "ok"}


def database_ready():
    with get_engine().connect() as conn:
        conn.execute(text("SELECT int_id FROM call_summary.workspaces LIMIT 1"))


@app.get("/ready/read")
def ready_read():
    try:
        database_ready()
    except SQLAlchemyError, ValidationError:
        return JSONResponse(
            {"status": "unavailable", "dependency": "database"}, status_code=503
        )
    return {"status": "ok"}


@app.get("/ready/upload")
def ready_upload():
    result = ready_read()
    if isinstance(result, JSONResponse):
        return result
    try:
        S3Storage().ready()
    except BotoCoreError, ClientError, ValidationError:
        return JSONResponse(
            {"status": "unavailable", "dependency": "storage"}, status_code=503
        )
    return {"status": "ok"}
