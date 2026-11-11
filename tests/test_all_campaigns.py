from datetime import timedelta
from unittest.mock import Mock

import pytest

from config import settings
from services.campaign_catalog import CATALOG, DEFAULT_LIMITS, render
from services.campaign_engine import validate_config, GLOBAL
from services.campaign_migration import prepare_import
from services.recipient_policy import contact_id
from test_campaigns import MemoryStore, NOW, setup
from test_selection_activation import activate


def test_previous_seven_campaign_sheet_keeps_archive_disabled():
    configs = {c: dict(enabled=True, daily_limit=20, initial_limit=20, ramp=[20],
                       started_on="", interval_seconds=720) for c in CATALOG if c != "archivio"}
    result = validate_config(configs)
    assert not result["archivio"]["enabled"]
    assert result["archivio"]["daily_limit"] == 0


@pytest.mark.parametrize("sector,first", [
    ("Studi Dentistici", "consulenza"), ("Studi Professionali", "consulenza"),
    ("Amministratori di Condominio", "archivio"), ("Grossisti e Distributori", "forecasting"),
    ("Gioiellerie", "media"), ("Ristorazione", "forecasting"),
])
def test_existing_contacts_gain_commercial_priority_without_losing_history(sector, first):
    cid = contact_id("studio@business.it")
    previous = {cid: dict(sent=["nfc"], history=[NOW-timedelta(days=40)],
                         campaign_order=["media", "nfc", "consulenza"], enabled=True)}
    rows = [["headers"], ["id", "Lazio", "Roma", "Roma", sector, "", "studio@business.it", "Da inviare"]]
    _, contacts, pairs, _ = prepare_import(rows, previous, {}, "nfc", NOW)
    contact = contacts[cid]
    assert contact["campaign_order"][0] == first
    assert contact["history"] == previous[cid]["history"]
    assert contact["sent"] == ["nfc"]
    if sector in {"Studi Professionali", "Studi Dentistici"}:
        assert "media:"+cid not in pairs
        assert "consulenza:"+cid in pairs and "archivio:"+cid in pairs
        assert "forecasting:"+cid not in pairs


def test_eight_approved_limits_sum_to_150_and_archive_template_is_ready():
    assert DEFAULT_LIMITS == dict(consulenza=35, training=15, nfc=20, sito=15, social=15,
                                  media=15, forecasting=15, archivio=20)
    assert sum(DEFAULT_LIMITS.values()) == 150
    _, html, plain, _ = render("archivio")
    assert "https://csd-station.it/archivio-ai/" in html
    assert "documenti riservati" in plain and "riferimenti" in plain


@pytest.mark.parametrize("fail", [False, True])
def test_shell_activation_uses_override_and_only_resumes_email_after_success(tmp_path, fail):
    result, calls = activate(tmp_path, fail_sync=fail, script_name="activate_all_campaigns.sh")
    job = next(c for c in calls if c[:3] == ["run", "jobs", "update"])
    execute = next(c for c in calls if c[:3] == ["run", "jobs", "execute"])
    assert not any(c.startswith("--args") for c in job)
    assert "--args=scripts/campaign_admin.py,activate150,--backup-bucket,scraping-505816-campaign-backups-707079344561" in execute
    assert "--update-env-vars=GLOBAL_DAILY_LIMIT=150" in job
    assert any("--update-env-vars=GLOBAL_DAILY_LIMIT=150,SMART_SELECTION_ENABLED=True" in c for c in calls)
    resumed = any(c[:4] == ["scheduler", "jobs", "resume", "campaign-email-dispatch"] for c in calls)
    assert resumed is not fail
    assert (result.returncode == 0) is not fail


def test_activation_does_not_unpause_if_sync_fails(monkeypatch):
    from scripts import campaign_admin as admin
    store, sheets = MemoryStore(), Mock()
    monkeypatch.setattr(settings, "GLOBAL_DAILY_LIMIT", 150)
    configure = Mock()
    monkeypatch.setattr(admin, "configure150", configure)
    def sync(args):
        raise RuntimeError("failed sync")
    monkeypatch.setattr(admin, "main", sync)
    with pytest.raises(RuntimeError, match="failed sync"):
        admin.activate150(store, sheets, "backup")
    configure.assert_called_once_with(store, sheets, "backup")
    sheets.book.worksheet.assert_not_called()


def test_activation_unpauses_only_after_successful_sync_and_reports_current_counts(monkeypatch):
    from scripts import campaign_admin as admin
    store, sheets = MemoryStore(), Mock()
    store.data[("mailbox_daily", "today")] = {"total": 81}
    events = []
    monkeypatch.setattr(settings, "GLOBAL_DAILY_LIMIT", 150)
    monkeypatch.setattr(admin, "configure150", lambda *args: events.append("configure"))
    def sync(args):
        events.append("sync")
        assert args == ["sync", "--legacy-campaign", "nfc", "--backup-bucket", "backup"]
        store.data[GLOBAL] = dict(contacts_synced_at=admin.utcnow(), paused=True, maintenance=False)
    monkeypatch.setattr(admin, "main", sync)
    sheets.configs.return_value = {c: dict(enabled=True, daily_limit=q, initial_limit=q) for c,q in DEFAULT_LIMITS.items()}
    def refresh(*args):
        events.append("resume")
        store.data[GLOBAL]["paused"] = False
    sheets.refresh_controls.side_effect = refresh
    admin.activate150(store, sheets, "backup")
    assert events == ["configure", "sync", "resume"]
    assert not store.get(*GLOBAL)["maintenance"] and not store.get(*GLOBAL)["paused"]
    assert store.get("mailbox_daily", "today")["total"] == 81
    sheets.update_report.assert_called_once_with(store)


def test_preexisting_media_pair_cannot_send_to_dentist(setup):
    from test_campaigns import add
    from services.campaign_engine import CampaignEngine
    store, transport = setup
    cid = add(store, campaign="media")
    store.data[("contacts", cid)]["sectors"] = ["Studi Dentistici"]
    result = CampaignEngine(store, transport, lambda: NOW).run("media")
    assert result["status"] == "skipped"
    assert store.get("pairs", "media:" + cid)["reason"] == "sector_not_targeted"
    transport.send.assert_not_called()


def test_global_150_is_shared_across_new_and_existing_campaigns(setup, monkeypatch):
    from test_campaigns import add
    from services.campaign_engine import CampaignEngine
    store, transport = setup
    monkeypatch.setattr(settings, "GLOBAL_DAILY_LIMIT", 150)
    cid = add(store, campaign="archivio")
    store.data[("contacts", cid)]["sectors"] = ["Studi Professionali"]
    store.data[("mailbox_daily", "2026-11-02")] = {"total": 149}
    assert CampaignEngine(store, transport, lambda: NOW).run("archivio")["status"] == "accepted"
    cid2 = add(store, email="another@business.it", campaign="nfc")
    result = CampaignEngine(store, transport, lambda: NOW + timedelta(minutes=5)).run("nfc")
    assert result["reason"] == "global_daily_limit"
    assert store.get("mailbox_daily", "2026-11-02")["total"] == 150
    assert transport.send.call_count == 1



def test_best_fit_claims_first_without_seen_marker_and_allows_others_during_interval(setup):
    from test_campaigns import add
    from services.campaign_catalog import campaign_order
    from services.campaign_engine import CampaignEngine
    store, transport = setup
    cid = add(store, campaign="archivio")
    store.data[("contacts", cid)].update(sectors=["Studi Professionali"],
        campaign_order=campaign_order(["Studi Professionali"]))
    result = CampaignEngine(store, transport, lambda: NOW).run("archivio")
    assert result["status"] == "skipped"
    transport.send.assert_not_called()
    assert CampaignEngine(store, transport, lambda: NOW).run("consulenza")["status"] == "accepted"
    cid2 = add(store, email="newstudio@business.it", campaign="archivio")
    store.data[("contacts", cid2)].update(sectors=["Studi Professionali"],
        campaign_order=campaign_order(["Studi Professionali"]))
    assert CampaignEngine(store, transport, lambda: NOW + timedelta(minutes=5)).run("archivio")["status"] == "accepted"
    assert transport.send.call_count == 2
