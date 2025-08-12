import httpx
import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
import logging

# Import from the root config directory (works with sys.path from streamlit_app_modular.py)
import sys
from pathlib import Path

# Add project root to path if not already there
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import (
    BUNDESTAG_API_BASE_URL,
    BUNDESTAG_API_KEY,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
    RATE_LIMIT_DELAY,
    CACHE_ENABLED,
    CACHE_DIR,
    CACHE_TTL
)
from .models import (
    VorgangListResponse,
    DrucksacheListResponse,
    PlenarprotokollListResponse,
    PersonListResponse,
    AktivitaetListResponse,
    Vorgang,
    Drucksache,
    Plenarprotokoll,
    Person,
    Aktivitaet,
    APIError
)

logger = logging.getLogger(__name__)


class BundestagAPIClient:
    """Client for the German Bundestag DIP API"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or BUNDESTAG_API_KEY
        self.base_url = base_url or BUNDESTAG_API_BASE_URL
        self.session = httpx.Client(timeout=DEFAULT_TIMEOUT)
        
        # Set up authentication header
        self.headers = {
            "Authorization": f"ApiKey {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "Bundestag-RAG-API/1.0"
        }
    
    def _get_cache_path(self, endpoint: str, params: Dict[str, Any]) -> Path:
        """Generate cache file path for request"""
        # Create a hash of the request parameters
        param_str = json.dumps(params, sort_keys=True)
        cache_key = hashlib.md5(f"{endpoint}:{param_str}".encode()).hexdigest()
        return CACHE_DIR / f"{cache_key}.json"
    
    def _load_from_cache(self, cache_path: Path) -> Optional[Dict[str, Any]]:
        """Load response from cache if valid"""
        if not CACHE_ENABLED or not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Check if cache is still valid
            cached_time = datetime.fromisoformat(cached_data['cached_at'])
            if datetime.now() - cached_time < timedelta(seconds=CACHE_TTL):
                logger.debug(f"Cache hit for {cache_path}")
                return cached_data['response']
            else:
                logger.debug(f"Cache expired for {cache_path}")
                cache_path.unlink()  # Remove expired cache
                return None
        except Exception as e:
            logger.warning(f"Error reading cache {cache_path}: {e}")
            return None
    
    def _save_to_cache(self, cache_path: Path, response: Dict[str, Any]):
        """Save response to cache"""
        if not CACHE_ENABLED:
            return
        
        try:
            cache_data = {
                'cached_at': datetime.now().isoformat(),
                'response': response
            }
            
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Response cached to {cache_path}")
        except Exception as e:
            logger.warning(f"Error saving cache {cache_path}: {e}")
    
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request with retry logic and caching"""
        params = params or {}
        
        # Check cache first
        cache_path = self._get_cache_path(endpoint, params)
        cached_response = self._load_from_cache(cache_path)
        if cached_response:
            return cached_response
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(MAX_RETRIES):
            try:
                # Add rate limiting
                if attempt > 0:
                    time.sleep(RATE_LIMIT_DELAY * attempt)
                
                logger.debug(f"Making request to {url} with params: {params}")
                
                response = self.session.get(
                    url,
                    headers=self.headers,
                    params=params
                )
                
                if response.status_code == 200:
                    json_response = response.json()
                    self._save_to_cache(cache_path, json_response)
                    return json_response
                elif response.status_code == 401:
                    raise Exception("Unauthorized: Check your API key")
                elif response.status_code == 404:
                    raise Exception("Not found")
                elif response.status_code == 400:
                    error_data = response.json()
                    raise Exception(f"Bad request: {error_data.get('message', 'Unknown error')}")
                else:
                    logger.warning(f"Request failed with status {response.status_code}: {response.text}")
                    if attempt == MAX_RETRIES - 1:
                        raise Exception(f"Request failed with status {response.status_code}")
                    
            except httpx.TimeoutException:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt == MAX_RETRIES - 1:
                    raise Exception("Request timeout")
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise e
                logger.warning(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
        
        raise Exception("Max retries exceeded")
    
    # Vorgänge (Procedures)
    def get_vorgaenge(self, **filters) -> VorgangListResponse:
        """Get list of procedures"""
        response = self._make_request("vorgang", filters)
        return VorgangListResponse(**response)
    
    def get_vorgang(self, vorgang_id: int) -> Vorgang:
        """Get specific procedure by ID"""
        response = self._make_request(f"vorgang/{vorgang_id}")
        return Vorgang(**response)
    
    # Drucksachen (Documents)
    def get_drucksachen(self, **filters) -> DrucksacheListResponse:
        """Get list of parliamentary documents"""
        response = self._make_request("drucksache", filters)
        return DrucksacheListResponse(**response)
    
    def get_drucksache(self, drucksache_id: int) -> Drucksache:
        """Get specific document by ID"""
        response = self._make_request(f"drucksache/{drucksache_id}")
        return Drucksache(**response)
    
    def get_drucksache_text(self, drucksache_id: int) -> Dict[str, Any]:
        """Get document with full text"""
        return self._make_request(f"drucksache-text/{drucksache_id}")
    
    # Plenarprotokolle (Plenary Protocols)
    def get_plenarprotokolle(self, **filters) -> PlenarprotokollListResponse:
        """Get list of plenary protocols"""
        response = self._make_request("plenarprotokoll", filters)
        return PlenarprotokollListResponse(**response)
    
    def get_plenarprotokoll(self, protokoll_id: int) -> Plenarprotokoll:
        """Get specific protocol by ID"""
        response = self._make_request(f"plenarprotokoll/{protokoll_id}")
        return Plenarprotokoll(**response)
    
    def get_plenarprotokoll_text(self, protokoll_id: int) -> Dict[str, Any]:
        """Get protocol with full text"""
        return self._make_request(f"plenarprotokoll-text/{protokoll_id}")
    
    # Personen (People)
    def get_personen(self, **filters) -> PersonListResponse:
        """Get list of people"""
        response = self._make_request("person", filters)
        return PersonListResponse(**response)
    
    def get_person(self, person_id: int) -> Person:
        """Get specific person by ID"""
        response = self._make_request(f"person/{person_id}")
        return Person(**response)
    
    # Aktivitäten (Activities)
    def get_aktivitaeten(self, **filters) -> AktivitaetListResponse:
        """Get list of activities"""
        response = self._make_request("aktivitaet", filters)
        return AktivitaetListResponse(**response)
    
    def get_aktivitaet(self, aktivitaet_id: int) -> Aktivitaet:
        """Get specific activity by ID"""
        response = self._make_request(f"aktivitaet/{aktivitaet_id}")
        return Aktivitaet(**response)
    
    # Search utilities
    def search_by_title(self, title: str, document_type: str = "drucksache", limit: int = 10) -> List[Dict[str, Any]]:
        """Search documents by title"""
        filters = {
            "f.titel": [title],
            "cursor": "",
            "rows": limit  # Limit API response instead of slicing after
        }
        
        if document_type == "drucksache":
            response = self.get_drucksachen(**filters)
            return response.documents  # No need to slice
        elif document_type == "plenarprotokoll":
            response = self.get_plenarprotokolle(**filters)
            return response.documents  # No need to slice
        elif document_type == "vorgang":
            response = self.get_vorgaenge(**filters)
            return response.documents  # No need to slice
        else:
            raise ValueError(f"Unsupported document type: {document_type}")
    
    def search_by_wahlperiode(self, wahlperiode: int, document_type: str = "drucksache", limit: int = 10) -> List[Dict[str, Any]]:
        """Search documents by electoral period"""
        filters = {
            "f.wahlperiode": [wahlperiode],
            "cursor": "",
            "rows": limit  # Limit API response instead of slicing after
        }
        
        if document_type == "drucksache":
            response = self.get_drucksachen(**filters)
            return response.documents  # No need to slice
        elif document_type == "plenarprotokoll":
            response = self.get_plenarprotokolle(**filters)
            return response.documents  # No need to slice
        elif document_type == "vorgang":
            response = self.get_vorgaenge(**filters)
            return response.documents  # No need to slice
        else:
            raise ValueError(f"Unsupported document type: {document_type}")
    
    def close(self):
        """Close the HTTP session"""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
