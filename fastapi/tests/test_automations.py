URL = "/api/automations/process"


def test_echo_action(client):
    response = client.post(URL, json={"action": "echo", "payload": {"key": "value"}})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["result"] == {"echo": {"key": "value"}}


def test_unknown_action_returns_400(client):
    response = client.post(URL, json={"action": "no_existe", "payload": {}})
    assert response.status_code == 400


def test_missing_action_returns_422(client):
    response = client.post(URL, json={"payload": {}})
    assert response.status_code == 422


def test_invalid_body_returns_422(client):
    response = client.post(URL, content=b"not json", headers={"content-type": "application/json"})
    assert response.status_code == 422
