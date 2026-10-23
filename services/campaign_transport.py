"""SMTP acceptance is distinct from delivery. Ambiguous failures are never retried blindly."""
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from config import settings
from services.recipient_policy import normalize_email


@dataclass(frozen=True)
class TransportResult:
    status: str
    message_id: str
    error: str = ""


class CampaignSMTP:
    def __init__(self):
        self.sender = normalize_email(settings.WORKSPACE_EMAIL)
        if not settings.WORKSPACE_APP_PASSWORD or settings.SMTP_PORT not in (465, 587):
            raise ValueError("SMTP credentials or TLS port missing")

    def send(self, recipient, campaign, dispatch_id):
        from services.campaign_catalog import render
        subject, body, plain, image_path = render(campaign)
        message = EmailMessage()
        message_id = make_msgid(idstring=dispatch_id, domain=self.sender.split("@")[1])
        message["Message-ID"] = message_id
        message["From"] = formataddr((settings.SENDER_NAME or "Carlo · CSD Station", self.sender))
        message["To"] = normalize_email(recipient)
        message["Reply-To"] = self.sender
        message["Subject"] = subject
        message["List-Unsubscribe"] = "<mailto:" + self.sender + "?subject=CANCELLAMI>"
        message.set_content(plain)
        message.add_alternative(body, subtype="html")
        message.get_payload()[-1].add_related(image_path.read_bytes(), maintype="image", subtype="jpeg", cid="<campaign_art>", filename=campaign + ".jpg", disposition="inline")
        data_started = False
        try:
            if settings.SMTP_PORT == 465:
                import ssl
                connection = smtplib.SMTP_SSL(settings.SMTP_HOST, 465, timeout=20, context=ssl.create_default_context())
            else:
                connection = smtplib.SMTP(settings.SMTP_HOST, 587, timeout=20)
            with connection as server:
                if settings.SMTP_PORT == 587:
                    import ssl
                    server.starttls(context=ssl.create_default_context())
                server.login(self.sender, settings.WORKSPACE_APP_PASSWORD.replace(" ", ""))
                data_started = True
                refused = server.send_message(message)
                if refused:
                    return TransportResult("rejected", message_id, "recipient_refused")
                # QUIT may fail after acceptance; don't turn accepted mail into a retry.
                result = TransportResult("accepted", message_id)
            return result
        except smtplib.SMTPRecipientsRefused as exc:
            messages = [str(value[1]).lower() for value in exc.recipients.values()]
            permanent = any("5.1.1" in msg or "user unknown" in msg or "no such user" in msg for msg in messages)
            return TransportResult("hard_bounce" if permanent else "rejected", message_id, "recipient_refused")
        except smtplib.SMTPDataError as exc:
            return TransportResult("rejected", message_id, "smtp_data_" + str(exc.smtp_code))
        except Exception as exc:
            if "result" in locals():
                return result
            return TransportResult("uncertain" if data_started else "rejected", message_id, type(exc).__name__)
