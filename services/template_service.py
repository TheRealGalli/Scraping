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
        Lead fields used: name, city, sector, website, email.
        Returns tuple: (subject, html_body, plain_text_body)
        """
        business_name = lead.get("name") or lead.get("place_id") or "vostra attività"
        city = lead.get("city") or "Italia"
        sector = lead.get("sector") or "commerciale"
        website = lead.get("website") or ""
        email = lead.get("email") or ""

        subject = 'Un semplice "TAP" per dominare Google Maps nel 2026'

        html_template = self.load_template()
        html_body = html_template.format(
            business_name=business_name,
            city=city,
            sector=sector,
            website=website if website else "#",
            unsubscribe_url="#unsubscribe"
        )

        plain_text_body = (
            f"Problemi a raccogliere Recensioni Google?\n\n"
            f"Passare da 3 a 50 recensioni a settimana non è mai stato così IMPORTANTE "
            f"per la visibilità online come nel 2026, e non è mai stato così SEMPLICE "
            f"come con le nostre Card NFC!!\n\n"
            f"Scopri di più sul nostro portale:\n"
            f"https://csd-station.it/?mode=nfc\n\n"
            f"la nostra soluzione a 20€ una Tantum, zero Abbonamenti!!\n\n"
            f"NFC Card\n\n"
            f"Inizia a raccogliere attivamente recensioni per migliorare la SEO del tuo "
            f"Business online nel modo più conveniente e più potente nel 2026.\n\n"
            f"Inutile girarci intorno: le recensioni Google sono il primo punto di contatto con il cliente.\n\n"
            f"Vengono prima del vostro sito web e prima della SEO interna del tuo sito. "
            f"Un cliente oggi guarda quasi esclusivamente le recensioni su Google Maps.\n\n"
            f"Un cliente avanzato che usa l'AI (come Chat GPT, Gemini, Claude) finisce "
            f"sempre dentro i punti locali con più recensioni Google.\n\n"
            f"Info e Ordini su WhatsApp:\nhttps://api.whatsapp.com/send/?phone=393518628203\n"
        )

        return subject, html_body, plain_text_body
