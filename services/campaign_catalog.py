"""Versioned targeting. Unknown sectors never opt in automatically."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "templates" / "campaigns"
CATALOG = {c["id"]: c for c in json.loads((ROOT / "campaigns.json").read_text(encoding="utf-8"))}
SECTOR_RULES = {
    "consulenza": ["Studi Professionali", "Hospitality", "Automotive"],
    "training": ["Studi Professionali", "Hospitality"],
    "nfc": ["Ristorazione", "Centri e Servizi", "Hospitality", "Boutique e Retail", "Automotive", "Fitness e Sport", "Veterinaria e Pet Care"],
    "sito": ["Ristorazione", "Centri e Servizi", "Hospitality", "Boutique e Retail", "Automotive", "Fitness e Sport", "Veterinaria e Pet Care"],
    "social": ["Ristorazione", "Centri e Servizi", "Hospitality", "Boutique e Retail", "Fitness e Sport", "Veterinaria e Pet Care"],
    "media": ["Hospitality", "Boutique e Retail"],
}
DEFAULT_LIMITS = dict(consulenza=35, training=15, nfc=20, sito=15, social=15, media=15, forecasting=15, archivio=20)
# Explicit commercial fit; new sectors never enter every campaign automatically.
for campaign in ("consulenza", "training", "sito", "social", "media"):
    SECTOR_RULES[campaign].append("Agenzie Immobiliari")
for campaign in ("consulenza", "training", "sito", "social", "media"):
    SECTOR_RULES[campaign].append("Architettura e Interior Design")
for campaign in ("sito", "social", "media"):
    SECTOR_RULES[campaign].append("Eventi e Wedding")
# Visual services for product, venue and portfolio businesses.
SECTOR_RULES["media"] = list(dict.fromkeys(SECTOR_RULES["media"] + [
    "Ristorazione", "Centri e Servizi", "Automotive", "Fitness e Sport",
    "Veterinaria e Pet Care", "Gioiellerie"
]))
SECTOR_RULES["nfc"] += ["Gioiellerie", "Studi Dentistici"]
SECTOR_RULES["sito"] += ["Gioiellerie", "Studi Dentistici"]
SECTOR_RULES["social"] += ["Gioiellerie", "Studi Dentistici"]
SECTOR_RULES["forecasting"] = ["Ristorazione", "Hospitality", "Boutique e Retail"]
# NFC + Video & Slide segments: the first service to propose for each one.
SEGMENT_RULES_V4 = {
    "Tatuaggi e Piercing": ["media", "nfc"],
    "Serramenti e Pergole": ["media"],
    "Artigiani su Misura": ["media", "sito"],
    "Cantine e Frantoi": ["media", "nfc"],
    "Autoscuole e Scuole di Lingue": ["media", "nfc"],
    "Noleggio Barche ed Escursioni": ["media"],
    "Grossisti e Distributori": ["media", "forecasting"],
    "Amministratori di Condominio": ["consulenza"],
}
for sector, campaigns in SEGMENT_RULES_V4.items():
    for campaign in campaigns:
        SECTOR_RULES[campaign].append(sector)
SECTOR_RULES["consulenza"] += ["Studi Dentistici", "Grossisti e Distributori"]
SECTOR_RULES["training"].append("Studi Dentistici")
SECTOR_RULES["archivio"] = ["Studi Professionali", "Studi Dentistici", "Amministratori di Condominio", "Architettura e Interior Design"]

# Commercial order replaces the old per-address rotation, also on existing imports.
SECTOR_PRIORITIES = {
    "Studi Professionali": ["consulenza", "archivio", "training"],
    "Studi Dentistici": ["consulenza", "training", "archivio", "nfc", "sito", "social"],
    "Amministratori di Condominio": ["archivio", "consulenza"],
    "Architettura e Interior Design": ["media", "sito", "archivio", "consulenza", "social", "training"],
    "Grossisti e Distributori": ["forecasting", "consulenza", "media"],
    "Ristorazione": ["forecasting", "nfc", "sito", "social", "media"],
    "Hospitality": ["forecasting", "nfc", "sito", "social", "consulenza", "training", "media"],
    "Gioiellerie": ["media", "sito", "social", "nfc"],
    "Boutique e Retail": ["media", "sito", "social", "nfc", "forecasting"],
    "Artigiani su Misura": ["media", "sito"],
}


def campaign_order(sectors):
    priorities = [SECTOR_PRIORITIES[s] for s in sectors if s in SECTOR_PRIORITIES]
    return sorted(CATALOG, key=lambda c: (
        min((order.index(c) for order in priorities if c in order), default=len(CATALOG)),
        list(CATALOG).index(c),
    ))


OPTIONAL_CAMPAIGNS = {"forecasting", "archivio"}
FOCUS_LIMITS = {c: (75 if c in {"nfc", "media"} else 0) for c in CATALOG}
RULE_VERSION = "2026-11-11-v5"


def disabled_config():
    return {"enabled": False, "daily_limit": 0, "initial_limit": 0,
            "started_on": "", "ramp": [0], "interval_seconds": 720}


def template_version(campaign):
    return hashlib.sha256((ROOT / (campaign + ".html")).read_bytes() + (ROOT / (campaign + ".txt")).read_bytes() + (ROOT / "assets" / CATALOG[campaign]["image"]).read_bytes()).hexdigest()[:16]


def render(campaign):
    c = CATALOG[campaign]
    body = (ROOT / (campaign + ".html")).read_text(encoding="utf-8")
    body = body.replace("assets/" + c["image"], "cid:campaign_art")
    return c["subject"], body, (ROOT / (campaign + ".txt")).read_text(encoding="utf-8"), ROOT / "assets" / c["image"]
