import os
import sys

# Ensure the root directory is in the path so we can import the backend app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.engine_loader import load_engine
# MUST load engine before importing recommender to initialize globals
load_engine()

from app.recommender import recommend as backend_recommend
from app.database import get_product_by_id, list_products as db_list_products

def health_check():
    return {"status": "healthy", "mode": "direct_import"}

def recommend(query, top_k=5, candidate_k=50):
    try:
        results = backend_recommend(query=query, top_k=top_k, candidate_k=candidate_k)
        return {"status": "success", "recommendations": results}
    except Exception as e:
        return {"status": "error", "error": {"message": str(e)}}

def recommend_quiz(quiz_data):
    try:
        results = backend_recommend(**quiz_data)
        return results # recommend already returns the dict with status, query, etc.
    except Exception as e:
        return {"status": "error", "error": {"message": str(e)}}

def get_product(product_id):
    try:
        product = get_product_by_id(product_id)
        if product:
            return {"status": "success", "product": product}
        return {"status": "error", "error": {"message": "Product not found"}}
    except Exception as e:
        return {"status": "error", "error": {"message": str(e)}}

def list_products(limit=20, offset=0, category=None, brand=None):
    try:
        products = db_list_products(limit=limit, offset=offset, category=category, brand=brand)
        return {"status": "success", "products": products}
    except Exception as e:
        return {"status": "error", "error": {"message": str(e)}}
