from flask import Blueprint, request, jsonify, current_app
from .schemas import validate_recommend_request
from .errors import APIError
from .recommender import recommend
import logging

logger = logging.getLogger(__name__)
api = Blueprint("api", __name__)

@api.route("/health", methods=["GET"])
def health():
    from .engine_loader import engine_config
    return jsonify({
        "status": "ok" if engine_config else "degraded",
        "service": "dermamatch-api",
        "engine_ready": engine_config is not None
    })

@api.route("/api/recommend", methods=["POST"])
def recommend_endpoint():
    data = request.get_json(silent=True) or {}
    validated = validate_recommend_request(data)
    
    if "query" not in validated and not any(k in validated for k in ["skin_type", "concerns", "category", "preferred_terms", "avoid_ingredients"]):
        raise APIError("Must provide a query or structured parameters.", code="MISSING_PARAMETERS")

    logger.info(f"NL Recommend request: {validated}")
    
    try:
        result = recommend(**validated)
        return jsonify(result)
    except ValueError as e:
        raise APIError(str(e))
    except Exception as e:
        logger.error(f"Engine error: {e}", exc_info=True)
        raise APIError("Internal engine error", code="ENGINE_ERROR", status_code=500)

@api.route("/api/recommend/quiz", methods=["POST"])
def recommend_quiz_endpoint():
    data = request.get_json(silent=True) or {}
    validated = validate_recommend_request(data)
    
    logger.info(f"Quiz Recommend request: {validated}")
    
    try:
        result = recommend(**validated)
        return jsonify(result)
    except ValueError as e:
        raise APIError(str(e))
    except Exception as e:
        logger.error(f"Engine error: {e}", exc_info=True)
        raise APIError("Internal engine error", code="ENGINE_ERROR", status_code=500)

@api.route("/api/products/<product_id>", methods=["GET"])
def get_product(product_id):
    from .engine_loader import catalog_by_id
    if product_id not in catalog_by_id.index:
        return jsonify({"status": "error", "error": {"code": "NOT_FOUND", "message": "Product not found"}}), 404
        
    product = catalog_by_id.loc[product_id]
    
    # Safely convert to dict
    product_dict = {
        "product_id": str(product["product_id"]),
        "product_name": str(product.get("product_name", "")),
        "brand_name": str(product.get("brand_name", "")),
        "category": str(product.get("primary_category", "")),
        "price_usd": float(product.get("effective_price_usd", 0.0))
    }
    
    return jsonify({
        "status": "ok",
        "product": product_dict
    })

@api.route("/api/products", methods=["GET"])
def list_products():
    from .engine_loader import catalog_by_id
    
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    category = request.args.get("category")
    brand = request.args.get("brand")
    
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
        
    return jsonify({
        "status": "ok",
        "total": len(filtered),
        "limit": limit,
        "offset": offset,
        "products": products
    })
