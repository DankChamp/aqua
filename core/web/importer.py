from core.documents import manager as doc_manager
from core.web.scraper import fetch_url
from core.web.search import search_duckduckgo


def import_url(url: str) -> dict:
    fetched = fetch_url(url)
    if not fetched:
        return {}
    doc = doc_manager.add_document(
        title=fetched.get("title") or url,
        content=fetched.get("content", ""),
        source="url",
        source_url=url,
    )
    return {
        "id": doc.id,
        "title": doc.title,
        "content_preview": doc.content[:300],
        "source_url": doc.source_url,
    }


def research_topic(topic: str, max_results: int = 5) -> list[dict]:
    results = search_duckduckgo(topic, max_results=max_results)
    imported = []
    for r in results:
        doc = import_url(r["url"])
        if doc:
            doc["search_title"] = r["title"]
            doc["search_snippet"] = r["snippet"]
            imported.append(doc)
    return imported
