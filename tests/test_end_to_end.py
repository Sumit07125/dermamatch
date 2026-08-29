import pytest
from streamlit_app import api_client
from app import create_app
import threading
from werkzeug.serving import make_server
import time

class ServerThread(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.server = make_server('127.0.0.1', 5001, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()

@pytest.fixture(scope="module")
def live_server():
    app = create_app()
    server = ServerThread(app)
    server.start()
    
    # Wait for server to be ready
    time.sleep(2)
    
    # Temporarily point API_URL to test server
    original_url = api_client.API_URL
    api_client.API_URL = "http://127.0.0.1:5001"
    
    yield
    
    api_client.API_URL = original_url
    server.shutdown()
    server.join()

def test_end_to_end_flow(live_server):
    health = api_client.health_check()
    assert health['status'] == 'ok'
    
    rec_result = api_client.recommend("lightweight sunscreen")
    assert rec_result['status'] in ['ok', 'no_high_confidence_match']
    
    products = api_client.list_products(limit=2)
    assert products['status'] == 'ok'
    assert len(products['products']) == 2
