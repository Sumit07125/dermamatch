import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_get_known_product(client):
    # We assume 'P439055' is in the dataset from previous inspection
    response = client.get('/api/products/P439055')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert data['product']['product_id'] == 'P439055'

def test_get_unknown_product(client):
    response = client.get('/api/products/P999999999')
    assert response.status_code == 404
    data = response.get_json()
    assert data['status'] == 'error'

def test_list_products(client):
    response = client.get('/api/products?limit=5')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert len(data['products']) <= 5
