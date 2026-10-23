"""Small document-store boundary; all sending decisions use a Firestore transaction."""
from config import settings


class FirestoreStore:
    def __init__(self):
        from google.cloud import firestore
        self.firestore = firestore
        self.db = firestore.Client(project=settings.project_id, database=settings.FIRESTORE_DATABASE)
        self.prefix = settings.CAMPAIGN_NAMESPACE + "_"

    def ref(self, key):
        collection, doc_id = key
        return self.db.collection(self.prefix + collection).document(doc_id)

    def get(self, collection, doc_id):
        return self.ref((collection, doc_id)).get().to_dict() or {}

    def all(self, collection):
        return {s.id: s.to_dict() for s in self.db.collection(self.prefix + collection).stream()}

    def put_many(self, collection, records):
        items = list(records.items())
        for offset in range(0, len(items), 350):
            batch = self.db.batch()
            for key, value in items[offset:offset + 350]:
                batch.set(self.ref((collection, key)), value)
            batch.commit()

    def atomic(self, keys, callback):
        transaction = self.db.transaction()

        @self.firestore.transactional
        def execute(tx):
            # All reads must happen before the first write, including on retries.
            values = {key: self.ref(key).get(transaction=tx).to_dict() or {} for key in keys}
            updates, result = callback(values)
            for key, value in updates.items():
                tx.set(self.ref(key), value)
            return result
        return execute(transaction)

    def due(self, campaign, now, limit=100):
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = self.db.collection(self.prefix + "pairs")
        query = query.where(filter=FieldFilter("campaign", "==", campaign))
        query = query.where(filter=FieldFilter("state", "==", "queued"))
        query = query.where(filter=FieldFilter("eligible_at", "<=", now))
        return [(s.id, s.to_dict()) for s in query.order_by("eligible_at").limit(limit).stream()]
