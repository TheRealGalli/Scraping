import logging
import urllib.parse
from typing import List
import httpx
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
}

CONTACT_PATH_KEYWORDS = ["contatt", "chi-siamo", "about", "contact", "info"]

class WebScraper:
    def __init__(self, timeout: float = None):
        self.timeout = timeout or settings.HTTP_TIMEOUT

    def extract_mailto_emails(self, html_content: str) -> List[str]:
        """Extracts emails directly from mailto: links in HTML (0 AI tokens, 100% accurate)."""
        if not html_content:
            return []
        emails = []
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if href.lower().startswith("mailto:"):
                    email_candidate = href[7:].split("?")[0].strip()
                    if email_candidate and email_candidate not in emails:
                        emails.append(email_candidate.lower())
        except Exception as e:
            logger.debug(f"Error parsing mailto links: {e}")
        return emails

    def clean_html_to_text(self, html_content: str) -> str:
        """Strips tags, scripts, styles and returns clean text content."""
        if not html_content:
            return ""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            for element in soup(["script", "style", "head", "meta", "svg", "noscript"]):
                element.decompose()
            text = soup.get_text(separator=" ", strip=True)
            return text
        except Exception as e:
            logger.warning(f"Error parsing HTML: {e}")
            return ""

    def find_contact_links(self, base_url: str, html_content: str) -> List[str]:
        """Finds subpages related to contact/about information."""
        if not html_content:
            return []

        contact_urls = []
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            parsed_base = urllib.parse.urlparse(base_url)
            
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                link_text = a_tag.get_text().lower()

                # Check if href or text contains contact keywords
                if any(kw in href.lower() or kw in link_text for kw in CONTACT_PATH_KEYWORDS):
                    full_url = urllib.parse.urljoin(base_url, href)
                    parsed_full = urllib.parse.urlparse(full_url)
                    
                    # Stay on same domain
                    if parsed_full.netloc == parsed_base.netloc and full_url not in contact_urls and full_url != base_url:
                        contact_urls.append(full_url)
                        if len(contact_urls) >= 2:  # Limit contact subpages
                            break
        except Exception as e:
            logger.warning(f"Error extracting contact links from {base_url}: {e}")

        return contact_urls

    def scrape_website_content(self, url: str) -> str:
        """
        Fetches website homepage and up to 2 contact subpages.
        Returns combined clean text extracted from HTML.
        """
        if not url or not url.startswith("http"):
            return ""

        combined_text = []

        try:
            with httpx.Client(timeout=self.timeout, headers=HEADERS, follow_redirects=True) as client:
                logger.info(f"Fetching homepage: {url}")
                resp = client.get(url)
                if resp.status_code == 200:
                    homepage_text = self.clean_html_to_text(resp.text)
                    combined_text.append(f"--- HOMEPAGE ({url}) ---\n" + homepage_text)
                    
                    contact_links = self.find_contact_links(url, resp.text)
                    for contact_url in contact_links:
                        try:
                            logger.info(f"Fetching contact page: {contact_url}")
                            c_resp = client.get(contact_url)
                            if c_resp.status_code == 200:
                                c_text = self.clean_html_to_text(c_resp.text)
                                combined_text.append(f"--- CONTACT PAGE ({contact_url}) ---\n" + c_text)
                        except Exception as ce:
                            logger.debug(f"Failed to fetch contact page {contact_url}: {ce}")
        except Exception as e:
            logger.warning(f"Failed to fetch main website {url}: {e}")

        return "\n\n".join(combined_text)
