from fastapi import APIRouter

from core.activity import get_activity

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
def activity(limit: int = 20):
    return get_activity(limit=limit)
