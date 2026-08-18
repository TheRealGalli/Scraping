import logging
import time
from typing import Dict, Any, List

from config import settings
from services.time_filter import is_night_time
from services.sheets_service import SheetsService
from services.geo_matrix import generate_search_targets
from services.places_service import PlacesService
from services.custom_search_service import CustomSearchService
from services.web_scraper import WebScraper
from services.email_extractor import EmailExtractor

logger = logging.getLogger(__name__)

def run_lead_generation_task():
    """
    Background worker process executed asynchronously on Cloud Run endpoint call.
    Pipeline optimized for ZERO token waste:
    1. Anti-night check (0 cost during night).
    2. Google Sheet deduplication via Place ID (0 cost for existing leads).
    3. Direct Gemini 3.5 Grounding Search (~50 tokens prompt).
    4. Mailto: / Regex extraction on HTML (0 AI tokens).
    5. Gemini NLP on HTML text (Fallback only if prior steps find no email).
    """
    logger.info("Starting background Lead Generation worker process...")

    # 1. Anti-night safety check
    if is_night_time():
        logger.info("Anti-night filter active (22:00-06:00 Europe/Rome). Terminating worker background task.")
        return

    # Initialize services
    sheets_service = SheetsService()
    places_service = PlacesService()
    custom_search_service = CustomSearchService()
    web_scraper = WebScraper()
    email_extractor = EmailExtractor()

    # 2. Fetch existing Place IDs & stored matrix index from Google Sheets
    existing_place_ids = sheets_service.get_existing_place_ids()
    start_offset = sheets_service.get_matrix_index()

    from services.geo_matrix import get_all_search_targets
    total_targets = len(get_all_search_targets())

    new_records: List[Dict[str, Any]] = []
    processed_count = 0
    executed_queries = 0

    logger.info(f"Starting matrix search from Google Sheets stored index {start_offset}/{total_targets}.")

    # 3. Stream search targets from matrix starting at stored offset
    for region, province, city, sector, keyword in generate_search_targets(offset=start_offset):
        if executed_queries >= settings.MAX_SEARCH_QUERIES_PER_RUN:
            logger.info(f"Reached MAX_SEARCH_QUERIES_PER_RUN limit ({settings.MAX_SEARCH_QUERIES_PER_RUN}). Stopping API calls for this run.")
            break
        if processed_count >= settings.MAX_PLACES_PER_RUN:
            logger.info(f"Reached MAX_PLACES_PER_RUN limit ({settings.MAX_PLACES_PER_RUN}). Wrapping up execution batch.")
            break

        executed_queries += 1
        query = f"{keyword} {city} {province} {region} Italia"
        logger.info(f"Executing Places search [{executed_queries}/{settings.MAX_SEARCH_QUERIES_PER_RUN}] for query: '{query}'")

        places = places_service.search_places(query, max_results=10)

        for place in places:
            place_id = place.get("place_id")
            if not place_id or place_id in existing_place_ids:
                logger.debug(f"Place ID '{place_id}' already stored or invalid. Discarding duplicate.")
                continue

            business_name = place.get("name", "")
            website = place.get("website", "")
            email = ""

            # OPTIMIZATION LEVEL 1: Direct Gemini Grounding search (DISABLED by default to avoid Vertex AI costs)
            # Re-enable via ENABLE_GEMINI_GROUNDING=True env var only when needed
            if settings.ENABLE_GEMINI_GROUNDING and business_name:
                logger.info(f"Level 1: Gemini Grounding direct search for '{business_name}'...")
                email = email_extractor.find_email_via_gemini_search(business_name, city, website) or ""

            # OPTIMIZATION LEVEL 2: Fetch website & HTML Scraping + Mailto: / Regex (0 AI tokens)
            if not email:
                if not website:
                    # Low-cost Place Details single-place website fetch for new place
                    website = places_service.get_place_website(place_id) or ""

                if not website and business_name:
                    logger.info(f"Website missing for '{business_name}'. Custom Search API fallback...")
                    website = custom_search_service.search_website_fallback(business_name, city) or ""

                if website:
                    logger.info(f"Level 2: Fetching website '{website}' for Mailto & Regex extraction...")
                    web_text = web_scraper.scrape_website_content(website)
                    
                    if web_text:
                        # Check Regex first (0 AI tokens)
                        email = email_extractor.extract_email_with_regex(web_text) or ""

                        # OPTIMIZATION LEVEL 3: Gemini NLP on HTML text (DISABLED - use Regex only to avoid Vertex AI costs)
                        # Re-enable via ENABLE_GEMINI_GROUNDING=True env var if Regex miss rate is too high
                        if not email and settings.ENABLE_GEMINI_GROUNDING:
                            logger.info(f"Level 3: Invoking Gemini NLP fallback on scraped HTML text...")
                            email = email_extractor.extract_email_with_gemini(web_text) or ""

            record = {
                "place_id": place_id,
                "region": region,
                "province": province,
                "city": city,
                "sector": sector,
                "website": website,
                "email": email
            }

            new_records.append(record)
            existing_place_ids.add(place_id)  # Avoid duplicates within same run batch
            processed_count += 1

            # Respect Google API rate limits
            time.sleep(settings.SLEEP_BETWEEN_CALLS)

            if processed_count >= settings.MAX_PLACES_PER_RUN:
                break

    # 4. Save updated matrix index to Google Sheets ConfigState tab for seamless continuation next run
    if total_targets > 0 and executed_queries > 0:
        next_index = (start_offset + executed_queries) % total_targets
        sheets_service.update_matrix_index(next_index)

    # 5. Batch append new records to Google Sheet
    if new_records:
        inserted = sheets_service.append_lead_records(new_records)
        logger.info(f"Successfully processed and appended {inserted} new lead records.")
    else:
        logger.info("No new lead records found or inserted in this run.")

    logger.info("Lead Generation background worker process completed.")
