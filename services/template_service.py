import os
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "cold_email_template.html")

class TemplateService:
    def __init__(self, template_path: str = None):
        self.template_path = template_path or TEMPLATE_PATH

    def load_template(self) -> str:
        """Loads HTML email template content."""
        if os.path.exists(self.template_path):
            with open(self.template_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            # Fallback default template
            return (
                "<p>Gentile team di <strong>{business_name}</strong>,</p>"
                "<p>Vi contattiamo in merito alla vostra attività a {city}.</p>"
                "<p>Cordiali saluti.</p>"
            )

    def render_email(self, lead: Dict[str, Any]) -> Tuple[str, str, str]:
        """
        Renders email subject, HTML body, and plain-text body for a given lead.
        Placeholders: business_name, city, sector, website.
        Returns tuple: (subject, html_body, plain_text_body)
        """
        business_name = lead.get("place_id") or "vostra attività"
        city = lead.get("city") or "Italia"
        sector = lead.get("sector") or "commerciale"
        website = lead.get("website") or ""

        subject = f"Opportunità di collaborazione per {city}"
        
        html_template = self.load_template()
        html_body = html_template.format(
            business_name=business_name,
            city=city,
            sector=sector,
            website=website if website else "attività"
        )

        plain_text_body = (
            f"Gentile team di {business_name},\n\n"
            f"Vi contattiamo in merito alla vostra attività nel settore {sector} a {city}.\n"
            f"Sito web: {website}\n\n"
            "Se siete interessati a saperne di più, rispondete a questa e-mail.\n\n"
            "Cordiali saluti."
        )

        return subject, html_body, plain_text_body
