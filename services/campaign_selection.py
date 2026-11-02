"""Bounded campaign shortlists built at sync time, without extra source lookups."""
from collections import defaultdict, deque
import hashlib

from config import settings
from services.campaign_catalog import CATALOG, SECTOR_RULES
from services.recipient_policy import exclusion_reason, next_contact_time

VERSION = 1
SHORTLIST_SIZE = 300


def previously_contacted(contact):
    # Test sends never consume the priority of a real first contact.
    return bool(contact.get("history") or contact.get("sent") or contact.get("legacy_keys"))


def geography(contact):
    locations = contact.get("locations", [])
    locations = sorted(locations, key=lambda loc: (
        not bool(loc.get("city")), loc.get("province", ""), loc.get("city", ""),
    ))
    location = locations[0] if locations else {}
    normalize = lambda value: " ".join(value.strip().casefold().split())
    province = normalize(location.get("province", ""))
    region = normalize(location.get("region", ""))
    city = normalize(location.get("city", ""))
    # Keep names scoped: two towns with the same name need not be the same place.
    province_key = region + "|" + province if province or region else "unknown"
    city_key = province_key + "|" + city if city else province_key + "|unknown"
    return province_key, city_key


def _interleave(entries, seed):
    groups = defaultdict(deque)
    for entry in entries:
        groups[entry["city"]].append(entry)
    while groups:
        # Rotate the geographic sample each sync window, including when there
        # are more distinct towns than fit in one bounded shortlist.
        for city in sorted(list(groups), key=lambda key: hashlib.sha256((seed + key).encode()).digest()):
            yield groups[city].popleft()
            if not groups[city]:
                del groups[city]


def build_selection_queues(contacts, pairs, suppressions, configs, now):
    """Inspect the existing sync snapshot once; publish at most 300 candidates/mode."""
    buckets = {campaign: {mode: [[], []] for mode in ("live", "test")} for campaign in CATALOG}
    for pid, pair in sorted(pairs.items()):
        campaign = pair.get("campaign")
        if campaign not in buckets or pair.get("state") != "queued":
            continue
        if pair.get("eligible_at", now) > now or not configs.get(campaign, {}).get("enabled"):
            continue
        cid = pair["contact_id"]
        contact = contacts.get(cid, {})
        suppression = suppressions.get(cid, {})
        if not contact.get("enabled") or contact.get("review_reason"):
            continue
        if suppression.get("blocked") or campaign in suppression.get("campaigns", []):
            continue
        if exclusion_reason(contact.get("email")):
            continue
        if not set(contact.get("sectors", [])).intersection(SECTOR_RULES[campaign]):
            continue
        first_contact = not previously_contacted(contact)
        province, city = geography(contact)
        entry = {"pair_id": pid, "contact_id": cid, "first_contact": first_contact,
                 "province": province, "city": city}
        for mode in ("live", "test"):
            prefix = "" if mode == "live" else "test_"
            if contact.get(prefix + "active") or campaign in contact.get(prefix + "sent", []):
                continue
            due = next_contact_time(contact.get(prefix + "history", []), now,
                                    settings.CONTACT_COOLDOWN_DAYS, settings.CONTACT_WINDOW_DAYS,
                                    settings.CONTACT_WINDOW_MAX_SENDS)
            if due <= now:
                buckets[campaign][mode][0 if first_contact else 1].append(entry)
    queues = {}
    seed = str(int(now.timestamp()) // 900)
    for campaign, modes in buckets.items():
        result = {}
        for mode, (first, previous) in modes.items():
            entries = []
            for group in (first, previous):
                for entry in _interleave(group, seed):
                    if len(entries) >= SHORTLIST_SIZE:
                        break
                    entries.append(entry)
            result[mode] = {"first_contact_total": len(first), "total": len(first) + len(previous),
                            "entries": entries}
        queues[campaign] = {"version": VERSION, "generated_at": now, "modes": result}
    return queues


def ordered_entries(queue, mode, stats, first_contact_only):
    entries = queue["modes"][mode]["entries"]
    provinces, cities = stats.get("provinces", {}), stats.get("cities", {})
    ranked = sorted(enumerate(entries), key=lambda item: (
        not item[1]["first_contact"],
        provinces.get(item[1]["province"], 0), cities.get(item[1]["city"], 0),
        item[1]["city"] == stats.get("last_city"), item[0],
    ))
    return [entry for _, entry in ranked if not first_contact_only or entry["first_contact"]]
