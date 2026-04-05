"""上传接口 tenant_id 显式领域校验"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def explicit_tenant_on():
    import app.api.file as file_api

    with patch.object(file_api.config, "rag_require_explicit_tenant_for_upload", True):
        yield


def test_upload_rejects_default_tenant_when_explicit_required(explicit_tenant_on):
    files = {"file": ("t.md", b"# hello\n", "text/markdown")}
    r = client.post("/api/upload", files=files, data={"tenant_id": "default"})
    assert r.status_code == 400


def test_upload_rejects_empty_tenant_when_explicit_required(explicit_tenant_on):
    files = {"file": ("t.md", b"# hello\n", "text/markdown")}
    r = client.post("/api/upload", files=files, data={"tenant_id": "  "})
    assert r.status_code == 400


def test_upload_ok_with_explicit_tenant_when_required(explicit_tenant_on):
    import app.api.file as file_api

    files = {"file": ("t.md", b"# hello\n", "text/markdown")}
    with patch.object(file_api.vector_index_service, "index_single_file", return_value=2):
        r = client.post("/api/upload", files=files, data={"tenant_id": "cybersec"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("code") == 200
