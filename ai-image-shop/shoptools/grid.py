"""1枚にまとめて生成された画像 (例: 3×3) を1枚ずつに切り分ける."""

from __future__ import annotations

from PIL import Image, ImageChops


def _edge_profile(img: Image.Image, axis: str) -> list[float]:
    """隣り合う列 (axis="x") / 行 (axis="y") の明るさの差の平均。コマの境目で大きくなる。"""
    gray = img.convert("L")
    w, h = gray.size
    if axis == "x":
        diff = ImageChops.difference(gray.crop((0, 0, w - 1, h)), gray.crop((1, 0, w, h)))
        return list(diff.resize((w - 1, 1), Image.BOX).tobytes())
    diff = ImageChops.difference(gray.crop((0, 0, w, h - 1)), gray.crop((0, 1, w, h)))
    return list(diff.resize((1, h - 1), Image.BOX).tobytes())


def find_cuts(profile: list[float], parts: int) -> list[int]:
    """等分位置の前後 25% の範囲で、差が一番大きい位置を境目とする。"""
    length = len(profile) + 1
    size = length / parts
    cuts = []
    for k in range(1, parts):
        lo = max(1, int(k * size - size / 4))
        hi = min(length - 1, int(k * size + size / 4))
        best = max(range(lo, hi), key=lambda i: profile[i - 1])
        cuts.append(best)
    return [0, *cuts, length]


def split(img: Image.Image, rows: int, cols: int, trim: int = 2) -> list[Image.Image]:
    """左上から右へ、上の段から順に切り出す。trim は境目のにじみを避けるために内側を削る px 数。"""
    xs = find_cuts(_edge_profile(img, "x"), cols) if cols > 1 else [0, img.width]
    ys = find_cuts(_edge_profile(img, "y"), rows) if rows > 1 else [0, img.height]
    tiles = []
    for r in range(rows):
        for c in range(cols):
            left = xs[c] + (trim if c > 0 else 0)
            right = xs[c + 1] - (trim if c < cols - 1 else 0)
            top = ys[r] + (trim if r > 0 else 0)
            bottom = ys[r + 1] - (trim if r < rows - 1 else 0)
            tiles.append(img.crop((left, top, right, bottom)))
    return tiles
