import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from config import settings
from services.campaign_catalog import CATALOG
from services.campaign_engine import CampaignEngine, GLOBAL, GATE, effective_limit
from services.campaign_migration import prepare_import
from services.campaign_sheets import CampaignSheets, boolean
from services.campaign_transport import CampaignSMTP, TransportResult
from services.recipient_policy import contact_id, exclusion_reason, next_contact_time, normalize_email
from services.time_filter import is_sender_operating_hours

NOW = datetime(2026, 11, 2, 10, tzinfo=timezone.utc)


class MemoryStore:
    """Atomic document semantics; no cloud credentials or network in tests."""
    def __init__(self):
        self.data = {}
        self.lock = threading.RLock()

    def atomic(self, keys, fn):
        with self.lock:
            updates, result = fn({key: copy.deepcopy(self.data.get(key, {})) for key in keys})
            self.data.update(copy.deepcopy(updates))
            return result

    def get(self, collection, key):
        with self.lock:
            return copy.deepcopy(self.data.get((collection, key), {}))

    def put_many(self, collection, records):
        with self.lock:
            self.data.update({(collection, key): copy.deepcopy(value) for key, value in records.items()})

    def all(self, collection):
        return {key: copy.deepcopy(value) for (coll, key), value in self.data.items() if coll == collection}

    def due(self, campaign, now, limit=100):
        return sorted([(key, value) for key, value in self.all("pairs").items() if value["campaign"] == campaign and value["state"] == "queued" and value["eligible_at"] <= now], key=lambda pair: pair[1]["eligible_at"])[:limit]


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(settings, "SENDING_ENABLED", True)
    monkeypatch.setattr(settings, "SENDER_MODE", "live")
    monkeypatch.setattr(settings, "GLOBAL_DAILY_LIMIT", 50)
    monkeypatch.setattr(settings, "GLOBAL_INTERVAL_SECONDS", 120)
    monkeypatch.setattr(settings, "GLOBAL_INTERVAL_MAX_SECONDS", 120)
    monkeypatch.setattr(settings, "WORKSPACE_EMAIL", "carlo@owned.it")
    monkeypatch.setattr(CampaignSheets, "refresh_controls", lambda *args: None)
    store = MemoryStore()
    store.data[GLOBAL] = {"migration_ready": True, "paused": False, "maintenance": False, "contacts_synced_at": NOW}
    for campaign in CATALOG:
        store.data[("campaigns", campaign)] = {"enabled": True, "daily_limit": 50, "initial_limit": 50, "started_on": "", "ramp": [50], "interval_seconds": 720}
    transport = MagicMock()
    transport.send.return_value = TransportResult("accepted", "msg-id")
    return store, transport


def add(store, email="hello@business.it", campaign="nfc", history=None):
    cid = contact_id(email)
    store.data[("contacts", cid)] = {"email": email, "enabled": True, "sectors": ["Hospitality"], "history": history or [], "sent": [], "campaign_order": [campaign] + [c for c in CATALOG if c != campaign]}
    for c in CATALOG:
        store.data[("pairs", c + ":" + cid)] = {"contact_id": cid, "campaign": c, "state": "queued", "eligible_at": NOW}
    return cid


@pytest.mark.parametrize("address", ["support@business.it", "tech-support@business.it", "privacy@business.it", "DPO@business.it", "no-reply@business.it", "pec@business.it", "hello@pec.business.it"])
def test_address_guards(address):
    assert exclusion_reason(address)


@pytest.mark.parametrize("address", ["hello@business.it", "info@business.it", "supporter@business.it", "carlo@specchio.it", "carlo+sales@business.it"])
def test_no_overbroad_substring_filter(address):
    assert exclusion_reason(address) == ""


@pytest.mark.parametrize("address", ["bad", "a@@b.it", "a@-b.it", "a..b@business.it", "a@business.it\r\nBcc:x@b.it", "a@b.it;b@b.it"])
def test_invalid_addresses(address):
    with pytest.raises(ValueError):
        normalize_email(address)


def test_cooldown_does_not_slide_and_window_boundary():
    history = [NOW, NOW + timedelta(days=30)]
    assert next_contact_time(history[:1], NOW + timedelta(days=3), 30, 90, 2) == NOW + timedelta(days=30)
    assert next_contact_time(history, NOW + timedelta(days=31), 30, 90, 2) == NOW + timedelta(days=90)
    assert next_contact_time(history, NOW + timedelta(days=90), 30, 90, 2) == NOW + timedelta(days=90)


@pytest.mark.parametrize("iso,allowed", [("2026-11-02T07:29:00+00:00", False), ("2026-11-02T08:00:00+00:00", True), ("2026-11-02T17:30:00+00:00", False), ("2026-11-07T10:00:00+00:00", False), ("2026-07-06T07:00:00+00:00", True)])
def test_business_hours(iso, allowed):
    assert is_sender_operating_hours(datetime.fromisoformat(iso)) == allowed


def test_concurrent_scheduler_and_retry_send_once(setup):
    store, transport = setup
    cid = add(store)
    engine = CampaignEngine(store, transport, lambda: NOW)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: engine.run("nfc", "same-schedule"), range(6)))
    assert sum(r["status"] == "accepted" for r in results) == 1
    assert transport.send.call_count == 1
    assert store.get("contacts", cid)["sent"] == ["nfc"]
    assert store.get("daily", "live:2026-11-02")["total"] == 1


def test_cross_campaign_cooldown_and_scan_continues(setup):
    store, transport = setup
    blocked = add(store, "hello@first.it", "social", [NOW - timedelta(days=1)])
    add(store, "hello@second.it", "social")
    result = CampaignEngine(store, transport, lambda: NOW).run("social")
    assert result["status"] == "accepted"
    assert transport.send.call_args[0][0] == "hello@second.it"
    assert store.get("pairs", "social:" + blocked)["eligible_at"] == NOW + timedelta(days=29)


def test_manual_suppression_applies_across_campaigns(setup):
    store, transport = setup
    cid = add(store)
    store.data[("suppressions", cid)] = {"blocked": True}
    for campaign in CATALOG:
        CampaignEngine(store, transport, lambda: NOW).run(campaign)
    transport.send.assert_not_called()


def test_timeout_is_not_retried_after_expired_gate(setup):
    store, transport = setup
    cid = add(store)
    transport.send.return_value = TransportResult("uncertain", "msg", "TimeoutError")
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "uncertain"
    later = NOW + timedelta(minutes=30)
    store.data[GLOBAL]["contacts_synced_at"] = later
    CampaignEngine(store, transport, lambda: later).run("nfc")
    assert transport.send.call_count == 1
    assert store.get("contacts", cid)["active"]


def test_daily_limit_survives_new_engine_instance(setup):
    store, transport = setup
    add(store)
    store.data[("mailbox_daily", "2026-11-02")] = {"total": 50}
    result = CampaignEngine(store, transport, lambda: NOW).run("nfc")
    assert result["reason"] == "global_daily_limit"
    transport.send.assert_not_called()


def test_dry_run_is_read_only_for_contacts_and_counters(setup, monkeypatch):
    store, transport = setup
    cid = add(store)
    before = store.get("contacts", cid)
    monkeypatch.setattr(settings, "SENDER_MODE", "dry_run")
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "preview"
    assert store.get("contacts", cid) == before
    assert not store.all("daily")
    assert not store.all("dispatches")
    transport.send.assert_not_called()


def test_test_mode_never_addresses_source_and_keeps_live_history(setup, monkeypatch):
    store, transport = setup
    cid = add(store)
    monkeypatch.setattr(settings, "SENDER_MODE", "test")
    monkeypatch.setattr(settings, "TEST_RECIPIENTS", "owner@owned.it")
    result = CampaignEngine(store, transport, lambda: NOW).run("nfc")
    assert result["status"] == "accepted"
    assert transport.send.call_args[0][0] == "owner@owned.it"
    assert store.get("contacts", cid)["sent"] == []
    assert store.get("contacts", cid)["test_sent"] == ["nfc"]
    assert not store.get("daily", "live:2026-11-02")


def test_test_retry_does_not_defer_live_pair_and_budget_is_shared(setup, monkeypatch):
    store, transport = setup
    cid = add(store)
    original = store.get("pairs", "nfc:" + cid)
    monkeypatch.setattr(settings, "SENDER_MODE", "test")
    monkeypatch.setattr(settings, "TEST_RECIPIENTS", "owner@owned.it")
    monkeypatch.setattr(settings, "GLOBAL_DAILY_LIMIT", 1)
    engine = CampaignEngine(store, transport, lambda: NOW)
    assert engine.run("nfc")["status"] == "accepted"
    engine.run("nfc")
    assert store.get("pairs", "nfc:" + cid) == original
    monkeypatch.setattr(settings, "SENDER_MODE", "live")
    assert engine.run("nfc")["reason"] == "global_daily_limit"
    assert transport.send.call_count == 1


def test_new_rome_day_has_new_quota(setup, monkeypatch):
    store, transport = setup
    add(store)
    store.data[("mailbox_daily", "2026-11-02")] = {"total": 50}
    tomorrow = NOW + timedelta(days=1)
    store.data[GLOBAL]["contacts_synced_at"] = tomorrow
    assert CampaignEngine(store, transport, lambda: tomorrow).run("nfc")["status"] == "accepted"


def test_global_turn_rotates_between_recent_ready_campaigns(setup):
    store, transport = setup
    add(store, "one@business.it", "nfc")
    add(store, "two@business.it", "social")
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "accepted"
    later = NOW + timedelta(minutes=3)
    assert CampaignEngine(store, transport, lambda: later).run("social")["status"] == "accepted"
    assert transport.send.call_count == 2


def test_reviewed_pair_cannot_hold_other_campaign_forever(setup):
    store, transport = setup
    cid = add(store, campaign="nfc")
    store.data[("pairs", "nfc:" + cid)].update(state="review", reason="transport_rejected")
    store.data[GATE] = {"seen": {"nfc": NOW}}
    assert CampaignEngine(store, transport, lambda: NOW).run("social")["status"] == "accepted"


def test_expired_gate_does_not_unlock_unresolved_recipient(setup):
    store, transport = setup
    cid = add(store)
    store.data[("contacts", cid)]["active"] = "previous-crashed-send"
    store.data[GATE] = {"token": "old", "until": NOW - timedelta(minutes=1)}
    CampaignEngine(store, transport, lambda: NOW).run("nfc")
    transport.send.assert_not_called()


def test_stale_import_stops_sender(setup):
    store, transport = setup
    add(store)
    store.data[GLOBAL]["contacts_synced_at"] = NOW - timedelta(hours=1)
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["reason"] == "contact_sync_required"
    transport.send.assert_not_called()


def test_fresh_sheets_failure_never_calls_transport(setup, monkeypatch):
    store, transport = setup
    add(store)
    def fail(*args):
        raise RuntimeError("Sheets unavailable")
    monkeypatch.setattr(CampaignSheets, "refresh_controls", fail)
    with pytest.raises(RuntimeError):
        CampaignEngine(store, transport, lambda: NOW).run("nfc")
    transport.send.assert_not_called()


def test_suppression_between_reserve_and_start_cancels(setup):
    store, transport = setup
    cid = add(store)
    engine = CampaignEngine(store, transport, lambda: NOW)
    assert engine._acquire("token", NOW)
    attempt = engine._reserve("nfc", "nfc:" + cid, cid, "token", "test")
    store.data[("suppressions", cid)] = {"blocked": True}
    assert engine._start(attempt, "token") is False


def test_hard_bounce_is_global(setup):
    store, transport = setup
    cid = add(store)
    transport.send.return_value = TransportResult("hard_bounce", "msg", "recipient_refused")
    CampaignEngine(store, transport, lambda: NOW).run("nfc")
    assert store.get("suppressions", cid)["blocked"] is True


def test_import_idempotence_duplicates_and_uncertain_history():
    headers = ["Place ID", "Regione", "Provincia", "Città", "Settore", "Sito Web", "Email", "Stato Invio", "Data Invio"]
    def row(place, email, state, date=""):
        return [place, "Toscana", "Siena", "Siena", "Hospitality", "", email, state, date]
    rows = [headers, row("1", "hello@business.it", "Inviato", "2026-10-01 10:00"), row("2", "hello@business.it", "Duplicato Email"), row("3", "error@business.it", "Errore Invio"), row("4", "nodate@business.it", "Inviato")]
    summary, contacts, pairs, events = prepare_import(rows, {}, {}, "nfc", NOW)
    assert summary["duplicate_email_rows"] == 1
    assert len(events) == 2
    assert contacts[contact_id("hello@business.it")]["sent"] == ["nfc"]
    assert contacts[contact_id("error@business.it")]["review_reason"]
    assert contacts[contact_id("nodate@business.it")]["review_reason"]
    _, again, _, new_events = prepare_import(rows, contacts, {}, "nfc", NOW)
    assert len(again[contact_id("hello@business.it")]["history"]) == 1
    # Re-emitting deterministic IDs repairs an interrupted import whose contacts
    # committed before its historical events. Existing events are not overwritten.
    assert set(new_events) == set(events)


def test_ramp_and_future_start():
    cfg = {"daily_limit": 40, "initial_limit": 5, "started_on": "2026-11-02", "ramp": [5, 10, 20, 40]}
    assert effective_limit(cfg, NOW.date()) == 5
    assert effective_limit(cfg, (NOW + timedelta(days=14)).date()) == 20
    assert effective_limit(cfg, (NOW - timedelta(days=1)).date()) == 0


def test_transport_embeds_only_current_image(monkeypatch):
    monkeypatch.setattr(settings, "WORKSPACE_EMAIL", "owner@owned.it")
    monkeypatch.setattr(settings, "WORKSPACE_APP_PASSWORD", "fake-test-only")
    server = MagicMock()
    server.__enter__.return_value = server
    server.send_message.return_value = {}
    monkeypatch.setattr("smtplib.SMTP", lambda *args, **kwargs: server)
    result = CampaignSMTP().send("recipient@owned.it", "social", "test")
    assert result.status == "accepted"
    message = server.send_message.call_args[0][0]
    assert "cid:campaign_art" in message.get_body(preferencelist=("html",)).get_content()
    images = [p for p in message.walk() if p.get_content_maintype() == "image"]
    assert len(images) == 1 and images[0].get_filename() == "social.jpg"
    assert "assets/" not in message.get_body(preferencelist=("html",)).get_content()


def test_campaign_route_fails_closed_without_secret(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    monkeypatch.setattr(settings, "SENDER_CRON_SECRET", "")
    assert TestClient(app).post("/send-emails/nfc").status_code == 401
    assert TestClient(app).post("/send-emails/unknown").status_code == 404
    assert TestClient(app).post("/send-emails").json()["reason"] == "legacy_sender_retired"


@pytest.mark.parametrize("pause", [120, 240])
def test_dispatch_persists_variable_pause_across_restarts(setup, monkeypatch, pause):
    store, transport = setup
    add(store, "first@business.it", "consulenza")
    add(store, "second@business.it", "training")
    monkeypatch.setattr(settings, "GLOBAL_INTERVAL_MAX_SECONDS", 240)
    monkeypatch.setattr("services.campaign_engine.random.randint", lambda low, high: pause)
    result = CampaignEngine(store, transport, lambda: NOW).dispatch()
    assert result["status"] == "accepted"
    assert result["pause_seconds"] == pause
    assert store.get("mailbox_daily", "2026-11-02")["next_at"] == NOW + timedelta(seconds=pause)
    result = CampaignEngine(store, transport, lambda: NOW + timedelta(seconds=pause - 1)).dispatch()
    assert result["reason"] == "global_interval"
    assert transport.send.call_count == 1


def test_dispatch_concurrent_ticks_cannot_burst(setup):
    store, transport = setup
    for i, campaign in enumerate(CATALOG):
        add(store, "business%d@business.it" % i, campaign)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: CampaignEngine(store, transport, lambda: NOW).dispatch(), range(6)))
    assert sum(r["status"] == "accepted" for r in results) == 1
    assert transport.send.call_count == 1


def test_dispatch_skips_disabled_campaign_and_never_catches_up(setup):
    store, transport = setup
    add(store, campaign="training")
    store.data[("campaigns", "consulenza")]["enabled"] = False
    result = CampaignEngine(store, transport, lambda: NOW).dispatch()
    assert result["status"] == "accepted"
    later = NOW + timedelta(hours=1)
    store.data[GLOBAL]["contacts_synced_at"] = later
    add(store, "other@business.it", "nfc")
    before = transport.send.call_count
    CampaignEngine(store, transport, lambda: later).dispatch()
    assert transport.send.call_count <= before + 1


def test_dispatch_respects_shared_legacy_budget(setup):
    store, transport = setup
    add(store)
    store.data[("mailbox_daily", "2026-11-02")] = {"total": 50, "legacy_count": 49}
    assert CampaignEngine(store, transport, lambda: NOW).dispatch()["reason"] == "global_daily_limit"
    transport.send.assert_not_called()


def test_pause_starts_after_slow_transport_finishes(setup):
    store, transport = setup
    add(store, campaign="consulenza")
    clock = [NOW]
    def send(*args):
        clock[0] += timedelta(seconds=45)
        return TransportResult("accepted", "slow")
    transport.send.side_effect = send
    CampaignEngine(store, transport, lambda: clock[0]).dispatch()
    assert store.get("mailbox_daily", "2026-11-02")["next_at"] == NOW + timedelta(seconds=165)


def test_dispatch_endpoint_requires_secret_and_stays_disabled(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    monkeypatch.setattr(settings, "SENDER_CRON_SECRET", "test-secret")
    monkeypatch.setattr(settings, "SENDING_ENABLED", False)
    client = TestClient(app)
    assert client.post("/dispatch-emails").status_code == 401
    assert client.post("/dispatch-emails", headers={"X-Sender-Secret": "test-secret"}).json()["reason"] == "sending_disabled"
