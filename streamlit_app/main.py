import streamlit as st
from api_client import recommend, recommend_quiz, health_check
from components import display_recommendation_card
from styles import apply_custom_styles

st.set_page_config(
    page_title="DermaMatch AI — Skincare Recommendations",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

apply_custom_styles("light")

st.markdown("""
<div style="text-align: center; margin-bottom: 2rem; padding: 1rem 0;">
    <h1 style="font-weight: 800; margin-bottom: 0; font-size: clamp(1.8rem, 5vw, 2.8rem);">DermaMatch AI ✨</h1>
    <h3 style="color: #7f8c8d; font-weight: 500; margin-top: 5px; font-size: clamp(1rem, 3vw, 1.3rem);">Ingredient-aware skincare recommendations</h3>
    <p style="color: #9aa5b1; font-size: clamp(12px, 2vw, 14px); max-width: 600px; margin: 0 auto;">
        Find products that match your skin type, concerns, preferences, budget, and ingredient requirements.
        Built from product ingredients, review signals, preferences, and semantic similarity.
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ── Responsive overrides ── */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        border-radius: 0 !important;
        margin-top: 0 !important;
    }
    .product-card { padding: 14px !important; }
    .product-title { font-size: 15px !important; }
    .product-price { font-size: 18px !important; }

    /* KEY FIX: ensure image is fully visible on mobile */
    .product-image-container {
        height: 160px !important;
        min-height: 160px !important;
        width: 100% !important;
        background-size: cover !important;
        background-position: center center !important;
        background-repeat: no-repeat !important;
        border-radius: 8px !important;
        display: block !important;
    }
}

@media (max-width: 480px) {
    .product-image-container {
        height: 140px !important;
        min-height: 140px !important;
        background-size: cover !important;
        background-position: center center !important;
    }
    h1 { font-size: 1.6rem !important; }
    .price-score-row { flex-wrap: wrap; gap: 6px; }
}

/* Remove Streamlit default sidebar hamburger clutter */
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
/* Full width tabs on mobile */
.stTabs [data-baseweb="tab-list"] { flex-wrap: wrap; gap: 4px; }
.stTabs [data-baseweb="tab"] { flex: 1; text-align: center; min-width: 120px; }

/* Ensure Streamlit columns stack properly on mobile */
@media (max-width: 640px) {
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }
}
</style>
""", unsafe_allow_html=True)

# Check API Health
health = health_check()
if health.get("status") == "error":
    st.markdown("""
    <div class="empty-state">
        <h3>API Unavailable</h3>
        <p>DermaMatch is temporarily unavailable. Please try again in a moment.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()
elif health.get("status") == "degraded":
    st.warning("⚠️ The Recommendation Engine is running in degraded mode.")

tab_quiz, tab_nl = st.tabs(["📋 Skincare Quiz", "💬 Natural Language"])

result = None
query_summary = []

with tab_nl:
    with st.container():
        st.html("""
        <div style="margin-bottom: 20px;">
            <h3 style="margin-bottom: 5px; color: var(--text-primary); font-weight: 600;">💬 Describe what you want</h3>
            <p style="color: var(--text-secondary); font-size: 14px; margin: 0;">Type in your own words, and our AI will understand exactly what you need.</p>
        </div>
        """)
        query = st.text_input(
            "Describe what you're looking for", 
            placeholder="e.g. lightweight sunscreen for oily acne-prone skin under ₹2500",
            key="nl_query",
            label_visibility="collapsed"
        )
        
        # Options row
        c1, c2 = st.columns([1, 4])
        with c1:
            top_k_nl = st.selectbox("Results", [3, 5], index=0, key="nl_top_k")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✨ Find My Best Matches", key="nl_submit", use_container_width=True):
            if not query.strip():
                st.warning("Please enter a query.")
            else:
                query_summary = [f"Query: {query}"]
                with st.spinner("Analyzing your preferences... Finding relevant products..."):
                    result = recommend(query, top_k=top_k_nl)

with tab_quiz:
    with st.container():
        st.html("""
        <div style="margin-bottom: 20px;">
            <h3 style="margin-bottom: 5px; color: var(--text-primary); font-weight: 600;">📋 Tell us what your skin needs</h3>
            <p style="color: var(--text-secondary); font-size: 14px; margin: 0;">Select your exact criteria to get a perfectly tailored skincare match.</p>
        </div>
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            skin_type = st.selectbox("Skin type", ["", "oily", "dry", "combination", "normal", "sensitive"])
            category = st.selectbox("Category", ["", "all", "cleanser", "moisturizer", "sunscreen", "serum", "mask", "treatment", "eye care"])
            budget_inr = st.number_input("Maximum Budget (₹)", min_value=0.0, step=500.0, value=2000.0)
            budget = budget_inr / 83.0 if budget_inr > 0 else 0.0
        
        with col2:
            concerns = st.multiselect("Concerns", ["acne", "hydration", "dark spots", "anti-aging", "oil control"])
            preferred_terms = st.multiselect("Preferred characteristics", ["lightweight", "fragrance-free", "non-greasy", "non-comedogenic"])
            avoid_ingredients = st.text_input("Avoid ingredients (comma separated)")
            
        c1, c2 = st.columns([1, 4])
        with c1:
            top_k_quiz = st.selectbox("Results", [3, 5], index=0, key="quiz_top_k")
            
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✨ Find My Best Matches", key="quiz_submit", use_container_width=True):
            quiz_data = {}
            if skin_type: 
                quiz_data["skin_type"] = skin_type
                query_summary.append(skin_type.title() + " Skin")
            if category and category != "all": 
                quiz_data["category"] = category
                query_summary.append(category.title())
            if budget > 0: 
                quiz_data["budget_max"] = budget
                query_summary.append(f"≤ ₹{budget_inr:,.0f}")
            if concerns: 
                quiz_data["concerns"] = concerns
                query_summary.extend([c.title() for c in concerns])
            if preferred_terms: 
                quiz_data["preferred_terms"] = preferred_terms
                query_summary.extend([p.title() for p in preferred_terms])
            if avoid_ingredients.strip():
                quiz_data["avoid_ingredients"] = [x.strip() for x in avoid_ingredients.split(",")]
            
            quiz_data["top_k"] = top_k_quiz
            
            if not quiz_data:
                st.warning("Please fill out at least some preferences.")
            else:
                with st.spinner("Analyzing your preferences... Finding relevant products..."):
                    result = recommend_quiz(quiz_data)

st.markdown("---")

if result is not None:
    if result.get("status") == "error":
        st.markdown("""
        <div class="empty-state">
            <h3>Something went wrong</h3>
            <p>We couldn't process your request. Please try again in a moment.</p>
        </div>
        """, unsafe_allow_html=True)
    elif result.get("status") == "no_high_confidence_match" or not result.get("recommendations"):
        st.markdown("""
        <div class="empty-state">
            <h3>No strong matches found</h3>
            <p>Your constraints were too restrictive.<br>Try increasing your budget or removing one constraint.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        recs = result.get("recommendations", [])
        latency = result.get("latency_ms", {})
        total_ms = latency.get("total", 0)
        retrieval_ms = latency.get("retrieval", 0)

        st.markdown("### Your recommendations")

        # ── AI Diagnostics Banner ──────────────────────────────────────────────
        top_rec = recs[0] if recs else {}
        top_scores = top_rec.get("score_breakdown", {})
        semantic_pct = int(float(top_scores.get("semantic_similarity", 0)) * 100)
        ingredient_pct = int(float(top_scores.get("ingredient_match", 0)) * 100)
        review_pct = int(float(top_scores.get("review_relevance", 0)) * 100)

        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(79,70,229,0.07), rgba(16,185,129,0.07));
            border: 1px solid rgba(79,70,229,0.18);
            border-radius: 12px;
            padding: 12px 18px;
            margin-bottom: 16px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
            font-size: 12.5px;
        ">
            <span style="font-weight: 700; color: #4f46e5; margin-right: 4px;">⚡ AI Engine</span>
            <span style="background:rgba(79,70,229,0.12);color:#4f46e5;padding:3px 10px;border-radius:20px;font-weight:600;">
                🕒 {total_ms:.0f} ms total
            </span>
            <span style="background:rgba(16,185,129,0.12);color:#059669;padding:3px 10px;border-radius:20px;font-weight:600;">
                🔍 {retrieval_ms:.0f} ms retrieval
            </span>
            <span style="background:rgba(245,158,11,0.12);color:#d97706;padding:3px 10px;border-radius:20px;font-weight:600;">
                🧠 {semantic_pct}% semantic
            </span>
            <span style="background:rgba(239,68,68,0.10);color:#dc2626;padding:3px 10px;border-radius:20px;font-weight:600;">
                🧪 {ingredient_pct}% ingredient
            </span>
            <span style="background:rgba(99,102,241,0.10);color:#6366f1;padding:3px 10px;border-radius:20px;font-weight:600;">
                💬 {review_pct}% reviews
            </span>
            <span style="margin-left:auto;color:#9ca3af;font-size:11px;">{len(recs)} results · ChromaDB + BGE</span>
        </div>
        """, unsafe_allow_html=True)
        # ─────────────────────────────────────────────────────────────────────

        st.markdown(f"**{len(recs)} matches found**")

        if query_summary:
            summary_html = " ".join([f'<span class="badge">{s}</span>' for s in query_summary])
            st.markdown(f"<div style='margin-bottom: 12px;'>{summary_html}</div>", unsafe_allow_html=True)
            
        c_sort, c_empty = st.columns([1, 4])
        with c_sort:
            sort_by = st.selectbox("Sort by", ["Best Match", "Price: Low to High", "Price: High to Low", "Ingredient Match"], label_visibility="collapsed")
            
        if sort_by == "Price: Low to High":
            recs = sorted(recs, key=lambda x: float(x.get('price_usd') if x.get('price_usd') and str(x.get('price_usd')).lower() != 'nan' else 9999))
        elif sort_by == "Price: High to Low":
            recs = sorted(recs, key=lambda x: float(x.get('price_usd') if x.get('price_usd') and str(x.get('price_usd')).lower() != 'nan' else 0), reverse=True)
        elif sort_by == "Ingredient Match":
            recs = sorted(recs, key=lambda x: float(x.get('ingredient_coverage') or 0), reverse=True)
            
        # Responsive card layout: 1 col on mobile (<= 1 result on tiny screen), else up to 3
        # Use a single-column layout which Streamlit renders better on mobile.
        # On desktop, st.columns(3) produces a 3-up grid correctly.
        num_cols = min(3, len(recs)) if recs else 1
        for i in range(0, len(recs), num_cols):
            # For a single result always use 1 col for clean centering
            actual_cols = min(num_cols, len(recs) - i)
            cols = st.columns(actual_cols)
            for j in range(actual_cols):
                if i + j < len(recs):
                    with cols[j]:
                        display_recommendation_card(recs[i+j], i+j+1)

st.markdown("""
<div style="text-align: center; margin-top: 60px; padding: 24px 0 16px; border-top: 1px solid rgba(128,128,128,0.2);">
    <p style="color:#4f46e5; font-weight:700; font-size:15px; margin-bottom:4px;">DermaMatch AI ✨</p>
    <p style="color:#9aa5b1; font-size:12px; margin-bottom:4px;">
        Powered by <strong>ChromaDB</strong> · <strong>SentenceTransformers (BGE)</strong> · <strong>Streamlit Cloud</strong>
    </p>
    <p style="color:#c4c9d1; font-size:11px;">
        Built by <strong>Sumit Mali</strong> · Recommendations are not medical advice
    </p>
</div>
""", unsafe_allow_html=True)
