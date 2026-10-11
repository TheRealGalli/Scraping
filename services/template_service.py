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
        business_name = (lead.get("name") or "").strip() or "la tua attività"
        city = lead.get("city") or "Italia"
        sector = lead.get("sector") or "commerciale"
        website = lead.get("website") or ""
        email = lead.get("email") or ""

        subject = 'Un semplice "TAP" per dominare Google Maps nel 2026'

        html_template = self.load_template()
        html_body = (
            html_template
            .replace("{business_name}", business_name)
            .replace("{city}", city)
            .replace("{sector}", sector)
            .replace("{website}", website if website else "#")
        )

        plain_text_body = (
            f"CSD Station — Card, Plate & Stand NFC per Recensioni Google\n\n"
            f"Un piccolo tap. Una grande connessione.\n\n"
            f"Raccogliere recensioni Google per {business_name} non è mai stato così semplice e determinante. "
            f"Nel 2026 le recensioni su Google Maps sono il primo fattore di scelta dei clienti e la principale fonte usata dai motori AI (ChatGPT, Gemini, Claude) per consigliare le attività locali.\n\n"
            f"Con le soluzioni NFC di CSD Station, per il cliente basta avvicinare lo smartphone o inquadrare il QR code per aprire all'istante la tua scheda Google e lasciare una recensione.\n\n"
            f"I NOSTRI FORMATI (zero abbonamenti, a partire da 19,90 € una tantum):\n"
            f"• Card NFC (19,90 €): Tascabile e sempre con te. Perfetta al momento del conto o al tavolo.\n"
            f"• Plate adesiva NFC (34,90 €): Postazione fissa, adesiva e senza ingombro per banconi e vetrine.\n"
            f"• Stand da banco NFC (39,90 €): In bella vista sul banco o alla cassa, invito immediato per i clienti.\n\n"
            f"IL VALORE AGGIUNTO CSD STATION:\n"
            f"1. Configurazione inclusa: colleghiamo direttamente la tua scheda Google e configuriamo il QR code.\n"
            f"2. Report mensili inclusi: statistiche sulle aperture per verificare l'impatto reale nel tempo.\n"
            f"3. Nessun canone mensile: un solo pagamento una tantum, zero abbonamenti ricorrenti.\n\n"
            f"Scopri tutti i dettagli sul nostro portale:\n"
            f"https://csd-station.it/?mode=nfc\n\n"
            f"Richiedi info o ordina su WhatsApp:\n"
            f"https://api.whatsapp.com/send/?phone=393518628203\n\n"
            f"---\n"
            f"CSD Station · Carlo Galli · P.IVA 01630510525\n"
            f"Dalla Toscana, in tutta Italia · carlo@csd-station.it\n\n"
            f"Hai ricevuto questa comunicazione B2B perché la tua attività è presente su Google Maps. "
            f"Rispondi 'CANCELLAMI' per non ricevere ulteriori comunicazioni.\n"
        )

        return subject, html_body, plain_text_body
