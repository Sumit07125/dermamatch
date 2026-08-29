import os
from pathlib import Path

# Project Roots
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
PROCESSED_DIR = DATA_DIR / "processed"

# API Config
API_HOST = os.getenv("DERMAMATCH_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("DERMAMATCH_API_PORT", 5000))
DEBUG = os.getenv("DERMAMATCH_DEBUG", "false").lower() == "true"

# Recommendation Engine Config
TOP_K = int(os.getenv("DERMAMATCH_TOP_K", 5))
CANDIDATE_K = int(os.getenv("DERMAMATCH_CANDIDATE_K", 50))
EMBEDDING_MODEL = os.getenv("DERMAMATCH_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# Paths
RECOMMENDATION_CATALOG_PATH = PROCESSED_DIR / "recommendation_catalog.csv"
APPLICATION_CATALOG_PATH = ARTIFACTS_DIR / "application_catalog.csv"
RECOMMENDATION_ENGINE_CONFIG_PATH = ARTIFACTS_DIR / "recommendation_engine_config.json"
INGREDIENT_PROFILES_PATH = ARTIFACTS_DIR / "ingredient_profiles.jsonl"
PRODUCT_EMBEDDINGS_PATH = ARTIFACTS_DIR / "product_embeddings.npy"
PRODUCT_EMBEDDING_IDS_PATH = ARTIFACTS_DIR / "product_embedding_ids.json"
CHROMA_DIR = ARTIFACTS_DIR / "chroma"
CHROMA_COLLECTION_NAME = "dermamatch_products"
