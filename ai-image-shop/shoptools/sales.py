"""売上の記録と集計 (確定申告用)."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

FIELDS = ["date", "site", "title", "qty", "price", "fee", "net", "memo"]


def add(path: Path, date: str, site: str, title: str, qty: int, price: int, fee: int, memo: str = "") -> dict:
    row = {
        "date": date, "site": site, "title": title, "qty": qty,
        "price": price, "fee": fee, "net": price * qty - fee, "memo": memo,
    }
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)
    return row


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def summarize(rows: list[dict], year: str | None = None) -> dict:
    """月別・サイト別に 売上 / 手数料 / 手取り を集計する。"""
    if year:
        rows = [r for r in rows if r["date"].startswith(year)]
    by_month: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    by_site: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    total = [0, 0, 0]
    for r in rows:
        gross = int(r["price"]) * int(r["qty"])
        vals = (gross, int(r["fee"]), int(r["net"]))
        for bucket in (by_month[r["date"][:7]], by_site[r["site"]], total):
            for i, v in enumerate(vals):
                bucket[i] += v
    return {"by_month": dict(sorted(by_month.items())), "by_site": dict(sorted(by_site.items())), "total": total}


def format_summary(summary: dict) -> str:
    lines = []
    header = f"{'':<12}{'売上':>12}{'手数料':>12}{'手取り':>12}"
    for label, key in (("■ 月別", "by_month"), ("■ サイト別", "by_site")):
        lines += [label, header]
        for name, (g, fee, net) in summary[key].items():
            lines.append(f"{name:<12}{g:>12,}{fee:>12,}{net:>12,}")
        lines.append("")
    g, fee, net = summary["total"]
    lines.append(f"{'合計':<12}{g:>12,}{fee:>12,}{net:>12,}")
    return "\n".join(lines)
