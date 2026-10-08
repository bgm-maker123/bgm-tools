#!/usr/bin/env python3
"""AI生成画像の販売準備ツール.

  python shop.py init    works/作品A                       作品フォルダのひな形を作る
  python shop.py package works/作品A                       サイト別の販売用一式を作る
  python shop.py describe works/作品A --site dlsite        説明文だけ表示する
  python shop.py sales add --site dlsite --title 作品A --price 550 --fee 165
  python shop.py sales summary --year 2026                 売上を集計する
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import sys
from pathlib import Path

from shoptools import config, listing, package, sales

EXAMPLES = config.ROOT / "examples"
DEFAULT_SALES = config.ROOT / "sales.csv"


def cmd_init(args: argparse.Namespace) -> None:
    work_dir = Path(args.work_dir)
    (work_dir / "images").mkdir(parents=True, exist_ok=True)
    for name in ("work.toml", "regions.json"):
        dest = work_dir / name
        if dest.exists():
            print(f"スキップ (既にあります): {dest}")
        else:
            shutil.copy(EXAMPLES / name, dest)
            print(f"作成: {dest}")
    print(f"\n次にやること:\n  1. {work_dir / 'images'} に販売する画像を入れる\n"
          f"  2. {work_dir / 'work.toml'} に作品情報を書く\n"
          f"  3. python shop.py package {work_dir}")


def cmd_package(args: argparse.Namespace) -> None:
    work_dir = Path(args.work_dir)
    work = config.load_work(work_dir / "work.toml")
    common, sites = config.load_sites(Path(args.sites) if args.sites else None)
    regions = work_dir / "regions.json"
    site_ids = args.site or list(sites)
    built, warnings = package.build(
        input_dir=work_dir / "images", work=work, common=common, sites=sites, site_ids=site_ids,
        out_root=Path(args.out) if args.out else work_dir / "dist",
        regions_path=regions if regions.exists() else None,
        cover_name=args.cover or work.get("cover"),
    )
    for w in warnings:
        print(f"[注意] {w}")
    for d in built:
        print(f"作成: {d}")


def cmd_describe(args: argparse.Namespace) -> None:
    work_dir = Path(args.work_dir)
    work = config.load_work(work_dir / "work.toml")
    _, sites = config.load_sites(Path(args.sites) if args.sites else None)
    count = len(list((work_dir / "images").glob("*"))) if (work_dir / "images").exists() else 0
    print(listing.render(sites[args.site], work, count))


def cmd_sales_add(args: argparse.Namespace) -> None:
    row = sales.add(Path(args.file), args.date, args.site, args.title, args.qty, args.price, args.fee, args.memo)
    print(f"記録しました: {row['date']} {row['site']} {row['title']} 手取り {row['net']:,}円")


def cmd_sales_summary(args: argparse.Namespace) -> None:
    rows = sales.read(Path(args.file))
    if not rows:
        print("売上の記録がまだありません")
        return
    print(sales.format_summary(sales.summarize(rows, args.year)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI生成画像の販売準備ツール")
    parser.add_argument("--sites", help="サイト設定ファイル (既定: config/sites.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="作品フォルダのひな形を作る")
    p.add_argument("work_dir")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("package", help="サイト別の販売用一式を作る")
    p.add_argument("work_dir")
    p.add_argument("--site", action="append", help="対象サイト (複数指定可。省略時は全サイト)")
    p.add_argument("--cover", help="メイン画像に使うファイル名 (省略時は work.toml の cover か1枚目)")
    p.add_argument("--out", help="出力先 (既定: 作品フォルダ/dist)")
    p.set_defaults(func=cmd_package)

    p = sub.add_parser("describe", help="説明文を表示する")
    p.add_argument("work_dir")
    p.add_argument("--site", required=True)
    p.set_defaults(func=cmd_describe)

    p_sales = sub.add_parser("sales", help="売上の記録・集計")
    sales_sub = p_sales.add_subparsers(dest="sales_command", required=True)

    p = sales_sub.add_parser("add", help="売上を1件記録する")
    p.add_argument("--date", default=datetime.date.today().isoformat(), help="YYYY-MM-DD (既定: 今日)")
    p.add_argument("--site", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--price", type=int, required=True, help="1個あたりの販売価格")
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--fee", type=int, default=0, help="手数料・送料などの合計")
    p.add_argument("--memo", default="")
    p.add_argument("--file", default=str(DEFAULT_SALES))
    p.set_defaults(func=cmd_sales_add)

    p = sales_sub.add_parser("summary", help="月別・サイト別に集計する")
    p.add_argument("--year")
    p.add_argument("--file", default=str(DEFAULT_SALES))
    p.set_defaults(func=cmd_sales_summary)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, FileNotFoundError, KeyError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
