import os
import tomllib
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "a3config.toml"
LEVELS = {"required", "advice", "off"}
ROLES = ["viewer", "member", "team_leader", "champion", "admin"]


class ConfigError(Exception):
    pass


def find_config(data_dir):
    explicit = os.environ.get("A3_CONFIG")
    if explicit:
        return Path(explicit)
    local = Path(data_dir) / "a3config.toml"
    return local if local.exists() else DEFAULT_PATH


def load_config(path):
    with open(path, "rb") as fh:
        cfg = tomllib.load(fh)
    cfg.setdefault("meta", {})
    pick = cfg.setdefault("picklists", {})
    for key in ("triggers", "severities", "fishbone_categories"):
        if not pick.get(key):
            raise ConfigError(f"[picklists].{key} must be a non-empty list in {path}")
    for key in ("locations", "departments", "topic_codes"):
        pick.setdefault(key, [])
    if "Not assessed" not in pick["severities"]:
        pick["severities"].insert(0, "Not assessed")
    cfg.setdefault("severity", {}).setdefault("high", [])
    wf = cfg.setdefault("workflow", {})
    wf.setdefault("signoff_steps", [])
    wf.setdefault("require_signoff_to_advance", False)
    wf.setdefault("signoff_roles", ["champion", "admin"])
    bad_roles = set(wf["signoff_roles"]) - set(ROLES)
    if bad_roles:
        raise ConfigError(f"Unknown role(s) in signoff_roles: {sorted(bad_roles)}")
    checks = cfg.setdefault("checks", {})
    types = cfg.setdefault("a3_types", {})
    for name in ("Basic", "Standard", "Extended"):
        t = types.setdefault(name, {})
        t.setdefault("hidden_fields", [])
        t.setdefault("hidden_sections", [])
        t.setdefault("checks", {})
    for scope, mapping in [("checks", checks)] + [(f"a3_types.{n}.checks", t["checks"]) for n, t in types.items()]:
        for check_id, level in mapping.items():
            if level not in LEVELS:
                raise ConfigError(f"[{scope}] '{check_id}' has invalid level '{level}' (use {sorted(LEVELS)})")
    cfg["_path"] = str(path)
    return cfg
