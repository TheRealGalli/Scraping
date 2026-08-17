import logging
from typing import Optional
import httpx

from config import settings

logger = logging.getLogger(__name__)

CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

class CustomSearchService:
    def __init__(self, api_key: str = None, cx: str = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.cx = cx or settings.CUSTOM_SEARCH_ENGINE_ID

    def search_website_fallback(self, business_name: str, city: str) -> Optional[str]:
        """
        Fallback search using Google Custom Search API.
        Query: '[Nome Attività] [Città]'
        Returns the link of the first relevant result.
        """
        if not self.api_key or not self.cx:
            logger.warning("GOOGLE_API_KEY or CUSTOM_SEARCH_ENGINE_ID missing. Custom Search fallback skipped.")
            return None

        query = f"{business_name} {city}"
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": 3
        }

        try:
            with httpx.Client(timeout=settings.HTTP_TIMEOUT) as client:
                response = client.get(CUSTOM_SEARCH_URL, params=params)
                if response.status_code != 200:
                    logger.error(f"Custom Search API error {response.status_code}: {response.text}")
                    return None

                data = response.json()
                items = data.get("items", [])
                
                for item in items:
                    link = item.get("link")
                    if link and link.startswith("http"):
                        # Skip pure directory aggregators if possible or pick top candidate
                        logger.info(f"Custom Search fallback found URL: {link} for '{query}'")
                        return link

                return None
        except Exception as e:
            logger.error(f"Error querying Custom Search API for '{query}': {e}")
            return None
