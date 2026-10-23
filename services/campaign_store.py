"""Small document-store boundary; all sending decisions use a Firestore transaction."""
from config import settings


class FirestoreStore:
    def __init__(self):
        from google.cloud import firestore
        self.firestore = firestore
        self.db = firestore.Client(project=settings.project_id, database=settings.FIRESTORE_DATABASE)
        self.prefix = settings.CAMPAIGN_NAMESPACE + "_"
        self.usage = {"document_reads": 0, "document_writes": 0}

    def ref(self, key):
        collection, doc_id = key
        return self.db.collection(self.prefix + collection).document(doc_id)

    def get(self, collection, doc_id):
        self.usage["document_reads"] += 1
        return self.ref((collection, doc_id)).get().to_dict() or {}

    def all(self, collection):
        rows = {s.id: s.to_dict() for s in self.db.collection(self.prefix + collection).stream()}
        self.usage["document_reads"] += max(1, len(rows))
        return rows

    def put_many(self, collection, records):
        items = list(records.items())
        for offset in range(0, len(items), 350):
            batch = self.db.batch()
            for key, value in items[offset:offset + 350]:
                batch.set(self.ref((collection, key)), dict(value, _updated_at=self.firestore.SERVER_TIMESTAMP))
            batch.commit()
            self.usage["document_writes"] += len(items[offset:offset + 350])

    def atomic(self, keys, callback):
        transaction = self.db.transaction()

        @self.firestore.transactional
        def execute(tx):
            # All reads must happen before the first write, including on retries.
            values = {key: self.ref(key).get(transaction=tx).to_dict() or {} for key in keys}
            self.usage["document_reads"] += len(keys)
            updates, result = callback(values)
            for key, value in updates.items():
                if business_value(value) != business_value(values.get(key, {})):
                    tx.set(self.ref(key), dict(value, _updated_at=self.firestore.SERVER_TIMESTAMP))
                    self.usage["document_writes"] += 1
            return result
        return execute(transaction)

    def due(self, campaign, now, limit=100):
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = self.db.collection(self.prefix + "pairs")
        query = query.where(filter=FieldFilter("campaign", "==", campaign))
        query = query.where(filter=FieldFilter("state", "==", "queued"))
        query = query.where(filter=FieldFilter("eligible_at", "<=", now))
        # Fetch a small page only when needed, keeping the same overall scan cap.
        query = query.order_by("eligible_at")
        scanned, cursor = 0, None
        while scanned < limit:
            page = query.start_after(cursor) if cursor is not None else query
            page_size = min(10, limit - scanned)
            snapshots = list(page.limit(page_size).stream())
            self.usage["document_reads"] += max(1, len(snapshots))
            if not snapshots:
                return
            cursor = snapshots[-1]
            for snapshot in snapshots:
                scanned += 1
                yield snapshot.id, snapshot.to_dict()
            if len(snapshots) < page_size:
                return

    def changed_since(self, collection, since):
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = self.db.collection(self.prefix + collection).where(filter=FieldFilter("_updated_at", ">=", since))
        rows = {s.id: s.to_dict() for s in query.stream()}
        self.usage["document_reads"] += max(1, len(rows))
        return rows


def business_value(value):
    return {k: v for k, v in value.items() if k != "_updated_at"}
