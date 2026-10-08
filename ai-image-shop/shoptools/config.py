"""設定ファイル (sites.toml / work.toml) の読み込み."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SITES = ROOT / "config" / "sites.toml"
TEMPLATE_DIR = ROOT / "templates"

REQUIRED_WORK_KEYS = ("title", "circle", "price", "tool", "summary")


def load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_sites(path: Path | None = None) -> tuple[dict, dict]:
    """(common設定, {サイトID: サイト設定}) を返す。サイト設定には common がマージ済み。"""
    data = load_toml(path or DEFAULT_SITES)
    common = data.get("common", {})
    sites = {key: {**common, **value} for key, value in data.get("sites", {}).items()}
    return common, sites


def load_work(path: Path) -> dict:
    work = load_toml(path)
    missing = [k for k in REQUIRED_WORK_KEYS if k not in work]
    if missing:
        raise ValueError(f"{path}: 必須項目がありません: {', '.join(missing)}")
    work.setdefault("tags", [])
    work.setdefault("adult", False)
    work.setdefault("contents", "")
    return work
