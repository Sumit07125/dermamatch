from .errors import APIError
from .config import TOP_K, CANDIDATE_K

def validate_recommend_request(data):
    if not isinstance(data, dict):
        raise APIError("Request body must be a JSON object.")
        
    validated = {}
    
    query = data.get("query")
    if query is not None:
        if not isinstance(query, str):
            raise APIError("query must be a string.")
        validated["query"] = query.strip()
        
    skin_type = data.get("skin_type")
    if skin_type is not None:
        if not isinstance(skin_type, str):
            raise APIError("skin_type must be a string.")
        validated["skin_type"] = skin_type.strip()
        
    concerns = data.get("concerns")
    if concerns is not None:
        if not isinstance(concerns, list) or not all(isinstance(c, str) for c in concerns):
            raise APIError("concerns must be a list of strings.")
        validated["concerns"] = [c.strip() for c in concerns]
        
    category = data.get("category")
    if category is not None:
        if not isinstance(category, str):
            raise APIError("category must be a string.")
        validated["category"] = category.strip()
        
    budget_max = data.get("budget_max")
    if budget_max is not None:
        try:
            budget_max = float(budget_max)
        except (ValueError, TypeError):
            raise APIError("budget_max must be a number.")
        if budget_max < 0:
            raise APIError("budget_max cannot be negative.")
        validated["budget_max"] = budget_max
        
    preferred_terms = data.get("preferred_terms")
    if preferred_terms is not None:
        if not isinstance(preferred_terms, list) or not all(isinstance(p, str) for p in preferred_terms):
            raise APIError("preferred_terms must be a list of strings.")
        validated["preferred_terms"] = [p.strip() for p in preferred_terms]
        
    avoid_ingredients = data.get("avoid_ingredients")
    if avoid_ingredients is not None:
        if not isinstance(avoid_ingredients, list) or not all(isinstance(a, str) for a in avoid_ingredients):
            raise APIError("avoid_ingredients must be a list of strings.")
        validated["avoid_ingredients"] = [a.strip() for a in avoid_ingredients]
        
    top_k = data.get("top_k", TOP_K)
    try:
        top_k = int(top_k)
    except (ValueError, TypeError):
        raise APIError("top_k must be an integer.")
    if top_k <= 0 or top_k > 50:
        raise APIError("top_k must be between 1 and 50.")
    validated["top_k"] = top_k
        
    candidate_k = data.get("candidate_k", CANDIDATE_K)
    try:
        candidate_k = int(candidate_k)
    except (ValueError, TypeError):
        raise APIError("candidate_k must be an integer.")
    if candidate_k < top_k or candidate_k > 200:
        raise APIError("candidate_k must be between top_k and 200.")
    validated["candidate_k"] = candidate_k
    
    return validated
