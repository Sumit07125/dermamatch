import streamlit as st
import hashlib
import base64
from pathlib import Path
def safe_str(val):
    if val is None or str(val).lower() == "nan":
        return None
    return str(val)

def safe_float(val):
    if val is None or str(val).lower() == "nan":
        return 0.0
    return float(val)

def get_product_image_b64(product_id: str) -> str:
    """Deterministically pick from ALL available product images based on product_id."""
    if not product_id:
        product_id = "default"

    img_dir = Path("d:/CODE/ORBO.ai/assets/product_images")
    if not img_dir.exists():
        return ""

    # Gather all images sorted so order is stable across runs
    all_images = sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.png"))
    if not all_images:
        return ""

    # Deterministic choice: same product always gets same image
    hash_int = int(hashlib.md5(str(product_id).encode()).hexdigest(), 16)
    image_path = all_images[hash_int % len(all_images)]

    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
            return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        return ""
    
def clean_list(val):
    if not val:
        return []
    if isinstance(val, str):
        if val.startswith('[') and val.endswith(']'):
            try:
                import ast
                val = ast.literal_eval(val)
            except:
                pass
    if isinstance(val, list):
        return [str(v) for v in val if safe_str(v)]
    return []

def display_product_card(product):
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### {safe_str(product.get('product_name')) or 'Unknown Product'}")
            st.markdown(f"**Brand:** {safe_str(product.get('brand_name')) or 'Unknown Brand'}")
            st.markdown(f"**Category:** {safe_str(product.get('category')) or 'Skincare'}")
        with col2:
            price_usd = product.get('price_usd')
            if price_usd and str(price_usd).lower() != 'nan':
                price_inr = float(price_usd) * 83.0
                st.markdown(f"### ₹{price_inr:,.2f}")
            else:
                st.markdown("### Price N/A")
        st.markdown("---")

def display_recommendation_card(rec: dict, rank: int):
    """
    Renders a premium product card using st.html for 100% bug-free CSS layout.
    """
    product_name = rec.get("product_name", "Unknown Product")
    brand_name = rec.get("brand_name", "Unknown Brand")
    category = rec.get("primary_category", "Skincare")
    product_id = rec.get("product_id", "")
    
    price_usd_val = safe_float(rec.get("price_usd"))
    price_inr_val = price_usd_val * 83.0  # Approx conversion
    price_str = f"₹{price_inr_val:,.2f}" if price_inr_val > 0 else "Price varies"
    
    scores_dict = rec.get("score_breakdown", {})
    if scores_dict:
        # User requested aggregate percentage to increase the displayed score
        non_zero_scores = []
        for key in ['semantic_similarity', 'ingredient_match', 'review_relevance', 'preference_match', 'rating_quality', 'diversity']:
            val = safe_float(scores_dict.get(key, 0.0))
            if val > 0:
                non_zero_scores.append(val)
                
        if non_zero_scores:
            recalc = sum(non_zero_scores) / len(non_zero_scores)
        else:
            recalc = 0.0
            
        scores_dict["final_score"] = recalc
        score_val = recalc
    else:
        score_val = safe_float(rec.get("final_score"))
        
    score_pct = int(score_val * 100)
    
    best_match_class = "best-match" if rank == 1 else ""
    rank_label = "BEST MATCH" if rank == 1 else ("GREAT MATCH" if rank == 2 else "STRONG MATCH")
    
    img_b64 = get_product_image_b64(product_id)
    
    if img_b64:
        img_html = f"""<div class="product-image-container" style="background-image: url('{img_b64}'); background-size: cover; background-position: center; border-radius: 8px;"></div>"""
    else:
        img_html = f"""<div class="product-image-container">✦</div>"""
    
    html = f"""
    <div class="product-card {best_match_class}">
        <div class="card-header-row">
            <div class="product-rank {best_match_class}">#{rank} {rank_label}</div>
            <div class="product-favorite" title="Favorite">♡</div>
        </div>
        
        {img_html}
        
        <h3 class="product-title">{product_name}</h3>
        <div class="product-brand">{brand_name}</div>
        
        <div style="margin-bottom: 16px;">
            <span class="badge">🏷️ {category}</span>
    """
    
    if rec.get("ingredient_data_available"):
        cov = safe_float(rec.get("ingredient_coverage"))
        html += f"""<span class="badge">🧪 {int(cov * 100)}% Match</span>"""
    else:
        html += f"""<span class="badge muted">Ingredient data unavailable</span>"""
        
    html += f"""
        </div>
        
        <div class="price-score-row">
            <div class="product-price">{price_str}</div>
            <div class="product-score">{score_pct}% Match</div>
        </div>
    </div>
    """
    
    # Use st.html to prevent markdown parser bugs
    st.html(html)

    with st.expander("✨ Why this match?"):
        reasons = clean_list(rec.get("reasons", []))
        import re
        for reason in reasons:
            if "Within budget" in reason and "$" in reason:
                match = re.search(r'\$(\d+\.?\d*)\s*≤\s*\$(\d+\.?\d*)', reason)
                if match:
                    p1 = float(match.group(1)) * 83.0
                    p2 = float(match.group(2)) * 83.0
                    reason = f"Within budget (₹{p1:,.0f} ≤ ₹{p2:,.0f})"
            st.html(f'<div class="reason-item"><span class="reason-icon" style="color: #4CAF50;">✓</span><span>{reason}</span></div>')
            
        evidences = clean_list(rec.get("review_evidence", []))
        if evidences:
            st.markdown("#### 💬 Review Signals")
            for ev in evidences:
                st.html(f'<div class="reason-item"><span class="reason-icon">⭐</span><span>{ev}</span></div>')

    if rec.get("ingredient_data_available"):
        with st.expander("🧪 Ingredient Deep Dive"):
            coverage = safe_float(rec.get("ingredient_coverage"))
            st.markdown(f"**Ingredient Match Coverage:** {int(coverage * 100)}%")
            matches = clean_list(rec.get("matched_ingredients", []))
            if matches:
                st.markdown("**Targeted Ingredients:**")
                for m in matches:
                    st.html(f'<div class="reason-item"><span class="reason-icon">🟢</span><span>{str(m).title()}</span></div>')
            else:
                st.markdown("No specific high-priority ingredient matches.")

    with st.expander("📊 Recommendation breakdown"):
        scores = rec.get("score_breakdown", {})
        if scores:
            for key, val in scores.items():
                pct = int(safe_float(val) * 100)
                
                # Skip ingredient/preference metrics if they are 0 (i.e. user didn't ask for them)
                if pct == 0 and key in ["ingredient_coverage", "ingredient_match", "preference_match", "review_relevance"]:
                    continue
                    
                label = key.replace('_', ' ').title()
                st.html(f"""
                <div>
                    <div class="score-label-row">
                        <span>{label}</span>
                        <span>{pct}%</span>
                    </div>
                    <div class="score-bar-container">
                        <div class="score-bar-fill" style="width: {pct}%"></div>
                    </div>
                </div>
                """)
        else:
            st.markdown("*Score breakdown unavailable.*")
