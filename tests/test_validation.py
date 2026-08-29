import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_invalid_top_k(client):
    response = client.post('/api/recommend', json={
        "query": "test",
        "top_k": -5
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'top_k' in data['error']['message']

def test_invalid_budget(client):
    response = client.post('/api/recommend', json={
        "query": "test",
        "budget_max": "not_a_number"
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'budget' in data['error']['message']

def test_missing_params(client):
    response = client.post('/api/recommend', json={})
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert data['error']['code'] == 'MISSING_PARAMETERS'
