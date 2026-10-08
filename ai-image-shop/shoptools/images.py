"""画像加工: メタデータ削除・リサイズ・透かし・モザイク."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def list_images(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def load(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    return img


def strip_metadata(img: Image.Image) -> Image.Image:
    """ピクセルだけをコピーして、生成パラメータ・EXIF・PNGテキスト等を全て落とす。"""
    return Image.frombytes(img.mode, img.size, img.tobytes())


def to_rgb(img: Image.Image) -> Image.Image:
    """透過部分を白背景にして RGB にする (JPEG保存用)。"""
    if img.mode == "RGB":
        return img
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.getchannel("A") if "A" in img.getbands() else None)
    return bg


def fit_cover(img: Image.Image, size: tuple[int, int], focus_y: float = 0.4) -> Image.Image:
    """切り抜いて指定サイズちょうどにする。focus_y は縦の切り抜き位置 (0=上端, 0.5=中央, 1=下端)。"""
    return ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, focus_y))


def resize_long_side(img: Image.Image, long_side: int) -> Image.Image:
    w, h = img.size
    scale = long_side / max(w, h)
    if scale >= 1:
        return img.copy()
    return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def mosaic_block_size(img: Image.Image, ratio: float, min_px: int) -> int:
    return max(min_px, math.ceil(max(img.size) * ratio))


def mosaic(img: Image.Image, box: tuple[int, int, int, int] | None, block: int) -> Image.Image:
    """box (x1, y1, x2, y2) の範囲をモザイクにする。box=None なら画像全体。"""
    out = img.copy()
    x1, y1, x2, y2 = box or (0, 0, *img.size)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(img.width, x2), min(img.height, y2)
    if x2 <= x1 or y2 <= y1:
        return out
    region = out.crop((x1, y1, x2, y2))
    small = region.resize(
        (max(1, math.ceil(region.width / block)), max(1, math.ceil(region.height / block))),
        Image.BOX,
    )
    big = small.resize((small.width * block, small.height * block), Image.NEAREST)
    out.paste(big.crop((0, 0, region.width, region.height)), (x1, y1))
    return out


def blur(img: Image.Image, strength: float = 0.02) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(max(img.size) * strength))


def load_font(font_path: str, size: int) -> ImageFont.ImageFont:
    if font_path:
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default(size=size)


def watermark(img: Image.Image, text: str, font_path: str = "", opacity: int = 70) -> Image.Image:
    """画像全体に斜めのタイル状の透かしを入れる。"""
    base = img.convert("RGBA")
    w, h = base.size
    font = load_font(font_path, max(16, min(w, h) // 12))

    # 回転しても隅まで埋まるよう、対角線の長さの正方形に敷き詰めてから回転する
    diag = math.ceil(math.hypot(w, h))
    layer = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top
    step_x, step_y = tw + tw // 2, th * 4
    for row, y in enumerate(range(0, diag, step_y)):
        offset = (step_x // 2) * (row % 2)
        for x in range(-offset, diag, step_x):
            draw.text((x, y), text, font=font, fill=(255, 255, 255, opacity),
                      stroke_width=max(1, th // 12), stroke_fill=(0, 0, 0, opacity))
    layer = layer.rotate(30, resample=Image.BICUBIC)
    left, top = (diag - w) // 2, (diag - h) // 2
    layer = layer.crop((left, top, left + w, top + h))

    out = Image.alpha_composite(base, layer)
    return out if img.mode == "RGBA" else out.convert("RGB")


def save(img: Image.Image, path: Path, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in (".jpg", ".jpeg"):
        to_rgb(img).save(path, "JPEG", quality=quality, optimize=True)
    else:
        img.save(path, optimize=True)
