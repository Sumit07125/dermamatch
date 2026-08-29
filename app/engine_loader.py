import json
import logging
import pandas as pd
from sentence_transformers import SentenceTransformer
import chromadb
from pathlib import Path
import sys

from .config import (
    APPLICATION_CATALOG_PATH,
    RECOMMENDATION_ENGINE_CONFIG_PATH,
    INGREDIENT_PROFILES_PATH,
    CHROMA_DIR,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL
)

logger = logging.getLogger(__name__)

# Globals to be imported by recommender.py
catalog_by_id = None
catalog = None
engine_config = None
ingredient_profiles = None
embedder = None
chroma_client = None
collection = None
product_embeddings = None
embedding_position = None

def load_engine():
    global catalog_by_id, catalog, engine_config, ingredient_profiles, embedder, chroma_client, collection, product_embeddings, embedding_position

    # Check required paths
    required_paths = [
        ("Application Catalog", APPLICATION_CATALOG_PATH),
        ("Engine Config", RECOMMENDATION_ENGINE_CONFIG_PATH),
        ("Ingredient Profiles", INGREDIENT_PROFILES_PATH),
        ("ChromaDB Directory", CHROMA_DIR)
    ]

    for name, path in required_paths:
        if not path.exists():
            msg = (
                f"\nCRITICAL STARTUP ERROR: Missing required artifact for Part 3.\n"
                f"Item: {name}\n"
                f"Expected location: {path}\n"
                f"How to fix: Ensure the Part 1/Part 2 data pipeline was run and paths are correct."
            )
            logger.error(msg)
            sys.exit(1)

    logger.info("Loading engine config...")
    with open(RECOMMENDATION_ENGINE_CONFIG_PATH, "r", encoding="utf-8") as f:
        engine_config = json.load(f)

    logger.info("Loading ingredient profiles...")
    ingredient_profiles = {}
    with open(INGREDIENT_PROFILES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                profile = json.loads(line)
                ingredient_profiles[str(profile["product_id"])] = profile

    logger.info("Loading application catalog...")
    catalog = pd.read_csv(APPLICATION_CATALOG_PATH, low_memory=False)
    catalog["product_id"] = catalog["product_id"].astype(str)
    catalog_by_id = catalog.set_index("product_id", drop=False)

    logger.info(f"Initializing SentenceTransformer ({EMBEDDING_MODEL})...")
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    logger.info("Connecting to ChromaDB...")
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = chroma_client.get_collection(name=CHROMA_COLLECTION_NAME)
    
    logger.info("Loading product embeddings from Chroma...")
    all_data = collection.get(include=['embeddings'])
    product_embeddings = all_data['embeddings']
    embedding_position = {str(pid): i for i, pid in enumerate(all_data['ids'])}
    
    logger.info("Recommendation Engine Loaded Successfully!")

