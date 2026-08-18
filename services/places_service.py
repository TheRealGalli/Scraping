import logging
from typing import List, Dict, Any
import httpx

from config import settings

logger = logging.getLogger(__name__)

PLACES_API_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

class PlacesService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY

    def _get_headers(self, field_mask: str = "places.id,places.displayName,places.formattedAddress") -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-FieldMask": field_mask
        }
        if self.api_key:
            headers["X-Goog-Api-Key"] = self.api_key
        else:
            try:
                import google.auth
                from google.auth.transport.requests import Request
                credentials, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
                credentials.refresh(Request())
                headers["Authorization"] = f"Bearer {credentials.token}"
                if project or settings.GCP_PROJECT:
                    headers["X-Goog-User-Project"] = project or settings.GCP_PROJECT
            except Exception as e:
                logger.warning(f"Could not obtain Google ADC credentials for Places API: {e}")
        return headers

    def search_places(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Searches places using Google Places API (New) searchText endpoint.
        Returns a list of place dictionaries with place_id, name, address, website.
        """
        headers = self._get_headers()
        if "X-Goog-Api-Key" not in headers and "Authorization" not in headers:
            logger.warning("Neither GOOGLE_API_KEY nor ADC token is available. Places API search skipped.")
            return []

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

    def get_place_website(self, place_id: str) -> str:
        """
        Fetches websiteUri for a specific place_id using Place Details API.
        Executed ONLY for newly discovered leads to minimize API costs.
        """
        if not place_id:
            return ""
        headers = self._get_headers(field_mask="websiteUri")
        if "X-Goog-Api-Key" not in headers and "Authorization" not in headers:
            return ""

        url = f"https://places.googleapis.com/v1/places/{place_id}"
        try:
            with httpx.Client(timeout=settings.HTTP_TIMEOUT) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("websiteUri", "")
                return ""
        except Exception as e:
            logger.warning(f"Failed to fetch website for place_id '{place_id}': {e}")
            return ""
