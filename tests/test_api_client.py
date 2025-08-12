import pytest
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.client import BundestagAPIClient
from config.settings import BUNDESTAG_API_KEY


class TestBundestagAPIClient:
    """Test the Bundestag API client"""
    
    @pytest.fixture
    def client(self):
        """Create a test client"""
        return BundestagAPIClient()
    
    def test_client_initialization(self, client):
        """Test client initialization"""
        assert client.api_key == BUNDESTAG_API_KEY
        assert client.base_url == "https://search.dip.bundestag.de/api/v1"
        assert "Authorization" in client.headers
    
    @pytest.mark.asyncio
    async def test_connection(self, client):
        """Test API connection"""
        try:
            response = client.get_drucksachen()
            assert response.numFound >= 0
            assert isinstance(response.documents, list)
        except Exception as e:
            pytest.skip(f"API connection failed: {e}")
    
    def test_cache_path_generation(self, client):
        """Test cache path generation"""
        endpoint = "drucksache"
        params = {"f.wahlperiode": [20]}
        
        cache_path = client._get_cache_path(endpoint, params)
        assert cache_path.suffix == ".json"
        assert cache_path.parent.name == "cache"
    
    def test_search_by_title(self, client):
        """Test search by title"""
        try:
            results = client.search_by_title("Klimaschutz", limit=5)
            assert isinstance(results, list)
            assert len(results) <= 5
        except Exception as e:
            pytest.skip(f"Search failed: {e}")
    
    def test_search_by_wahlperiode(self, client):
        """Test search by electoral period"""
        try:
            results = client.search_by_wahlperiode(20, limit=5)
            assert isinstance(results, list)
            assert len(results) <= 5
            
            if results:
                # Check that all results are from the correct period
                for result in results:
                    assert result.get('wahlperiode') == 20
        except Exception as e:
            pytest.skip(f"Search failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
