"""Sheets control surface. Original Italy A:K and ConfigState are never overwritten."""
import json
import hashlib
from datetime import datetime, timezone

import gspread

from config import settings
from services.campaign_catalog import CATALOG, DEFAULT_LIMITS, RULE_VERSION, SECTOR_RULES
from services.campaign_engine import GLOBAL, validate_config, effective_limit
from services.recipient_policy import contact_id, normalize_email, next_contact_time
from services.sheets_service import SheetsService

HEADERS = {
    "Campagne": ["ID", "Attiva", "Quota", "Quota iniziale", "Inizio", "Rampa", "Intervallo secondi"],
    "Esclusioni": ["Email", "Ambito", "Motivo", "Data", "Attiva"],
    "Contatti": ["ID", "Email", "Settori", "Abilitato", "Revisione", "Ultimo invio", "Campagne inviate", "Riferimento autorizzazione", "Stato sync", "Non prima del UTC"],
    "Invii": ["ID", "Contatto ID", "Campagna", "Mittente", "Data UTC", "Stato", "Modo", "ID messaggio", "Errore", "Versione template"],
    "RegoleSettori": ["Campagna", "Settore", "Versione"],
    "Panoramica": ["Data", "Modo", "Campagna", "Tentativi quota", "Accettati", "Incerti", "Rifiutati", "Quota richiesta", "Quota effettiva", "Quota globale", "Tentativi casella", "Residuo globale", "Sync contatti UTC", "Pausa globale"],
    "ControlloInvii": ["Pausa globale"],
}


def boolean(value, default=False):
    value = str(value).strip().lower()
    if value in {"true", "vero", "si", "sì", "1"}:
        return True
    if value in {"false", "falso", "no", "0"}:
        return False
    if not value:
        return default
    raise ValueError("Expected TRUE or FALSE")


class CampaignSheets:
    def __init__(self, workbook=None):
        self._book = workbook

    @property
    def book(self):
        if self._book is None:
            self._book = SheetsService()._get_client().open_by_key(settings.SPREADSHEET_ID)
        return self._book

    def rows(self, name):
        return self.book.worksheet(name).get_all_values()

    def ensure(self):
        existing = {s.title for s in self.book.worksheets()}
        for title, headers in HEADERS.items():
            if title in existing:
                ws = self.book.worksheet(title)
                actual = [ws.row_values(1)] if hasattr(ws, "row_values") else self.rows(title)[:1]
                if not actual or actual[0] != headers:
                    raise ValueError("Unexpected headers; refusing to replace " + title)
                continue
            ws = self.book.add_worksheet(title=title, rows=1000, cols=max(len(headers), 12))
            ws.update(range_name="A1", values=[headers], value_input_option="RAW")
            ws.freeze(rows=1)
            if title == "Campagne":
                ws.append_rows([[c, "FALSE", DEFAULT_LIMITS[c], 5, "", "5", max(720, 36000 // DEFAULT_LIMITS[c])] for c in CATALOG], value_input_option="RAW")
            elif title == "ControlloInvii":
                ws.append_row(["TRUE"], value_input_option="RAW")
            elif title == "RegoleSettori":
                ws.append_rows([[c, s, RULE_VERSION] for c in CATALOG for s in SECTOR_RULES[c]], value_input_option="RAW")

    def configs(self):
        rows = self.rows("Campagne")
        if not rows or rows[0] != HEADERS["Campagne"]:
            raise ValueError("Invalid Campagne headers")
        configs = {}
        for raw in rows[1:]:
            row = raw + [""] * (7 - len(raw))
            cid = row[0].strip()
            if not cid and not any(row):
                continue
            if cid not in CATALOG or cid in configs:
                raise ValueError("Unknown or duplicate campaign ID")
            configs[cid] = {"enabled": boolean(row[1]), "daily_limit": int(row[2]), "initial_limit": int(row[3]), "started_on": row[4].strip(), "ramp": [int(x.strip()) for x in row[5].split(";") if x.strip()], "interval_seconds": int(row[6])}
        return validate_config(configs)

    def refresh_controls(self, store, now):
        configs = self.configs()
        pause_rows = self.rows("ControlloInvii")
        if len(pause_rows) != 2 or pause_rows[0] != HEADERS["ControlloInvii"]:
            raise ValueError("Invalid ControlloInvii")
        paused = boolean(pause_rows[1][0], default=True)
        rows = self.rows("Esclusioni")
        if not rows or rows[0] != HEADERS["Esclusioni"]:
            raise ValueError("Invalid Esclusioni headers")
        previous_control = store.get(*GLOBAL)
        exclusions_hash = hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()
        configs_hash = hashlib.sha256(json.dumps(configs, sort_keys=True).encode()).hexdigest()
        # Monotonic safety: deleting a row cannot silently reinstate a suppressed address.
        blocks = {}
        for raw in rows[1:]:
            row = raw + [""] * (5 - len(raw))
            if not any(row):
                continue
            if not boolean(row[4], default=True):
                continue
            email = normalize_email(row[0])
            scope = row[1].strip() or "globale"
            if scope != "globale" and scope not in CATALOG:
                raise ValueError("Invalid exclusion scope")
            if exclusions_hash == previous_control.get("exclusions_hash"):
                continue
            cid = contact_id(email)
            item = blocks.setdefault(cid, store.get("suppressions", cid) or {"blocked": False, "campaigns": []})
            item = dict(item)
            item["blocked"] = item.get("blocked", False) or scope == "globale"
            item["campaigns"] = sorted(set(item.get("campaigns", []) + ([scope] if scope != "globale" else [])))
            item.update(reason=row[2], registered_at=item.get("registered_at", now), request_date=row[3])
            blocks[cid] = item
        store.put_many("suppressions", blocks)
        if configs_hash != previous_control.get("configs_hash"):
            store.put_many("campaigns", configs)
        def update(d):
            return {GLOBAL: dict(d[GLOBAL], paused=paused, controls_synced_at=now, exclusions_hash=exclusions_hash, configs_hash=configs_hash)}, None
        store.atomic([GLOBAL], update)

    def read_source(self):
        rows = self.rows(settings.SHEET_NAME)
        if not rows:
            raise ValueError("Source sheet is empty")
        required = ["Place ID", "Regione", "Provincia", "Città", "Settore", "Sito Web", "Email", "Stato Invio", "Data Invio"]
        if rows[0][:9] != required:
            raise ValueError("Source headers differ from existing code; review before importing")
        return rows

    def contact_overrides(self):
        rows = self.rows("Contatti")
        if not rows or rows[0] != HEADERS["Contatti"]:
            raise ValueError("Invalid Contatti headers")
        result = {}
        for raw in rows[1:]:
            row = raw + [""] * (9 - len(raw))
            if not any(row):
                continue
            cid = contact_id(row[1])
            if row[0] != cid or cid in result:
                raise ValueError("Contatti IDs changed or duplicated")
            result[cid] = {"enabled": boolean(row[3]), "reference": row[7].strip()}
        return result

    def update_report(self, store):
        read = store.report_get if callable(getattr(type(store), "report_get", None)) else store.get
        # Reports are system-owned; manual columns in Contatti are preserved by key.
        contacts = store.all("contacts")
        overrides = self.contact_overrides()
        values = []
        now = datetime.now(timezone.utc)
        for cid, c in sorted(contacts.items()):
            o = overrides.get(cid, {})
            history = c.get("history", [])
            due = next_contact_time(history, now, settings.CONTACT_COOLDOWN_DAYS, settings.CONTACT_WINDOW_DAYS, settings.CONTACT_WINDOW_MAX_SENDS)
            values.append([cid, c["email"], "; ".join(c.get("sectors", [])), str(o.get("enabled", c.get("enabled", False))).upper(), c.get("review_reason", ""), max(history).isoformat() if history else "", "; ".join(c.get("sent", [])), o.get("reference", c.get("reference", "")), "sincronizzato", due.isoformat()])
        self.update_contacts(values)
        dispatches = store.all("dispatches")
        history = [HEADERS["Invii"]]
        counts = {}
        for did, e in sorted(dispatches.items(), key=lambda item: (item[1].get("at") or datetime.min.replace(tzinfo=timezone.utc), item[0])):
            at = e.get("at")
            history.append([did, e.get("contact_id", ""), e.get("campaign", ""), e.get("sender", ""), at.isoformat() if at else "", e.get("state", ""), e.get("mode", ""), e.get("message_id", ""), e.get("error", ""), e.get("template_version", "legacy")])
            import pytz
            key = (at.astimezone(pytz.timezone(settings.TIMEZONE)).date().isoformat() if at else "unknown", e.get("mode", ""), e.get("campaign", ""))
            bucket = counts.setdefault(key, {"accepted": 0, "uncertain": 0, "rejected": 0})
            if e.get("state") in bucket:
                bucket[e["state"]] += 1
            elif e.get("state") == "legacy_accepted":
                bucket["accepted"] += 1
        self.append_events(history)
        daily = store.all("daily")
        control = read(*GLOBAL)
        summary = [HEADERS["Panoramica"]]
        for date_key, d in sorted(daily.items()):
            mode, day = date_key.split(":", 1)
            mailbox_total = read("mailbox_daily", day).get("total", 0)
            for campaign in CATALOG:
                states = counts.get((day, mode, campaign), {"accepted": 0, "uncertain": 0, "rejected": 0})
                cfg = read("campaigns", campaign)
                actual_limit = effective_limit(cfg, datetime.strptime(day, "%Y-%m-%d").date()) if cfg else 0
                summary.append([day, mode, campaign, d.get("campaigns", {}).get(campaign, 0), states["accepted"], states["uncertain"], states["rejected"], cfg.get("daily_limit", 0), actual_limit, settings.GLOBAL_DAILY_LIMIT, mailbox_total, max(0, settings.GLOBAL_DAILY_LIMIT - mailbox_total), str(control.get("contacts_synced_at", "")), str(control.get("paused", True)).upper()])
        self.replace_report("Panoramica", summary)

    def update_contacts(self, values):
        ws = self.book.worksheet("Contatti")
        rows = ws.get_all_values()
        if not rows or rows[0] != HEADERS["Contatti"]:
            raise ValueError("Invalid Contatti headers")
        positions = {row[0]: n for n, row in enumerate(rows[1:], 2) if row}
        new, patches = [], []
        for row in values:
            number = positions.get(row[0])
            if number:
                # D and H are human-owned; never overwrite even if edited mid-sync.
                previous = rows[number - 1] + [""] * 10
                for label, start, end in (("A{}:C{}", 0, 3), ("E{}:G{}", 4, 7), ("I{}:J{}", 8, 10)):
                    if [str(v) for v in previous[start:end]] != [str(v) for v in row[start:end]]:
                        patches.append({"range": label.format(number, number), "values": [row[start:end]]})
            else:
                new.append(row)
        ws.resize(rows=max(ws.row_count, len(rows) + len(new)), cols=max(ws.col_count, 12))
        for offset in range(0, len(patches), 1500):
            ws.batch_update(patches[offset:offset + 1500], value_input_option="RAW")
        if new:
            for offset in range(0, len(new), 1000):
                ws.append_rows(new[offset:offset + 1000], value_input_option="RAW")

    def append_events(self, values):
        ws = self.book.worksheet("Invii")
        existing = ws.get_all_values()
        if not existing or existing[0] != HEADERS["Invii"]:
            raise ValueError("Invalid Invii headers")
        positions = {row[0]: (n, row) for n, row in enumerate(existing[1:], 2) if row}
        new, patches = [], []
        for row in values[1:]:
            old = positions.get(row[0])
            if not old:
                new.append(row)
            elif old[1] != row:
                patches.append({"range": f"A{old[0]}:J{old[0]}", "values": [row]})
        ws.resize(rows=max(ws.row_count, len(existing) + len(new)), cols=max(ws.col_count, 12))
        for offset in range(0, len(patches), 500):
            ws.batch_update(patches[offset:offset + 500], value_input_option="RAW")
        for offset in range(0, len(new), 1000):
            ws.append_rows(new[offset:offset + 1000], value_input_option="RAW")

    def replace_report(self, title, values):
        ws = self.book.worksheet(title)
        # RAW prevents scraped values from becoming spreadsheet formulas.
        if [[str(v) for v in row] for row in ws.get_all_values()] == [[str(v) for v in row] for row in values]:
            return
        ws.resize(rows=max(1000, len(values)), cols=max(12, len(values[0])))
        ws.clear()
        for offset in range(0, len(values), 1000):
            ws.update(range_name="A" + str(offset + 1), values=values[offset:offset + 1000], value_input_option="RAW")
