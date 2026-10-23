import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from config import settings
from services.campaign_catalog import CATALOG, SECTOR_RULES, template_version
from services.recipient_policy import exclusion_reason, next_contact_time, normalize_email
from services.time_filter import is_sender_operating_hours

logger = logging.getLogger(__name__)
GLOBAL = ("control", "global")
GATE = ("control", "gate")


def utcnow():
    return datetime.now(timezone.utc)


def pair_key(campaign, cid):
    return campaign + ":" + cid


def effective_limit(config, day):
    limit = config["daily_limit"]
    initial = config["initial_limit"]
    started = config.get("started_on")
    if not started:
        return min(limit, initial)
    age = (day - datetime.strptime(started, "%Y-%m-%d").date()).days
    if age < 0:
        return 0
    # Explicit configuration, not an automatic increase based on domain age.
    weeks = config.get("ramp", [initial])
    return min(limit, weeks[min(age // 7, len(weeks) - 1)])


def validate_config(config):
    if set(config) != set(CATALOG):
        raise ValueError("Six known campaigns required")
    for cid, c in config.items():
        if not isinstance(c.get("enabled"), bool):
            raise ValueError("Invalid campaign state: " + cid)
        for key in ("daily_limit", "initial_limit", "interval_seconds"):
            if type(c.get(key)) is not int or not 0 <= c[key] <= (86400 if key == "interval_seconds" else 1000):
                raise ValueError("Invalid " + key + ": " + cid)
        if c["interval_seconds"] < 60:
            raise ValueError("Campaign interval must be at least 60 seconds")
        ramp = c.get("ramp", [c["initial_limit"]])
        if not ramp or len(ramp) > 52 or any(type(x) is not int or x < 0 or x > c["daily_limit"] for x in ramp):
            raise ValueError("Invalid ramp: " + cid)
        if c.get("started_on"):
            datetime.strptime(c["started_on"], "%Y-%m-%d")
    return config


def config_keys():
    return [("campaigns", c) for c in CATALOG]


class CampaignEngine:
    def __init__(self, store, transport=None, clock=utcnow):
        self.store, self.transport, self.clock = store, transport, clock

    def _acquire(self, token, now):
        def acquire(d):
            gate = d[GATE]
            if gate.get("until", now) > now:
                return {}, False
            gate = dict(gate, token=token, until=now + timedelta(seconds=settings.CAMPAIGN_LEASE_SECONDS))
            return {GATE: gate}, True
        return self.store.atomic([GATE], acquire)

    def _release(self, token):
        def release(d):
            gate = d[GATE]
            if gate.get("token") != token:
                return {}, None
            return {GATE: dict(gate, until=self.clock())}, None
        self.store.atomic([GATE], release)

    def run(self, campaign, execution_id=""):
        if campaign not in CATALOG:
            raise ValueError("Unknown campaign")
        now = self.clock()
        if not is_sender_operating_hours(now):
            return {"status": "skipped", "reason": "outside_operating_hours"}
        if not settings.SENDING_ENABLED:
            return {"status": "skipped", "reason": "sending_disabled"}
        if settings.SENDER_MODE not in {"dry_run", "test", "live"}:
            raise ValueError("Invalid SENDER_MODE")
        if min(settings.GLOBAL_DAILY_LIMIT, settings.GLOBAL_INTERVAL_SECONDS, settings.CONTACT_COOLDOWN_DAYS, settings.CONTACT_WINDOW_DAYS, settings.CONTACT_WINDOW_MAX_SENDS) <= 0 or settings.CAMPAIGN_LEASE_SECONDS < 90:
            raise ValueError("Sender limits must be positive")
        if settings.SENDER_MODE != "dry_run" and self.transport is None:
            from services.campaign_transport import CampaignSMTP
            self.transport = CampaignSMTP()  # Validate configuration before reserving anything.
        if settings.SENDER_MODE == "test" and not any(x.strip() for x in settings.TEST_RECIPIENTS.split(",")):
            raise ValueError("TEST_RECIPIENTS required in test mode")
        token = uuid.uuid4().hex
        if not self._acquire(token, now):
            return {"status": "skipped", "reason": "another_dispatch_in_progress"}
        try:
            from services.campaign_sheets import CampaignSheets
            # Fresh manual exclusions and campaign controls on every execution.
            CampaignSheets().refresh_controls(self.store, self.clock())
            return self._run_locked(campaign, token, execution_id)
        finally:
            self._release(token)

    def _run_locked(self, campaign, token, execution_id):
        now = self.clock()
        def heartbeat(d):
            gate = dict(d[GATE])
            seen = dict(gate.get("seen", {}))
            seen[campaign] = now
            gate["seen"] = seen
            return {GATE: gate}, None
        self.store.atomic([GATE], heartbeat)
        control = self.store.get(*GLOBAL)
        if not control.get("migration_ready") or control.get("maintenance") or control.get("paused", True):
            return {"status": "skipped", "reason": "not_ready_or_paused"}
        fresh = control.get("contacts_synced_at")
        if not fresh or now - fresh > timedelta(minutes=settings.CAMPAIGN_SHEET_MAX_AGE_MINUTES):
            return {"status": "skipped", "reason": "contact_sync_required"}
        configs = validate_config({c: self.store.get("campaigns", c) for c in CATALOG})
        if not configs[campaign]["enabled"]:
            return {"status": "skipped", "reason": "campaign_disabled"}
        # Bounded pages: deferred records are moved out of the due index, not discarded.
        reasons = {}
        for pid, pair in self.store.due(campaign, now):
            result = self._reserve(campaign, pid, pair["contact_id"], token, execution_id)
            if result["status"] == "reserved":
                if settings.SENDER_MODE == "dry_run":
                    self._finish(result, "preview", "", "")
                    return dict(status="preview", campaign=campaign, contact_id=result["contact_id"])
                if not is_sender_operating_hours(self.clock()):
                    self._finish(result, "cancelled", "", "outside_operating_hours")
                    return {"status": "skipped", "reason": "outside_operating_hours"}
                # Test mode never sends to the source contact.
                target = result["email"]
                if settings.SENDER_MODE == "test":
                    owned = [normalize_email(x) for x in settings.TEST_RECIPIENTS.split(",") if x.strip()]
                    if not owned:
                        self._finish(result, "cancelled", "", "test_allowlist_missing")
                        raise ValueError("TEST_RECIPIENTS required in test mode")
                    target = owned[0]
                if not self._start(result, token, target):
                    self._finish(result, "cancelled", "", "cancelled_before_transport")
                    return {"status": "skipped", "reason": "cancelled_before_transport"}
                try:
                    from services.campaign_transport import CampaignSMTP
                    transport = self.transport or CampaignSMTP()
                    outcome = transport.send(target, campaign, result["dispatch_id"])
                except Exception as exc:
                    # After start, the safe default is ambiguity; retain contact lock.
                    self._finish(result, "uncertain", "", type(exc).__name__)
                    raise
                self._finish(result, outcome.status, outcome.message_id, outcome.error)
                logger.info(json.dumps({"event": "campaign_dispatch", "campaign": campaign, "contact_id": result["contact_id"], "dispatch_id": result["dispatch_id"], "status": outcome.status, "mode": settings.SENDER_MODE}))
                return {"status": outcome.status, "dispatch_id": result["dispatch_id"], "campaign": campaign}
            reasons[result["reason"]] = reasons.get(result["reason"], 0) + 1
            if result["reason"] in {"global_daily_limit", "global_interval", "campaign_daily_limit", "campaign_interval", "fair_turn", "lease_lost", "paused"}:
                return result
        def idle(d):
            gate = dict(d[GATE])
            if gate.get("token") != token:
                return {}, None
            mode = "live" if settings.SENDER_MODE == "live" else "test"
            ready = dict(gate.get("ready_" + mode, {}))
            ready.pop(campaign, None)
            gate["ready_" + mode] = ready
            return {GATE: gate}, None
        self.store.atomic([GATE], idle)
        return {"status": "skipped", "reason": "no_eligible_candidates", "details": reasons}

    def _reserve(self, campaign, pid, cid, token, execution_id):
        now = self.clock()
        import pytz
        day = now.astimezone(pytz.timezone(settings.TIMEZONE)).date()
        is_preview = settings.SENDER_MODE == "dry_run"
        # Test counters and history are isolated from production, including deduplication.
        mode = "live" if settings.SENDER_MODE == "live" else "test"
        daily_key = ("daily", mode + ":" + day.isoformat())
        mailbox_key = ("mailbox_daily", day.isoformat())
        contact_key = ("contacts", cid)
        pair_doc = ("pairs", pid)
        suppression = ("suppressions", cid)
        attempt_key = ("dispatches", uuid.uuid4().hex)
        keys = list(dict.fromkeys([GLOBAL, GATE, daily_key, mailbox_key, contact_key, pair_doc, suppression] + config_keys() + [("pairs", pair_key(c, cid)) for c in CATALOG]))

        def reserve(d):
            gate, control, contact, pair = d[GATE], d[GLOBAL], d[contact_key], d[pair_doc]
            def skip(reason, due=None, state=None):
                updates = {}
                if mode == "live" and pair:
                    changed = dict(pair, reason=reason)
                    if due:
                        changed["eligible_at"] = due
                    if state:
                        changed["state"] = state
                    updates[pair_doc] = changed
                return updates, {"status": "skipped", "reason": reason}
            if gate.get("token") != token or gate.get("until", now) <= now:
                return skip("lease_lost")
            if control.get("maintenance") or control.get("paused", True) or not control.get("migration_ready"):
                return skip("paused")
            if not contact or not contact.get("enabled") or contact.get("review_reason"):
                return skip("contact_disabled_or_review", state="review")
            if pair.get("state") != "queued" or pair.get("eligible_at", now) > now:
                return skip("candidate_no_longer_due")
            if d[suppression].get("blocked") or campaign in d[suppression].get("campaigns", []):
                return skip("suppressed", state="suppressed")
            reason = exclusion_reason(contact.get("email"))
            if reason:
                return skip(reason, state="excluded")
            configs = validate_config({c: d[("campaigns", c)] for c in CATALOG})
            if not configs[campaign]["enabled"]:
                return skip("campaign_disabled")
            if not set(contact.get("sectors", [])).intersection(SECTOR_RULES[campaign]):
                return skip("sector_not_targeted", state="review")
            history_field = "history" if mode == "live" else "test_history"
            sent_field = "sent" if mode == "live" else "test_sent"
            active_field = "active" if mode == "live" else "test_active"
            history = contact.get(history_field, [])
            if campaign in contact.get(sent_field, []):
                return skip("already_sent", state="sent" if mode == "live" else None, due=now + timedelta(days=1))
            if contact.get(active_field):
                return skip("unresolved_dispatch", due=now + timedelta(hours=1))
            due = next_contact_time(history, now, settings.CONTACT_COOLDOWN_DAYS, settings.CONTACT_WINDOW_DAYS, settings.CONTACT_WINDOW_MAX_SENDS)
            if due > now:
                return skip("contact_cooldown", due=due)
            daily = d[daily_key] or {"total": 0, "campaigns": {}, "next_campaign_at": {}}
            mailbox = d[mailbox_key] or {"total": 0}
            if mailbox.get("total", 0) >= settings.GLOBAL_DAILY_LIMIT:
                return skip("global_daily_limit")
            if mailbox.get("next_at", now) > now:
                return skip("global_interval")
            if daily.get("campaigns", {}).get(campaign, 0) >= effective_limit(configs[campaign], day):
                return skip("campaign_daily_limit")
            if daily.get("next_campaign_at", {}).get(campaign, now) > now:
                return skip("campaign_interval")
            # Campaign fairness per contact. Disabled, empty or exhausted campaigns do not hold it.
            def can_claim(c):
                other_pair = d[("pairs", pair_key(c, cid))]
                return (
                    configs[c]["enabled"]
                    and c not in contact.get(sent_field, [])
                    and c not in d[suppression].get("campaigns", [])
                    and set(contact.get("sectors", [])).intersection(SECTOR_RULES[c])
                    and daily.get("campaigns", {}).get(c, 0) < effective_limit(configs[c], day)
                    and other_pair.get("state") == "queued"
                    and other_pair.get("eligible_at", now) <= now
                    and (c == campaign or gate.get("seen", {}).get(c, now - timedelta(days=1)) > now - timedelta(minutes=20))
                )
            choices = [c for c in CATALOG if can_claim(c)]
            order = contact.get("campaign_order", list(CATALOG))
            if choices:
                winner = min(choices, key=lambda c: order.index(c) if c in order else len(order))
                if campaign != winner:
                    return skip("another_campaign_has_priority", due=now + timedelta(minutes=10))
            # Rate fairness: priority rotates with daily quota consumption, with a short
            # grace period. Idle campaigns cannot hold the global sender forever.
            if is_preview:
                return {}, {"status": "reserved", "dispatch_id": attempt_key[1], "contact_id": cid, "campaign": campaign, "email": contact["email"], "mode": "preview", "pair_id": pid}
            gate = dict(gate)
            ready = dict(gate.get("ready_" + mode, {}))
            ready[campaign] = now + timedelta(minutes=20)
            available = [c for c, expiry in ready.items() if expiry > now and c in CATALOG and configs[c]["enabled"] and daily.get("campaigns", {}).get(c, 0) < effective_limit(configs[c], day)]
            order_global = list(CATALOG)
            cursor = gate.get("cursor_" + mode, 0)
            winner = min(available, key=lambda c: (daily.get("campaigns", {}).get(c, 0) / max(1, effective_limit(configs[c], day)), (order_global.index(c) - cursor) % len(order_global)))
            gate["ready_" + mode] = ready
            if winner != campaign:
                return {GATE: gate}, {"status": "skipped", "reason": "fair_turn"}
            gate["cursor_" + mode] = (order_global.index(campaign) + 1) % len(order_global)
            daily = dict(daily)
            daily["campaigns"] = dict(daily.get("campaigns", {}))
            daily["next_campaign_at"] = dict(daily.get("next_campaign_at", {}))
            daily["total"] += 1
            daily["campaigns"][campaign] = daily["campaigns"].get(campaign, 0) + 1
            daily["next_at"] = now + timedelta(seconds=settings.GLOBAL_INTERVAL_SECONDS)
            daily["next_campaign_at"][campaign] = now + timedelta(seconds=configs[campaign]["interval_seconds"])
            attempt = {"dispatch_id": attempt_key[1], "contact_id": cid, "campaign": campaign, "email": contact["email"], "mode": mode, "pair_id": pid, "state": "reserved", "at": now, "execution_id": execution_id, "template_version": template_version(campaign), "sender": settings.WORKSPACE_EMAIL, "lease_token": token}
            contact = dict(contact, **{active_field: attempt_key[1]})
            mailbox = dict(mailbox, total=mailbox.get("total", 0) + 1, next_at=daily["next_at"])
            return {GATE: gate, daily_key: daily, mailbox_key: mailbox, contact_key: contact, attempt_key: attempt}, dict(attempt, status="reserved")
        return self.store.atomic(keys, reserve)

    def _start(self, attempt, token, target=None):
        cid = attempt["contact_id"]
        ck, sk, ak = ("contacts", cid), ("suppressions", cid), ("dispatches", attempt["dispatch_id"])
        now = self.clock()
        def start(d):
            if d[GATE].get("token") != token or d[GATE].get("until", now) <= now or d[GLOBAL].get("paused", True) or d[GLOBAL].get("maintenance") or d[sk].get("blocked") or attempt["campaign"] in d[sk].get("campaigns", []) or not d[ck].get("enabled") or not is_sender_operating_hours(now):
                return {}, False
            if d[ak].get("state") != "reserved":
                return {}, False
            return {ak: dict(d[ak], state="started", started_at=now, delivery_target=target or attempt["email"])}, True
        return self.store.atomic([GLOBAL, GATE, ck, sk, ak], start)

    def _finish(self, attempt, status, message_id, error):
        if attempt["mode"] == "preview":
            return
        ck = ("contacts", attempt["contact_id"])
        ak = ("dispatches", attempt["dispatch_id"])
        pk = ("pairs", attempt["pair_id"])
        sk = ("suppressions", attempt["contact_id"])
        now = self.clock()
        def finish(d):
            if d[ak].get("state") not in {"reserved", "started", "uncertain"}:
                return {}, None
            contact = dict(d[ck])
            is_live = attempt["mode"] == "live"
            active = "active" if is_live else "test_active"
            updates = {ak: dict(d[ak], state=status, message_id=message_id, error=error, finished_at=now)}
            if status != "uncertain":
                contact[active] = ""
            if status == "accepted":
                field = "sent" if is_live else "test_sent"
                contact[field] = sorted(set(contact.get(field, []) + [attempt["campaign"]]))
                hf = "history" if is_live else "test_history"
                contact[hf] = sorted(contact.get(hf, []) + [now])
                if is_live:
                    updates[pk] = dict(d[pk], state="sent", reason="accepted", dispatch_id=attempt["dispatch_id"])
            elif status == "rejected" and is_live:
                updates[pk] = dict(d[pk], state="review", reason="transport_rejected")
                contact["review_reason"] = "transport_rejected"
            elif status == "hard_bounce" and is_live:
                updates[pk] = dict(d[pk], state="excluded", reason="hard_bounce")
                updates[sk] = dict(d[sk], blocked=True, reason="hard_bounce", registered_at=now)
            updates[ck] = contact
            return updates, None
        self.store.atomic([ck, ak, pk, sk], finish)
