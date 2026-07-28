from typing import Optional

import httpx


class VoiceBackendClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def chat(self, message: str, session_id: str = "voice", system: Optional[str] = None) -> str:
        body = {"message": message, "session_id": session_id, "task_type": "conversation"}
        if system:
            body["system"] = system
        resp = httpx.post(f"{self.base_url}/chat", json=body, timeout=60.0)
        resp.raise_for_status()
        return resp.json()["reply"]

    def get_system_prompt(self) -> str:
        try:
            resp = httpx.get(f"{self.base_url}/profile/system-prompt", timeout=5.0)
            resp.raise_for_status()
            return resp.json().get("text", "")
        except Exception:
            return ""

    def is_reachable(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=3.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def create_document(self, title: str, content: str) -> dict:
        resp = httpx.post(f"{self.base_url}/documents", json={"title": title, "content": content}, timeout=30.0)
        resp.raise_for_status()
        return resp.json()

    def search_web(self, query: str, max_results: int = 3) -> list[dict]:
        resp = httpx.post(f"{self.base_url}/web/search", json={"query": query, "max_results": max_results}, timeout=15.0)
        resp.raise_for_status()
        return resp.json().get("results", [])

    def create_flashcard(self, question: str, answer: str, topic: str = "") -> dict:
        resp = httpx.post(f"{self.base_url}/flashcards", json={"question": question, "answer": answer, "topic": topic}, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
