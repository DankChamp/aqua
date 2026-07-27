import logging

logger = logging.getLogger("aqua.web.search")

try:
    from ddgs import DDGS
    HAS_DDGS = True
    logger.info("ddgs imported successfully")
except ImportError:
    HAS_DDGS = False
    logger.warning("ddgs not installed; web search disabled")


def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    if not HAS_DDGS:
        return []

    try:
        with DDGS() as ddgs:
            results_raw = ddgs.text(query, max_results=max_results)
            results = []
            for r in results_raw:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                })
            return results
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)
        return []
