"""Cloud Run Job entry point. Defaults to read-only migration planning."""
import argparse
import json
import sys
import uuid
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from services.campaign_catalog import CATALOG
from services.campaign_engine import GATE, GLOBAL, utcnow
from services.campaign_migration import prepare_import
from services.campaign_sheets import CampaignSheets
from services.campaign_store import FirestoreStore


def backup(sheets, bucket_name, run_id):
    if not bucket_name:
        raise ValueError("--backup-bucket required for apply")
    from google.cloud import storage
    snapshot = {ws.title: ws.get_all_values() for ws in sheets.book.worksheets()}
    blob = storage.Client(project=settings.project_id).bucket(bucket_name).blob("campaign-backups/" + run_id + ".json")
    blob.upload_from_string(json.dumps(snapshot, ensure_ascii=False), content_type="application/json", if_generation_match=0)
    return "gs://" + bucket_name + "/" + blob.name



def configure150(store, sheets, bucket_name, expand_scraper=False):
    """Explicit backed-up repair/configuration; source leads are never rewritten."""
    from services.campaign_sheets import HEADERS
    from services.campaign_catalog import DEFAULT_LIMITS, SECTOR_RULES, RULE_VERSION
    from services.geo_matrix import convert_matrix_offset
    now, token = utcnow(), uuid.uuid4().hex
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-configure-" + token[:8]
    def acquire(d):
        if d[GATE].get("until", now) > now:
            raise ValueError("Another sender/admin operation is active; retry later")
        return {GATE: dict(d[GATE], token=token, until=now + timedelta(hours=2)),
                GLOBAL: dict(d[GLOBAL], maintenance=True, paused=True)}, None
    store.atomic([GATE, GLOBAL], acquire)
    try:
        backup_url = backup(sheets, bucket_name, run_id)
        state_ws, state_values = None, None
        if expand_scraper:
            state_ws = sheets.book.worksheet("ConfigState")
            state_values = state_ws.get_all_values()
            if len(state_values) < 2 or state_values[1][0] != "matrix_index":
                raise ValueError("Unexpected ConfigState cursor layout")
            if len(state_values) >= 3 and any(state_values[2]) and state_values[2][0] != "sector_profile":
                raise ValueError("ConfigState row 3 already in use")
            profile = state_values[2][1] if len(state_values) >= 3 and len(state_values[2]) >= 2 else "legacy_v1"
            if profile not in {"legacy_v1", "expanded_v2"}:
                raise ValueError("Unknown scraper profile")
            offset = int(state_values[1][1])
            if profile == "legacy_v1":
                offset = convert_matrix_offset(offset, max(1, settings.CYCLES_PER_CITY))
        # Repair the explicit control tab, including a malformed pasted A1.
        values = [HEADERS["Campagne"]] + [[c, "TRUE", q, q, "", str(q), 720] for c, q in DEFAULT_LIMITS.items()]
        ws = sheets.book.worksheet("Campagne")
        ws.clear()
        ws.update(range_name="A1:G7", values=values, value_input_option="RAW")
        sheets.ensure()
        sheets.book.worksheet("ControlloInvii").update(range_name="A2", values=[["TRUE"]], value_input_option="RAW")
        rules = [HEADERS["RegoleSettori"]] + [[c, sector, RULE_VERSION] for c in CATALOG for sector in SECTOR_RULES[c]]
        ws = sheets.book.worksheet("RegoleSettori")
        ws.clear()
        ws.update(range_name="A1", values=rules, value_input_option="RAW")
        if expand_scraper:
            state_ws.update(range_name="A2:C3", values=[
                ["matrix_index", str(offset), now.isoformat()],
                ["sector_profile", "expanded_v2", now.isoformat()]
            ], value_input_option="RAW")
        sheets.refresh_controls(store, utcnow())
        sheets.update_report(store)
        store.atomic([GLOBAL], lambda d: ({GLOBAL: dict(d[GLOBAL], maintenance=False, paused=True)}, None))
        print(json.dumps({"status": "configured", "quota_total": sum(DEFAULT_LIMITS.values()),
                          "paused": True, "backup": backup_url,
                          "scraper_profile": "expanded_v2" if expand_scraper else "unchanged"}))
    finally:
        def unlock(d):
            if d[GATE].get("token") != token:
                return {}, None
            return {GATE: dict(d[GATE], until=utcnow())}, None
        store.atomic([GATE], unlock)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "apply", "sync", "report", "pause", "resolve", "configure150"])
    parser.add_argument("--legacy-campaign", choices=["unknown", "nfc"], default="unknown")
    parser.add_argument("--backup-bucket", default="")
    parser.add_argument("--expand-scraper", action="store_true", help="Only while the scraper Scheduler is paused")
    parser.add_argument("--dispatch-id", default="")
    parser.add_argument("--outcome", choices=["accepted", "not_sent"])
    parser.add_argument("--evidence", default="")
    args = parser.parse_args(argv)
    store, sheets, now = FirestoreStore(), CampaignSheets(), utcnow()
    if args.command == "configure150":
        configure150(store, sheets, args.backup_bucket, args.expand_scraper)
        return
    if args.command == "pause":
        store.atomic([GLOBAL], lambda d: ({GLOBAL: dict(d[GLOBAL], maintenance=True)}, None))
        print(json.dumps({"status": "maintenance_enabled", "note": "Wait for in-flight dispatches to settle before editing"}))
        return
    if args.command == "resolve":
        if not args.dispatch_id or not args.outcome or not args.evidence:
            parser.error("resolve requires --dispatch-id --outcome --evidence")
        from services.campaign_engine import CampaignEngine
        event = store.get("dispatches", args.dispatch_id)
        if not store.get(*GLOBAL).get("maintenance"):
            raise ValueError("Enable maintenance with pause before resolving a dispatch")
        if event.get("state") not in {"uncertain", "started", "reserved"}:
            raise ValueError("Dispatch not unresolved")
        gate = store.get(*GATE)
        if gate.get("until", now) > now:
            raise ValueError("An operation is still in flight; wait for its lease to expire")
        CampaignEngine(store)._finish(event, "accepted" if args.outcome == "accepted" else "cancelled", event.get("message_id", ""), "manual_resolution:" + args.evidence)
        print(json.dumps({"status": "resolved", "dispatch_id": args.dispatch_id}))
        return
    if args.command == "report":
        sheets.update_report(store)
        print(json.dumps({"status": "report_updated"}))
        return
    source = sheets.read_source()
    existing = store.all("contacts")
    titles = {s.title for s in sheets.book.worksheets()}
    overrides = sheets.contact_overrides() if "Contatti" in titles else {}
    summary, contacts, pairs, events = prepare_import(source, existing, overrides, args.legacy_campaign, now)
    print(json.dumps({"status": "plan", "summary": summary}, ensure_ascii=False))
    if args.command == "plan":
        return
    if args.command == "sync" and not store.get(*GLOBAL).get("migration_ready"):
        raise ValueError("Run apply before sync")
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    token = uuid.uuid4().hex
    def lock(d):
        if d[GATE].get("until", now) > now:
            raise ValueError("Sender or another admin job is active; retry later")
        return {GATE: dict(d[GATE], token=token, until=now + timedelta(hours=2)), GLOBAL: dict(d[GLOBAL], maintenance=True)}, None
    store.atomic([GATE, GLOBAL], lock)
    try:
        backup_url = backup(sheets, args.backup_bucket, run_id)
        # Re-read after exclusion from sender activity; reconcile any final accepted dispatch.
        sheets.ensure()
        source = sheets.read_source()
        summary, contacts, pairs, events = prepare_import(source, store.all("contacts"), sheets.contact_overrides(), args.legacy_campaign, utcnow())
        store.put_many("contacts", contacts)
        previous_pairs = store.all("pairs")
        for pid in pairs:
            if pid in previous_pairs:
                previous = previous_pairs[pid]
                contact = contacts[pairs[pid]["contact_id"]]
                resume = previous.get("reason") in {"sector_not_targeted", "contact_disabled_or_review"} and contact.get("enabled") and not contact.get("review_reason")
                if not resume:
                    pairs[pid] = dict(previous)
        store.put_many("pairs", pairs)
        existing_events = store.all("dispatches")
        store.put_many("dispatches", {key: value for key, value in events.items() if key not in existing_events})
        sheets.refresh_controls(store, utcnow())
        # Seed current day's counters from known legacy sends; never reset existing usage.
        import pytz
        today = utcnow().astimezone(pytz.timezone(settings.TIMEZONE)).date()
        legacy_today = [e for e in store.all("dispatches").values() if e.get("state") == "legacy_accepted" and e.get("at") and e["at"].astimezone(pytz.timezone(settings.TIMEZONE)).date() == today]
        dk = ("daily", "live:" + today.isoformat())
        mk = ("mailbox_daily", today.isoformat())
        def seed(d):
            daily = dict(d[dk] or {"total": 0, "campaigns": {}, "next_campaign_at": {}})
            # Maintain imported component separately so rerunning adds only the delta.
            previous = daily.get("legacy_count", 0)
            delta = max(0, len(legacy_today) - previous)
            daily["total"] = daily.get("total", 0) + delta
            counts = dict(daily.get("campaigns", {}))
            old_counts = daily.get("legacy_campaigns", {})
            new_counts = {c: sum(e["campaign"] == c for e in legacy_today) for c in CATALOG}
            for c in CATALOG:
                counts[c] = counts.get(c, 0) + max(0, new_counts[c] - old_counts.get(c, 0))
            daily.update(campaigns=counts, legacy_count=len(legacy_today), legacy_campaigns=new_counts)
            mailbox = dict(d[mk] or {"total": 0})
            mailbox_delta = max(0, len(legacy_today) - mailbox.get("legacy_count", 0))
            mailbox.update(total=mailbox.get("total", 0) + mailbox_delta, legacy_count=len(legacy_today))
            return {dk: daily, mk: mailbox}, None
        store.atomic([dk, mk], seed)
        def ready(d):
            return {GLOBAL: dict(d[GLOBAL], migration_ready=True, contacts_synced_at=utcnow(), last_import=run_id, backup=backup_url)}, None
        store.atomic([GLOBAL], ready)
        sheets.update_report(store)
        store.atomic([GLOBAL], lambda d: ({GLOBAL: dict(d[GLOBAL], maintenance=False)}, None))
        print(json.dumps({"status": "applied", "summary": summary, "backup": backup_url, "run_id": run_id}))
    finally:
        # On any error maintenance remains True; fixing/retrying cannot silently send.
        def unlock(d):
            if d[GATE].get("token") != token:
                return {}, None
            return {GATE: dict(d[GATE], until=utcnow())}, None
        store.atomic([GATE], unlock)


if __name__ == "__main__":
    main()
