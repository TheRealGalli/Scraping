from datetime import timedelta

import pytest

from config import settings
from services.campaign_catalog import CATALOG
from services.campaign_engine import CampaignEngine, GLOBAL, GATE
from services.campaign_migration import prepare_import
from services.campaign_selection import SHORTLIST_SIZE, build_selection_queues, geography, previously_contacted
from test_campaigns import NOW, add, setup


def located(store, email, city, province, campaign="nfc", history=None):
    cid = add(store, email, campaign, history)
    store.data[("contacts", cid)]["locations"] = [
        {"region": "Italia", "province": province, "city": city}
    ]
    # Give this test contact one campaign; do not rely on cross-campaign ties.
    for other in CATALOG:
        if other != campaign:
            store.data[("pairs", other + ":" + cid)]["state"] = "sent"
    return cid


def publish(store, now=NOW):
    queues = build_selection_queues(
        store.all("contacts"), store.all("pairs"), store.all("suppressions"),
        store.all("campaigns"), now,
    )
    store.put_many("selection_queues", queues)
    return queues


@pytest.fixture
def smart(setup, monkeypatch):
    monkeypatch.setattr(settings, "SMART_SELECTION_ENABLED", True)
    store, transport = setup
    for campaign in CATALOG:
        store.data[("campaigns", campaign)]["enabled"] = campaign in {"nfc", "media"}
    return store, transport


def test_shortlist_reaches_other_cities_beyond_a_large_milan_block(smart):
    store, _ = smart
    for n in range(SHORTLIST_SIZE + 20):
        located(store, f"lead{n}@milano.it", "Milano", "MI")
    roma = located(store, "hello@roma.it", "Roma", "RM")
    torino = located(store, "hello@torino.it", "Torino", "TO")
    queue = publish(store)["nfc"]["modes"]["live"]
    assert len(queue["entries"]) == SHORTLIST_SIZE
    assert queue["first_contact_total"] == SHORTLIST_SIZE + 22
    ids = {entry["contact_id"] for entry in queue["entries"]}
    assert {roma, torino} <= ids


def test_first_contact_wins_even_if_its_city_already_received_more(smart):
    store, transport = smart
    located(store, "old@roma.it", "Roma", "RM", history=[NOW - timedelta(days=40)])
    located(store, "new@milano.it", "Milano", "MI")
    # Roma is unserved; the new Milano contact still has first priority.
    milano = geography({"locations": [{"region": "Italia", "province": "MI", "city": "Milano"}]})
    store.data[GATE] = {"selection_live": {"day": "2026-11-02", "provinces": {milano[0]: 20}, "cities": {milano[1]: 20}}}
    publish(store)
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "accepted"
    assert transport.send.call_args.args[0] == "new@milano.it"


def test_new_contacts_in_another_campaign_take_priority_over_followups(smart):
    store, transport = smart
    located(store, "old@milano.it", "Milano", "MI", history=[NOW - timedelta(days=40)])
    located(store, "new@roma.it", "Roma", "RM", campaign="media")
    publish(store)
    engine = CampaignEngine(store, transport, lambda: NOW)
    assert engine.run("nfc")["reason"] == "no_eligible_candidates"
    transport.send.assert_not_called()
    assert engine.run("media")["status"] == "accepted"
    assert transport.send.call_args.args[0] == "new@roma.it"


def test_geographic_rotation_is_shared_across_campaigns_and_instances(smart):
    store, transport = smart
    located(store, "first@milano.it", "Milano", "MI")
    located(store, "second@milano.it", "Milano", "MI", campaign="media")
    located(store, "hello@torino.it", "Torino", "TO", campaign="media")
    publish(store)
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "accepted"
    later = NOW + timedelta(minutes=3)
    assert CampaignEngine(store, transport, lambda: later).run("media")["status"] == "accepted"
    assert transport.send.call_args.args[0] == "hello@torino.it"
    assert sum(store.get(*GATE)["selection_live"]["cities"].values()) == 2


@pytest.mark.parametrize("age", [None, timedelta(minutes=31)])
def test_missing_or_stale_selection_stops_before_sending(smart, age):
    store, transport = smart
    located(store, "new@milano.it", "Milano", "MI")
    if age is not None:
        publish(store, NOW - age)
    result = CampaignEngine(store, transport, lambda: NOW).run("nfc")
    assert result["reason"] == "selection_sync_required"
    transport.send.assert_not_called()


def test_reservation_rechecks_history_changed_after_shortlist(smart):
    store, transport = smart
    cid = located(store, "new@milano.it", "Milano", "MI")
    publish(store)
    store.data[("contacts", cid)]["history"] = [NOW - timedelta(days=40)]
    result = CampaignEngine(store, transport, lambda: NOW).run("nfc")
    assert result["reason"] == "no_eligible_candidates"
    transport.send.assert_not_called()


def test_exhausted_first_contact_snapshot_waits_for_sync_before_followups(smart):
    store, transport = smart
    located(store, "first@milano.it", "Milano", "MI")
    located(store, "old@roma.it", "Roma", "RM", history=[NOW - timedelta(days=40)])
    publish(store)
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "accepted"
    later = NOW + timedelta(minutes=15)
    assert CampaignEngine(store, transport, lambda: later).run("nfc")["reason"] == "no_eligible_candidates"
    assert transport.send.call_count == 1
    publish(store, later)
    assert CampaignEngine(store, transport, lambda: later).run("nfc")["status"] == "accepted"
    assert transport.send.call_args.args[0] == "old@roma.it"


def test_suppression_added_after_shortlist_is_still_enforced(smart):
    store, transport = smart
    cid = located(store, "new@milano.it", "Milano", "MI")
    publish(store)
    store.data[("suppressions", cid)] = {"blocked": True}
    CampaignEngine(store, transport, lambda: NOW).run("nfc")
    transport.send.assert_not_called()


def test_out_of_target_new_contact_does_not_block_an_eligible_followup(smart):
    store, transport = smart
    located(store, "old@milano.it", "Milano", "MI", history=[NOW - timedelta(days=40)])
    cid = located(store, "new@roma.it", "Roma", "RM", campaign="media")
    store.data[("contacts", cid)]["sectors"] = ["Non classificato"]
    publish(store)
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "accepted"
    assert transport.send.call_args.args[0] == "old@milano.it"


def test_new_contacts_in_a_campaign_with_exhausted_budget_do_not_block_others(smart, monkeypatch):
    store, transport = smart
    monkeypatch.setattr(settings, "GLOBAL_DAILY_LIMIT", 100)
    located(store, "old@milano.it", "Milano", "MI", history=[NOW - timedelta(days=40)])
    located(store, "new@roma.it", "Roma", "RM", campaign="media")
    publish(store)
    store.data[("daily", "live:2026-11-02")] = {"total": 50, "campaigns": {"media": 50}}
    store.data[("mailbox_daily", "2026-11-02")] = {"total": 50}
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "accepted"
    assert transport.send.call_args.args[0] == "old@milano.it"


def test_geographic_sample_changes_between_sync_windows(smart):
    store, _ = smart
    for n in range(SHORTLIST_SIZE + 30):
        located(store, f"hello{n}@business.it", f"Citta {n}", "Provincia")
    first = publish(store)["nfc"]["modes"]["live"]["entries"]
    next_window = publish(store, NOW + timedelta(minutes=15))["nfc"]["modes"]["live"]["entries"]
    assert {e["city"] for e in first} != {e["city"] for e in next_window}


def test_geographic_daily_counts_reset_on_the_next_rome_day(smart):
    store, transport = smart
    located(store, "new@milano.it", "Milano", "MI")
    store.data[GATE] = {"selection_live": {"day": "2026-11-01", "provinces": {"old": 150}, "cities": {"old": 150}}}
    publish(store)
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "accepted"
    stats = store.get(*GATE)["selection_live"]
    assert stats["day"] == "2026-11-02" and "old" not in stats["cities"]
    assert sum(stats["cities"].values()) == 1


def test_owned_test_sends_preserve_first_contact_priority_and_live_geo_counts(smart, monkeypatch):
    store, transport = smart
    cid = located(store, "new@milano.it", "Milano", "MI")
    monkeypatch.setattr(settings, "SENDER_MODE", "test")
    monkeypatch.setattr(settings, "TEST_RECIPIENTS", "owner@owned.it")
    publish(store)
    assert CampaignEngine(store, transport, lambda: NOW).run("nfc")["status"] == "accepted"
    assert transport.send.call_args.args[0] == "owner@owned.it"
    assert not previously_contacted(store.get("contacts", cid))
    assert not store.get(*GATE).get("selection_live")
    assert sum(store.get(*GATE)["selection_test"]["cities"].values()) == 1


def test_first_contact_priority_uses_real_history_including_legacy_sends():
    assert not previously_contacted({"test_sent": ["nfc"], "test_history": [NOW]})
    assert previously_contacted({"sent": ["nfc"]})
    assert previously_contacted({"legacy_keys": ["old-send-without-timestamp"]})
    assert previously_contacted({"history": [NOW - timedelta(days=100)]})


def test_import_captures_geography_and_deduplicates_email_preserving_history():
    rows = [["headers"],
            ["p1", "Lombardia", "Milano", "Milano", "Hospitality", "", "info@business.it", "Inviato", "2026-10-23 10:00"],
            ["p2", "Piemonte", "Torino", "Torino", "Hospitality", "", "INFO@business.it", "Da inviare"]]
    _, contacts, _, _ = prepare_import(rows, {}, {}, "nfc", NOW)
    assert len(contacts) == 1
    contact = next(iter(contacts.values()))
    assert {loc["city"] for loc in contact["locations"]} == {"Milano", "Torino"}
    assert contact["sent"] == ["nfc"] and len(contact["history"]) == 1
    _, again, _, _ = prepare_import(rows, contacts, {}, "nfc", NOW)
    assert next(iter(again.values()))["locations"] == contact["locations"]
