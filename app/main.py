"""FastAPI web app: upload documents and ask questions about them."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import azure_services
from .text_utils import extract_text, safe_filename

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
STATIC_DIR = Path(__file__).parent / "static"
log = logging.getLogger("ask-my-docs")

# Send logs, requests and errors to Application Insights when it is configured.
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get("SKIP_INDEX_SETUP") != "1":
        azure_services.ensure_index()
    yield


app = FastAPI(title="Ask My Documents", lifespan=lifespan)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload(file: Annotated[UploadFile, File()]):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")
    name = safe_filename(file.filename or "file")
    try:
        text = extract_text(name, data)
    except ValueError as err:
        raise HTTPException(400, str(err)) from err
    if not text.strip():
        raise HTTPException(400, "No text found. Scanned PDFs (images) are not supported.")

    azure_services.save_file(name, data)
    chunks = azure_services.index_document(name, text)
    log.info("Indexed %s (%d chunks)", name, chunks)
    return {"file": name, "chunks": chunks}


@app.post("/ask")
def ask(body: Question):
    try:
        return azure_services.answer_question(body.question)
    except Exception as err:  # show a clean message, keep details in the logs
        log.exception("Question failed")
        raise HTTPException(502, "The AI service failed. Try again.") from err
