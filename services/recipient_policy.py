"""Conservative address validation, shared by all campaigns and legacy rows."""
import hashlib
import re
from datetime import timedelta

BLOCKED_ROLES = {"support", "supporto", "assistenza", "helpdesk", "privacy", "dpo", "gdpr", "dataprotection", "noreply", "donotreply", "abuse", "postmaster", "security", "webmaster"}


def normalize_email(raw):
    raw = (raw or "").strip()
    if len(raw) > 254 or raw.count("@") != 1 or re.search(r"[\s\x00-\x1f\x7f,;<>]", raw):
        raise ValueError("invalid_email")
    local, domain = raw.rsplit("@", 1)
    if not local or len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", local):
        raise ValueError("invalid_email")
    try:
        domain = domain.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise ValueError("invalid_email")
    labels = domain.split(".")
    if len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in labels) or labels[-1].isdigit():
        raise ValueError("invalid_email")
    # Conservative deduplication for business recipients; preserve dots and +suffixes.
    return local.lower() + "@" + domain


def contact_id(email):
    return hashlib.sha256(normalize_email(email).encode()).hexdigest()


def exclusion_reason(email):
    try:
        email = normalize_email(email)
    except ValueError:
        return "invalid_email"
    local, domain = email.split("@")
    tokens = set(re.split(r"[._+\-]+", local))
    compact = re.sub(r"[._+\-]", "", local)
    if BLOCKED_ROLES.intersection(tokens) or compact in BLOCKED_ROLES:
        return "technical_or_privacy_address"
    if "pec" in tokens or "pec" in domain.split(".") or domain in {"pec.it", "legalmail.it", "pecmail.it", "postecert.it", "arubapec.it"}:
        return "pec_address_review"
    return ""


def next_contact_time(history, now, cooldown_days, window_days, window_max):
    history = sorted(x for x in history if x <= now)
    due = now
    if history:
        due = max(due, history[-1] + timedelta(days=cooldown_days))
    recent = [x for x in history if x > now - timedelta(days=window_days)]
    if len(recent) >= window_max:
        due = max(due, recent[-window_max] + timedelta(days=window_days))
    return due
