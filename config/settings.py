import os
from pathlib import Path
from typing import Optional

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# API Configuration
BUNDESTAG_API_BASE_URL = "https://search.dip.bundestag.de/api/v1"
BUNDESTAG_API_KEY = os.getenv("BUNDESTAG_API_KEY", "")

# Request Configuration
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 1.0  # seconds between requests

# Cache Configuration
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
CACHE_TTL = 3600  # 1 hour in seconds

# Vector Storage Configuration
VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vectors"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Default local model
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"  # Updated OpenAI embedding model (more efficient)

# RAG Configuration
MAX_CONTEXT_LENGTH = 4000
TOP_K_RESULTS = 5
SIMILARITY_THRESHOLD = 0.7

# CLI Configuration
DEFAULT_FORMAT = "json"
MAX_DISPLAY_RESULTS = 10

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Create necessary directories
CACHE_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
