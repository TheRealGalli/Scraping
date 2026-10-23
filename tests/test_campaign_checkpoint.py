import copy
import gzip
import json
from datetime import datetime, timedelta, timezone

import pytest
from google.api_core.exceptions import NotFound, PreconditionFailed

from services.campaign_checkpoint import Checkpoint, IncrementalStore, COLLECTIONS, encode, decode
from services.campaign_store import business_value
from test_campaigns import MemoryStore


class TrackedStore(MemoryStore):
    def __init__(self):
        super().__init__()
        self.scans, self.queries, self.writes = [], [], []
        self.usage = {"document_reads": 0, "document_writes": 0}

    def all(self, collection):
        self.scans.append(collection)
        return super().all(collection)

    def changed_since(self, collection, since):
        self.queries.append((collection, since))
        return {key: copy.deepcopy(value) for (coll, key), value in self.data.items()
                if coll == collection and value.get("_updated_at", since - timedelta(days=1)) >= since}

    def put_many(self, collection, records):
        self.writes.extend((collection, key) for key in records)
        super().put_many(collection, records)


class Blob:
    def __init__(self):
        self.generation, self.body = None, None

    def reload(self):
        if self.body is None:
            raise NotFound("missing")

    def download_as_bytes(self, if_generation_match):
        assert if_generation_match == self.generation
        return self.body

    def upload_from_string(self, body, content_type, if_generation_match):
        if if_generation_match != (self.generation or 0):
            raise PreconditionFailed("another checkpoint won")
        self.body = body
        self.generation = (self.generation or 0) + 1


def checkpoint(store, blob):
    result = Checkpoint.__new__(Checkpoint)
    result.real, result.blob, result.generation = store, blob, 0
    result.identity = ["test-project", "(default)", "campaign_sender_v1"]
    return result


def test_checkpoint_bootstraps_once_then_reads_only_new_and_modified_documents():
    store, blob = TrackedStore(), Blob()
    store.data[("contacts", "one")] = {"email": "owner@business.it", "enabled": True}
    first = checkpoint(store, blob)
    cached = first.load()
    assert first.bootstrap and len(store.scans) == len(COLLECTIONS)
    first.save()
    store.scans.clear()
    stamp = datetime.now(timezone.utc)
    store.data[("contacts", "one")] = {"email": "owner@business.it", "enabled": False, "_updated_at": stamp}
    store.data[("dispatches", "delivery")] = {"state": "uncertain", "at": stamp, "_updated_at": stamp}
    second = checkpoint(store, blob)
    cached = second.load()
    assert not second.bootstrap and not store.scans
    assert len(store.queries) == len(COLLECTIONS)
    assert cached.all("contacts")["one"]["enabled"] is False
    assert cached.all("dispatches")["delivery"]["state"] == "uncertain"
    # Report access never creates more billable Firestore reads.
    assert cached.report_get("contacts", "one")["enabled"] is False
    second.save()
    store.data[("dispatches", "delivery")].update(state="accepted", _updated_at=datetime.now(timezone.utc))
    third = checkpoint(store, blob)
    assert third.load().all("dispatches")["delivery"]["state"] == "accepted"


def test_incremental_writer_skips_identical_data_and_preserves_live_atomic_reads():
    store = TrackedStore()
    data = {c: {} for c in COLLECTIONS}
    data["contacts"]["one"] = {"enabled": True, "_updated_at": datetime.now(timezone.utc)}
    cached = IncrementalStore(store, data)
    cached.put_many("contacts", {"one": {"enabled": True}})
    assert not store.writes
    cached.put_many("contacts", {"one": {"enabled": False}})
    assert store.writes == [("contacts", "one")]
    store.data[("control", "global")] = {"paused": True}
    assert cached.get("control", "global")["paused"] is True
    cached.atomic([("control", "global")], lambda d: ({("control", "global"): dict(d[("control", "global")], maintenance=True)}, None))
    assert cached.all("control")["global"] == {"paused": True, "maintenance": True}


def test_checkpoint_compare_and_swap_prevents_lost_updates():
    store, blob = TrackedStore(), Blob()
    first, stale = checkpoint(store, blob), checkpoint(store, blob)
    first.load()
    stale.load()
    first.save()
    with pytest.raises(PreconditionFailed):
        stale.save()
    # Successful snapshot remains intact and readable.
    assert checkpoint(store, blob).load().all("contacts") == {}


def test_weekly_audit_reconciles_out_of_band_deletion():
    store, blob = TrackedStore(), Blob()
    store.data[("contacts", "removed")] = {"enabled": True}
    first = checkpoint(store, blob)
    first.load()
    first.full_refresh_at -= timedelta(days=8)
    first.save()
    del store.data[("contacts", "removed")]
    fresh = checkpoint(store, blob)
    assert fresh.load().all("contacts") == {}
    assert fresh.bootstrap


def test_corrupt_checkpoint_fails_instead_of_silently_trusting_stale_data():
    blob = Blob()
    blob.body, blob.generation = b"invalid compressed data", 1
    with pytest.raises(gzip.BadGzipFile):
        checkpoint(TrackedStore(), blob).load()


def test_datetime_and_identity_roundtrip():
    now = datetime.now(timezone.utc)
    restored = json.loads(json.dumps({"date": now}, default=encode), object_hook=decode)
    assert restored["date"] == now
    blob = Blob()
    original = checkpoint(TrackedStore(), blob)
    original.load()
    original.save()
    different = checkpoint(TrackedStore(), blob)
    different.identity[0] = "wrong-project"
    with pytest.raises(ValueError, match="identity"):
        different.load()


def test_lazy_candidate_pages_keep_scan_cap_without_prefetching_100():
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from services.campaign_store import FirestoreStore
    snapshots = [SimpleNamespace(id=str(i), to_dict=lambda i=i: {"eligible_at": i}) for i in range(25)]
    class Query:
        def __init__(self, start=0, cap=100):
            self.start, self.cap = start, cap
        def where(self, **kwargs): return self
        def order_by(self, *args): return self
        def start_after(self, snapshot): return Query(int(snapshot.id) + 1, self.cap)
        def limit(self, cap): return Query(self.start, cap)
        def stream(self):
            return iter(snapshots[self.start:self.start + self.cap])
    store = FirestoreStore.__new__(FirestoreStore)
    store.db = MagicMock()
    store.db.collection.return_value = Query()
    store.prefix, store.usage = "test_", {"document_reads": 0, "document_writes": 0}
    iterator = store.due("nfc", datetime.now(timezone.utc))
    assert next(iterator)[0] == "0"
    assert store.usage["document_reads"] == 10
    store.usage["document_reads"] = 0
    assert len(list(store.due("nfc", datetime.now(timezone.utc), limit=23))) == 23
    assert store.usage["document_reads"] == 23


def test_sync_twice_does_not_rewrite_unchanged_contacts_pairs_or_backups(monkeypatch):
    import scripts.campaign_admin as admin
    from services.campaign_migration import prepare_import
    from services.campaign_sheets import HEADERS
    from test_campaigns import NOW, GLOBAL, GATE
    real, blob = TrackedStore(), Blob()
    source = [["Place ID", "Regione", "Provincia", "Città", "Settore", "Sito Web", "Email", "Stato Invio", "Data Invio", "Rating", "Recensioni"]]
    source += [[str(i), "", "", "", "Hospitality", "", "business%d@owned.it" % i, "Da inviare", "", "", ""] for i in range(100)]
    _, contacts, pairs, events = prepare_import(source, {}, {}, "nfc", NOW)
    real.put_many("contacts", contacts)
    real.put_many("pairs", pairs)
    real.data[GLOBAL] = {"migration_ready": True, "paused": True}
    real.data[GATE] = {"until": NOW - timedelta(seconds=1)}
    class Sheets:
        def ensure(self): pass
        def read_source(self): return source
        def contact_overrides(self): return {}
        def configs(self): return {"fixed": "config"}
        def rows(self, name): return [HEADERS[name], ["TRUE"]] if name == "ControlloInvii" else [HEADERS[name]]
        def refresh_controls(self, store, now): pass
        def update_report(self, store):
            assert len(store.all("contacts")) == len(source) - 1
            assert len(store.all("pairs")) >= len(pairs)
    backups = []
    monkeypatch.setattr(admin, "FirestoreStore", lambda: real)
    monkeypatch.setattr(admin, "CampaignSheets", Sheets)
    monkeypatch.setattr(admin, "utcnow", lambda: NOW)
    monkeypatch.setattr(admin, "backup", lambda *args: backups.append("backup") or "gs://bucket/backup")
    monkeypatch.setattr("services.campaign_checkpoint.Checkpoint", lambda store, bucket: checkpoint(store, blob))
    args = ["sync", "--legacy-campaign", "nfc", "--backup-bucket", "bucket"]
    real.writes.clear()
    admin.main(args)
    assert not [key for collection, key in real.writes if collection in {"contacts", "pairs", "dispatches"}]
    assert len(backups) == 1
    real.scans.clear()
    real.writes.clear()
    admin.main(args)
    assert not real.scans
    assert not [key for collection, key in real.writes if collection in {"contacts", "pairs", "dispatches"}]
    assert len(backups) == 1
    assert real.get(*GLOBAL)["maintenance"] is False
    # A new scraper row imports only its contact and six relevant pairs.
    source.append(["new", "", "", "", "Hospitality", "", "new@owned.it", "Da inviare", "", "", ""])
    real.writes.clear()
    admin.main(args)
    imported = [(collection, key) for collection, key in real.writes if collection in {"contacts", "pairs", "dispatches"}]
    assert len(imported) == 7
    assert len(backups) == 2
