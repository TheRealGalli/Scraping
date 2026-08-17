import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from config import settings

logger = logging.getLogger(__name__)

# Path to inline image attachment
_NFC_IMAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "nfc_card.jpg")

class SMTPService:
    def __init__(self, sender_email: str = None, app_password: str = None):
        self.sender_email = sender_email or settings.WORKSPACE_EMAIL
        self.app_password = app_password or settings.WORKSPACE_APP_PASSWORD
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT

    def send_email(self, to_email: str, subject: str, html_body: str, plain_text_body: str) -> bool:
        """
        Connects to Google Workspace SMTP server (smtp.gmail.com:587 TLS),
        authenticates via App Password, and sends an email with inline NFC card image.
        Returns True if successful, False if sending fails.
        """
        if not self.sender_email or not self.app_password:
            logger.error("WORKSPACE_EMAIL or WORKSPACE_APP_PASSWORD is not configured. SMTP send skipped.")
            return False

        if not to_email or "@" not in to_email:
            logger.warning(f"Invalid target recipient email: '{to_email}'")
            return False

        try:
            # Use 'related' to allow inline CID image references inside the HTML part
            msg_root = MIMEMultipart("mixed")
            msg_root["Subject"] = subject
            msg_root["From"] = self.sender_email
            msg_root["To"] = to_email

            # Alternative container (plain + html)
            msg_alternative = MIMEMultipart("alternative")
            part_plain = MIMEText(plain_text_body, "plain", "utf-8")
            msg_alternative.attach(part_plain)

            # Related container to embed inline image inside html
            msg_related = MIMEMultipart("related")
            part_html = MIMEText(html_body, "html", "utf-8")
            msg_related.attach(part_html)

            # Attach NFC card image as inline CID if file exists
            if os.path.exists(_NFC_IMAGE_PATH):
                with open(_NFC_IMAGE_PATH, "rb") as img_file:
                    img_data = img_file.read()
                mime_img = MIMEImage(img_data, _subtype="jpeg")
                mime_img.add_header("Content-ID", "<nfc_card>")
                mime_img.add_header("Content-Disposition", "inline", filename="nfc_card.jpg")
                msg_related.attach(mime_img)
                logger.debug("Attached inline NFC card image (cid:nfc_card).")
            else:
                logger.warning(f"NFC card image not found at: {_NFC_IMAGE_PATH}")

            msg_alternative.attach(msg_related)
            msg_root.attach(msg_alternative)

            logger.info(f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}...")
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, [to_email], msg_root.as_string())

            logger.info(f"Successfully sent email to '{to_email}' via Google Workspace SMTP.")
            return True

        except Exception as e:
            logger.error(f"SMTP error sending email to '{to_email}': {e}")
            return False
