from functools import lru_cache
from core.router import AIRouter


@lru_cache
def get_router() -> AIRouter:
    from config import get_settings
    return AIRouter(get_settings())
