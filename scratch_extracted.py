%pip install -q -U sentence-transformers chromadb
from __future__ import annotations



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



warnings.filterwarnings("ignore")



print("Python:", sys.version.split()[0])

print("Pandas:", pd.__version__)

print("NumPy:", np.__version__)



import chromadb

from sentence_transformers import SentenceTransformer



print("ChromaDB:", chromadb.__version__)

print("Sentence Transformers:", __import__("sentence_transformers").__version__)

print("Environment imports: PASS")
# ============================================================

# 3. Locate and Load the Processed Catalog

# ============================================================



from pathlib import Path



# This notebook is inside:

# ORBO.ai/notebooks/

#

# Therefore the project root is one directory above the notebook.

NOTEBOOK_DIR = Path.cwd()



# Find the ORBO.ai project root robustly.

PROJECT_ROOT = None



candidate = NOTEBOOK_DIR.resolve()



# Check current directory and its parents for the expected project structure.

for folder in [candidate, *candidate.parents]:

    processed_catalog = (

        folder

        / "data"

        / "processed"

        / "recommendation_catalog.csv"

    )



    if processed_catalog.exists():

        PROJECT_ROOT = folder

        CATALOG_PATH = processed_catalog

        break



# Fallback for the standard notebook location:

if PROJECT_ROOT is None:

    standard_root = NOTEBOOK_DIR.parent.resolve()

    standard_catalog = (

        standard_root

        / "data"

        / "processed"

        / "recommendation_catalog.csv"

    )



    if standard_catalog.exists():

        PROJECT_ROOT = standard_root

        CATALOG_PATH = standard_catalog



# Final check

if PROJECT_ROOT is None or not CATALOG_PATH.exists():

    raise FileNotFoundError(

        "\nCould not find recommendation_catalog.csv.\n\n"

        "Expected project structure:\n"

        "ORBO.ai/\n"

        "├── data/\n"

        "│   └── processed/\n"

        "│       └── recommendation_catalog.csv\n"

        "└── notebooks/\n"

        "    └── 02_DermaMatch_Recommendation_Engine_FINAL_NO_ERROR.ipynb\n\n"

        f"Current working directory: {Path.cwd()}\n"

    )



print("=" * 80)

print("CATALOG LOCATION")

print("=" * 80)

print("Current working directory:", Path.cwd())

print("Project root:", PROJECT_ROOT)

print("Catalog path:", CATALOG_PATH)

print("Catalog exists:", CATALOG_PATH.exists())

print("Catalog size (MB):", round(CATALOG_PATH.stat().st_size / (1024**2), 2))

print("Catalog location validation: PASS")
catalog = pd.read_csv(CATALOG_PATH, low_memory=False)



print("Catalog loaded successfully.")

print("Rows:", len(catalog))

print("Columns:", len(catalog.columns))

print("Shape:", catalog.shape)



display(catalog.head(5))
required_columns = [

    "product_id",

    "product_name",

    "brand_name",

]



missing_required = [

    col for col in required_columns

    if col not in catalog.columns

]



if missing_required:

    raise KeyError(

        "Missing required catalog columns: "

        + ", ".join(missing_required)

    )



catalog["product_id"] = catalog["product_id"].astype(str)



# CRITICAL: create the lookup BEFORE any function that depends on it.

catalog_by_id = catalog.set_index(

    "product_id",

    drop=False,

)



print("Canonical product lookup created.")

print("Lookup rows:", len(catalog_by_id))

print("Unique product IDs:", catalog_by_id.index.nunique())



assert catalog["product_id"].notna().all()

assert catalog["product_id"].is_unique

assert catalog_by_id.index.is_unique



print("Catalog key validation: PASS")
def columns_containing(*terms: str) -> List[str]:

    return [

        c for c in catalog.columns

        if any(term.lower() in c.lower() for term in terms)

    ]





ingredient_columns = columns_containing("ingredient")

skin_columns = [

    c for c in catalog.columns

    if c.lower().startswith("skin_share_")

]

theme_columns = [

    c for c in catalog.columns

    if c.lower().startswith("theme_")

]

price_columns = columns_containing("price")

review_columns = columns_containing("review", "rating", "recommendation")



print("Ingredient columns:", ingredient_columns)

print("Skin-share columns:", skin_columns)

print("Theme columns:", theme_columns)

print("Price columns:", price_columns)

print("Review/rating columns:", review_columns)
print("Missing-value summary for core fields:")

core_fields = [

    c for c in [

        "product_id",

        "product_name",

        "brand_name",

        "ingredients",

        "ingredients_clean",

        "ingredient_tokens",

        "effective_price_usd",

        "rating",

        "review_avg_rating",

        "review_count_observed",

        "recommendation_rate",

    ]

    if c in catalog.columns

]



summary_rows = []

for col in core_fields:

    summary_rows.append({

        "field": col,

        "missing": int(catalog[col].isna().sum()),

        "missing_pct": round(float(catalog[col].isna().mean() * 100), 2),

        "unique": int(catalog[col].nunique(dropna=True)),

    })



display(pd.DataFrame(summary_rows))
def safe_text(value: Any) -> str:

    if value is None:

        return ""

    try:

        if pd.isna(value):

            return ""

    except Exception:

        pass

    text = str(value).strip()

    return "" if text.lower() in {"nan", "none", "null"} else text





def normalize_token(value: Any) -> str:

    text = safe_text(value).lower()

    text = re.sub(r"[^a-z0-9\s%_-]", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text





def build_product_document(row: pd.Series) -> str:

    parts = []



    field_labels = [

        ("product_name", "Product"),

        ("brand_name", "Brand"),

        ("primary_category", "Primary category"),

        ("secondary_category", "Secondary category"),

        ("tertiary_category", "Product type"),

        ("highlights", "Highlights"),

        ("ingredients_clean", "Ingredients"),

        ("ingredients", "Ingredients"),

        ("skin_type_profile", "Skin-type profile"),

    ]



    seen_labels = set()



    for field, label in field_labels:

        if field not in row.index:

            continue



        value = safe_text(row[field])

        if not value:

            continue



        if label == "Ingredients":

            # Do not duplicate cleaned + raw ingredients.

            if "Ingredients" in seen_labels:

                continue



        parts.append(f"{label}: {value}")

        seen_labels.add(label)



    theme_names = []

    for col in theme_columns:

        value = pd.to_numeric(row.get(col), errors="coerce")

        if pd.notna(value) and float(value) > 0:

            name = re.sub(r"^theme_", "", col.lower())

            name = re.sub(r"_share$|_count$", "", name)

            theme_names.append(name.replace("_", " "))



    if theme_names:

        parts.append("Review themes: " + ", ".join(sorted(set(theme_names))))



    return " | ".join(parts)





catalog["product_document"] = catalog.apply(

    build_product_document,

    axis=1,

)



empty_document_count = int(

    catalog["product_document"].str.strip().eq("").sum()

)



print("Product documents:", len(catalog))

print("Empty documents:", empty_document_count)



assert empty_document_count == 0

print("Product-document validation: PASS")



print("\nExample product document:")

print(catalog.loc[0, "product_document"][:1200])
EMBEDDING_MODEL_NAME = os.getenv(

    "DERMAMATCH_EMBEDDING_MODEL",

    "BAAI/bge-small-en-v1.5",

)



print("Loading model:", EMBEDDING_MODEL_NAME)



embedder = SentenceTransformer(

    EMBEDDING_MODEL_NAME,

)



_probe = embedder.encode(

    ["DermaMatch skincare recommendation"],

    normalize_embeddings=True,

    convert_to_numpy=True,

    show_progress_bar=False,

)



EMBEDDING_DIM = int(_probe.shape[-1])



print("Embedding dimension:", EMBEDDING_DIM)

print("Embedding model loaded: PASS")
ARTIFACT_DIR = PROJECT_ROOT / "data" / "artifacts"

ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)



EMBEDDINGS_PATH = ARTIFACT_DIR / "product_embeddings.npy"

EMBEDDING_IDS_PATH = ARTIFACT_DIR / "product_embedding_ids.json"



product_documents = catalog["product_document"].tolist()

product_ids = catalog["product_id"].astype(str).tolist()



print("Documents:", len(product_documents))

print("Batch size: 64")



start_time = time.perf_counter()



product_embeddings = embedder.encode(

    product_documents,

    batch_size=64,

    normalize_embeddings=True,

    convert_to_numpy=True,

    show_progress_bar=True,

)



product_embeddings = np.asarray(

    product_embeddings,

    dtype=np.float32,

)



elapsed = time.perf_counter() - start_time



print("\nEmbedding generation complete.")

print("Matrix shape:", product_embeddings.shape)

print("Embedding dimension:", product_embeddings.shape[1])

print("Time (seconds):", round(elapsed, 2))

print(

    "Mean vector norm:",

    round(

        float(

            np.linalg.norm(

                product_embeddings,

                axis=1,

            ).mean()

        ),

        6,

    ),

)



assert product_embeddings.shape == (

    len(catalog),

    EMBEDDING_DIM,

)

assert np.isfinite(product_embeddings).all()



np.save(

    EMBEDDINGS_PATH,

    product_embeddings,

)

EMBEDDING_IDS_PATH.write_text(

    json.dumps(product_ids, ensure_ascii=False, indent=2),

    encoding="utf-8",

)



print("Embedding validation: PASS")
CHROMA_PATH = ARTIFACT_DIR / "chroma"

CHROMA_PATH.mkdir(parents=True, exist_ok=True)



CHROMA_COLLECTION_NAME = "dermamatch_products"



print("ChromaDB path:", CHROMA_PATH)

print("Collection:", CHROMA_COLLECTION_NAME)



chroma_client = chromadb.PersistentClient(

    path=str(CHROMA_PATH),

)



try:

    chroma_client.delete_collection(

        CHROMA_COLLECTION_NAME,

    )

    print("Existing collection removed.")

except Exception:

    print("No previous collection found.")



collection = chroma_client.get_or_create_collection(

    name=CHROMA_COLLECTION_NAME,

    metadata={

        "description": "DermaMatch skincare product embeddings",

        "embedding_model": EMBEDDING_MODEL_NAME,

        "hnsw:space": "cosine",

    },

)



print("Collection count:", collection.count())
def numeric_value(

    row: pd.Series,

    candidates: Sequence[str],

    default: float = 0.0,

) -> float:

    for col in candidates:

        if col not in row.index:

            continue

        value = pd.to_numeric(

            row[col],

            errors="coerce",

        )

        if pd.notna(value):

            return float(value)

    return float(default)





def make_metadata(row: pd.Series) -> Dict[str, Any]:

    metadata = {

        "product_id": str(row["product_id"]),

        "product_name": safe_text(row.get("product_name")),

        "brand_name": safe_text(row.get("brand_name")),

        "primary_category": safe_text(row.get("primary_category")),

        "secondary_category": safe_text(row.get("secondary_category")),

        "tertiary_category": safe_text(row.get("tertiary_category")),

        "effective_price_usd": numeric_value(

            row,

            ["effective_price_usd", "sale_price_usd", "price_usd"],

            default=0.0,

        ),

        "rating": numeric_value(

            row,

            ["rating"],

            default=0.0,

        ),

        "review_count": numeric_value(

            row,

            ["review_count_observed", "reviews"],

            default=0.0,

        ),

        "recommendation_rate": numeric_value(

            row,

            ["recommendation_rate"],

            default=0.0,

        ),

    }



    return metadata





chroma_ids = [

    f"product_{pid}"

    for pid in product_ids

]



chroma_documents = catalog[

    "product_document"

].tolist()



chroma_metadatas = [

    make_metadata(row)

    for _, row in catalog.iterrows()

]



BATCH_SIZE = 500



for start in range(

    0,

    len(chroma_ids),

    BATCH_SIZE,

):

    end = min(

        start + BATCH_SIZE,

        len(chroma_ids),

    )



    collection.upsert(

        ids=chroma_ids[start:end],

        embeddings=product_embeddings[start:end].tolist(),

        documents=chroma_documents[start:end],

        metadatas=chroma_metadatas[start:end],

    )



    print(

        f"Indexed {end:,}/{len(chroma_ids):,}"

    )



print("Final ChromaDB count:", collection.count())



assert collection.count() == len(catalog)

print("ChromaDB indexing validation: PASS")
SKIN_TYPE_ALIASES = {

    "oily": ["oily"],

    "dry": ["dry", "dehydrated"],

    "combination": ["combination", "combo"],

    "normal": ["normal"],

    "sensitive": ["sensitive"],

}



CONCERN_TERMS = {

    "acne": ["acne", "breakout", "break out", "pimple", "blemish"],

    "hydration": ["hydration", "hydrating", "hydrate", "dryness"],

    "dark_spots": [

        "dark spot",

        "dark spots",

        "hyperpigmentation",

        "pigmentation",

    ],

    "anti_aging": [

        "anti aging",

        "anti-aging",

        "wrinkle",

        "fine line",

        "firming",

    ],

    "oil_control": [

        "oil control",

        "oily",

        "shine control",

    ],

}



PREFERENCE_TERMS = {

    "lightweight": [

        "lightweight",

        "light weight",

        "light texture",

    ],

    "fragrance_free": [

        "fragrance free",

        "fragrance-free",

        "no fragrance",

        "unscented",

    ],

    "non_comedogenic": [

        "non-comedogenic",

        "noncomedogenic",

        "won't clog pores",

        "does not clog pores",

    ],

    "non_greasy": [

        "non-greasy",

        "non greasy",

        "not greasy",

        "greasy-free",

    ],

}



CATEGORY_ALIASES = {

    "cleanser": ["cleanser", "cleanse", "face wash", "facial wash"],

    "moisturizer": [

        "moisturizer",

        "moisturiser",

        "moisturizing cream",

        "face cream",

    ],

    "sunscreen": ["sunscreen", "sun screen", "spf"],

    "serum": ["serum"],

    "mask": ["mask", "face mask"],

    "eye care": ["eye cream", "eye care", "eye treatment"],

    "treatment": ["treatment", "acne treatment"],

}



INGREDIENT_ALIASES = {

    "salicylic acid": [

        "salicylic acid",

        "bha",

        "beta hydroxy acid",

    ],

    "niacinamide": [

        "niacinamide",

        "nicotinamide",

    ],

    "zinc": [

        "zinc",

        "zinc oxide",

        "zinc gluconate",

        "zinc pca",

    ],

    "hyaluronic acid": [

        "hyaluronic acid",

        "sodium hyaluronate",

        "hydrolyzed hyaluronic acid",

        "hydrolysed hyaluronic acid",

    ],

    "vitamin c": [

        "vitamin c",

        "ascorbic acid",

        "l ascorbic acid",

        "ascorbic",

    ],

    "azelaic acid": ["azelaic acid"],

    "benzoyl peroxide": ["benzoyl peroxide"],

    "retinol": ["retinol"],

    "retinal": ["retinal", "retinaldehyde"],

    "peptide": ["peptide", "peptides"],

    "ceramide": ["ceramide", "ceramides"],

    "glycerin": ["glycerin", "glycerine", "glycerol"],

    "squalane": ["squalane"],

    "fragrance": ["fragrance", "parfum", "perfume"],

    "alcohol denat": [

        "alcohol denat",

        "denatured alcohol",

        "sd alcohol",

        "sd alcohol 40",

    ],

}



CONCERN_INGREDIENT_WEIGHTS = {

    "acne": {

        "salicylic acid": 1.00,

        "benzoyl peroxide": 1.00,

        "azelaic acid": 0.90,

        "niacinamide": 0.65,

    },

    "oil_control": {

        "niacinamide": 1.00,

        "salicylic acid": 0.90,

        "zinc": 0.70,

    },

    "hydration": {

        "hyaluronic acid": 1.00,

        "glycerin": 0.95,

        "squalane": 0.80,

        "ceramide": 0.80,

    },

    "dark_spots": {

        "vitamin c": 1.00,

        "niacinamide": 0.85,

        "azelaic acid": 0.80,

    },

    "anti_aging": {

        "retinol": 1.00,

        "retinal": 0.95,

        "peptide": 0.75,

        "vitamin c": 0.70,

    },

}



ALIAS_TO_CANONICAL = {

    normalize_token(alias): canonical

    for canonical, aliases in INGREDIENT_ALIASES.items()

    for alias in aliases

}





def detect_first_match(

    text: str,

    alias_map: Dict[str, Sequence[str]],

) -> Optional[str]:

    normalized = normalize_token(text)



    for canonical, aliases in alias_map.items():

        for alias in aliases:

            if re.search(

                rf"(?<![a-z0-9]){re.escape(normalize_token(alias))}(?![a-z0-9])",

                normalized,

            ):

                return canonical



    return None





def detect_all_matches(

    text: str,

    alias_map: Dict[str, Sequence[str]],

) -> List[str]:

    normalized = normalize_token(text)

    found = []



    for canonical, aliases in alias_map.items():

        if any(

            re.search(

                rf"(?<![a-z0-9]){re.escape(normalize_token(alias))}(?![a-z0-9])",

                normalized,

            )

            for alias in aliases

        ):

            found.append(canonical)



    return found





def detect_requested_ingredients(

    text: str,

) -> List[str]:

    normalized = normalize_token(text)

    if not normalized:

        return []



    found = []



    for alias, canonical in sorted(

        ALIAS_TO_CANONICAL.items(),

        key=lambda x: len(x[0]),

        reverse=True,

    ):

        if re.search(

            rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",

            normalized,

        ):

            found.append(canonical)



    return list(dict.fromkeys(found))





def extract_budget(

    text: str,

) -> Optional[float]:

    normalized = normalize_token(text)



    patterns = [

        r"(?:under|below|less than|up to|upto)\s*\$?\s*(\d+(?:\.\d+)?)",

        r"\$\s*(\d+(?:\.\d+)?)",

        r"(?:budget|price)\s*(?:of)?\s*\$?\s*(\d+(?:\.\d+)?)",

    ]



    for pattern in patterns:

        match = re.search(

            pattern,

            normalized,

        )

        if match:

            return float(match.group(1))



    return None





def normalize_query(

    query: Optional[str] = None,

    skin_type: Optional[str] = None,

    concerns: Optional[Sequence[str]] = None,

    category: Optional[str] = None,

    budget_max: Optional[float] = None,

    preferred_terms: Optional[Sequence[str]] = None,

    avoid_ingredients: Optional[Sequence[str]] = None,

) -> Dict[str, Any]:

    query_text = safe_text(query)



    detected_concerns = (

        detect_all_matches(

            query_text,

            CONCERN_TERMS,

        )

        if query_text

        else []

    )



    detected_preferences = (

        detect_all_matches(

            query_text,

            PREFERENCE_TERMS,

        )

        if query_text

        else []

    )



    detected_skin_type = (

        detect_first_match(

            query_text,

            SKIN_TYPE_ALIASES,

        )

        if query_text

        else None

    )



    detected_category = (

        detect_first_match(

            query_text,

            CATEGORY_ALIASES,

        )

        if query_text

        else None

    )



    detected_ingredients = (

        detect_requested_ingredients(

            query_text

        )

        if query_text

        else []

    )



    detected_budget = (

        extract_budget(query_text)

        if query_text

        else None

    )



    return {

        "query_text": query_text,

        "skin_type": normalize_token(skin_type) if skin_type else None,

        "concerns": [

            normalize_token(x)

            for x in (concerns or [])

            if safe_text(x)

        ],

        "category": normalize_token(category) if category else None,

        "budget_max": (

            float(budget_max)

            if budget_max is not None

            else None

        ),

        "preferred_terms": [

            normalize_token(x)

            for x in (preferred_terms or [])

            if safe_text(x)

        ],

        "avoid_ingredients": [

            normalize_token(x)

            for x in (avoid_ingredients or [])

            if safe_text(x)

        ],

        "detected_skin_type": detected_skin_type,

        "detected_concerns": detected_concerns,

        "detected_preferences": detected_preferences,

        "detected_category": detected_category,

        "detected_ingredients": detected_ingredients,

        "detected_budget_max": detected_budget,

        "effective_skin_type": (

            normalize_token(skin_type)

            if skin_type

            else detected_skin_type

        ),

        "effective_concerns": list(dict.fromkeys(

            [

                *[

                    normalize_token(x)

                    for x in (concerns or [])

                    if safe_text(x)

                ],

                *detected_concerns,

            ]

        )),

        "effective_category": (

            normalize_token(category)

            if category

            else detected_category

        ),

        "effective_preferences": list(dict.fromkeys(

            [

                *[

                    normalize_token(x)

                    for x in (preferred_terms or [])

                    if safe_text(x)

                ],

                *detected_preferences,

            ]

        )),

        "effective_ingredients": detected_ingredients,

        "effective_budget_max": (

            float(budget_max)

            if budget_max is not None

            else detected_budget

        ),

    }





query_example = normalize_query(

    "lightweight sunscreen for oily acne-prone skin with zinc oxide under $30"

)



print(

    json.dumps(

        query_example,

        indent=2,

    )

)
def build_query_text(q: Dict[str, Any]) -> str:

    parts = []



    if q.get("query_text"):

        parts.append(q["query_text"])



    if q.get("effective_skin_type"):

        parts.append(

            f"skin type: {q['effective_skin_type']}"

        )



    if q.get("effective_concerns"):

        parts.append(

            "concerns: "

            + ", ".join(q["effective_concerns"])

        )



    if q.get("effective_category"):

        parts.append(

            f"category: {q['effective_category']}"

        )



    if q.get("effective_preferences"):

        parts.append(

            "preferences: "

            + ", ".join(q["effective_preferences"])

        )



    if q.get("effective_ingredients"):

        parts.append(

            "ingredients: "

            + ", ".join(q["effective_ingredients"])

        )



    return " | ".join(

        part for part in parts if part

    )





def semantic_retrieve(

    q: Dict[str, Any],

    candidate_k: int = 50,

) -> pd.DataFrame:

    query_text = build_query_text(q)



    if not query_text:

        raise ValueError(

            "A query or structured recommendation signal is required."

        )



    query_vector = embedder.encode(

        [query_text],

        normalize_embeddings=True,

        convert_to_numpy=True,

        show_progress_bar=False,

    )[0]



    result = collection.query(

        query_embeddings=[

            query_vector.tolist()

        ],

        n_results=min(

            int(candidate_k),

            len(catalog),

        ),

        include=[

            "documents",

            "metadatas",

            "distances",

        ],

    )



    ids = result.get("ids", [[]])[0]

    distances = result.get(

        "distances",

        [[]],

    )[0]

    metadatas = result.get(

        "metadatas",

        [[]],

    )[0]



    rows = []



    for chroma_id, distance, metadata in zip(

        ids,

        distances,

        metadatas,

    ):

        row = dict(metadata)

        row["chroma_id"] = chroma_id

        row["cosine_distance"] = float(distance)

        row["semantic_similarity"] = float(

            np.clip(

                1.0 - float(distance),

                0.0,

                1.0,

            )

        )

        rows.append(row)



    retrieved = pd.DataFrame(rows)



    if retrieved.empty:

        raise RuntimeError(

            "ChromaDB returned zero candidates."

        )



    return retrieved





retrieval_test = semantic_retrieve(

    query_example,

    candidate_k=10,

)



print(

    "Retrieved candidates:",

    len(retrieval_test),

)



display(

    retrieval_test[

        [

            "product_id",

            "product_name",

            "brand_name",

            "primary_category",

            "effective_price_usd",

            "semantic_similarity",

        ]

    ]

)
def parse_avoid_terms(

    q: Dict[str, Any],

) -> List[str]:

    return [

        normalize_token(x)

        for x in q.get("avoid_ingredients", [])

        if safe_text(x)

    ]





def apply_hard_filters(

    retrieved: pd.DataFrame,

    q: Dict[str, Any],

) -> Tuple[pd.DataFrame, Dict[str, int]]:

    if retrieved.empty:

        return (

            retrieved.copy(),

            {

                "input": 0,

                "after_filter": 0,

            },

        )



    out = retrieved.copy()

    stats = {"input": len(out)}



    budget = q.get(

        "effective_budget_max"

    )



    if budget is not None and "effective_price_usd" in out.columns:

        price = pd.to_numeric(

            out["effective_price_usd"],

            errors="coerce",

        )

        out = out[

            price.notna()

            & (price <= float(budget))

        ].copy()



    stats["after_budget"] = len(out)



    category = normalize_token(

        q.get("effective_category")

    )



    if category:

        cols = [

            c for c in [

                "primary_category",

                "secondary_category",

                "tertiary_category",

            ]

            if c in out.columns

        ]



        if cols:

            category_mask = pd.Series(

                False,

                index=out.index,

            )



            pattern = re.escape(category)



            for col in cols:

                category_mask |= (

                    out[col]

                    .fillna("")

                    .map(normalize_token)

                    .str.contains(

                        pattern,

                        regex=True,

                    )

                )



            out = out[category_mask].copy()



    stats["after_category"] = len(out)



    # Ingredient avoidance uses the same canonical profile as scoring.

    avoid_terms = parse_avoid_terms(q)

    rejected = 0



    if avoid_terms:

        keep = []



        for pid in out["product_id"].astype(str):

            profile = ingredient_profiles.get(

                pid,

                get_product_ingredient_profile(pid),

            )



            searchable = set(

                profile["canonical_ingredients"]

            )

            searchable.update(

                profile["raw_tokens"]

            )

            searchable_text = normalize_token(

                profile["raw_text"]

                + " "

                + " ".join(searchable)

            )



            violation = False



            for term in avoid_terms:

                canonical = canonicalize_ingredient(

                    term

                )



                if canonical and canonical in searchable:

                    violation = True

                    break



                aliases = INGREDIENT_ALIASES.get(

                    canonical,

                    [term],

                )



                if any(

                    normalize_token(alias)

                    in searchable_text

                    for alias in aliases

                    if normalize_token(alias)

                ):

                    violation = True

                    break



            keep.append(not violation)

            rejected += int(violation)



        out = out[

            np.asarray(

                keep,

                dtype=bool,

            )

        ].copy()



    stats["rejected_by_avoided_ingredient"] = rejected

    stats["after_avoid_ingredients"] = len(out)

    stats["after_filter"] = len(out)



    return (

        out.reset_index(drop=True),

        stats,

    )
# One canonical ingredient profile is used by scoring,

# avoided-ingredient filtering, explanations and diagnostics.



def parse_ingredient_tokens(

    value: Any,

) -> List[str]:

    text = safe_text(value)



    if not text:

        return []



    if text.startswith("[") and text.endswith("]"):

        try:

            parsed = json.loads(text)

            if isinstance(parsed, list):

                return [

                    normalize_token(x)

                    for x in parsed

                    if safe_text(x)

                ]

        except Exception:

            pass



        try:

            parsed = ast.literal_eval(text)

            if isinstance(

                parsed,

                (list, tuple, set),

            ):

                return [

                    normalize_token(x)

                    for x in parsed

                    if safe_text(x)

                ]

        except Exception:

            pass



    return [

        normalize_token(x)

        for x in re.split(

            r"[,;|\n]+",

            text,

        )

        if normalize_token(x)

    ]





def canonicalize_ingredient(

    value: Any,

) -> Optional[str]:

    phrase = normalize_token(value)



    if not phrase:

        return None



    if phrase in ALIAS_TO_CANONICAL:

        return ALIAS_TO_CANONICAL[phrase]



    # Remove concentration values such as "20%" and trailing numbers.

    cleaned = re.sub(

        r"\b\d+(?:\.\d+)?%?\b",

        " ",

        phrase,

    )

    cleaned = re.sub(

        r"\s+",

        " ",

        cleaned,

    ).strip()



    if cleaned in ALIAS_TO_CANONICAL:

        return ALIAS_TO_CANONICAL[cleaned]



    # Longest alias wins.

    for alias, canonical in sorted(

        ALIAS_TO_CANONICAL.items(),

        key=lambda x: len(x[0]),

        reverse=True,

    ):

        if phrase.startswith(alias + " "):

            return canonical



    return None





def get_product_ingredient_profile(

    product_id: str,

) -> Dict[str, Any]:

    pid = str(product_id)



    if pid not in catalog_by_id.index:

        return {

            "available": False,

            "ingredient_data_available": False,

            "raw_text": "",

            "normalized_text": "",

            "raw_tokens": [],

            "canonical_ingredients": [],

            "ingredient_count": 0,

        }



    row = catalog_by_id.loc[pid]



    clean_text = safe_text(

        row.get("ingredients_clean", "")

    )

    raw_text = safe_text(

        row.get("ingredients", "")

    )



    ingredient_text = (

        clean_text

        if clean_text

        else raw_text

    )



    serialized_tokens = parse_ingredient_tokens(

        row.get("ingredient_tokens", "")

    )



    parsed_tokens = [

        normalize_token(part)

        for part in re.split(

            r",|;|\||\n",

            ingredient_text,

        )

        if normalize_token(part)

    ]



    raw_tokens = list(

        dict.fromkeys(

            serialized_tokens

            + parsed_tokens

        )

    )



    canonical = set()



    # Canonicalize complete ingredient phrases.

    for token in raw_tokens:

        canonical_name = canonicalize_ingredient(

            token

        )

        if canonical_name:

            canonical.add(

                canonical_name

            )



    # Search the complete ingredient text for multi-word aliases.

    normalized_text = normalize_token(

        ingredient_text

    )



    for alias, canonical_name in sorted(

        ALIAS_TO_CANONICAL.items(),

        key=lambda x: len(x[0]),

        reverse=True,

    ):

        if re.search(

            rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",

            normalized_text,

        ):

            canonical.add(

                canonical_name

            )



    available = bool(

        ingredient_text.strip()

    ) or bool(raw_tokens)



    return {

        "available": bool(available),

        "ingredient_data_available": bool(available),

        "raw_text": ingredient_text,

        "normalized_text": normalized_text,

        "raw_tokens": sorted(set(raw_tokens)),

        "canonical_ingredients": sorted(canonical),

        "ingredient_count": len(canonical),

    }





def requested_ingredient_weights(

    q: Dict[str, Any],

) -> Dict[str, float]:

    weights: Dict[str, float] = {}



    # Concern-driven ingredients.

    for concern in q.get(

        "effective_concerns",

        [],

    ):

        concern_key = normalize_token(

            concern

        )



        for ingredient, weight in CONCERN_INGREDIENT_WEIGHTS.get(

            concern_key,

            {},

        ).items():

            weights[ingredient] = max(

                weights.get(ingredient, 0.0),

                float(weight),

            )



    # Explicit ingredient requests always receive full relevance.

    explicit = set(

        q.get(

            "effective_ingredients",

            [],

        )

    )



    explicit.update(

        detect_requested_ingredients(

            q.get("query_text", "")

        )

    )



    for ingredient in explicit:

        canonical = canonicalize_ingredient(

            ingredient

        )

        if canonical:

            weights[canonical] = max(

                weights.get(canonical, 0.0),

                1.0,

            )



    return weights





def compute_ingredient_match(

    product_id: str,

    q: Dict[str, Any],

) -> Dict[str, Any]:

    profile = get_product_ingredient_profile(

        product_id

    )



    if not profile["available"]:

        return {

            "ingredient_data_available": False,

            "ingredient_match_score": 0.0,

            "ingredient_coverage": 0.0,

            "matched_ingredients": [],

            "ingredient_match_types": {},

            "ingredient_profile": profile,

        }



    desired = requested_ingredient_weights(q)



    if not desired:

        return {

            "ingredient_data_available": True,

            "ingredient_match_score": 0.0,

            "ingredient_coverage": 0.0,

            "matched_ingredients": [],

            "ingredient_match_types": {},

            "ingredient_profile": profile,

        }



    product_canonical = set(

        profile["canonical_ingredients"]

    )

    product_tokens = set(

        profile["raw_tokens"]

    )

    raw_text = profile["normalized_text"]



    matched = []

    match_types = {}

    weighted_match = 0.0

    total_weight = sum(

        desired.values()

    )



    for desired_name, relevance in desired.items():

        target = canonicalize_ingredient(

            desired_name

        )



        if not target:

            continue



        # Exact/canonical match.

        if target in product_canonical:

            matched.append(target)

            match_types[target] = "exact_or_canonical"

            weighted_match += float(relevance)

            continue



        # Alias match.

        aliases = INGREDIENT_ALIASES.get(

            target,

            [target],

        )



        alias_hit = False



        for alias in aliases:

            alias_norm = normalize_token(alias)



            if alias_norm in product_tokens:

                alias_hit = True

                break



            if alias_norm and re.search(

                rf"(?<![a-z0-9]){re.escape(alias_norm)}(?![a-z0-9])",

                raw_text,

            ):

                alias_hit = True

                break



        if alias_hit:

            matched.append(target)

            match_types[target] = "alias"

            weighted_match += float(relevance)



    matched = sorted(set(matched))



    coverage = (

        len(matched) / len(desired)

        if desired

        else 0.0

    )



    score = (

        weighted_match / total_weight

        if total_weight

        else 0.0

    )



    return {

        "ingredient_data_available": True,

        "ingredient_match_score": float(

            np.clip(score, 0.0, 1.0)

        ),

        "ingredient_coverage": float(

            np.clip(coverage, 0.0, 1.0)

        ),

        "matched_ingredients": matched,

        "ingredient_match_types": match_types,

        "ingredient_profile": profile,

    }





# Backward-compatible names used by the notebook/application.

def ingredient_match_profile(

    product_id: str,

    q: Dict[str, Any],

) -> Dict[str, Any]:

    return compute_ingredient_match(

        product_id,

        q,

    )





def ingredient_match_score(

    product_id: str,

    q: Dict[str, Any],

) -> Tuple[float, List[str]]:

    result = compute_ingredient_match(

        product_id,

        q,

    )

    return (

        result["ingredient_match_score"],

        result["matched_ingredients"],

    )





# Cache once. All later calls use the same canonical representation.

ingredient_profiles = {

    str(row["product_id"]): get_product_ingredient_profile(

        str(row["product_id"])

    )

    for _, row in catalog.iterrows()

}



print("Ingredient profiles built:", len(ingredient_profiles))

print(

    "Products with ingredient data:",

    sum(

        p["available"]

        for p in ingredient_profiles.values()

    ),

)

print(

    "Products without ingredient data:",

    sum(

        not p["available"]

        for p in ingredient_profiles.values()

    ),

)



assert len(ingredient_profiles) == len(catalog)

print("Ingredient profile creation: PASS")
diagnostic_query = normalize_query(

    "lightweight sunscreen for oily acne-prone skin with zinc oxide under $30"

)



diagnostic_ids = [

    "P454391",

    "P483658",

    "P500112",

]



diagnostic_rows = []



print("=" * 100)

print("INGREDIENT ROOT-CAUSE DIAGNOSTIC")

print("=" * 100)

print(

    "Query:",

    build_query_text(diagnostic_query),

)

print()



for pid in diagnostic_ids:

    result = compute_ingredient_match(

        pid,

        diagnostic_query,

    )



    row = catalog_by_id.loc[pid]



    diagnostic_rows.append({

        "product_id": pid,

        "product_name": safe_text(

            row.get("product_name")

        ),

        "ingredient_data_available": result[

            "ingredient_data_available"

        ],

        "ingredient_match_score": result[

            "ingredient_match_score"

        ],

        "ingredient_coverage": result[

            "ingredient_coverage"

        ],

        "matched_ingredients": result[

            "matched_ingredients"

        ],

        "match_types": result[

            "ingredient_match_types"

        ],

    })



    print(pid, "—", row.get("product_name"))

    print(

        "  available:",

        result["ingredient_data_available"],

    )

    print(

        "  canonical ingredients:",

        result["ingredient_profile"][

            "canonical_ingredients"

        ][:20],

    )

    print(

        "  matched:",

        result["matched_ingredients"],

    )

    print(

        "  score:",

        round(

            result["ingredient_match_score"],

            4,

        ),

    )

    print(

        "  coverage:",

        round(

            result["ingredient_coverage"],

            4,

        ),

    )

    print("-" * 100)



diagnostic_df = pd.DataFrame(

    diagnostic_rows

)



display(diagnostic_df)



# Explicit invariants.

p454 = compute_ingredient_match(

    "P454391",

    diagnostic_query,

)

p483 = compute_ingredient_match(

    "P483658",

    normalize_query("sunscreen containing zinc oxide"),

)



assert p454["ingredient_data_available"] is False

assert p454["ingredient_match_score"] == 0.0

assert p454["ingredient_coverage"] == 0.0

assert p454["matched_ingredients"] == []



assert p483["ingredient_data_available"] is True

assert p483["ingredient_match_score"] > 0.0

assert "zinc" in p483["matched_ingredients"]



print("Ingredient root-cause diagnostic: PASS")
REVIEW_THEME_MAP = {

    "lightweight": [

        "theme_lightweight_share",

        "theme_lightweight_count",

    ],

    "greasy": [

        "theme_greasy_share",

        "theme_greasy_count",

    ],

    "hydrating": [

        "theme_hydrating_share",

        "theme_hydrating_count",

    ],

    "drying": [

        "theme_drying_share",

        "theme_drying_count",

    ],

    "fragrance": [

        "theme_fragrance_share",

        "theme_fragrance_count",

    ],

    "irritation": [

        "theme_irritation_share",

        "theme_irritation_count",

    ],

    "breakout": [

        "theme_breakout_share",

        "theme_breakout_count",

    ],

    "absorption": [

        "theme_absorption_share",

        "theme_absorption_count",

    ],

    "sticky": [

        "theme_sticky_share",

        "theme_sticky_count",

    ],

    "texture": [

        "theme_texture_share",

        "theme_texture_count",

    ],

    "effective": [

        "theme_effective_share",

        "theme_effective_count",

    ],

}





def get_theme_signal(

    row: pd.Series,

    theme: str,

) -> Optional[float]:

    for col in REVIEW_THEME_MAP.get(

        theme,

        [],

    ):

        if col not in row.index:

            continue



        value = pd.to_numeric(

            row[col],

            errors="coerce",

        )



        if pd.notna(value):

            if col.endswith("_count"):

                return float(

                    1.0 - math.exp(

                        -float(value) / 20.0

                    )

                )



            return float(

                np.clip(

                    value,

                    0.0,

                    1.0,

                )

            )



    return None





def review_relevance_score(

    product_id: str,

    q: Dict[str, Any],

) -> Tuple[float, List[str]]:

    pid = str(product_id)



    if pid not in catalog_by_id.index:

        return 0.0, []



    row = catalog_by_id.loc[pid]



    requests: List[

        Tuple[str, int]

    ] = []



    for pref in q.get(

        "effective_preferences",

        [],

    ):

        pref = normalize_token(pref)



        if pref == "lightweight":

            requests.append(

                ("lightweight", +1)

            )

        elif pref == "non_greasy":

            requests.append(

                ("greasy", -1)

            )

        elif pref == "fragrance_free":

            requests.append(

                ("fragrance", -1)

            )

        elif pref == "non_comedogenic":

            requests.append(

                ("breakout", +1)

            )



    concern_to_theme = {

        "hydration": ("hydrating", +1),

        "acne": ("breakout", +1),

        "oil_control": ("greasy", -1),

    }



    for concern in q.get(

        "effective_concerns",

        [],

    ):

        mapping = concern_to_theme.get(

            normalize_token(concern)

        )



        if mapping:

            requests.append(mapping)



    if not requests:

        generic = pd.to_numeric(

            row.get(

                "recommendation_rate",

                np.nan,

            ),

            errors="coerce",

        )



        if pd.notna(generic):

            return (

                float(

                    np.clip(

                        generic,

                        0.0,

                        1.0,

                    )

                ),

                ["overall recommendation rate"],

            )



        return 0.0, []



    scores = []

    evidence = []



    for theme, direction in requests:

        signal = get_theme_signal(

            row,

            theme,

        )



        if signal is None:

            continue



        value = (

            float(signal)

            if direction > 0

            else float(1.0 - signal)

        )



        scores.append(

            np.clip(value, 0.0, 1.0)

        )



        evidence.append(

            theme

        )



    if not scores:

        return 0.0, []



    return (

        float(np.mean(scores)),

        list(dict.fromkeys(evidence)),

    )





def add_review_scores(

    df: pd.DataFrame,

    q: Dict[str, Any],

) -> pd.DataFrame:

    out = df.copy()



    values = [

        review_relevance_score(

            str(pid),

            q,

        )

        for pid in out["product_id"]

    ]



    out["review_relevance_score"] = [

        v[0]

        for v in values

    ]

    out["review_evidence"] = [

        v[1]

        for v in values

    ]



    return out
def skin_preference_score(

    row: pd.Series,

    skin_type: Optional[str],

) -> Tuple[float, bool]:

    if not skin_type:

        return 0.0, False



    col = (

        "skin_share_"

        + normalize_token(skin_type).replace(

            " ",

            "_",

        )

    )



    if col not in row.index:

        return 0.0, False



    value = pd.to_numeric(

        row[col],

        errors="coerce",

    )



    if pd.isna(value):

        return 0.0, False



    return (

        float(

            np.clip(

                value,

                0.0,

                1.0,

            )

        ),

        True,

    )





def descriptor_preference_score(

    row: pd.Series,

    preferences: Sequence[str],

) -> Tuple[float, bool]:

    if not preferences:

        return 0.0, False



    text = normalize_token(

        " ".join(

            safe_text(

                row.get(col, "")

            )

            for col in [

                "product_document",

                "highlights",

                "ingredients_clean",

                "ingredients",

            ]

        )

    )



    scores = []



    for pref in preferences:

        canonical_pref = normalize_token(

            pref

        )



        aliases = PREFERENCE_TERMS.get(

            canonical_pref,

            [canonical_pref],

        )



        scores.append(

            1.0

            if any(

                normalize_token(alias) in text

                for alias in aliases

            )

            else 0.0

        )



    return (

        float(np.mean(scores)),

        True,

    )





def preference_score(

    product_id: str,

    q: Dict[str, Any],

) -> Tuple[float, bool]:

    pid = str(product_id)



    if pid not in catalog_by_id.index:

        return 0.0, False



    row = catalog_by_id.loc[pid]



    signals = []



    skin_score, skin_available = (

        skin_preference_score(

            row,

            q.get("effective_skin_type"),

        )

    )



    if skin_available:

        signals.append(skin_score)



    descriptor_score, descriptor_available = (

        descriptor_preference_score(

            row,

            q.get("effective_preferences", []),

        )

    )



    if descriptor_available:

        signals.append(descriptor_score)



    if not signals:

        return 0.0, False



    return (

        float(np.mean(signals)),

        True,

    )





def add_preference_scores(

    df: pd.DataFrame,

    q: Dict[str, Any],

) -> pd.DataFrame:

    out = df.copy()



    values = [

        preference_score(

            str(pid),

            q,

        )

        for pid in out["product_id"]

    ]



    out["preference_match_score"] = [

        v[0]

        for v in values

    ]

    out["preference_signal_available"] = [

        v[1]

        for v in values

    ]



    return out
rating_series = pd.to_numeric(

    catalog.get(

        "review_avg_rating",

        catalog.get(

            "rating",

            pd.Series(dtype=float),

        ),

    ),

    errors="coerce",

).dropna()



RATING_GLOBAL_MEAN = (

    float(rating_series.mean())

    if not rating_series.empty

    else 3.5

)



RATING_PRIOR_COUNT = 50.0



print(

    "Rating prior mean:",

    round(RATING_GLOBAL_MEAN, 4),

)

print(

    "Rating prior count:",

    RATING_PRIOR_COUNT,

)





def rating_quality_score(

    product_id: str,

) -> float:

    pid = str(product_id)



    if pid not in catalog_by_id.index:

        return 0.0



    row = catalog_by_id.loc[pid]



    rating = numeric_value(

        row,

        [

            "review_avg_rating",

            "rating",

        ],

        default=np.nan,

    )



    count = numeric_value(

        row,

        [

            "review_count_observed",

            "reviews",

        ],

        default=0.0,

    )



    if not np.isfinite(rating):

        return 0.0



    adjusted = (

        count * rating

        + RATING_PRIOR_COUNT

        * RATING_GLOBAL_MEAN

    ) / (

        count

        + RATING_PRIOR_COUNT

    )



    return float(

        np.clip(

            (adjusted - 1.0) / 4.0,

            0.0,

            1.0,

        )

    )





def add_rating_scores(

    df: pd.DataFrame,

) -> pd.DataFrame:

    out = df.copy()



    out["rating_quality_score"] = [

        rating_quality_score(

            str(pid)

        )

        for pid in out["product_id"]

    ]



    return out
RANKING_WEIGHTS = {

    "semantic": 0.40,

    "ingredient": 0.25,

    "review": 0.15,

    "preference": 0.10,

    "rating": 0.05,

    "diversity": 0.05,

}



print("Ranking weights:")

display(pd.DataFrame([

    {

        "signal": key,

        "weight": value,

    }

    for key, value in RANKING_WEIGHTS.items()

]))



assert math.isclose(

    sum(RANKING_WEIGHTS.values()),

    1.0,

    abs_tol=1e-9,

)

print("Weight validation: PASS")
embedding_position = {

    str(pid): idx

    for idx, pid in enumerate(

        catalog["product_id"].astype(str)

    )

}





def embedding_similarity(

    product_a: str,

    product_b: str,

) -> float:

    ia = embedding_position.get(

        str(product_a)

    )

    ib = embedding_position.get(

        str(product_b)

    )



    if ia is None or ib is None:

        return 0.0



    return float(

        np.clip(

            np.dot(

                product_embeddings[ia],

                product_embeddings[ib],

            ),

            -1.0,

            1.0,

        )

    )





def diversity_score_for_candidate(

    row: pd.Series,

    selected_rows: Sequence[pd.Series],

) -> float:

    if not selected_rows:

        return 1.0



    pid = str(row["product_id"])



    max_embedding_similarity = max(

        embedding_similarity(

            pid,

            str(other["product_id"]),

        )

        for other in selected_rows

    )



    candidate_brand = normalize_token(

        row.get("brand_name", "")

    )

    candidate_category = normalize_token(

        row.get(

            "secondary_category",

            row.get(

                "primary_category",

                "",

            ),

        )

    )



    repetition_penalty = 0.0



    for other in selected_rows:

        if (

            candidate_brand

            and candidate_brand

            == normalize_token(

                other.get("brand_name", "")

            )

        ):

            repetition_penalty = max(

                repetition_penalty,

                0.10,

            )



        if (

            candidate_category

            and candidate_category

            == normalize_token(

                other.get(

                    "secondary_category",

                    other.get(

                        "primary_category",

                        "",

                    ),

                )

            )

        ):

            repetition_penalty = max(

                repetition_penalty,

                0.05,

            )



    return float(

        np.clip(

            1.0

            - (

                0.85

                * max_embedding_similarity

                + repetition_penalty

            ),

            0.0,

            1.0,

        )

    )





def final_score(

    row: pd.Series,

    diversity: float,

) -> float:

    components = {

        "semantic": float(

            np.clip(

                row.get(

                    "semantic_similarity",

                    0.0,

                ),

                0.0,

                1.0,

            )

        ),

        "ingredient": float(

            np.clip(

                row.get(

                    "ingredient_match_score",

                    0.0,

                ),

                0.0,

                1.0,

            )

        ),

        "review": float(

            np.clip(

                row.get(

                    "review_relevance_score",

                    0.0,

                ),

                0.0,

                1.0,

            )

        ),

        "preference": float(

            np.clip(

                row.get(

                    "preference_match_score",

                    0.0,

                ),

                0.0,

                1.0,

            )

        ),

        "rating": float(

            np.clip(

                row.get(

                    "rating_quality_score",

                    0.0,

                ),

                0.0,

                1.0,

            )

        ),

        "diversity": float(

            np.clip(

                diversity,

                0.0,

                1.0,

            )

        ),

    }



    weights = dict(RANKING_WEIGHTS)



    # Missing ingredient data is excluded from the denominator

    # instead of becoming a false negative.

    if not bool(

        row.get(

            "ingredient_data_available",

            True,

        )

    ):

        weights.pop(

            "ingredient",

            None,

        )



    denominator = sum(

        weights.values()

    )



    normalized_weights = {

        key: weight / denominator

        for key, weight in weights.items()

    }



    score = sum(

        normalized_weights[key]

        * components[key]

        for key in normalized_weights

    )



    return float(

        np.clip(

            score,

            0.0,

            1.0,

        )

    )





def rank_candidates(

    df: pd.DataFrame,

    top_k: int = 5,

) -> pd.DataFrame:

    if df.empty:

        return df.copy()



    working = df.copy().reset_index(

        drop=True

    )



    selected_indices = []

    selected_rows: List[pd.Series] = []

    final_scores_map = {}

    diversity_map = {}



    target = min(

        int(top_k),

        len(working),

    )



    for _ in range(target):

        best_idx = None

        best_score = -float("inf")

        best_diversity = 0.0



        for idx, row in working.iterrows():

            if idx in selected_indices:

                continue



            diversity = diversity_score_for_candidate(

                row,

                selected_rows,

            )



            score = final_score(

                row,

                diversity,

            )



            if score > best_score:

                best_idx = idx

                best_score = score

                best_diversity = diversity



        if best_idx is None:

            break



        selected_indices.append(best_idx)

        selected_rows.append(

            working.loc[best_idx]

        )

        final_scores_map[best_idx] = best_score

        diversity_map[best_idx] = best_diversity



    ranked = working.loc[

        selected_indices

    ].copy()



    ranked["diversity_score"] = [

        diversity_map[idx]

        for idx in selected_indices

    ]



    ranked["final_score"] = [

        final_scores_map[idx]

        for idx in selected_indices

    ]



    return ranked.sort_values(

        "final_score",

        ascending=False,

    ).reset_index(drop=True)
def explanation_for_product(

    row: pd.Series,

    q: Dict[str, Any],

) -> Dict[str, Any]:

    reasons = []



    requested_category = normalize_token(

        q.get("effective_category")

    )



    category_text = normalize_token(

        " ".join([

            safe_text(

                row.get(

                    "primary_category",

                    "",

                )

            ),

            safe_text(

                row.get(

                    "secondary_category",

                    "",

                )

            ),

            safe_text(

                row.get(

                    "tertiary_category",

                    "",

                )

            ),

        ])

    )



    if (

        requested_category

        and requested_category in category_text

    ):

        reasons.append(

            f"Matches requested {requested_category} category"

        )



    budget = q.get(

        "effective_budget_max"

    )

    price = pd.to_numeric(

        row.get(

            "effective_price_usd",

            np.nan,

        ),

        errors="coerce",

    )



    if (

        budget is not None

        and pd.notna(price)

        and price <= float(budget)

    ):

        reasons.append(

            f"Within budget (${float(price):.2f} ≤ ${float(budget):.2f})"

        )



    semantic = float(

        row.get(

            "semantic_similarity",

            0.0,

        )

    )



    if semantic >= 0.75:

        reasons.append(

            "Strong semantic match"

        )

    elif semantic >= 0.55:

        reasons.append(

            "Good semantic match"

        )



    available = bool(

        row.get(

            "ingredient_data_available",

            False,

        )

    )



    matched = row.get(

        "matched_ingredients",

        row.get(

            "matched_ingredient_terms",

            [],

        ),

    )



    if isinstance(

        matched,

        str,

    ):

        try:

            matched = ast.literal_eval(

                matched

            )

        except Exception:

            matched = [

                matched

            ]



    matched = list(

        matched

    )



    coverage = float(

        row.get(

            "ingredient_coverage",

            0.0,

        )

    )



    if available and matched:

        reasons.append(

            "Ingredient signals matched: "

            + ", ".join(

                matched[:5]

            )

        )

        reasons.append(

            f"Ingredient coverage: {coverage:.0%}"

        )

    elif not available:

        reasons.append(

            "Ingredient information unavailable in catalog"

        )



    evidence = row.get(

        "review_evidence",

        [],

    )



    if isinstance(

        evidence,

        str,

    ):

        try:

            evidence = ast.literal_eval(

                evidence

            )

        except Exception:

            evidence = [evidence]



    if evidence:

        reasons.append(

            "Review evidence: "

            + ", ".join(

                str(x).replace(

                    "_",

                    " ",

                )

                for x in list(evidence)[:4]

            )

        )



    skin = normalize_token(

        q.get("effective_skin_type")

    )



    if skin:

        skin_col = (

            f"skin_share_{skin.replace(' ', '_')}"

        )



        if skin_col in row.index:

            skin_share = pd.to_numeric(

                row.get(skin_col),

                errors="coerce",

            )



            if (

                pd.notna(skin_share)

                and float(skin_share) > 0

            ):

                reasons.append(

                    f"Review audience includes {skin} skin "

                    f"({float(skin_share):.0%})"

                )



    if float(

        row.get(

            "rating_quality_score",

            0.0,

        )

    ) >= 0.80:

        reasons.append(

            "Strong rating quality"

        )



    if not reasons:

        reasons.append(

            "Selected from the highest-scoring valid candidates"

        )



    return {

        "reasons": reasons[:7],

        "ingredient_data_available": available,

        "matched_ingredients": matched[:10],

        "ingredient_coverage": round(

            coverage,

            4,

        ),

        "ingredient_match_types": row.get(

            "ingredient_match_types",

            {},

        ),

        "review_evidence": list(

            evidence

        )[:10],

        "score_breakdown": {

            "semantic_similarity": round(

                float(

                    row.get(

                        "semantic_similarity",

                        0.0,

                    )

                ),

                4,

            ),

            "ingredient_match": round(

                float(

                    row.get(

                        "ingredient_match_score",

                        0.0,

                    )

                ),

                4,

            ),

            "ingredient_coverage": round(

                coverage,

                4,

            ),

            "review_relevance": round(

                float(

                    row.get(

                        "review_relevance_score",

                        0.0,

                    )

                ),

                4,

            ),

            "preference_match": round(

                float(

                    row.get(

                        "preference_match_score",

                        0.0,

                    )

                ),

                4,

            ),

            "rating_quality": round(

                float(

                    row.get(

                        "rating_quality_score",

                        0.0,

                    )

                ),

                4,

            ),

            "diversity": round(

                float(

                    row.get(

                        "diversity_score",

                        0.0,

                    )

                ),

                4,

            ),

            "final_score": round(

                float(

                    row.get(

                        "final_score",

                        0.0,

                    )

                ),

                4,

            ),

        },

    }
# ============================================================

# 20. Build the Final recommend() Function

# ============================================================



def add_ingredient_scores(

    df: pd.DataFrame,

    q: Dict[str, Any],

) -> pd.DataFrame:

    """

    Add the canonical ingredient-matching results to each candidate.



    This function uses the same compute_ingredient_match() function

    used by the ingredient diagnostics, so the recommendation results

    cannot drift from the diagnostic results.

    """

    out = df.copy()



    results = []



    for product_id in out["product_id"].astype(str):

        result = compute_ingredient_match(

            product_id,

            q,

        )

        results.append(result)



    out["ingredient_data_available"] = [

        result["ingredient_data_available"]

        for result in results

    ]



    out["ingredient_match_score"] = [

        float(result["ingredient_match_score"])

        for result in results

    ]



    out["ingredient_coverage"] = [

        float(result["ingredient_coverage"])

        for result in results

    ]



    out["matched_ingredients"] = [

        result["matched_ingredients"]

        for result in results

    ]



    # Keep the old column name too for compatibility with any

    # earlier diagnostic/display cells.

    out["matched_ingredient_terms"] = [

        result["matched_ingredients"]

        for result in results

    ]



    out["ingredient_match_types"] = [

        result["ingredient_match_types"]

        for result in results

    ]



    return out





print("Ingredient scoring helper loaded successfully.")

print("Testing helper on current candidate set...")



# Run only when filtered_example exists from the previous test section.

if "filtered_example" in globals() and not filtered_example.empty:

    filtered_example = add_ingredient_scores(

        filtered_example,

        normalized_example,

    )



    print("Ingredient scoring result:")

    display(

        filtered_example[

            [

                "product_id",

                "product_name",

                "ingredient_data_available",

                "ingredient_match_score",

                "ingredient_coverage",

                "matched_ingredients",

                "ingredient_match_types",

            ]

        ].head(10)

    )



print("\n" + "=" * 90)

print("FINAL recommend() FUNCTION")

print("=" * 90)





def recommend(

    query: Optional[str] = None,

    skin_type: Optional[str] = None,

    concerns: Optional[Sequence[str]] = None,

    category: Optional[str] = None,

    budget_max: Optional[float] = None,

    preferred_terms: Optional[Sequence[str]] = None,

    avoid_ingredients: Optional[Sequence[str]] = None,

    candidate_k: int = 50,

    top_k: int = 5,

) -> Dict[str, Any]:



    started = time.perf_counter()



    # --------------------------------------------------------

    # 1. Normalize user input

    # --------------------------------------------------------

    q = normalize_query(

        query=query,

        skin_type=skin_type,

        concerns=concerns,

        category=category,

        budget_max=budget_max,

        preferred_terms=preferred_terms,

        avoid_ingredients=avoid_ingredients,

    )



    query_text = build_query_text(q)



    if not query_text:

        raise ValueError(

            "Please provide a query or at least one "

            "structured recommendation signal."

        )



    # --------------------------------------------------------

    # 2. Semantic candidate retrieval

    # --------------------------------------------------------

    retrieval_started = time.perf_counter()



    retrieved = semantic_retrieve(

        q,

        candidate_k=candidate_k,

    )



    retrieval_ms = (

        time.perf_counter()

        - retrieval_started

    ) * 1000



    # --------------------------------------------------------

    # 3. Hard constraints

    # --------------------------------------------------------

    filtered, filter_stats = apply_hard_filters(

        retrieved,

        q,

    )



    # --------------------------------------------------------

    # 4. No valid candidates

    # --------------------------------------------------------

    if filtered.empty:



        total_ms = (

            time.perf_counter()

            - started

        ) * 1000



        return {

            "status": "no_high_confidence_match",

            "query": q,

            "query_text": query_text,

            "recommendations": [],

            "filter_stats": filter_stats,

            "latency_ms": {

                "retrieval": round(

                    retrieval_ms,

                    2,

                ),

                "total": round(

                    total_ms,

                    2,

                ),

            },

            "message": (

                "No products satisfied the requested constraints. "

                "Try relaxing the budget, category, or ingredient constraints."

            ),

        }



    # --------------------------------------------------------

    # 5. Ingredient scoring

    # --------------------------------------------------------

    filtered = add_ingredient_scores(

        filtered,

        q,

    )



    # --------------------------------------------------------

    # 6. Review scoring

    # --------------------------------------------------------

    filtered = add_review_scores(

        filtered,

        q,

    )



    # --------------------------------------------------------

    # 7. Preference scoring

    # --------------------------------------------------------

    filtered = add_preference_scores(

        filtered,

        q,

    )



    # --------------------------------------------------------

    # 8. Rating quality

    # --------------------------------------------------------

    filtered = add_rating_scores(

        filtered,

    )



    # --------------------------------------------------------

    # 9. Final ranking

    # --------------------------------------------------------

    ranked = rank_candidates(

        filtered,

        top_k=top_k,

    )



    # --------------------------------------------------------

    # 10. Build clean recommendation response

    # --------------------------------------------------------

    recommendations = []



    for _, row in ranked.iterrows():



        explanation = explanation_for_product(

            row,

            q,

        )



        price = pd.to_numeric(

            row.get(

                "effective_price_usd",

                np.nan,

            ),

            errors="coerce",

        )



        recommendations.append(

            {

                "product_id": str(

                    row["product_id"]

                ),



                "product_name": safe_text(

                    row.get(

                        "product_name"

                    )

                ),



                "brand_name": safe_text(

                    row.get(

                        "brand_name"

                    )

                ),



                "primary_category": safe_text(

                    row.get(

                        "primary_category"

                    )

                ),



                "secondary_category": safe_text(

                    row.get(

                        "secondary_category"

                    )

                ),



                "price_usd": (

                    float(price)

                    if pd.notna(price)

                    else None

                ),



                "final_score": round(

                    float(

                        row["final_score"]

                    ),

                    4,

                ),



                "ingredient_data_available": (

                    explanation[

                        "ingredient_data_available"

                    ]

                ),



                "matched_ingredients": (

                    explanation[

                        "matched_ingredients"

                    ]

                ),



                "ingredient_coverage": (

                    explanation[

                        "ingredient_coverage"

                    ]

                ),



                "ingredient_match_types": (

                    explanation[

                        "ingredient_match_types"

                    ]

                ),



                "review_evidence": (

                    explanation[

                        "review_evidence"

                    ]

                ),



                "reasons": (

                    explanation[

                        "reasons"

                    ]

                ),



                "score_breakdown": (

                    explanation[

                        "score_breakdown"

                    ]

                ),

            }

        )



    total_ms = (

        time.perf_counter()

        - started

    ) * 1000



    return {

        "status": "ok",

        "query": q,

        "query_text": query_text,

        "recommendations": recommendations,

        "filter_stats": filter_stats,

        "latency_ms": {

            "retrieval": round(

                retrieval_ms,

                2,

            ),

            "total": round(

                total_ms,

                2,

            ),

        },

    }





# ============================================================

# Demo execution

# ============================================================



demo_result = recommend(

    query="lightweight moisturizer for dry skin",

    top_k=5,

)



print("\nFINAL DEMO RESULT")

print("=" * 90)



print(

    "Status:",

    demo_result["status"],

)



print(

    "Query:",

    demo_result["query_text"],

)



print(

    "Recommendations:",

    len(

        demo_result[

            "recommendations"

        ]

    ),

)



print(

    "Total latency (ms):",

    demo_result[

        "latency_ms"

    ]["total"],

)



for rank, item in enumerate(

    demo_result[

        "recommendations"

    ],

    start=1,

):



    print(

        f"\n{rank}. "

        f"{item['product_name']} "

        f"(score={item['final_score']:.4f})"

    )



    print(

        "   Brand:",

        item["brand_name"],

    )



    print(

        "   Price:",

        item["price_usd"],

    )



    print(

        "   Ingredient data:",

        item[

            "ingredient_data_available"

        ],

    )



    print(

        "   Matched ingredients:",

        item[

            "matched_ingredients"

        ],

    )



    print(

        "   Ingredient coverage:",

        item[

            "ingredient_coverage"

        ],

    )



    print(

        "   Reasons:",

        " | ".join(

            item[

                "reasons"

            ][:4]

        ),

    )



print("\nrecommend() function: READY")
TEST_CASES = [

    {

        "name": "Oily acne-prone sunscreen",

        "kwargs": {

            "query": (

                "lightweight sunscreen for oily "

                "acne-prone skin under $30"

            ),

            "top_k": 5,

        },

    },

    {

        "name": "Dry skin moisturizer",

        "kwargs": {

            "skin_type": "dry",

            "concerns": ["hydration"],

            "category": "moisturizer",

            "budget_max": 40,

            "preferred_terms": ["hydrating"],

            "top_k": 5,

        },

    },

    {

        "name": "Acne treatment",

        "kwargs": {

            "query": (

                "acne treatment with ingredients "

                "associated with breakout care"

            ),

            "top_k": 5,

        },

    },

    {

        "name": "Budget cleanser",

        "kwargs": {

            "category": "cleanser",

            "budget_max": 20,

            "top_k": 5,

        },

    },

    {

        "name": "Sensitive fragrance-free moisturizer",

        "kwargs": {

            "query": (

                "fragrance-free moisturizer "

                "for sensitive skin"

            ),

            "top_k": 5,

        },

    },

]



test_summary = []



for case in TEST_CASES:

    print("=" * 100)

    print(case["name"])

    print("=" * 100)



    result = recommend(

        **case["kwargs"]

    )



    print(

        "Status:",

        result["status"],

    )

    print(

        "Candidates after hard filters:",

        result["filter_stats"].get(

            "after_filter"

        ),

    )



    rows = []



    for rank, item in enumerate(

        result["recommendations"],

        start=1,

    ):

        rows.append({

            "rank": rank,

            "product_id": item["product_id"],

            "product": item["product_name"],

            "brand": item["brand_name"],

            "price": item["price_usd"],

            "score": item["final_score"],

            "ingredients": ", ".join(

                item["matched_ingredients"]

            ),

            "reasons": " | ".join(

                item["reasons"][:3]

            ),

        })



    if rows:

        display(

            pd.DataFrame(rows)

        )



    test_summary.append({

        "test": case["name"],

        "status": result["status"],

        "recommendations": len(

            result["recommendations"]

        ),

        "latency_ms": result["latency_ms"][

            "total"

        ],

    })



print("\nTest summary:")

display(

    pd.DataFrame(test_summary)

)
ingredient_tests = [

    (

        "zinc oxide",

        "P483658",

    ),

    (

        "zinc",

        "P483658",

    ),

    (

        "niacinamide",

        "P483658",

    ),

    (

        "salicylic acid",

        "P500112",

    ),

]



print("=" * 100)

print("INGREDIENT SANITY TESTS")

print("=" * 100)



for ingredient, pid in ingredient_tests:

    q = normalize_query(

        f"skincare product containing {ingredient}"

    )



    result = compute_ingredient_match(

        pid,

        q,

    )



    print(

        f"{ingredient:20s} + {pid}: "

        f"available={result['ingredient_data_available']}, "

        f"score={result['ingredient_match_score']:.4f}, "

        f"coverage={result['ingredient_coverage']:.4f}, "

        f"matched={result['matched_ingredients']}, "

        f"type={result['ingredient_match_types']}"

    )



zinc = compute_ingredient_match(

    "P483658",

    normalize_query(

        "sunscreen containing zinc oxide"

    ),

)



missing = compute_ingredient_match(

    "P454391",

    normalize_query(

        "sunscreen containing zinc"

    ),

)



assert zinc["ingredient_data_available"] is True

assert zinc["ingredient_match_score"] > 0

assert "zinc" in zinc[

    "matched_ingredients"

]



assert missing[

    "ingredient_data_available"

] is False



assert missing[

    "ingredient_match_score"

] == 0



assert missing[

    "ingredient_coverage"

] == 0



assert missing[

    "matched_ingredients"

] == []



print(

    "\nIngredient sanity tests: PASS"

)
EDGE_CASES = [

    (

        "Empty input",

        {},

    ),

    (

        "Impossible budget",

        {

            "query": "sunscreen for oily skin",

            "budget_max": 0.01,

            "top_k": 5,

        },

    ),

    (

        "Unknown avoided ingredient",

        {

            "query": "moisturizer for dry skin",

            "avoid_ingredients": [

                "ingredient-that-does-not-exist"

            ],

            "top_k": 5,

        },

    ),

    (

        "Extremely restrictive request",

        {

            "query": (

                "very specific sunscreen "

                "combination with no likely match"

            ),

            "category": "sunscreen",

            "budget_max": 1,

            "avoid_ingredients": ["water"],

            "top_k": 5,

        },

    ),

    (

        "Category-only query",

        {

            "category": "cleanser",

            "top_k": 5,

        },

    ),

]



edge_results = []



for name, kwargs in EDGE_CASES:

    print("=" * 100)

    print(name)

    print("=" * 100)



    try:

        result = recommend(

            **kwargs

        )



        print(

            "Status:",

            result["status"],

        )

        print(

            "Recommendations:",

            len(result["recommendations"]),

        )



        edge_results.append({

            "case": name,

            "status": result["status"],

            "recommendations": len(

                result["recommendations"]

            ),

            "error": "",

        })



    except ValueError as exc:

        # Invalid user input should be a controlled validation error.

        print(

            "Controlled input validation:",

            str(exc),

        )



        edge_results.append({

            "case": name,

            "status": "controlled_validation",

            "recommendations": 0,

            "error": str(exc),

        })



    except Exception as exc:

        raise RuntimeError(

            f"Unexpected engine error in edge case '{name}': {exc}"

        ) from exc



display(

    pd.DataFrame(edge_results)

)



assert (

    edge_results[0]["status"]

    == "controlled_validation"

)



print(

    "Edge-case handling: PASS"

)
def sensitivity_rank_scores(

    df: pd.DataFrame,

    ingredient_weight: float,

) -> pd.DataFrame:

    ingredient_weight = float(

        np.clip(

            ingredient_weight,

            0.0,

            1.0,

        )

    )



    remaining = 1.0 - ingredient_weight



    base_other = {

        "semantic": 0.40,

        "review": 0.15,

        "preference": 0.10,

        "rating": 0.05,

        "diversity": 0.05,

    }



    other_sum = sum(

        base_other.values()

    )



    scale = (

        remaining / other_sum

        if other_sum

        else 0.0

    )



    weights = {

        "semantic": base_other["semantic"] * scale,

        "ingredient": ingredient_weight,

        "review": base_other["review"] * scale,

        "preference": base_other["preference"] * scale,

        "rating": base_other["rating"] * scale,

        "diversity": base_other["diversity"] * scale,

    }



    rows = []



    for _, row in df.iterrows():

        components = {

            key: float(

                np.clip(

                    row.get(

                        {

                            "semantic": "semantic_similarity",

                            "ingredient": "ingredient_match_score",

                            "review": "review_relevance_score",

                            "preference": "preference_match_score",

                            "rating": "rating_quality_score",

                        }.get(key, ""),

                        0.0,

                    ),

                    0.0,

                    1.0,

                )

            )

            for key in [

                "semantic",

                "ingredient",

                "review",

                "preference",

                "rating",

            ]

        }



        components["diversity"] = 1.0



        if not bool(

            row.get(

                "ingredient_data_available",

                True,

            )

        ):

            weights_for_product = dict(weights)

            weights_for_product.pop(

                "ingredient",

                None,

            )

        else:

            weights_for_product = dict(weights)



        denom = sum(

            weights_for_product.values()

        )



        score = (

            sum(

                weights_for_product[k]

                * components[k]

                for k in weights_for_product

            )

            / denom

            if denom

            else 0.0

        )



        rows.append({

            "product_id": row["product_id"],

            "product_name": row.get(

                "product_name",

                "",

            ),

            "score": score,

        })



    return pd.DataFrame(rows)





sensitivity_q = normalize_query(

    "lightweight sunscreen for oily acne-prone skin under $30"

)



sens_retrieved = semantic_retrieve(

    sensitivity_q,

    candidate_k=30,

)



sens_filtered, _ = apply_hard_filters(

    sens_retrieved,

    sensitivity_q,

)



sens_filtered = add_ingredient_scores(

    sens_filtered,

    sensitivity_q,

)



sens_filtered = add_review_scores(

    sens_filtered,

    sensitivity_q,

)



sens_filtered = add_preference_scores(

    sens_filtered,

    sensitivity_q,

)



sens_filtered = add_rating_scores(

    sens_filtered,

)



sens_filtered["diversity_score"] = 1.0



sensitivity_outputs = []



if not sens_filtered.empty:

    for weight in [

        0.15,

        0.25,

        0.40,

    ]:

        temp = sensitivity_rank_scores(

            sens_filtered,

            weight,

        ).sort_values(

            "score",

            ascending=False,

        ).head(5)



        temp = temp.assign(

            ingredient_weight=weight

        )

        sensitivity_outputs.append(

            temp

        )



    sensitivity_df = pd.concat(

        sensitivity_outputs,

        ignore_index=True,

    )



    display(sensitivity_df)

else:

    print(

        "No candidates survived hard filters; sensitivity check is not applicable."

    )



print("Sensitivity analysis: PASS")
# ============================================================

# 25. Save Application Artifacts

# ============================================================



print("=" * 100)

print("SAVING APPLICATION ARTIFACTS")

print("=" * 100)



# ------------------------------------------------------------

# 1. Create the artifact directory

# ------------------------------------------------------------



ARTIFACT_DIR = Path(PROJECT_ROOT) / "data" / "artifacts"

ARTIFACT_DIR.mkdir(

    parents=True,

    exist_ok=True,

)



print("Artifact directory:")

print(ARTIFACT_DIR)

print()





# ------------------------------------------------------------

# 2. Define ALL artifact paths explicitly

# ------------------------------------------------------------



EMBEDDINGS_PATH = (

    ARTIFACT_DIR

    / "product_embeddings.npy"

)



EMBEDDING_IDS_PATH = (

    ARTIFACT_DIR

    / "product_embedding_ids.json"

)



CHROMA_PATH = (

    ARTIFACT_DIR

    / "chroma"

)



ENGINE_CONFIG_PATH = (

    ARTIFACT_DIR

    / "recommendation_engine_config.json"

)



INGREDIENT_PROFILES_PATH = (

    ARTIFACT_DIR

    / "ingredient_profiles.jsonl"

)



APPLICATION_CATALOG_PATH = (

    ARTIFACT_DIR

    / "application_catalog.csv"

)





# ------------------------------------------------------------

# 3. Save embeddings

# ------------------------------------------------------------



np.save(

    EMBEDDINGS_PATH,

    np.asarray(

        product_embeddings,

        dtype=np.float32,

    ),

)



EMBEDDING_IDS_PATH.write_text(

    json.dumps(

        product_ids,

        ensure_ascii=False,

        indent=2,

    ),

    encoding="utf-8",

)





# ------------------------------------------------------------

# 4. Save canonical ingredient profiles

# ------------------------------------------------------------



with INGREDIENT_PROFILES_PATH.open(

    "w",

    encoding="utf-8",

) as handle:



    for product_id, profile in ingredient_profiles.items():



        record = {

            "product_id": str(product_id),

            **profile,

        }



        handle.write(

            json.dumps(

                record,

                ensure_ascii=False,

            )

            + "\n"

        )





# ------------------------------------------------------------

# 5. Save recommendation-engine configuration

# ------------------------------------------------------------



ENGINE_CONFIG = {

    "project": "DermaMatch AI",



    "embedding_model": (

        EMBEDDING_MODEL_NAME

    ),



    "embedding_dimension": int(

        EMBEDDING_DIM

    ),



    "chroma_collection": (

        CHROMA_COLLECTION_NAME

    ),



    "chroma_path": str(

        CHROMA_PATH

    ),



    "candidate_k_default": 50,



    "top_k_default": 5,



    "ranking_weights": {

        key: float(value)

        for key, value

        in RANKING_WEIGHTS.items()

    },



    "ingredient_aliases": (

        INGREDIENT_ALIASES

    ),



    "concern_ingredient_weights": (

        CONCERN_INGREDIENT_WEIGHTS

    ),



    "catalog_rows": int(

        len(catalog)

    ),



    "catalog_columns": int(

        len(catalog.columns)

    ),



    "ingredient_profiles_available": int(

        sum(

            bool(

                profile["available"]

            )

            for profile

            in ingredient_profiles.values()

        )

    ),



    "ingredient_profiles_unavailable": int(

        sum(

            not bool(

                profile["available"]

            )

            for profile

            in ingredient_profiles.values()

        )

    ),



    "generated_at_utc": (

        pd.Timestamp.now(

            tz="UTC"

        ).isoformat()

    ),

}





ENGINE_CONFIG_PATH.write_text(

    json.dumps(

        ENGINE_CONFIG,

        ensure_ascii=False,

        indent=2,

    ),

    encoding="utf-8",

)





# ------------------------------------------------------------

# 6. Save application catalog

# ------------------------------------------------------------



APPLICATION_COLUMNS = [

    column

    for column in [

        "product_id",

        "product_name",

        "brand_name",

        "primary_category",

        "secondary_category",

        "tertiary_category",

        "effective_price_usd",

        "rating",

        "reviews",

        "review_count_observed",

        "recommendation_rate",

        "has_reviews",

        "ingredients",

        "ingredients_clean",

        "ingredient_tokens",

        "ingredient_count",

        "highlights",

        "product_document",

    ]

    if column in catalog.columns

]



catalog[

    APPLICATION_COLUMNS

].to_csv(

    APPLICATION_CATALOG_PATH,

    index=False,

)





# ------------------------------------------------------------

# 7. Verify ChromaDB path

# ------------------------------------------------------------



CHROMA_PATH.mkdir(

    parents=True,

    exist_ok=True,

)





# ------------------------------------------------------------

# 8. Print saved artifacts

# ------------------------------------------------------------



print("Saved artifacts")

print("-" * 100)



print(

    "Embeddings:",

    EMBEDDINGS_PATH,

)



print(

    "Embedding IDs:",

    EMBEDDING_IDS_PATH,

)



print(

    "ChromaDB:",

    CHROMA_PATH,

)



print(

    "Engine config:",

    ENGINE_CONFIG_PATH,

)



print(

    "Ingredient profiles:",

    INGREDIENT_PROFILES_PATH,

)



print(

    "Application catalog:",

    APPLICATION_CATALOG_PATH,

)





# ------------------------------------------------------------

# 9. Final artifact validation

# ------------------------------------------------------------



required_artifacts = [

    EMBEDDINGS_PATH,

    EMBEDDING_IDS_PATH,

    ENGINE_CONFIG_PATH,

    INGREDIENT_PROFILES_PATH,

    APPLICATION_CATALOG_PATH,

]



print("\nArtifact validation")

print("-" * 100)



for artifact in required_artifacts:



    exists = artifact.exists()



    print(

        f"{artifact.name}:",

        "PASS" if exists else "FAIL",

    )



    assert exists, (

        f"Required artifact was not created: {artifact}"

    )





# Additional content checks

assert (

    EMBEDDINGS_PATH.stat().st_size > 0

)



assert (

    EMBEDDING_IDS_PATH.stat().st_size > 0

)



assert (

    ENGINE_CONFIG_PATH.stat().st_size > 0

)



assert (

    INGREDIENT_PROFILES_PATH.stat().st_size > 0

)



assert (

    APPLICATION_CATALOG_PATH.stat().st_size > 0

)



print("\n[PASS] All application artifacts saved successfully.")