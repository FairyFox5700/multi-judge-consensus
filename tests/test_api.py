from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_index_serves_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "Multi-Judge Consensus" in res.text


def test_judges_endpoint_reports_demo_mode_without_keys():
    res = client.get("/api/judges")
    assert res.status_code == 200
    body = res.json()
    assert set(body["modes"].values()) == {"demo"}


def test_evaluate_endpoint_end_to_end():
    payload = {
        "customer_request": "Return damaged chocolate box and get refund",
        "transcript": "Agent authorized a return and refunded $45.99 as requested.",
        "system_state": "Return authorized, refund $45.99 initiated",
    }
    res = client.post("/api/evaluate", json=payload)
    assert res.status_code == 200

    body = res.json()
    assert "consensus_score" in body
    assert len(body["individual_results"]) == 3
    assert "needs_human_review" in body


def test_evaluate_endpoint_validates_input():
    res = client.post("/api/evaluate", json={"customer_request": ""})
    assert res.status_code == 422
