from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.web import scraper, search, importer

router = APIRouter(prefix="/web", tags=["web"])


class FetchRequest(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    max_results: int = 5


class ResearchRequest(BaseModel):
    topic: str
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
    docs = importer.research_topic(body.topic, max_results=body.max_results)
    return {"documents": docs}
