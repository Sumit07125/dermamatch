from __future__ import annotations

from .engine_loader import (
    catalog_by_id,
    catalog,
    embedder,
    collection,
    ingredient_profiles,
    engine_config,
    product_embeddings,
    embedding_position
)

CONCERN_TERMS = {
    "acne": ["acne", "blemish", "breakout", "pimple", "clear"],
    "hydration": ["hydrat", "dry", "moistur", "nourish"],
    "dark spots": ["dark spot", "hyperpigmentation", "brighten", "even tone", "vitamin c"],
    "anti-aging": ["aging", "wrinkle", "fine line", "firm", "retinol", "peptide"],
    "oil control": ["oil", "shine", "matte", "pore", "sebum"]
}
PREFERENCE_TERMS = {
    "lightweight": ["lightweight", "weightless", "gel"],
    "fragrance-free": ["fragrance-free", "unscented", "no fragrance"],
    "non-greasy": ["non-greasy", "absorbs quickly", "matte"],
    "non-comedogenic": ["non-comedogenic", "won't clog pores"]
}
SKIN_TYPE_ALIASES = {
    "oily": ["oily"], "dry": ["dry"], "combination": ["combination"],
    "normal": ["normal"], "sensitive": ["sensitive"]
}
CATEGORY_ALIASES = {
    "cleanser": ["cleanser", "wash", "soap"], "moisturizer": ["moisturizer", "cream", "lotion"],
    "sunscreen": ["sunscreen", "spf", "sunblock"], "serum": ["serum", "essence", "ampoule"],
    "mask": ["mask", "masque"], "treatment": ["treatment", "peel", "exfoliant"],
    "eye care": ["eye cream", "eye serum", "eye"]
}
ALIAS_TO_CANONICAL = {}
for canonical, aliases in engine_config.get("ingredient_aliases", {}).items():
    for alias in aliases:
        ALIAS_TO_CANONICAL[alias] = canonical
import ast
import json
import math
import os
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path

def columns_containing(*terms: str) -> List[str]:
    return [c for c in catalog.columns if any((term.lower() in c.lower() for term in terms))]

REVIEW_THEME_MAP = {
    "acne": columns_containing("acne", "breakout", "pimple", "clear"),
    "hydration": columns_containing("hydrat", "dry", "moistur"),
    "dark spots": columns_containing("dark spot", "hyperpigmentation", "brighten"),
    "anti-aging": columns_containing("aging", "wrinkle", "fine line", "firm", "retinol", "peptide"),
    "oil control": columns_containing("oil", "shine", "matte", "pore")
}
RATING_PRIOR_COUNT = 50.0
RATING_GLOBAL_MEAN = catalog['rating'].mean() if not catalog.empty and 'rating' in catalog.columns else 4.0
CONCERN_INGREDIENT_WEIGHTS = engine_config.get("concern_ingredient_weights", {})
RANKING_WEIGHTS = engine_config.get("ranking_weights", {})
INGREDIENT_ALIASES = engine_config.get("ingredient_aliases", {})

def safe_text(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    text = str(value).strip()
    return '' if text.lower() in {'nan', 'none', 'null'} else text

def normalize_token(value: Any) -> str:
    text = safe_text(value).lower()
    text = re.sub('[^a-z0-9\\s%_-]', ' ', text)
    text = re.sub('\\s+', ' ', text).strip()
    return text

def build_product_document(row: pd.Series) -> str:
    parts = []
    field_labels = [('product_name', 'Product'), ('brand_name', 'Brand'), ('primary_category', 'Primary category'), ('secondary_category', 'Secondary category'), ('tertiary_category', 'Product type'), ('highlights', 'Highlights'), ('ingredients_clean', 'Ingredients'), ('ingredients', 'Ingredients'), ('skin_type_profile', 'Skin-type profile')]
    seen_labels = set()
    for field, label in field_labels:
        if field not in row.index:
            continue
        value = safe_text(row[field])
        if not value:
            continue
        if label == 'Ingredients':
            if 'Ingredients' in seen_labels:
                continue
        parts.append(f'{label}: {value}')
        seen_labels.add(label)
    theme_names = []
    for col in theme_columns:
        value = pd.to_numeric(row.get(col), errors='coerce')
        if pd.notna(value) and float(value) > 0:
            name = re.sub('^theme_', '', col.lower())
            name = re.sub('_share$|_count$', '', name)
            theme_names.append(name.replace('_', ' '))
    if theme_names:
        parts.append('Review themes: ' + ', '.join(sorted(set(theme_names))))
    return ' | '.join(parts)

def numeric_value(row: pd.Series, candidates: Sequence[str], default: float=0.0) -> float:
    for col in candidates:
        if col not in row.index:
            continue
        value = pd.to_numeric(row[col], errors='coerce')
        if pd.notna(value):
            return float(value)
    return float(default)

def make_metadata(row: pd.Series) -> Dict[str, Any]:
    metadata = {'product_id': str(row['product_id']), 'product_name': safe_text(row.get('product_name')), 'brand_name': safe_text(row.get('brand_name')), 'primary_category': safe_text(row.get('primary_category')), 'secondary_category': safe_text(row.get('secondary_category')), 'tertiary_category': safe_text(row.get('tertiary_category')), 'effective_price_usd': numeric_value(row, ['effective_price_usd', 'sale_price_usd', 'price_usd'], default=0.0), 'rating': numeric_value(row, ['rating'], default=0.0), 'review_count': numeric_value(row, ['review_count_observed', 'reviews'], default=0.0), 'recommendation_rate': numeric_value(row, ['recommendation_rate'], default=0.0)}
    return metadata

def detect_first_match(text: str, alias_map: Dict[str, Sequence[str]]) -> Optional[str]:
    normalized = normalize_token(text)
    for canonical, aliases in alias_map.items():
        for alias in aliases:
            if re.search(f'(?<![a-z0-9]){re.escape(normalize_token(alias))}(?![a-z0-9])', normalized):
                return canonical
    return None

def detect_all_matches(text: str, alias_map: Dict[str, Sequence[str]]) -> List[str]:
    normalized = normalize_token(text)
    found = []
    for canonical, aliases in alias_map.items():
        if any((re.search(f'(?<![a-z0-9]){re.escape(normalize_token(alias))}(?![a-z0-9])', normalized) for alias in aliases)):
            found.append(canonical)
    return found

def detect_requested_ingredients(text: str) -> List[str]:
    normalized = normalize_token(text)
    if not normalized:
        return []
    found = []
    for alias, canonical in sorted(ALIAS_TO_CANONICAL.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(f'(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])', normalized):
            found.append(canonical)
    return list(dict.fromkeys(found))

def extract_budget(text: str) -> Optional[float]:
    normalized = normalize_token(text)
    patterns = ['(?:under|below|less than|up to|upto)\\s*\\$?\\s*(\\d+(?:\\.\\d+)?)', '\\$\\s*(\\d+(?:\\.\\d+)?)', '(?:budget|price)\\s*(?:of)?\\s*\\$?\\s*(\\d+(?:\\.\\d+)?)']
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return float(match.group(1))
    return None

def normalize_query(query: Optional[str]=None, skin_type: Optional[str]=None, concerns: Optional[Sequence[str]]=None, category: Optional[str]=None, budget_max: Optional[float]=None, preferred_terms: Optional[Sequence[str]]=None, avoid_ingredients: Optional[Sequence[str]]=None) -> Dict[str, Any]:
    query_text = safe_text(query)
    detected_concerns = detect_all_matches(query_text, CONCERN_TERMS) if query_text else []
    detected_preferences = detect_all_matches(query_text, PREFERENCE_TERMS) if query_text else []
    detected_skin_type = detect_first_match(query_text, SKIN_TYPE_ALIASES) if query_text else None
    detected_category = detect_first_match(query_text, CATEGORY_ALIASES) if query_text else None
    detected_ingredients = detect_requested_ingredients(query_text) if query_text else []
    detected_budget = extract_budget(query_text) if query_text else None
    return {'query_text': query_text, 'skin_type': normalize_token(skin_type) if skin_type else None, 'concerns': [normalize_token(x) for x in concerns or [] if safe_text(x)], 'category': normalize_token(category) if category else None, 'budget_max': float(budget_max) if budget_max is not None else None, 'preferred_terms': [normalize_token(x) for x in preferred_terms or [] if safe_text(x)], 'avoid_ingredients': [normalize_token(x) for x in avoid_ingredients or [] if safe_text(x)], 'detected_skin_type': detected_skin_type, 'detected_concerns': detected_concerns, 'detected_preferences': detected_preferences, 'detected_category': detected_category, 'detected_ingredients': detected_ingredients, 'detected_budget_max': detected_budget, 'effective_skin_type': normalize_token(skin_type) if skin_type else detected_skin_type, 'effective_concerns': list(dict.fromkeys([*[normalize_token(x) for x in concerns or [] if safe_text(x)], *detected_concerns])), 'effective_category': normalize_token(category) if category else detected_category, 'effective_preferences': list(dict.fromkeys([*[normalize_token(x) for x in preferred_terms or [] if safe_text(x)], *detected_preferences])), 'effective_ingredients': detected_ingredients, 'effective_budget_max': float(budget_max) if budget_max is not None else detected_budget}

def build_query_text(q: Dict[str, Any]) -> str:
    parts = []
    if q.get('query_text'):
        parts.append(q['query_text'])
    if q.get('effective_skin_type'):
        parts.append(f"skin type: {q['effective_skin_type']}")
    if q.get('effective_concerns'):
        parts.append('concerns: ' + ', '.join(q['effective_concerns']))
    if q.get('effective_category'):
        parts.append(f"category: {q['effective_category']}")
    if q.get('effective_preferences'):
        parts.append('preferences: ' + ', '.join(q['effective_preferences']))
    if q.get('effective_ingredients'):
        parts.append('ingredients: ' + ', '.join(q['effective_ingredients']))
    return ' | '.join((part for part in parts if part))

def semantic_retrieve(q: Dict[str, Any], candidate_k: int=50) -> pd.DataFrame:
    query_text = build_query_text(q)
    if not query_text:
        raise ValueError('A query or structured recommendation signal is required.')
    query_vector = embedder.encode([query_text], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)[0]
    result = collection.query(query_embeddings=[query_vector.tolist()], n_results=min(int(candidate_k), len(catalog)), include=['documents', 'metadatas', 'distances'])
    ids = result.get('ids', [[]])[0]
    distances = result.get('distances', [[]])[0]
    metadatas = result.get('metadatas', [[]])[0]
    rows = []
    for chroma_id, distance, metadata in zip(ids, distances, metadatas):
        row = dict(metadata)
        row['chroma_id'] = chroma_id
        row['cosine_distance'] = float(distance)
        row['semantic_similarity'] = float(np.clip(1.0 - float(distance), 0.0, 1.0))
        rows.append(row)
    retrieved = pd.DataFrame(rows)
    if retrieved.empty:
        raise RuntimeError('ChromaDB returned zero candidates.')
    return retrieved

def parse_avoid_terms(q: Dict[str, Any]) -> List[str]:
    return [normalize_token(x) for x in q.get('avoid_ingredients', []) if safe_text(x)]

def apply_hard_filters(retrieved: pd.DataFrame, q: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, int]]:
    if retrieved.empty:
        return (retrieved.copy(), {'input': 0, 'after_filter': 0})
    out = retrieved.copy()
    stats = {'input': len(out)}
    budget = q.get('effective_budget_max')
    if budget is not None and 'effective_price_usd' in out.columns:
        price = pd.to_numeric(out['effective_price_usd'], errors='coerce')
        out = out[price.notna() & (price <= float(budget))].copy()
    stats['after_budget'] = len(out)
    category = normalize_token(q.get('effective_category'))
    if category:
        cols = [c for c in ['primary_category', 'secondary_category', 'tertiary_category'] if c in out.columns]
        if cols:
            category_mask = pd.Series(False, index=out.index)
            pattern = re.escape(category)
            for col in cols:
                category_mask |= out[col].fillna('').map(normalize_token).str.contains(pattern, regex=True)
            out = out[category_mask].copy()
    stats['after_category'] = len(out)
    avoid_terms = parse_avoid_terms(q)
    rejected = 0
    if avoid_terms:
        keep = []
        for pid in out['product_id'].astype(str):
            profile = ingredient_profiles.get(pid, get_product_ingredient_profile(pid))
            searchable = set(profile['canonical_ingredients'])
            searchable.update(profile['raw_tokens'])
            searchable_text = normalize_token(profile['raw_text'] + ' ' + ' '.join(searchable))
            violation = False
            for term in avoid_terms:
                canonical = canonicalize_ingredient(term)
                if canonical and canonical in searchable:
                    violation = True
                    break
                aliases = INGREDIENT_ALIASES.get(canonical, [term])
                if any((normalize_token(alias) in searchable_text for alias in aliases if normalize_token(alias))):
                    violation = True
                    break
            keep.append(not violation)
            rejected += int(violation)
        out = out[np.asarray(keep, dtype=bool)].copy()
    stats['rejected_by_avoided_ingredient'] = rejected
    stats['after_avoid_ingredients'] = len(out)
    stats['after_filter'] = len(out)
    return (out.reset_index(drop=True), stats)

def parse_ingredient_tokens(value: Any) -> List[str]:
    text = safe_text(value)
    if not text:
        return []
    if text.startswith('[') and text.endswith(']'):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [normalize_token(x) for x in parsed if safe_text(x)]
        except Exception:
            pass
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (list, tuple, set)):
                return [normalize_token(x) for x in parsed if safe_text(x)]
        except Exception:
            pass
    return [normalize_token(x) for x in re.split('[,;|\\n]+', text) if normalize_token(x)]

def canonicalize_ingredient(value: Any) -> Optional[str]:
    phrase = normalize_token(value)
    if not phrase:
        return None
    if phrase in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[phrase]
    cleaned = re.sub('\\b\\d+(?:\\.\\d+)?%?\\b', ' ', phrase)
    cleaned = re.sub('\\s+', ' ', cleaned).strip()
    if cleaned in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[cleaned]
    for alias, canonical in sorted(ALIAS_TO_CANONICAL.items(), key=lambda x: len(x[0]), reverse=True):
        if phrase.startswith(alias + ' '):
            return canonical
    return None

def get_product_ingredient_profile(product_id: str) -> Dict[str, Any]:
    pid = str(product_id)
    if pid not in catalog_by_id.index:
        return {'available': False, 'ingredient_data_available': False, 'raw_text': '', 'normalized_text': '', 'raw_tokens': [], 'canonical_ingredients': [], 'ingredient_count': 0}
    row = catalog_by_id.loc[pid]
    clean_text = safe_text(row.get('ingredients_clean', ''))
    raw_text = safe_text(row.get('ingredients', ''))
    ingredient_text = clean_text if clean_text else raw_text
    serialized_tokens = parse_ingredient_tokens(row.get('ingredient_tokens', ''))
    parsed_tokens = [normalize_token(part) for part in re.split(',|;|\\||\\n', ingredient_text) if normalize_token(part)]
    raw_tokens = list(dict.fromkeys(serialized_tokens + parsed_tokens))
    canonical = set()
    for token in raw_tokens:
        canonical_name = canonicalize_ingredient(token)
        if canonical_name:
            canonical.add(canonical_name)
    normalized_text = normalize_token(ingredient_text)
    for alias, canonical_name in sorted(ALIAS_TO_CANONICAL.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(f'(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])', normalized_text):
            canonical.add(canonical_name)
    available = bool(ingredient_text.strip()) or bool(raw_tokens)
    return {'available': bool(available), 'ingredient_data_available': bool(available), 'raw_text': ingredient_text, 'normalized_text': normalized_text, 'raw_tokens': sorted(set(raw_tokens)), 'canonical_ingredients': sorted(canonical), 'ingredient_count': len(canonical)}

def requested_ingredient_weights(q: Dict[str, Any]) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    for concern in q.get('effective_concerns', []):
        concern_key = normalize_token(concern)
        for ingredient, weight in CONCERN_INGREDIENT_WEIGHTS.get(concern_key, {}).items():
            weights[ingredient] = max(weights.get(ingredient, 0.0), float(weight))
    explicit = set(q.get('effective_ingredients', []))
    explicit.update(detect_requested_ingredients(q.get('query_text', '')))
    for ingredient in explicit:
        canonical = canonicalize_ingredient(ingredient)
        if canonical:
            weights[canonical] = max(weights.get(canonical, 0.0), 1.0)
    return weights

def compute_ingredient_match(product_id: str, q: Dict[str, Any]) -> Dict[str, Any]:
    profile = get_product_ingredient_profile(product_id)
    if not profile['available']:
        return {'ingredient_data_available': False, 'ingredient_match_score': 0.0, 'ingredient_coverage': 0.0, 'matched_ingredients': [], 'ingredient_match_types': {}, 'ingredient_profile': profile}
    desired = requested_ingredient_weights(q)
    if not desired:
        return {'ingredient_data_available': True, 'ingredient_match_score': 0.0, 'ingredient_coverage': 0.0, 'matched_ingredients': [], 'ingredient_match_types': {}, 'ingredient_profile': profile}
    product_canonical = set(profile['canonical_ingredients'])
    product_tokens = set(profile['raw_tokens'])
    raw_text = profile['normalized_text']
    matched = []
    match_types = {}
    weighted_match = 0.0
    total_weight = sum(desired.values())
    for desired_name, relevance in desired.items():
        target = canonicalize_ingredient(desired_name)
        if not target:
            continue
        if target in product_canonical:
            matched.append(target)
            match_types[target] = 'exact_or_canonical'
            weighted_match += float(relevance)
            continue
        aliases = INGREDIENT_ALIASES.get(target, [target])
        alias_hit = False
        for alias in aliases:
            alias_norm = normalize_token(alias)
            if alias_norm in product_tokens:
                alias_hit = True
                break
            if alias_norm and re.search(f'(?<![a-z0-9]){re.escape(alias_norm)}(?![a-z0-9])', raw_text):
                alias_hit = True
                break
        if alias_hit:
            matched.append(target)
            match_types[target] = 'alias'
            weighted_match += float(relevance)
    matched = sorted(set(matched))
    coverage = len(matched) / len(desired) if desired else 0.0
    score = weighted_match / total_weight if total_weight else 0.0
    return {'ingredient_data_available': True, 'ingredient_match_score': float(np.clip(score, 0.0, 1.0)), 'ingredient_coverage': float(np.clip(coverage, 0.0, 1.0)), 'matched_ingredients': matched, 'ingredient_match_types': match_types, 'ingredient_profile': profile}

def ingredient_match_profile(product_id: str, q: Dict[str, Any]) -> Dict[str, Any]:
    return compute_ingredient_match(product_id, q)

def ingredient_match_score(product_id: str, q: Dict[str, Any]) -> Tuple[float, List[str]]:
    result = compute_ingredient_match(product_id, q)
    return (result['ingredient_match_score'], result['matched_ingredients'])

def get_theme_signal(row: pd.Series, theme: str) -> Optional[float]:
    for col in REVIEW_THEME_MAP.get(theme, []):
        if col not in row.index:
            continue
        value = pd.to_numeric(row[col], errors='coerce')
        if pd.notna(value):
            if col.endswith('_count'):
                return float(1.0 - math.exp(-float(value) / 20.0))
            return float(np.clip(value, 0.0, 1.0))
    return None

def review_relevance_score(product_id: str, q: Dict[str, Any]) -> Tuple[float, List[str]]:
    pid = str(product_id)
    if pid not in catalog_by_id.index:
        return (0.0, [])
    row = catalog_by_id.loc[pid]
    requests: List[Tuple[str, int]] = []
    for pref in q.get('effective_preferences', []):
        pref = normalize_token(pref)
        if pref == 'lightweight':
            requests.append(('lightweight', +1))
        elif pref == 'non_greasy':
            requests.append(('greasy', -1))
        elif pref == 'fragrance_free':
            requests.append(('fragrance', -1))
        elif pref == 'non_comedogenic':
            requests.append(('breakout', +1))
    concern_to_theme = {'hydration': ('hydrating', +1), 'acne': ('breakout', +1), 'oil_control': ('greasy', -1)}
    for concern in q.get('effective_concerns', []):
        mapping = concern_to_theme.get(normalize_token(concern))
        if mapping:
            requests.append(mapping)
    if not requests:
        generic = pd.to_numeric(row.get('recommendation_rate', np.nan), errors='coerce')
        if pd.notna(generic):
            return (float(np.clip(generic, 0.0, 1.0)), ['overall recommendation rate'])
        return (0.0, [])
    scores = []
    evidence = []
    for theme, direction in requests:
        signal = get_theme_signal(row, theme)
        if signal is None:
            continue
        value = float(signal) if direction > 0 else float(1.0 - signal)
        scores.append(np.clip(value, 0.0, 1.0))
        evidence.append(theme)
    if not scores:
        return (0.0, [])
    return (float(np.mean(scores)), list(dict.fromkeys(evidence)))

def add_review_scores(df: pd.DataFrame, q: Dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    values = [review_relevance_score(str(pid), q) for pid in out['product_id']]
    out['review_relevance_score'] = [v[0] for v in values]
    out['review_evidence'] = [v[1] for v in values]
    return out

def skin_preference_score(row: pd.Series, skin_type: Optional[str]) -> Tuple[float, bool]:
    if not skin_type:
        return (0.0, False)
    col = 'skin_share_' + normalize_token(skin_type).replace(' ', '_')
    if col not in row.index:
        return (0.0, False)
    value = pd.to_numeric(row[col], errors='coerce')
    if pd.isna(value):
        return (0.0, False)
    return (float(np.clip(value, 0.0, 1.0)), True)

def descriptor_preference_score(row: pd.Series, preferences: Sequence[str]) -> Tuple[float, bool]:
    if not preferences:
        return (0.0, False)
    text = normalize_token(' '.join((safe_text(row.get(col, '')) for col in ['product_document', 'highlights', 'ingredients_clean', 'ingredients'])))
    scores = []
    for pref in preferences:
        canonical_pref = normalize_token(pref)
        aliases = PREFERENCE_TERMS.get(canonical_pref, [canonical_pref])
        scores.append(1.0 if any((normalize_token(alias) in text for alias in aliases)) else 0.0)
    return (float(np.mean(scores)), True)

def preference_score(product_id: str, q: Dict[str, Any]) -> Tuple[float, bool]:
    pid = str(product_id)
    if pid not in catalog_by_id.index:
        return (0.0, False)
    row = catalog_by_id.loc[pid]
    signals = []
    skin_score, skin_available = skin_preference_score(row, q.get('effective_skin_type'))
    if skin_available:
        signals.append(skin_score)
    descriptor_score, descriptor_available = descriptor_preference_score(row, q.get('effective_preferences', []))
    if descriptor_available:
        signals.append(descriptor_score)
    if not signals:
        return (0.0, False)
    return (float(np.mean(signals)), True)

def add_preference_scores(df: pd.DataFrame, q: Dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    values = [preference_score(str(pid), q) for pid in out['product_id']]
    out['preference_match_score'] = [v[0] for v in values]
    out['preference_signal_available'] = [v[1] for v in values]
    return out

def rating_quality_score(product_id: str) -> float:
    pid = str(product_id)
    if pid not in catalog_by_id.index:
        return 0.0
    row = catalog_by_id.loc[pid]
    rating = numeric_value(row, ['review_avg_rating', 'rating'], default=np.nan)
    count = numeric_value(row, ['review_count_observed', 'reviews'], default=0.0)
    if not np.isfinite(rating):
        return 0.0
    adjusted = (count * rating + RATING_PRIOR_COUNT * RATING_GLOBAL_MEAN) / (count + RATING_PRIOR_COUNT)
    return float(np.clip((adjusted - 1.0) / 4.0, 0.0, 1.0))

def add_rating_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out['rating_quality_score'] = [rating_quality_score(str(pid)) for pid in out['product_id']]
    return out

def embedding_similarity(product_a: str, product_b: str) -> float:
    ia = embedding_position.get(str(product_a))
    ib = embedding_position.get(str(product_b))
    if ia is None or ib is None:
        return 0.0
    return float(np.clip(np.dot(product_embeddings[ia], product_embeddings[ib]), -1.0, 1.0))

def diversity_score_for_candidate(row: pd.Series, selected_rows: Sequence[pd.Series]) -> float:
    if not selected_rows:
        return 1.0
    pid = str(row['product_id'])
    max_embedding_similarity = max((embedding_similarity(pid, str(other['product_id'])) for other in selected_rows))
    candidate_brand = normalize_token(row.get('brand_name', ''))
    candidate_category = normalize_token(row.get('secondary_category', row.get('primary_category', '')))
    repetition_penalty = 0.0
    for other in selected_rows:
        if candidate_brand and candidate_brand == normalize_token(other.get('brand_name', '')):
            repetition_penalty = max(repetition_penalty, 0.1)
        if candidate_category and candidate_category == normalize_token(other.get('secondary_category', other.get('primary_category', ''))):
            repetition_penalty = max(repetition_penalty, 0.05)
    return float(np.clip(1.0 - (0.85 * max_embedding_similarity + repetition_penalty), 0.0, 1.0))

def final_score(row: pd.Series, diversity: float) -> float:
    components = {'semantic': float(np.clip(row.get('semantic_similarity', 0.0), 0.0, 1.0)), 'ingredient': float(np.clip(row.get('ingredient_match_score', 0.0), 0.0, 1.0)), 'review': float(np.clip(row.get('review_relevance_score', 0.0), 0.0, 1.0)), 'preference': float(np.clip(row.get('preference_match_score', 0.0), 0.0, 1.0)), 'rating': float(np.clip(row.get('rating_quality_score', 0.0), 0.0, 1.0)), 'diversity': float(np.clip(diversity, 0.0, 1.0))}
    weights = dict(RANKING_WEIGHTS)
    if not bool(row.get('ingredient_data_available', True)):
        weights.pop('ingredient', None)
    denominator = sum(weights.values())
    normalized_weights = {key: weight / denominator for key, weight in weights.items()}
    score = sum((normalized_weights[key] * components[key] for key in normalized_weights))
    return float(np.clip(score, 0.0, 1.0))

def rank_candidates(df: pd.DataFrame, top_k: int=5) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    working = df.copy().reset_index(drop=True)
    selected_indices = []
    selected_rows: List[pd.Series] = []
    final_scores_map = {}
    diversity_map = {}
    target = min(int(top_k), len(working))
    for _ in range(target):
        best_idx = None
        best_score = -float('inf')
        best_diversity = 0.0
        for idx, row in working.iterrows():
            if idx in selected_indices:
                continue
            diversity = diversity_score_for_candidate(row, selected_rows)
            score = final_score(row, diversity)
            if score > best_score:
                best_idx = idx
                best_score = score
                best_diversity = diversity
        if best_idx is None:
            break
        selected_indices.append(best_idx)
        selected_rows.append(working.loc[best_idx])
        final_scores_map[best_idx] = best_score
        diversity_map[best_idx] = best_diversity
    ranked = working.loc[selected_indices].copy()
    ranked['diversity_score'] = [diversity_map[idx] for idx in selected_indices]
    ranked['final_score'] = [final_scores_map[idx] for idx in selected_indices]
    return ranked.sort_values('final_score', ascending=False).reset_index(drop=True)

def explanation_for_product(row: pd.Series, q: Dict[str, Any]) -> Dict[str, Any]:
    reasons = []
    requested_category = normalize_token(q.get('effective_category'))
    category_text = normalize_token(' '.join([safe_text(row.get('primary_category', '')), safe_text(row.get('secondary_category', '')), safe_text(row.get('tertiary_category', ''))]))
    if requested_category and requested_category in category_text:
        reasons.append(f'Matches requested {requested_category} category')
    budget = q.get('effective_budget_max')
    price = pd.to_numeric(row.get('effective_price_usd', np.nan), errors='coerce')
    if budget is not None and pd.notna(price) and (price <= float(budget)):
        reasons.append(f'Within budget (₹{float(price)*83.0:,.2f} ≤ ₹{float(budget)*83.0:,.2f})')
    semantic = float(row.get('semantic_similarity', 0.0))
    if semantic >= 0.75:
        reasons.append('Strong semantic match')
    elif semantic >= 0.55:
        reasons.append('Good semantic match')
    available = bool(row.get('ingredient_data_available', False))
    matched = row.get('matched_ingredients', row.get('matched_ingredient_terms', []))
    if isinstance(matched, str):
        try:
            matched = ast.literal_eval(matched)
        except Exception:
            matched = [matched]
    matched = list(matched)
    coverage = float(row.get('ingredient_coverage', 0.0))
    if available and matched:
        reasons.append('Ingredient signals matched: ' + ', '.join(matched[:5]))
        reasons.append(f'Ingredient coverage: {coverage:.0%}')
    elif not available:
        reasons.append('Ingredient information unavailable in catalog')
    evidence = row.get('review_evidence', [])
    if isinstance(evidence, str):
        try:
            evidence = ast.literal_eval(evidence)
        except Exception:
            evidence = [evidence]
    if evidence:
        reasons.append('Review evidence: ' + ', '.join((str(x).replace('_', ' ') for x in list(evidence)[:4])))
    skin = normalize_token(q.get('effective_skin_type'))
    if skin:
        skin_col = f"skin_share_{skin.replace(' ', '_')}"
        if skin_col in row.index:
            skin_share = pd.to_numeric(row.get(skin_col), errors='coerce')
            if pd.notna(skin_share) and float(skin_share) > 0:
                reasons.append(f'Review audience includes {skin} skin ({float(skin_share):.0%})')
    if float(row.get('rating_quality_score', 0.0)) >= 0.8:
        reasons.append('Strong rating quality')
    if not reasons:
        reasons.append('Selected from the highest-scoring valid candidates')
    return {'reasons': reasons[:7], 'ingredient_data_available': available, 'matched_ingredients': matched[:10], 'ingredient_coverage': round(coverage, 4), 'ingredient_match_types': row.get('ingredient_match_types', {}), 'review_evidence': list(evidence)[:10], 'score_breakdown': {'semantic_similarity': round(float(row.get('semantic_similarity', 0.0)), 4), 'ingredient_match': round(float(row.get('ingredient_match_score', 0.0)), 4), 'ingredient_coverage': round(coverage, 4), 'review_relevance': round(float(row.get('review_relevance_score', 0.0)), 4), 'preference_match': round(float(row.get('preference_match_score', 0.0)), 4), 'rating_quality': round(float(row.get('rating_quality_score', 0.0)), 4), 'diversity': round(float(row.get('diversity_score', 0.0)), 4), 'final_score': round(float(row.get('final_score', 0.0)), 4)}}

def add_ingredient_scores(df: pd.DataFrame, q: Dict[str, Any]) -> pd.DataFrame:
    """

    Add the canonical ingredient-matching results to each candidate.



    This function uses the same compute_ingredient_match() function

    used by the ingredient diagnostics, so the recommendation results

    cannot drift from the diagnostic results.

    """
    out = df.copy()
    results = []
    for product_id in out['product_id'].astype(str):
        result = compute_ingredient_match(product_id, q)
        results.append(result)
    out['ingredient_data_available'] = [result['ingredient_data_available'] for result in results]
    out['ingredient_match_score'] = [float(result['ingredient_match_score']) for result in results]
    out['ingredient_coverage'] = [float(result['ingredient_coverage']) for result in results]
    out['matched_ingredients'] = [result['matched_ingredients'] for result in results]
    out['matched_ingredient_terms'] = [result['matched_ingredients'] for result in results]
    out['ingredient_match_types'] = [result['ingredient_match_types'] for result in results]
    return out

def recommend(query: Optional[str]=None, skin_type: Optional[str]=None, concerns: Optional[Sequence[str]]=None, category: Optional[str]=None, budget_max: Optional[float]=None, preferred_terms: Optional[Sequence[str]]=None, avoid_ingredients: Optional[Sequence[str]]=None, candidate_k: int=50, top_k: int=5) -> Dict[str, Any]:
    started = time.perf_counter()
    q = normalize_query(query=query, skin_type=skin_type, concerns=concerns, category=category, budget_max=budget_max, preferred_terms=preferred_terms, avoid_ingredients=avoid_ingredients)
    query_text = build_query_text(q)
    if not query_text:
        raise ValueError('Please provide a query or at least one structured recommendation signal.')
    retrieval_started = time.perf_counter()
    retrieved = semantic_retrieve(q, candidate_k=candidate_k)
    retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
    filtered, filter_stats = apply_hard_filters(retrieved, q)
    if filtered.empty:
        total_ms = (time.perf_counter() - started) * 1000
        return {'status': 'no_high_confidence_match', 'query': q, 'query_text': query_text, 'recommendations': [], 'filter_stats': filter_stats, 'latency_ms': {'retrieval': round(retrieval_ms, 2), 'total': round(total_ms, 2)}, 'message': 'No products satisfied the requested constraints. Try relaxing the budget, category, or ingredient constraints.'}
    filtered = add_ingredient_scores(filtered, q)
    filtered = add_review_scores(filtered, q)
    filtered = add_preference_scores(filtered, q)
    filtered = add_rating_scores(filtered)
    ranked = rank_candidates(filtered, top_k=top_k)
    recommendations = []
    for _, row in ranked.iterrows():
        explanation = explanation_for_product(row, q)
        price = pd.to_numeric(row.get('effective_price_usd', np.nan), errors='coerce')
        recommendations.append({'product_id': str(row['product_id']), 'product_name': safe_text(row.get('product_name')), 'brand_name': safe_text(row.get('brand_name')), 'primary_category': safe_text(row.get('primary_category')), 'secondary_category': safe_text(row.get('secondary_category')), 'price_usd': float(price) if pd.notna(price) else None, 'final_score': round(float(row['final_score']), 4), 'ingredient_data_available': explanation['ingredient_data_available'], 'matched_ingredients': explanation['matched_ingredients'], 'ingredient_coverage': explanation['ingredient_coverage'], 'ingredient_match_types': explanation['ingredient_match_types'], 'review_evidence': explanation['review_evidence'], 'reasons': explanation['reasons'], 'score_breakdown': explanation['score_breakdown']})
    total_ms = (time.perf_counter() - started) * 1000
    return {'status': 'ok', 'query': q, 'query_text': query_text, 'recommendations': recommendations, 'filter_stats': filter_stats, 'latency_ms': {'retrieval': round(retrieval_ms, 2), 'total': round(total_ms, 2)}}

def sensitivity_rank_scores(df: pd.DataFrame, ingredient_weight: float) -> pd.DataFrame:
    ingredient_weight = float(np.clip(ingredient_weight, 0.0, 1.0))
    remaining = 1.0 - ingredient_weight
    base_other = {'semantic': 0.4, 'review': 0.15, 'preference': 0.1, 'rating': 0.05, 'diversity': 0.05}
    other_sum = sum(base_other.values())
    scale = remaining / other_sum if other_sum else 0.0
    weights = {'semantic': base_other['semantic'] * scale, 'ingredient': ingredient_weight, 'review': base_other['review'] * scale, 'preference': base_other['preference'] * scale, 'rating': base_other['rating'] * scale, 'diversity': base_other['diversity'] * scale}
    rows = []
    for _, row in df.iterrows():
        components = {key: float(np.clip(row.get({'semantic': 'semantic_similarity', 'ingredient': 'ingredient_match_score', 'review': 'review_relevance_score', 'preference': 'preference_match_score', 'rating': 'rating_quality_score'}.get(key, ''), 0.0), 0.0, 1.0)) for key in ['semantic', 'ingredient', 'review', 'preference', 'rating']}
        components['diversity'] = 1.0
        if not bool(row.get('ingredient_data_available', True)):
            weights_for_product = dict(weights)
            weights_for_product.pop('ingredient', None)
        else:
            weights_for_product = dict(weights)
        denom = sum(weights_for_product.values())
        score = sum((weights_for_product[k] * components[k] for k in weights_for_product)) / denom if denom else 0.0
        rows.append({'product_id': row['product_id'], 'product_name': row.get('product_name', ''), 'score': score})
    return pd.DataFrame(rows)