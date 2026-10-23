"""Bulk-report cache only. Sending decisions always remain transactional in Firestore."""
import gzip
import json
from datetime import datetime, timedelta, timezone

from config import settings
from services.campaign_store import business_value

COLLECTIONS = ("contacts", "pairs", "dispatches", "daily", "mailbox_daily", "campaigns", "control", "suppressions")


def encode(value):
    if isinstance(value, datetime):
        return {"__campaign_datetime__": value.isoformat()}
    raise TypeError("Unsupported checkpoint value: " + type(value).__name__)


def decode(value):
    if set(value) == {"__campaign_datetime__"}:
        return datetime.fromisoformat(value["__campaign_datetime__"])
    return value


class IncrementalStore:
    def __init__(self, real, data):
        self.real, self.data = real, data

    def all(self, collection):
        return self.data[collection]

    def report_get(self, collection, key):
        return self.data[collection].get(key, {})

    def get(self, collection, key):
        # Never use cached controls for an administrative decision.
        return self.real.get(collection, key)

    def put_many(self, collection, records):
        old = self.data[collection]
        changed = {key: value for key, value in records.items()
                   if key not in old or business_value(value) != business_value(old[key])}
        self.real.put_many(collection, changed)
        old.update(changed)

    def atomic(self, keys, callback):
        captured = {}
        def wrapped(values):
            updates, result = callback(values)
            captured.clear()
            captured.update(updates)
            return updates, result
        result = self.real.atomic(keys, wrapped)
        for (collection, key), value in captured.items():
            if collection in self.data:
                self.data[collection][key] = value
        return result


class Checkpoint:
    def __init__(self, store, bucket_name):
        if not bucket_name:
            raise ValueError("Backup bucket required for incremental sync")
        from google.cloud import storage
        self.real = store
        self.blob = storage.Client(project=settings.project_id).bucket(bucket_name).blob(
            "campaign-checkpoints/" + settings.CAMPAIGN_NAMESPACE + "-" + settings.FIRESTORE_DATABASE + ".json.gz")
        self.identity = [settings.project_id, settings.FIRESTORE_DATABASE, settings.CAMPAIGN_NAMESPACE]
        self.generation = 0

    def load(self):
        from google.api_core.exceptions import NotFound
        # Start watermark BEFORE reading: updates committed during this run are
        # deliberately replayed next time. Timestamps are assigned by Firestore.
        self.started = datetime.now(timezone.utc)
        try:
            self.blob.reload()
            self.generation = int(self.blob.generation)
            payload = json.loads(gzip.decompress(self.blob.download_as_bytes(
                if_generation_match=self.generation)), object_hook=decode)
        except NotFound:
            self.generation = 0
            payload = None
        if payload is None:
            data = {collection: self.real.all(collection) for collection in COLLECTIONS}
            self.full_refresh_at = self.started
            self.bootstrap = True
        else:
            if payload.get("version") != 1 or payload.get("identity") != self.identity:
                raise ValueError("Checkpoint identity/version differs; do not reuse")
            data = payload["data"]
            if set(data) != set(COLLECTIONS):
                raise ValueError("Incomplete checkpoint")
            self.full_refresh_at = payload.get("full_refresh_at", payload["watermark"])
            if self.started - self.full_refresh_at >= timedelta(days=7):
                # Bounded weekly reconciliation catches out-of-band deletions too.
                data = {collection: self.real.all(collection) for collection in COLLECTIONS}
                self.full_refresh_at = self.started
                self.bootstrap = True
            else:
                since = payload["watermark"] - timedelta(minutes=5)
                for collection in COLLECTIONS:
                    data[collection].update(self.real.changed_since(collection, since))
                self.bootstrap = False
        self.store = IncrementalStore(self.real, data)
        return self.store

    def save(self):
        payload = {"version": 1, "identity": self.identity, "watermark": self.started,
                   "data": self.store.data, "full_refresh_at": self.full_refresh_at}
        body = gzip.compress(json.dumps(payload, default=encode, ensure_ascii=False).encode())
        # No overwrite if another execution replaced the checkpoint. Failure
        # leaves the old watermark so changes will be replayed safely.
        self.blob.upload_from_string(body, content_type="application/gzip",
                                     if_generation_match=self.generation)
        return {"bootstrap": self.bootstrap, "checkpoint_bytes": len(body), **self.real.usage}
