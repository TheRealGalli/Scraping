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
    "media": ["Studi Professionali", "Hospitality", "Boutique e Retail"],
}
DEFAULT_LIMITS = dict(consulenza=40, training=35, nfc=50, sito=45, social=45, media=40)
RULE_VERSION = "2026-10-23-v1"


def template_version(campaign):
    return hashlib.sha256((ROOT / (campaign + ".html")).read_bytes() + (ROOT / (campaign + ".txt")).read_bytes() + (ROOT / "assets" / CATALOG[campaign]["image"]).read_bytes()).hexdigest()[:16]


def render(campaign):
    c = CATALOG[campaign]
    body = (ROOT / (campaign + ".html")).read_text(encoding="utf-8")
    body = body.replace("assets/" + c["image"], "cid:campaign_art")
    return c["subject"], body, (ROOT / (campaign + ".txt")).read_text(encoding="utf-8"), ROOT / "assets" / c["image"]
