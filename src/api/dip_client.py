"""
DIP (Dokumentations- und Informationssystem für Parlamentsmaterialien) API Client
Specialized client for searching and retrieving PDF documents from the Bundestag API.
"""
import httpx
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pathlib import Path
import hashlib
import json

logger = logging.getLogger(__name__)


class DIPAPIClient:
    """Client for Bundestag DIP API with focus on PDF document search and retrieval"""
    
    def __init__(self, api_key: str, base_url: str = "https://search.dip.bundestag.de/api/v1"):
        """
        Initialize the DIP API client.
        
        Args:
            api_key: API key for authentication
            base_url: Base URL for the API (default: official DIP API)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = httpx.Client(timeout=30.0)
        self.headers = {
            "Authorization": f"ApiKey {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "Bundestag-PDF-Browser/1.0"
        }
        logger.info(f"DIP API Client initialized with base URL: {self.base_url}")
    
    def _make_request(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> Dict[str, Any]:
        """
        Make a request to the API with retry logic.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            method: HTTP method (GET, POST, etc.)
            
        Returns:
            JSON response as dictionary
            
        Raises:
            httpx.HTTPError: On request failures after retries
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Log request (without exposing API key)
        safe_url = url.replace(self.api_key, "***REDACTED***") if self.api_key in url else url
        logger.debug(f"API Request: {method} {safe_url} with params: {params}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                headers=self.headers
            )
            
            logger.debug(f"API Response: Status {response.status_code}")
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
    )
    def search_documents(
        self,
        query: str,
        doc_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        wahlperiode: Optional[int] = None,
        offset: int = 0,
        limit: int = 20,
        fulltext: bool = True
    ) -> Dict[str, Any]:
        """
        Search for documents with PDF content.
        
        Args:
            query: Search query string
            doc_type: Document type filter (drucksache, plenarprotokoll, vorgang)
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            wahlperiode: Parliamentary term number
            offset: Pagination offset
            limit: Number of results per page
            fulltext: Whether to search in full text (True) or metadata only (False)
            
        Returns:
            API response with search results
        """
        params = {
            "f.datum.start": date_from,
            "f.datum.end": date_to,
            "cursor": offset,
            "pageSize": limit
        }
        
        # Add query parameter based on fulltext setting
        if fulltext:
            params["f.volltext"] = query
        else:
            params["f.titel"] = query
        
        # Add document type filter
        if doc_type:
            params["f.typ"] = doc_type
        
        # Add wahlperiode filter
        if wahlperiode:
            params["f.wahlperiode"] = wahlperiode
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        logger.info(f"Searching documents with query='{query}', type={doc_type}, offset={offset}")
        
        # Different endpoints based on document type
        if doc_type == "drucksache":
            endpoint = "drucksache"
        elif doc_type == "plenarprotokoll":
            endpoint = "plenarprotokoll"
        elif doc_type == "vorgang":
            endpoint = "vorgang"
        else:
            # Use generic search endpoint
            endpoint = "vorgang"  # Most comprehensive endpoint
        
        return self._make_request(endpoint, params)
    
    def get_document_by_id(self, doc_id: str, doc_type: str = "vorgang") -> Dict[str, Any]:
        """
        Get a specific document by ID.
        
        Args:
            doc_id: Document ID
            doc_type: Document type (drucksache, plenarprotokoll, vorgang)
            
        Returns:
            Document details
        """
        endpoint = f"{doc_type}/{doc_id}"
        logger.info(f"Fetching document: {endpoint}")
        return self._make_request(endpoint)
    
    def extract_pdf_url(self, document: Dict[str, Any]) -> Optional[str]:
        """
        Extract PDF URL from a document response.
        
        Args:
            document: Document data from API
            
        Returns:
            PDF URL if available, None otherwise
        """
        # Try different possible fields where PDF URL might be stored
        pdf_fields = [
            "fundstelle.pdf_url",
            "fundstelle.dokumentUrl",
            "drucksachetext",
            "dokumentUrl",
            "pdf_url"
        ]
        
        for field in pdf_fields:
            # Navigate nested fields
            parts = field.split('.')
            value = document
            try:
                for part in parts:
                    value = value.get(part, {})
                if value and isinstance(value, str) and ('pdf' in value.lower() or 'http' in value):
                    logger.debug(f"Found PDF URL in field '{field}': {value}")
                    return value
            except (AttributeError, TypeError):
                continue
        
        # Check if there's a list of documents/files
        if 'fundstelle' in document and isinstance(document['fundstelle'], dict):
            fundstelle = document['fundstelle']
            if 'dokument' in fundstelle:
                docs = fundstelle['dokument']
                if isinstance(docs, list):
                    for doc in docs:
                        if isinstance(doc, dict) and 'dokumentUrl' in doc:
                            url = doc['dokumentUrl']
                            if 'pdf' in url.lower():
                                logger.debug(f"Found PDF URL in dokument list: {url}")
                                return url
        
        logger.debug(f"No PDF URL found in document: {document.get('id', 'unknown')}")
        return None
    
    def get_document_types(self) -> List[Dict[str, str]]:
        """
        Get available document types.
        
        Returns:
            List of document type definitions
        """
        return [
            {"value": "drucksache", "label": "Drucksache (Printed Paper)"},
            {"value": "plenarprotokoll", "label": "Plenarprotokoll (Plenary Protocol)"},
            {"value": "vorgang", "label": "Vorgang (Procedure)"},
        ]
    
    def get_wahlperioden(self) -> List[int]:
        """
        Get available parliamentary terms (Wahlperioden).
        
        Returns:
            List of available term numbers
        """
        # Bundestag terms from 1st (1949) to current (20th, started 2021)
        # Return recent ones (last 5 terms)
        current_term = 20  # As of 2025
        return list(range(current_term, max(0, current_term - 5), -1))
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()
        logger.info("DIP API Client closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class CachedDIPAPIClient(DIPAPIClient):
    """DIP API Client with caching support for search results"""
    
    def __init__(
        self, 
        api_key: str, 
        base_url: str = "https://search.dip.bundestag.de/api/v1",
        cache_dir: Optional[Path] = None,
        cache_ttl: int = 3600
    ):
        """
        Initialize cached DIP API client.
        
        Args:
            api_key: API key for authentication
            base_url: Base URL for the API
            cache_dir: Directory for cache files (default: data/cache)
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        super().__init__(api_key, base_url)
        self.cache_dir = cache_dir or Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl
        logger.info(f"Cache enabled with TTL={cache_ttl}s at {self.cache_dir}")
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key from endpoint and parameters."""
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(f"{endpoint}:{param_str}".encode()).hexdigest()
    
    def _load_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load response from cache if valid."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            
            # Check TTL
            cached_time = datetime.fromisoformat(cached['timestamp'])
            age = (datetime.now() - cached_time).total_seconds()
            
            if age < self.cache_ttl:
                logger.debug(f"Cache hit: {cache_key} (age: {age:.1f}s)")
                return cached['data']
            else:
                logger.debug(f"Cache expired: {cache_key} (age: {age:.1f}s)")
                cache_file.unlink()
                
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        
        return None
    
    def _save_cache(self, cache_key: str, data: Dict[str, Any]):
        """Save response to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            cached = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached, f, ensure_ascii=False, indent=2)
            logger.debug(f"Cached response: {cache_key}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    def _make_request(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> Dict[str, Any]:
        """Override to add caching."""
        params = params or {}
        cache_key = self._get_cache_key(endpoint, params)
        
        # Try cache first
        cached_data = self._load_cache(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Make request
        data = super()._make_request(endpoint, params, method)
        
        # Save to cache
        self._save_cache(cache_key, data)
        
        return data
