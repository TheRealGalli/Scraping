import logging
import re
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Common false positive patterns and dummy domains to filter out
INVALID_DOMAINS_OR_EXTS = [
    "png", "jpg", "jpeg", "gif", "svg", "webp", "wixpress", "sentry.io",
    "example.com", "domain.com", "email.com", "schema.org", "fontawesome",
    "bootstrap", "jquery", "wordpress", "gravatar"
]

class EmailExtractor:
    def __init__(self, project_id: str = None, location: str = None, model_name: str = None):
        self.project_id = project_id or settings.GCP_PROJECT
        self.location = location or settings.GCP_LOCATION
        self.model_name = model_name or settings.GEMINI_MODEL_NAME
        self._vertex_initialized = False
        self._model = None
        self._model_with_grounding = None

    def _init_vertex_ai(self):
        """Initializes Vertex AI SDK lazily using ADC."""
        if self._vertex_initialized:
            return
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel, Tool, grounding
            
            if self.project_id:
                vertexai.init(project=self.project_id, location=self.location)
            else:
                vertexai.init(location=self.location)
            
            # Standard model without tools
            try:
                self._model = GenerativeModel(self.model_name)
            except Exception as me:
                logger.warning(f"Could not load specified model {self.model_name}: {me}. Falling back to gemini-3.5-flash-lite.")
                self._model = GenerativeModel("gemini-3.5-flash-lite")

            # Model configured with Google Search Grounding tool
            try:
                search_tool = Tool.from_google_search_retrieval(grounding.GoogleSearchRetrieval())
                self._model_with_grounding = GenerativeModel(self.model_name, tools=[search_tool])
                logger.info(f"Initialized Vertex AI {self.model_name} with Google Search Grounding.")
            except Exception as ge:
                logger.warning(f"Could not initialize Google Search Grounding: {ge}")
                self._model_with_grounding = self._model
                
            self._vertex_initialized = True
        except Exception as e:
            logger.warning(f"Could not initialize Vertex AI SDK: {e}. Will rely on Regex fallback.")
            self._vertex_initialized = False

    def find_email_via_gemini_search(self, business_name: str, city: str, website: str = "") -> Optional[str]:
        """
        Ultra-lightweight direct web search via Gemini Grounding.
        Uses ~50 tokens prompt instead of parsing entire HTML pages.
        """
        if not settings.ENABLE_GEMINI_GROUNDING:
            return None

        self._init_vertex_ai()
        if not self._model_with_grounding:
            return None

        prompt = (
            f"Usa la ricerca Google per trovare l'indirizzo e-mail di contatto ufficiale dell'attività commerciale '{business_name}' a {city} (sito web: {website}).\n"
            "Restituisci ESCLUSIVAMENTE l'indirizzo e-mail in formato testo semplice (senza spazi, virgolette, spiegazioni o formattazione markdown).\n"
            "Se non trovi alcuna e-mail reale e valida, rispondi soltanto 'NONE'."
        )

        try:
            response = self._model_with_grounding.generate_content(prompt)
            raw_result = (response.text or "").strip()
            
            if raw_result and raw_result.upper() != "NONE":
                cleaned_result = raw_result.lower().strip(" '\"`\n\r")
                if EMAIL_REGEX.fullmatch(cleaned_result) and self._is_valid_email(cleaned_result):
                    logger.info(f"Gemini Grounding direct search found email for '{business_name}': {cleaned_result}")
                    return cleaned_result
        except Exception as e:
            logger.warning(f"Gemini Grounding direct search failed for '{business_name}': {e}")

        return None

    def extract_email_with_gemini(self, text: str) -> Optional[str]:
        """Extracts primary contact email from scraped text using Vertex AI Gemini Flash model."""
        if not text:
            return None

        self._init_vertex_ai()
        if not self._model:
            return None

        prompt = (
            "Sei un assistente esperto in estrazione dati aziendali.\n"
            "Analizza il seguente testo tratto dal sito web di un'attività commerciale e individua l'indirizzo e-mail di contatto principale.\n"
            "Restituisci ESCLUSIVAMENTE l'indirizzo e-mail in formato testo semplice (senza spazi, virgolette, spiegazioni o blocchi di codice markdown).\n"
            "Se non è presente alcuna e-mail di contatto reale e valida, rispondi soltanto 'NONE'.\n\n"
            f"TESTO SITO WEB:\n{text[:3000]}"
        )

        try:
            response = self._model.generate_content(prompt)
            raw_result = (response.text or "").strip()
            
            if raw_result and raw_result.upper() != "NONE":
                cleaned_result = raw_result.lower().strip(" '\"`\n\r")
                if EMAIL_REGEX.fullmatch(cleaned_result) and self._is_valid_email(cleaned_result):
                    logger.info(f"Gemini NLP extracted email: {cleaned_result}")
                    return cleaned_result
        except Exception as e:
            logger.warning(f"Gemini NLP extraction failed: {e}")

        return None

    def _is_valid_email(self, email: str) -> bool:
        """Filters out non-contact emails, dummy addresses, and static file extensions."""
        email_lower = email.lower()
        if any(ext in email_lower for ext in INVALID_DOMAINS_OR_EXTS):
            return False
        return True

    def extract_email_with_regex(self, text: str) -> Optional[str]:
        """Regex fallback to find and return the best contact email found in text."""
        if not text:
            return None

        matches = EMAIL_REGEX.findall(text)
        if not matches:
            return None

        valid_emails = []
        for match in matches:
            email_clean = match.lower().strip(".")
            if self._is_valid_email(email_clean):
                valid_emails.append(email_clean)

        if not valid_emails:
            return None

        priority_prefixes = ["info@", "contatt", "prenotazion", "segreteria@", "amministrazione@", "commerciale@"]
        for email in valid_emails:
            if any(prefix in email for prefix in priority_prefixes):
                logger.info(f"Regex extracted priority email: {email}")
                return email

        selected = valid_emails[0]
        logger.info(f"Regex extracted email: {selected}")
        return selected

    def extract_email(self, text: str) -> Optional[str]:
        """
        Fallback extraction method:
        1. Tries Gemini NLP on scraped text.
        2. Falls back to Regex extraction.
        """
        if not text:
            return None

        email = self.extract_email_with_gemini(text)
        if not email:
            email = self.extract_email_with_regex(text)
        
        return email
