"""Pure, repeatable import planning. No emails and no Places/AI calls."""
from collections import Counter
from datetime import datetime
import hashlib
import pytz

from config import settings
from services.campaign_catalog import CATALOG, SECTOR_RULES
from services.recipient_policy import contact_id, exclusion_reason, normalize_email


def prepare_import(rows, existing, overrides, legacy_campaign, now):
    if legacy_campaign not in {"unknown", "nfc"}:
        raise ValueError("legacy_campaign must be explicitly nfc or unknown")
    contacts, pairs, events = {}, {}, {}
    summary = Counter(rows=max(0, len(rows) - 1))
    known = {"Da inviare", "Inviato", "Errore Invio", "Duplicato Email", "Email Supporto", "Nessuna email"}
    for index, raw in enumerate(rows[1:], 2):
        row = raw + [""] * max(0, 11 - len(raw))
        if not any(row):
            continue
        try:
            email = normalize_email(row[6])
        except ValueError:
            summary["invalid_or_empty_email"] += 1
            continue
        cid = contact_id(email)
        if cid not in contacts:
            previous = existing.get(cid, {})
            order = list(CATALOG)
            offset = int(cid[:8], 16) % len(order)
            contacts[cid] = dict(previous, email=email, sectors=[], sources=[], source_count=0, enabled=overrides.get(cid, {}).get("enabled", previous.get("enabled", True)), reference=overrides.get(cid, {}).get("reference", previous.get("reference", "")), campaign_order=previous.get("campaign_order", order[offset:] + order[:offset]), history=list(previous.get("history", [])), sent=list(previous.get("sent", [])), legacy_keys=list(previous.get("legacy_keys", [])))
        else:
            summary["duplicate_email_rows"] += 1
        c = contacts[cid]
        if row[4].strip() and row[4].strip() not in c["sectors"]:
            c["sectors"].append(row[4].strip())
        c["source_count"] += 1
        # Keep the full source in Italy/backups; bound the document for shared
        # franchise mailboxes that may appear on thousands of source rows.
        if len(c["sources"]) < 100:
            c["sources"].append({"row": index, "place_id": row[0][:256], "website": row[5][:2048]})
        reason = exclusion_reason(email)
        if reason:
            c["review_reason"] = reason
        status = row[7].strip()
        summary["status:" + (status or "empty")] += 1
        if status not in known:
            c["review_reason"] = "unknown_legacy_status"
        if status == "Errore Invio":
            c["review_reason"] = "ambiguous_legacy_error"
        if status != "Inviato":
            continue
        key = hashlib.sha256((cid + "|" + row[8].strip()).encode()).hexdigest()
        stamp = None
        try:
            stamp = pytz.timezone(settings.TIMEZONE).localize(datetime.strptime(row[8].strip(), "%Y-%m-%d %H:%M"), is_dst=None)
            if stamp > now:
                raise ValueError("future legacy date")
        except (ValueError, pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
            stamp = None
            c["review_reason"] = "legacy_date_requires_review"
            summary["legacy_date_requires_review"] += 1
        if legacy_campaign == "unknown":
            c["review_reason"] = "legacy_campaign_requires_review"
        if stamp and stamp not in c["history"]:
            c["history"].append(stamp)
        # Conservatively never repeat the NFC introduction for previously-sent contacts.
        c["sent"] = sorted(set(c["sent"] + ["nfc"]))
        if key not in c["legacy_keys"]:
            c["legacy_keys"].append(key)
        events["legacy-" + key] = {"contact_id": cid, "campaign": legacy_campaign, "at": stamp, "state": "legacy_accepted", "mode": "live", "sender": "unknown_legacy", "source_row": index, "template_version": "legacy"}
    for cid, c in contacts.items():
        c["history"] = sorted(c["history"])
        c["sectors"] = sorted(c["sectors"])
        for campaign in CATALOG:
            if set(c["sectors"]).intersection(SECTOR_RULES[campaign]):
                pairs[campaign + ":" + cid] = {"campaign": campaign, "contact_id": cid, "state": "sent" if campaign in c["sent"] else "queued", "eligible_at": now, "reason": "imported"}
    # Removing a source row must not leave an invisible, still-enabled contact in the registry.
    for cid, c in existing.items():
        if cid not in contacts:
            contacts[cid] = dict(c, enabled=False, review_reason="missing_from_source")
    summary["contacts"] = len(contacts)
    summary["pairs"] = len(pairs)
    summary["review_contacts"] = sum(bool(c.get("review_reason")) for c in contacts.values())
    return dict(summary), contacts, pairs, events
