import httpx

from config import get_settings


async def push_summary_to_emma(item_type: str, title: str, summary: str, tags: list[str] | None = None) -> bool:
    settings = get_settings()
    if not settings.emma_api_url:
        return False
    try:
        headers = {"Content-Type": "application/json"}
        if settings.emma_api_key:
            headers["Authorization"] = f"Bearer {settings.emma_api_key}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            body = {
                "item_type": item_type,
                "title": title,
                "summary": summary[:500],
                "tags": tags or [],
            }
            resp = await client.post(
                f"{settings.emma_api_url}/ingest/research-summary",
                json=body,
                headers=headers,
            )
            return resp.status_code == 200
    except httpx.HTTPError:
        return False
