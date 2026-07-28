import re
from typing import Optional

from .client import VoiceBackendClient


class VoiceCommandRouter:
    def __init__(self, client: VoiceBackendClient):
        self.client = client

    def route(self, transcript: str) -> Optional[str]:
        text = transcript.strip().lower()
        if not text:
            return None

        if re.search(r"\b(?:search|look up|find)\s+(.+)$", text):
            query = re.search(r"\b(?:search|look up|find)\s+(.+)$", text).group(1).strip()
            try:
                results = self.client.search_web(query)
                if results:
                    titles = [r["title"] for r in results[:3]]
                    return f"Here's what I found: {'; '.join(titles)}"
                return f"I didn't find anything for {query}."
            except Exception as e:
                return f"Sorry, the search failed: {e}"

        doc_match = re.search(r"\b(?:save|store|remember)\s+(.+?)(?:\s+as\s+a\s+document)?$", text)
        if doc_match:
            content = doc_match.group(1).strip()
            title = content[:60]
            try:
                self.client.create_document(title, content)
                return f"I've saved that as a document titled '{title}'."
            except Exception as e:
                return f"Sorry, I couldn't save that: {e}"

        card_match = re.search(r"\b(?:make|create)\s+(?:a\s+)?flashcard\s+(.+?)\s*[:-]\s*(.+)$", text)
        if card_match:
            question = card_match.group(1).strip()
            answer = card_match.group(2).strip()
            try:
                self.client.create_flashcard(question, answer)
                return f"Created a flashcard: {question}"
            except Exception as e:
                return f"Sorry, I couldn't create that flashcard: {e}"

        return None
