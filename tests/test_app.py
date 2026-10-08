"""Unit tests. They do not call Azure (Azure calls are replaced with fakes)."""
import os

os.environ["SKIP_INDEX_SETUP"] = "1"

import pytest
from fastapi.testclient import TestClient

from app import azure_services, main
from app.text_utils import chunk_text, extract_text, safe_filename, safe_key


def test_chunk_text_splits_with_overlap():
    text = "word " * 1000
    chunks = chunk_text(text, size=200, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_chunk_text_empty():
    assert chunk_text("   ") == []


def test_chunk_text_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("abc", size=10, overlap=10)


def test_safe_key_is_valid_for_search():
    key = safe_key("my file.pdf", "3")
    assert key.isalnum()


def test_safe_filename_removes_paths():
    assert safe_filename("../../etc/pass wd.txt") == "pass_wd.txt"


def test_extract_text_rejects_unknown_type():
    with pytest.raises(ValueError):
        extract_text("image.png", b"123")


client = TestClient(main.app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_home_page():
    res = client.get("/")
    assert res.status_code == 200
    assert "Ask My Documents" in res.text


def test_upload_and_ask(monkeypatch):
    saved = {}
    monkeypatch.setattr(azure_services, "save_file", lambda name, data: saved.update(name=name))
    monkeypatch.setattr(azure_services, "index_document", lambda name, text: 2)
    monkeypatch.setattr(
        azure_services,
        "answer_question",
        lambda q: {
            "answer": "Fake answer [1]",
            "sources": [{"source": "a.txt", "chunk_no": 0, "content": "x"}],
        },
    )

    res = client.post("/upload", files={"file": ("a.txt", b"Hello Azure", "text/plain")})
    assert res.status_code == 200
    assert res.json() == {"file": "a.txt", "chunks": 2}
    assert saved["name"] == "a.txt"

    res = client.post("/ask", json={"question": "What is this?"})
    assert res.status_code == 200
    assert res.json()["answer"] == "Fake answer [1]"


def test_upload_rejects_bad_type():
    res = client.post("/upload", files={"file": ("a.exe", b"MZ", "application/octet-stream")})
    assert res.status_code == 400


def test_ask_validates_input():
    assert client.post("/ask", json={"question": "x"}).status_code == 422
