import os
os.environ["SIGNED_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123/signed"
os.environ["FREE_QUEUE_URL"]   = "https://sqs.us-east-1.amazonaws.com/123/free"
os.environ["S3_BUCKET"]        = "test-bucket"
os.environ["API_KEY"]          = "test-api-key"
os.environ["DB_HOST"]          = "localhost"
os.environ["DB_USER"]          = "test"
os.environ["DB_PASSWORD"]      = "test"

import pytest
import io
from unittest.mock import patch, MagicMock

with patch("boto3.client"):
    from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_returns_200(client):
    res = client.get("/")
    assert res.status_code == 200


def test_health(client):
    res = client.get("/health")
    assert res.json == {"status": "ok"}


def test_convert_no_file_returns_400(client):
    res = client.post("/convert")
    assert res.status_code == 400
    assert "no file" in res.json["error"]


def test_convert_wrong_file_type_returns_400(client):
    data = {"file": (io.BytesIO(b"fake content"), "document.pdf")}
    res = client.post("/convert", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "docx" in res.json["error"]


def test_convert_without_api_key_goes_to_free_queue(client):
    with patch("app.s3"), patch("app.sqs") as mock_sqs:
        data = {"file": (io.BytesIO(b"fake docx"), "doc.docx")}
        res = client.post("/convert", data=data, content_type="multipart/form-data")
        assert res.status_code == 200
        assert res.json["queue"] == "free"
        call_args = mock_sqs.send_message.call_args
        assert "free" in call_args.kwargs["QueueUrl"]


def test_convert_with_valid_api_key_goes_to_signed_queue(client):
    with patch("app.s3"), patch("app.sqs") as mock_sqs:
        data = {"file": (io.BytesIO(b"fake docx"), "doc.docx")}
        headers = {"X-API-Key": "test-api-key"}
        res = client.post("/convert", data=data,
                          content_type="multipart/form-data", headers=headers)
        assert res.status_code == 200
        assert res.json["queue"] == "signed"
        call_args = mock_sqs.send_message.call_args
        assert "signed" in call_args.kwargs["QueueUrl"]


def test_convert_with_wrong_api_key_goes_to_free_queue(client):
    with patch("app.s3"), patch("app.sqs") as mock_sqs:
        data = {"file": (io.BytesIO(b"fake docx"), "doc.docx")}
        headers = {"X-API-Key": "wrong-key"}
        res = client.post("/convert", data=data,
                          content_type="multipart/form-data", headers=headers)
        assert res.json["queue"] == "free"


def test_job_not_found_returns_pending(client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value = mock_cursor
    with patch("app.get_db", return_value=mock_conn):
        res = client.get("/jobs/fake-job-id")
        assert res.json["status"] == "pending"


def test_job_done_returns_download_url(client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("done", "outputs/fake-job-id.pdf")
    mock_conn.cursor.return_value = mock_cursor
    with patch("app.get_db", return_value=mock_conn), patch("app.s3") as mock_s3:
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/file.pdf"
        res = client.get("/jobs/fake-job-id")
        assert res.json["status"] == "done"
        assert "download_url" in res.json


def test_job_failed_returns_failed(client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("failed", None)
    mock_conn.cursor.return_value = mock_cursor
    with patch("app.get_db", return_value=mock_conn):
        res = client.get("/jobs/fake-job-id")
        assert res.json["status"] == "failed"
