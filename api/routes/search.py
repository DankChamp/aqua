from fastapi import APIRouter

from core.search.vector import hybrid_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(q: str, limit: int = 10):
    return hybrid_search(q, limit=limit)
