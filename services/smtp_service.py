import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import settings

logger = logging.getLogger(__name__)

class SMTPService:
    def __init__(self, sender_email: str = None, app_password: str = None):
        self.sender_email = sender_email or settings.WORKSPACE_EMAIL
        self.app_password = app_password or settings.WORKSPACE_APP_PASSWORD
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT

    def send_email(self, to_email: str, subject: str, html_body: str, plain_text_body: str) -> bool:
        """
        Connects to Google Workspace SMTP server (smtp.gmail.com:587 TLS),
        authenticates via App Password, and sends an email.
        Returns True if successful, False if sending fails.
        """
        if not self.sender_email or not self.app_password:
            logger.error("WORKSPACE_EMAIL or WORKSPACE_APP_PASSWORD is not configured. SMTP send skipped.")
            return False

        if not to_email or "@" not in to_email:
            logger.warning(f"Invalid target recipient email: '{to_email}'")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = to_email

            # Attach plain text and HTML parts
            part_plain = MIMEText(plain_text_body, "plain", "utf-8")
            part_html = MIMEText(html_body, "html", "utf-8")
            msg.attach(part_plain)
            msg.attach(part_html)

            logger.info(f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}...")
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, [to_email], msg.as_string())

            logger.info(f"Successfully sent email to '{to_email}' via Google Workspace SMTP.")
            return True

        except Exception as e:
            logger.error(f"SMTP error sending email to '{to_email}': {e}")
            return False
