import os
import sys

# Ensure the root directory is in the path so we can import the backend app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.engine_loader import load_engine
# MUST load engine before importing recommender to initialize globals
load_engine()

from app.recommender import recommend as backend_recommend

def health_check():
    return {"status": "healthy", "mode": "direct_import"}

def recommend(query, top_k=5, candidate_k=50):
    try:
        # Pass through backend result directly — it already has {status, recommendations, latency_ms}
        return backend_recommend(query=query, top_k=top_k, candidate_k=candidate_k)
    except Exception as e:
        return {"status": "error", "error": {"message": str(e)}}

def recommend_quiz(quiz_data):
    try:
        results = backend_recommend(**quiz_data)
        return results # recommend already returns the dict with status, query, etc.
    except Exception as e:
        return {"status": "error", "error": {"message": str(e)}}

from app.engine_loader import catalog_by_id

def get_product(product_id):
    try:
        if product_id not in catalog_by_id.index:
            return {"status": "error", "error": {"message": "Product not found"}}
            
        product = catalog_by_id.loc[product_id]
        
        product_dict = {
            "product_id": str(product["product_id"]),
            "product_name": str(product.get("product_name", "")),
            "brand_name": str(product.get("brand_name", "")),
            "category": str(product.get("primary_category", "")),
            "price_usd": float(product.get("effective_price_usd", 0.0))
        }
        return {"status": "success", "product": product_dict}
    except Exception as e:
        return {"status": "error", "error": {"message": str(e)}}

def list_products(limit=20, offset=0, category=None, brand=None):
    try:
        filtered = catalog_by_id
        
        if category:
            filtered = filtered[filtered["primary_category"].str.lower() == category.lower()]
        if brand:
            filtered = filtered[filtered["brand_name"].str.lower() == brand.lower()]
            
        page = filtered.iloc[offset:offset+limit]
        
        products = []
        for _, row in page.iterrows():
            products.append({
                "product_id": str(row["product_id"]),
                "product_name": str(row.get("product_name", "")),
                "brand_name": str(row.get("brand_name", "")),
                "category": str(row.get("primary_category", "")),
                "price_usd": float(row.get("effective_price_usd", 0.0))
            })
            
        return {"status": "success", "products": products}
    except Exception as e:
        return {"status": "error", "error": {"message": str(e)}}
