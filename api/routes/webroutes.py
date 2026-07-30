import asyncio
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_ai_router
from core.router import AIRouter, TaskType
from core.web import search, importer
from core.web.scraper import fetch_url

logger = logging.getLogger("aqua.web")

router = APIRouter(prefix="/web", tags=["web"])


class FetchRequest(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    max_results: int = 5


class ResearchRequest(BaseModel):
    topic: str
    max_results: int = 5


class AskRequest(BaseModel):
    query: str
    max_results: int = 5


@router.post("/fetch")
def web_fetch(body: FetchRequest):
    doc = importer.import_url(body.url)
    if not doc:
        return {"error": "Failed to fetch URL"}
    return doc


@router.post("/search")
def web_search(body: SearchRequest):
    results = search.search_duckduckgo(body.query, max_results=body.max_results)
    return {"results": results}


@router.post("/research")
def web_research(body: ResearchRequest):
    return importer.research_topic(body.topic, max_results=body.max_results)


@router.post("/ask")
async def web_ask(body: AskRequest, ai_router: AIRouter = Depends(get_ai_router)):
    try:
        results = await asyncio.to_thread(search.search_duckduckgo, body.query, body.max_results)
    except Exception as exc:
        logger.warning("Search failed: %s", exc)
        return {"answer": "Web search failed. Please try again.", "sources": []}

    if not results:
        return {"answer": "No search results found.", "sources": []}

    async def fetch_source(r: dict) -> dict:
        snippet = r.get("snippet", "")
        content = await asyncio.to_thread(fetch_url, r["url"], 10)
        if content and "error" not in content:
            text = content.get("content", "")[:3000]
        else:
            text = snippet[:500]
        return {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": snippet,
            "content": text,
        }

    sources = await asyncio.gather(*[fetch_source(r) for r in results[:3]])

    sources_block = "\n\n".join(
        f"[Source {i+1}] {s['title']}\n{s['url']}\n{s['content']}"
        for i, s in enumerate(sources)
    )

    system = (
        "You are a research assistant. Synthesize information from the provided sources "
        "to answer the user's question. Be thorough but concise.\n\n"
        "CRITICAL: Cite sources inline using numbered references like [1], [2], etc. "
        "At the end, list all sources with their numbers and URLs.\n\n"
        f"Sources:\n{sources_block}"
    )

    try:
        result = await ai_router.run(TaskType.RESEARCH, body.query, system=system)
    except Exception as exc:
        logger.warning("AI research failed: %s", exc)
        return {"answer": "AI synthesis failed. The raw search results are still available below.", "sources": [
            {"title": s["title"], "url": s["url"], "snippet": s["snippet"]} for s in sources
        ]}

    sources_out = [
        {"title": s["title"], "url": s["url"], "snippet": s["snippet"]}
        for s in sources
    ]

    return {"answer": result.text, "sources": sources_out, "provider": result.provider, "model": result.model}
