def test_health_check_reports_ok_when_database_is_reachable(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
