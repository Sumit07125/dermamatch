import streamlit as st
import random
import base64
from pathlib import Path

def get_random_background_b64():
    """Pick a random background from assets/backgrounds on every reload."""
    bg_dir = Path("d:/CODE/ORBO.ai/assets/backgrounds")
    if not bg_dir.exists():
        return ""

    # Collect all image files (jpg + png)
    images = sorted(bg_dir.glob("*.jpg")) + sorted(bg_dir.glob("*.png"))
    if not images:
        return ""

    img_path = random.choice(images)   # fresh random pick every page load
    try:
        ext = img_path.suffix.lower().lstrip(".")
        mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
        with open(img_path, "rb") as f:
            return f"data:image/{mime};base64,{base64.b64encode(f.read()).decode()}"
    except Exception:
        return ""

def apply_custom_styles(theme="light"):
    bg_b64 = get_random_background_b64()

    # ── Inject background via JS into the parent page ──────────────────────────
    if bg_b64:
        import streamlit.components.v1 as components
        components.html(f"""
        <script>
        (function() {{
            var DATA_URL = '{bg_b64}';

            function injectStyle() {{
                try {{
                    var doc = window.parent.document;
                    // Remove any previous version we injected
                    var old = doc.getElementById('dermamatch-bg-style');
                    if (old) old.remove();

                    // Inject a <style> tag into parent <head>
                    var s = doc.createElement('style');
                    s.id = 'dermamatch-bg-style';
                    s.textContent = [
                        'body, .stApp, [data-testid="stAppViewContainer"] {{',
                        '    background-image: url("' + DATA_URL + '") !important;',
                        '    background-size: cover !important;',
                        '    background-position: center !important;',
                        '    background-attachment: fixed !important;',
                        '    background-repeat: no-repeat !important;',
                        '}}',
                        '[data-testid="stHeader"] {{',
                        '    background: rgba(255,255,255,0.7) !important;',
                        '    backdrop-filter: blur(8px) !important;',
                        '}}'
                    ].join('\\n');
                    doc.head.appendChild(s);
                }} catch(e) {{ /* cross-origin blocked */ }}
            }}

            injectStyle();
            setTimeout(injectStyle, 200);
            setTimeout(injectStyle, 800);
            setTimeout(injectStyle, 2000);
            // Keep fighting Streamlit re-renders
            setInterval(injectStyle, 3000);
        }})();
        </script>
        """, height=0, scrolling=False)

    # ── All other app CSS ───────────────────────────────────────────────────────
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --card-bg: #ffffff;
            --text-primary: #2d3748;
            --text-secondary: #718096;
            --border-color: rgba(128, 128, 128, 0.2);
            --badge-bg: rgba(128, 128, 128, 0.08);
            --accent-green: #4CAF50;
            --img-bg: linear-gradient(135deg, rgba(128,128,128,0.05) 0%, rgba(128,128,128,0.1) 100%);
        }

        html, body {
            font-family: 'Inter', sans-serif !important;
        }

        /* Frosted-glass main content area */
        .block-container {
            padding-top: 2rem !important;
            max-width: 1100px !important;
            background-color: rgba(255, 255, 255, 0.20) !important;
            border-radius: 20px !important;
            margin-top: 1rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            padding-bottom: 2rem !important;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06) !important;
            backdrop-filter: blur(18px) !important;
            -webkit-backdrop-filter: blur(18px) !important;
            border: 1px solid rgba(255, 255, 255, 0.35) !important;
        }

        /* Product Card */
        .product-card {
            background-color: rgba(255, 255, 255, 0.75);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.5);
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease-in-out;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 100%;
            color: var(--text-primary);
        }
        .product-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.1);
            border-color: var(--accent-green);
        }
        .product-card.best-match {
            border: 2px solid var(--accent-green);
            box-shadow: 0 8px 24px rgba(76, 175, 80, 0.18);
        }
        .product-card.best-match::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 4px;
            background: linear-gradient(90deg, #4CAF50, #81C784);
        }

        .product-image-container {
            width: 100%;
            height: 200px;
            background: var(--img-bg);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 16px;
            color: var(--text-secondary);
            font-size: 48px;
            flex-shrink: 0;
            overflow: hidden;
        }

        .card-header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }

        .product-rank {
            background-color: var(--badge-bg);
            color: var(--text-primary);
            padding: 4px 10px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 11px;
            letter-spacing: 0.5px;
            display: inline-block;
        }
        .product-rank.best-match {
            background-color: var(--accent-green);
            color: white;
        }

        .product-favorite {
            color: var(--text-secondary);
            font-size: 18px;
            cursor: pointer;
        }

        .product-title {
            font-size: 17px;
            font-weight: 700;
            margin: 0 0 4px 0;
            line-height: 1.3;
            color: var(--text-primary);
            word-break: normal;
            overflow-wrap: break-word;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .product-brand {
            color: var(--text-secondary);
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }

        .price-score-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: auto;
            padding-top: 12px;
            border-top: 1px solid var(--border-color);
        }

        .product-price {
            font-size: 21px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .product-score {
            font-size: 14px;
            font-weight: 700;
            color: var(--accent-green);
            background: rgba(76, 175, 80, 0.1);
            padding: 4px 12px;
            border-radius: 10px;
        }

        .badge {
            background-color: var(--badge-bg);
            color: var(--text-primary);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            display: inline-block;
            margin-right: 6px;
            margin-bottom: 12px;
        }
        .badge.muted {
            color: var(--text-secondary);
            font-style: italic;
            opacity: 0.8;
        }

        .stExpander {
            border-radius: 10px !important;
            border: 1px solid var(--border-color) !important;
            box-shadow: none !important;
            background-color: transparent !important;
        }
        .stExpander summary p {
            font-weight: 600 !important;
            color: var(--text-primary) !important;
        }

        .reason-item {
            display: flex;
            align-items: flex-start;
            margin-bottom: 6px;
            font-size: 14px;
            line-height: 1.5;
            color: var(--text-primary);
        }
        .reason-icon {
            margin-right: 8px;
            font-weight: bold;
        }

        .score-bar-container {
            width: 100%;
            background-color: var(--border-color);
            border-radius: 4px;
            height: 8px;
            margin-top: 4px;
            margin-bottom: 12px;
        }
        .score-bar-fill {
            height: 100%;
            border-radius: 4px;
            background: linear-gradient(90deg, #4CAF50, #81C784);
        }
        .score-label-row {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-primary);
        }

        .empty-state {
            text-align: center;
            padding: 40px;
            background: var(--badge-bg);
            border-radius: 16px;
            border: 1px dashed var(--border-color);
            margin: 20px 0;
            color: var(--text-primary);
        }
        .empty-state h3 { margin-top: 0; color: var(--text-primary); }
        .empty-state p  { color: var(--text-secondary); }
        </style>
    """, unsafe_allow_html=True)
