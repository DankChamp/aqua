from fastapi import Request


def get_ai_router():
    from core.deps import get_router
    return get_router()
