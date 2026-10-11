"""Per-store configuration: display name, support inbox, team routing.

Each store gets stores/<store_id>.json, e.g.::
    {
        "store_name": "H&M",
        "support_email": "support@hm.com",
        "team_emails": {
            "shipping": "shipping@hm.com",
            "refund": "refund@hm.com",
            "return": "returns@hm.com",
            "product": "product@hm.com",
            "other": "support@hm.com"
        },
        "use_team_inboxes": false
    }

Missing file -> Annizon defaults (backward compatible).
"""
import json
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "stores"

CATEGORIES = ("shipping", "refund", "return", "product", "other")

DEFAULTS = {
    "store_name": "Annizon",
    "support_email": "info@annizon.com",
    "team_emails": {
        "shipping": "shipping@annizon.com",
        "refund": "refund@annizon.com",
        "return": "return@annizon.com",
        "product": "product@annizon.com",
        "other": "info@annizon.com",
    },
    "use_team_inboxes": False,
}


def get_store_config(store_id="default"):
    """Load one store's config; Annizon defaults when no file exists."""
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if store_id == "default":
        return cfg
    path = CONFIG_DIR / f"{store_id}.json"
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            cfg.update({k: v for k, v in saved.items() if k in cfg})
            if "team_emails" in saved:
                cfg["team_emails"].update(saved["team_emails"])
        except Exception:
            pass
    return cfg


def save_store_config(store_id, config):
    """Persist one store's config. Only known keys are kept."""
    CONFIG_DIR.mkdir(exist_ok=True)
    clean = {k: v for k, v in config.items() if k in DEFAULTS}
    # Team inboxes a store didn't set fall back to ITS OWN support email —
    # never to another store's addresses.
    fallback = config.get("support_email", DEFAULTS["support_email"])
    teams = {cat: fallback for cat in CATEGORIES}
    teams.update(config.get("team_emails", {}))
    clean["team_emails"] = teams
    path = CONFIG_DIR / f"{store_id}.json"
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def resolve_team_email(store_id, category):
    """Which inbox gets this ticket? Respects use_team_inboxes like triage.py."""
    cfg = get_store_config(store_id)
    if category not in CATEGORIES:
        category = "other"
    if cfg.get("use_team_inboxes"):
        return cfg["team_emails"].get(category, cfg["support_email"])
    return cfg["support_email"]
