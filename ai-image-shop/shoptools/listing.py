"""作品説明文・タグの生成."""

from __future__ import annotations

from string import Template

from .config import TEMPLATE_DIR

AI_TAG = "AI生成"


def tags_with_ai(tags: list[str]) -> list[str]:
    """AI生成タグを必ず先頭に入れる。"""
    rest = [t for t in tags if t != AI_TAG]
    return [AI_TAG, *rest]


def ai_notice(work: dict) -> str:
    return work.get("ai_notice") or (
        f"本作品は画像生成AI（{work['tool']}）を使用して制作しています。"
    )


def render(site: dict, work: dict, image_count: int) -> str:
    template = Template((TEMPLATE_DIR / site["template"]).read_text(encoding="utf-8"))
    tags = tags_with_ai(work["tags"])
    text = template.safe_substitute(
        title=work["title"],
        circle=work["circle"],
        price=f"{int(work['price']):,}",
        tool=work["tool"],
        summary=work["summary"].strip(),
        contents=(work["contents"].strip() or f"画像 {image_count}枚"),
        count=image_count,
        tags="、".join(tags),
        hashtags=" ".join(f"#{t}" for t in tags),
        ai_notice=ai_notice(work),
        adult_notice=(
            "※成人向け作品です。18歳未満の方はご購入いただけません。\n"
            "※登場人物はすべて18歳以上の架空の人物です。"
        ) if work["adult"] else "",
        site_name=site["name"],
    )
    # 空行が3つ以上続かないように整える
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip() + "\n"
