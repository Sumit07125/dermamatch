import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_recommend_nl(client):
    response = client.post('/api/recommend', json={
        "query": "lightweight sunscreen for oily acne-prone skin under $30",
        "top_k": 5
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] in ["ok", "no_high_confidence_match"]
    if data['status'] == "ok":
        assert len(data['recommendations']) > 0

def test_recommend_quiz(client):
    response = client.post('/api/recommend/quiz', json={
        "skin_type": "oily",
        "concerns": ["acne"],
        "category": "sunscreen",
        "budget_max": 30,
        "preferred_terms": ["lightweight"],
        "avoid_ingredients": ["fragrance"],
        "top_k": 5
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] in ["ok", "no_high_confidence_match"]

def test_impossible_budget(client):
    response = client.post('/api/recommend', json={
        "query": "sunscreen",
        "budget_max": 0.50
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == "no_high_confidence_match"
    assert data['recommendations'] == []

def test_avoid_ingredient(client):
    response = client.post('/api/recommend/quiz', json={
        "category": "moisturizer",
        "avoid_ingredients": ["fragrance"]
    })
    assert response.status_code == 200
    data = response.get_json()
    if data['status'] == "ok":
        # Make sure none of the recommendations contain fragrance
        for rec in data['recommendations']:
            assert "fragrance" not in rec.get('matched_ingredients', [])

def test_ingredient_regression_zinc_present(client):
    # Test for P483658 which is known to contain zinc
    response = client.post('/api/recommend', json={
        "query": "sunscreen containing zinc oxide"
    })
    assert response.status_code == 200
    data = response.get_json()
    if data['status'] == "ok":
        for rec in data['recommendations']:
            if rec['product_id'] == 'P483658':
                assert rec['ingredient_data_available'] is True
                assert 'zinc' in [str(i).lower() for i in rec['matched_ingredients']]

def test_ingredient_regression_missing(client):
    # Test for P454391 which is known to have missing ingredient data
    # We just run a general query and if it happens to be returned, verify it.
    response = client.post('/api/recommend', json={
        "query": "face wash"
    })
    assert response.status_code == 200
    data = response.get_json()
    if data['status'] == "ok":
        for rec in data['recommendations']:
            if rec['product_id'] == 'P454391':
                assert rec['ingredient_data_available'] is False
                assert rec['matched_ingredients'] == []
