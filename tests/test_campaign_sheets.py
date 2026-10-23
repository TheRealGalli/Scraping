from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from gspread.utils import a1_to_rowcol

from services.campaign_catalog import CATALOG
from services.campaign_engine import GLOBAL
from services.campaign_sheets import CampaignSheets, HEADERS
from services.recipient_policy import contact_id


class Sheet:
    def __init__(self, title, values):
        self.title, self.values = title, deepcopy(values)
        self.row_count, self.col_count = 1000, 12
        self.calls = []

    def get_all_values(self):
        return deepcopy(self.values)

    def resize(self, rows, cols):
        self.row_count, self.col_count = rows, cols

    def update(self, range_name, values, value_input_option):
        assert value_input_option == "RAW"
        self.calls.append((range_name, deepcopy(values)))
        row, col = a1_to_rowcol(range_name.split(":")[0])
        for n, data in enumerate(values, row - 1):
            while len(self.values) <= n:
                self.values.append([])
            while len(self.values[n]) < col - 1 + len(data):
                self.values[n].append("")
            self.values[n][col - 1:col - 1 + len(data)] = data

    def batch_update(self, patches, value_input_option):
        for patch in patches:
            self.update(patch["range"], patch["values"], value_input_option)

    def append_rows(self, rows, value_input_option):
        assert value_input_option == "RAW"
        self.values.extend(deepcopy(rows))

    def clear(self):
        self.values = []


class Book:
    def __init__(self, sheets):
        self.sheets = {s.title: s for s in sheets}

    def worksheet(self, name):
        return self.sheets[name]


def test_contact_projection_preserves_human_columns_and_raw_values():
    cid = contact_id("hello@business.it")
    old = [cid, "hello@business.it", "Hospitality", "FALSE", "", "", "", "request-123", "", ""]
    sheet = Sheet("Contatti", [HEADERS["Contatti"], old])
    adapter = CampaignSheets(Book([sheet]))
    generated = [cid, "hello@business.it", "Hospitality; Automotive", "TRUE", "review", "today", "nfc", "wrong-reference", "sincronizzato", "tomorrow"]
    adapter.update_contacts([generated])
    assert sheet.values[1][3] == "FALSE"
    assert sheet.values[1][7] == "request-123"
    assert sheet.values[1][2] == "Hospitality; Automotive"
    assert all(not r.startswith("D") and not r.startswith("H") for r, _ in sheet.calls)


def test_event_projection_reconciles_state_without_duplicate_rows():
    header = HEADERS["Invii"]
    old = ["event-1", "contact", "nfc", "sender", "date", "started", "live", "", "", "v1"]
    sheet = Sheet("Invii", [header, old])
    adapter = CampaignSheets(Book([sheet]))
    accepted = old[:]
    accepted[5] = "accepted"
    adapter.append_events([header, accepted])
    adapter.append_events([header, accepted])
    assert len(sheet.values) == 2
    assert sheet.values[1][5] == "accepted"


def test_config_and_suppression_snapshot_fail_closed_and_are_monotonic():
    configs = [[cid, "FALSE", "50", "5", "", "5;10;50", "720"] for cid in CATALOG]
    exclusions = Sheet("Esclusioni", [HEADERS["Esclusioni"], ["hello@business.it", "globale", "rifiuto", "", "TRUE"]])
    adapter = CampaignSheets(Book([Sheet("Campagne", [HEADERS["Campagne"]] + configs), exclusions, Sheet("ControlloInvii", [HEADERS["ControlloInvii"], ["TRUE"]])]))
    data = {}
    store = MagicMock()
    store.get.side_effect = lambda coll, key: data.get((coll, key), {})
    store.put_many.side_effect = lambda coll, entries: data.update({(coll, k): v for k, v in entries.items()})
    store.atomic.side_effect = lambda keys, callback: callback({GLOBAL: {}})[1]
    adapter.refresh_controls(store, datetime.now(timezone.utc))
    assert data[("suppressions", contact_id("hello@business.it"))]["blocked"]
    exclusions.values = [HEADERS["Esclusioni"]]
    adapter.refresh_controls(store, datetime.now(timezone.utc))
    assert data[("suppressions", contact_id("hello@business.it"))]["blocked"]
    exclusions.values.append(["bad-address", "globale", "", "", "TRUE"])
    with pytest.raises(ValueError):
        adapter.refresh_controls(store, datetime.now(timezone.utc))


def test_report_reconciles_rome_day_effective_quota_and_shared_budget():
    now = datetime(2026, 11, 2, 10, tzinfo=timezone.utc)
    cid = contact_id("hello@business.it")
    sheets = [Sheet(name, [HEADERS[name]]) for name in ("Contatti", "Invii", "Panoramica")]
    adapter = CampaignSheets(Book(sheets))
    store = MagicMock()
    data = {
        "contacts": {cid: {"email": "hello@business.it", "sectors": ["Hospitality"], "enabled": True, "history": [now], "sent": ["nfc"]}},
        "dispatches": {"dispatch-1": {"contact_id": cid, "campaign": "nfc", "at": now, "mode": "live", "state": "accepted"}},
        "daily": {"live:2026-11-02": {"total": 1, "campaigns": {"nfc": 1}}},
    }
    store.all.side_effect = lambda collection: data[collection]
    def get(collection, key):
        if collection == "control":
            return {"paused": False, "contacts_synced_at": now}
        if collection == "mailbox_daily":
            return {"total": 2}
        return {"daily_limit": 50, "initial_limit": 5, "started_on": "", "ramp": [5]}
    store.get.side_effect = get
    adapter.update_report(store)
    row = next(row for row in adapter.book.worksheet("Panoramica").values[1:] if row[2] == "nfc")
    assert row[3:6] == [1, 1, 0]
    assert row[7:12] == [50, 5, 150, 2, 148]
    assert len(adapter.book.worksheet("Invii").values) == 2


def test_configure150_repairs_paste_and_converts_cursor_once(monkeypatch):
    from scripts.campaign_admin import configure150
    from test_campaigns import MemoryStore
    sheets = [Sheet(name, [HEADERS[name]]) for name in HEADERS]
    sheets.extend([
        Sheet("Italy", [["original"], ["keep-me"]]),
        Sheet("ConfigState", [["Key", "Value", "Last Updated"], ["matrix_index", "9", "old"]])
    ])
    book = Book(sheets)
    book.worksheet("Campagne").values = [["all pasted text in A1"]]
    book.worksheet("ControlloInvii").values.append(["FALSE"])
    adapter = CampaignSheets(book)
    monkeypatch.setattr(adapter, "ensure", lambda: None)
    monkeypatch.setattr(adapter, "update_report", lambda store: None)
    backups = []
    def backup(*args):
        backups.append(deepcopy(book.worksheet("Campagne").values))
        return "gs://test/backup"
    monkeypatch.setattr("scripts.campaign_admin.backup", backup)
    store = MemoryStore()
    configure150(store, adapter, "test", True)
    rows = adapter.rows("Campagne")
    assert rows[0] == HEADERS["Campagne"]
    assert sum(int(row[2]) for row in rows[1:]) == 150
    assert all(int(row[2]) == int(row[3]) == int(row[5]) for row in rows[1:])
    assert adapter.rows("ConfigState")[1][1] == "12"
    assert adapter.rows("ConfigState")[2][1] == "expanded_v2"
    configure150(store, adapter, "test", True)
    assert adapter.rows("ConfigState")[1][1] == "12"
    assert adapter.rows("Italy") == [["original"], ["keep-me"]]
    assert store.get(*GLOBAL)["paused"] is True
    assert backups[0] == [["all pasted text in A1"]]
    assert any(row[1] == "Agenzie Immobiliari" for row in adapter.rows("RegoleSettori")[1:])


def test_configure_backup_failure_does_not_rewrite_sheet(monkeypatch):
    from scripts.campaign_admin import configure150
    from test_campaigns import MemoryStore
    original = [["broken original"]]
    adapter = CampaignSheets(Book([Sheet("Campagne", original)]))
    def fail(*args):
        raise RuntimeError("backup failed")
    monkeypatch.setattr("scripts.campaign_admin.backup", fail)
    store = MemoryStore()
    with pytest.raises(RuntimeError):
        configure150(store, adapter, "test")
    assert adapter.rows("Campagne") == original
    assert store.get(*GLOBAL)["maintenance"] is True
    assert store.get(*GLOBAL)["paused"] is True
