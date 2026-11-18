from fastapi.testclient import TestClient

from pgrv.api import create_app

from .conftest import needs_pg


@needs_pg
def test_backup_verify_and_metrics_over_http(cfg):
    client = TestClient(create_app(cfg))
    assert client.get("/healthz").json() == {"status": "ok"}
    backup_id = client.post("/backups").json()["id"]
    body = client.post(f"/backups/{backup_id}/verify").json()
    assert body["ok"] is True and body["problems"] == []
    assert client.get("/backups").json()[0]["tables"] == 2
    assert "pgrv_last_verification_success 1.0" in client.get("/metrics").text
    assert client.post("/backups/999/verify").status_code == 404
