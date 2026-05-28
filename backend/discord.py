import httpx


async def post_match_to_discord(
    webhook_url: str,
    title: str,
    company_name: str,
    location: str | None,
    score: float,
    tier: str,
    summary: str,
    job_url: str,
    mention_type: str,
    mention_id: str,
) -> None:
    if not webhook_url:
        return

    is_strong = tier == "strong"
    color = 0x22c55e if is_strong else 0xeab308
    tier_label = "STRONG MATCH" if is_strong else "BORDERLINE"

    content = ""
    if is_strong and mention_type in ("user", "role") and mention_id:
        prefix = "&" if mention_type == "role" else ""
        content = f"<@{prefix}{mention_id}>"

    embed = {
        "title": title,
        "url": job_url,
        "color": color,
        "description": summary,
        "fields": [
            {"name": "Company", "value": company_name, "inline": True},
            {"name": "Location", "value": location or "Not specified", "inline": True},
            {"name": "Score", "value": f"{score:.2f} | {tier_label}", "inline": True},
        ],
    }

    payload: dict = {"embeds": [embed]}
    if content:
        payload["content"] = content

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
