"""画像フォルダから、サイト別の販売用一式 (メイン画像・サンプル・本編ZIP・説明文) を作る."""

from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from pathlib import Path

from . import images, listing

PRODUCT_README = """\
{title}
{circle}

{ai_notice}

■ ご利用について
・個人での私的利用の範囲でお楽しみください。
・無断での再配布、転売、SNS等への転載、AI学習への利用は禁止します。
"""


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "untitled"


def load_regions(path: Path | None) -> dict[str, list[list[int]]]:
    """モザイク範囲ファイル: {"ファイル名": [[x1, y1, x2, y2], ...]} (元画像のピクセル座標)."""
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def pick_evenly(items: list, count: int) -> list:
    if count >= len(items):
        return list(items)
    if count <= 1:
        return items[:1]
    idx = sorted({round(i * (len(items) - 1) / (count - 1)) for i in range(count)})
    return [items[i] for i in idx]


def prepare(input_dir: Path, common: dict, regions: dict) -> tuple[list[tuple[str, "images.Image.Image"]], list[str]]:
    """全画像を読み込み、メタデータ削除とモザイクを適用する。"""
    paths = images.list_images(input_dir)
    if not paths:
        raise ValueError(f"{input_dir} に画像 (png/jpg/webp) がありません")
    unknown = set(regions) - {p.name for p in paths}
    warnings = [f"モザイク範囲に書かれた {name} が画像フォルダにありません" for name in sorted(unknown)]

    prepared = []
    for path in paths:
        img = images.load(path)
        if common.get("strip_metadata", True):
            img = images.strip_metadata(img)
        if max(img.size) < common.get("min_long_side", 0):
            warnings.append(f"{path.name}: 長辺 {max(img.size)}px は小さめです (目安 {common['min_long_side']}px 以上)")
        block = images.mosaic_block_size(img, common["mosaic_ratio"], common["mosaic_min_px"])
        for box in regions.get(path.name, []):
            img = images.mosaic(img, tuple(box), block)
        prepared.append((path.name, img))
    return prepared, warnings


def build_site(site_id: str, site: dict, work: dict, prepared: list, out_dir: Path, cover_name: str | None) -> Path:
    site_dir = out_dir / site_id
    quality = site["jpeg_quality"]

    # メイン画像
    cover_src = dict(prepared).get(cover_name) if cover_name else None
    if cover_name and cover_src is None:
        raise ValueError(f"表紙に指定した {cover_name} が見つかりません")
    cover = images.fit_cover(cover_src or prepared[0][1], tuple(site["cover_size"]))
    images.save(cover, site_dir / "cover.jpg", quality)

    # サンプル画像
    for i, (_, img) in enumerate(pick_evenly(prepared, site["sample_count"]), 1):
        sample = images.resize_long_side(img, site["sample_long_side"])
        if site["sample_filter"] == "mosaic":
            block = images.mosaic_block_size(sample, site["mosaic_ratio"] * 3, site["mosaic_min_px"])
            sample = images.mosaic(sample, None, block)
        elif site["sample_filter"] == "blur":
            sample = images.blur(sample)
        if site["sample_watermark"]:
            sample = images.watermark(sample, site["watermark_text"], site["font_path"], site["watermark_opacity"])
        images.save(sample, site_dir / "samples" / f"sample_{i:02d}.jpg", quality)

    # 本編ZIP
    if site["product"] == "zip":
        write_product_zip(site_dir / f"{safe_name(work['title'])}.zip", work, prepared, site)

    # 説明文
    (site_dir / "description.txt").write_text(listing.render(site, work, len(prepared)), encoding="utf-8")
    return site_dir


def write_product_zip(path: Path, work: dict, prepared: list, site: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    folder = safe_name(work["title"])
    ext = site["product_image_format"].lower().lstrip(".")
    fmt = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[ext]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (_, img) in enumerate(prepared, 1):
            buf = BytesIO()
            if fmt == "JPEG":
                images.to_rgb(img).save(buf, fmt, quality=95)
            else:
                img.save(buf, fmt)
            zf.writestr(f"{folder}/{i:03d}.{ext}", buf.getvalue())
        readme = PRODUCT_README.format(title=work["title"], circle=work["circle"], ai_notice=listing.ai_notice(work))
        zf.writestr(f"{folder}/はじめにお読みください.txt", readme)


def build(input_dir: Path, work: dict, common: dict, sites: dict, site_ids: list[str],
          out_root: Path, regions_path: Path | None = None, cover_name: str | None = None) -> tuple[list[Path], list[str]]:
    unknown = [s for s in site_ids if s not in sites]
    if unknown:
        raise ValueError(f"不明なサイト: {', '.join(unknown)} (使えるのは {', '.join(sites)})")
    prepared, warnings = prepare(input_dir, common, load_regions(regions_path))
    if work["adult"] and not regions_path:
        warnings.append("成人向け作品ですがモザイク範囲ファイル (--regions) が指定されていません")
    out_dir = out_root / safe_name(work["title"])
    built = [build_site(s, sites[s], work, prepared, out_dir, cover_name) for s in site_ids]
    return built, warnings
