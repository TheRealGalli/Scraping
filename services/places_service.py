import logging
from typing import List, Dict, Any
import httpx

from config import settings

logger = logging.getLogger(__name__)

PLACES_API_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

class PlacesService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY

    def search_places(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Searches places using Google Places API (New) searchText endpoint.
        Returns a list of place dictionaries with place_id, name, address, website.
        """
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY is not set. Places API search skipped.")
            return []

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.websiteUri"
        }

        body = {
            "textQuery": query,
            "languageCode": "it",
            "pageSize": min(max_results, 20)
        }

        try:
            with httpx.Client(timeout=settings.HTTP_TIMEOUT) as client:
                response = client.post(PLACES_API_TEXT_SEARCH_URL, json=body, headers=headers)
                
                if response.status_code != 200:
                    logger.error(f"Places API (New) error {response.status_code}: {response.text}")
                    return []

                data = response.json()
                places_raw = data.get("places", [])
                
                results = []
                for p in places_raw:
                    place_id = p.get("id")
                    if not place_id:
                        continue
                    
                    display_name_obj = p.get("displayName", {})
                    name = display_name_obj.get("text", "") if isinstance(display_name_obj, dict) else str(display_name_obj)
                    address = p.get("formattedAddress", "")
                    website = p.get("websiteUri", "")

                    results.append({
                        "place_id": place_id,
                        "name": name,
                        "address": address,
                        "website": website
                    })
                
                logger.info(f"Places API returned {len(results)} results for query: '{query}'")
                return results

        except Exception as e:
            logger.error(f"Failed to query Places API (New) for '{query}': {e}")
            return []
