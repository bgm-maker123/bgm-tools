import sys
import zipfile
from pathlib import Path

from PIL import Image, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shop  # noqa: E402
from shoptools import images, listing, package, sales  # noqa: E402


def make_png(path: Path, size=(1200, 1600), color=(200, 100, 50), prompt="secret prompt"):
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", prompt)
    img = Image.new("RGB", size, color)
    # モザイク確認用に細かい市松模様を入れる
    for x in range(0, 200, 2):
        for y in range(0, 200, 2):
            img.putpixel((x, y), (0, 0, 0))
    img.save(path, pnginfo=info)


def make_work(tmp_path: Path, n=3, adult=False) -> Path:
    work_dir = tmp_path / "work"
    assert shop.main(["init", str(work_dir)]) == 0
    for i in range(1, n + 1):
        make_png(work_dir / "images" / f"{i:03d}.png")
    toml = (work_dir / "work.toml").read_text(encoding="utf-8")
    (work_dir / "work.toml").write_text(toml.replace("adult = false", f"adult = {str(adult).lower()}"), encoding="utf-8")
    (work_dir / "regions.json").write_text('{"001.png": [[0, 0, 200, 200]]}', encoding="utf-8")
    return work_dir


def test_strip_metadata_removes_prompt(tmp_path):
    src = tmp_path / "a.png"
    make_png(src)
    assert "parameters" in Image.open(src).info
    out = tmp_path / "b.png"
    images.save(images.strip_metadata(images.load(src)), out)
    assert "parameters" not in Image.open(out).info


def test_mosaic_flattens_region():
    img = Image.new("RGB", (100, 100), (255, 255, 255))
    for x in range(0, 40, 2):
        img.putpixel((x, 0), (0, 0, 0))
    out = images.mosaic(img, (0, 0, 40, 40), 10)
    block = out.crop((0, 0, 10, 10))
    assert len(block.getcolors()) == 1
    assert out.getpixel((50, 50)) == (255, 255, 255)


def test_watermark_changes_image_keeps_size():
    img = Image.new("RGB", (640, 480), (100, 100, 100))
    out = images.watermark(img, "SAMPLE")
    assert out.size == img.size and out.mode == "RGB"
    assert out.tobytes() != img.tobytes()


def test_pick_evenly():
    assert package.pick_evenly(list(range(10)), 3) == [0, 4, 9]  # round(4.5) == 4
    assert package.pick_evenly([1, 2], 5) == [1, 2]


def test_render_includes_ai_notice_and_tag():
    site = {"template": "dlsite.txt", "name": "DLsite"}
    work = {"title": "T", "circle": "C", "price": 1100, "tool": "SD", "summary": "S",
            "contents": "", "tags": ["x"], "adult": True}
    text = listing.render(site, work, 7)
    assert "画像生成AI（SD）" in text
    assert "AI生成、x" in text
    assert "画像 7枚" in text
    assert "18歳未満" in text


def test_package_end_to_end(tmp_path):
    work_dir = make_work(tmp_path, n=6)
    assert shop.main(["package", str(work_dir)]) == 0
    dist = work_dir / "dist" / "作品タイトル"

    for site in ("dlsite", "fanza", "yahoo"):
        assert (dist / site / "description.txt").exists()
        assert Image.open(dist / site / "cover.jpg").size in ((560, 420), (1200, 1200))
    assert len(list((dist / "dlsite" / "samples").glob("*.jpg"))) == 5
    assert max(Image.open(dist / "dlsite" / "samples" / "sample_01.jpg").size) == 1280
    assert not (dist / "yahoo" / "作品タイトル.zip").exists()

    with zipfile.ZipFile(dist / "dlsite" / "作品タイトル.zip") as zf:
        names = zf.namelist()
        assert len([n for n in names if n.endswith(".png")]) == 6
        with zf.open("作品タイトル/001.png") as f:
            img = Image.open(f)
            img.load()
    assert "parameters" not in img.info
    # 001.png の左上はモザイク済み (市松模様が消えている)
    assert img.getpixel((0, 0)) == img.getpixel((1, 1))


def test_package_warns_adult_without_regions(tmp_path, capsys):
    work_dir = make_work(tmp_path, n=2, adult=True)
    (work_dir / "regions.json").unlink()
    assert shop.main(["package", str(work_dir), "--site", "dlsite"]) == 0
    assert "モザイク範囲" in capsys.readouterr().out


def test_unknown_site_is_error(tmp_path):
    work_dir = make_work(tmp_path, n=1)
    assert shop.main(["package", str(work_dir), "--site", "booth"]) == 1


def test_sales_summary(tmp_path):
    f = tmp_path / "sales.csv"
    sales.add(f, "2026-09-01", "dlsite", "A", 2, 550, 330)
    sales.add(f, "2026-10-05", "yahoo", "B", 1, 3000, 300)
    sales.add(f, "2025-12-31", "dlsite", "A", 1, 550, 165)
    s = sales.summarize(sales.read(f), "2026")
    assert s["total"] == [4100, 630, 3470]
    assert s["by_site"]["dlsite"] == [1100, 330, 770]
    assert list(s["by_month"]) == ["2026-09", "2026-10"]
    assert "合計" in sales.format_summary(s)
