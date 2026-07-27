from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.profile import manager as profile_mgr

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileEntry(BaseModel):
    key: str
    value: str
    category: str = ""


class SystemPromptBody(BaseModel):
    text: str


@router.get("")
def list_profile():
    return profile_mgr.get_all()


@router.post("")
def set_profile(entry: ProfileEntry):
    profile_mgr.set(entry.key, entry.value, entry.category)
    return {"ok": True}


@router.delete("/{key}")
def delete_profile(key: str):
    ok = profile_mgr.delete(key)
    if not ok:
        raise HTTPException(404, f"Profile key '{key}' not found")
    return {"ok": True}


@router.get("/system-prompt")
def get_system_prompt():
    return {"text": profile_mgr.get_system_prompt()}


@router.put("/system-prompt")
def set_system_prompt(body: SystemPromptBody):
    profile_mgr.set_system_prompt(body.text)
    return {"ok": True}
