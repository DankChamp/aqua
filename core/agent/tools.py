import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ToolResult:
    success: bool = True
    data: Any = None
    error: str = ""

    def to_string(self) -> str:
        if not self.success:
            return f"Error: {self.error}"
        if isinstance(self.data, str):
            return self.data
        try:
            return json.dumps(self.data, indent=2, default=str)
        except (TypeError, ValueError):
            return str(self.data)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict = field(default_factory=dict)

    async def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError


class WebSearchTool(Tool):
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web for current information on any topic",
            parameters={
                "query": "the search query string",
                "max_results": "number of results to return (default 5)",
            },
        )

    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        from core.web.search import search_duckduckgo
        try:
            results = search_duckduckgo(query, max_results=max_results)
            if not results:
                return ToolResult(success=True, data="No results found.")
            formatted = []
            for r in results:
                formatted.append(f"• {r['title']}\n  {r['snippet']}\n  {r['url']}")
            return ToolResult(success=True, data="\n\n".join(formatted))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class CreateFlashcardTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_flashcard",
            description="Save a flashcard with a question and answer for study",
            parameters={
                "question": "the question text",
                "answer": "the answer text",
                "topic": "optional topic/category",
            },
        )

    async def execute(self, question: str, answer: str, topic: str = "") -> ToolResult:
        from core.study.flashcards import add_flashcard
        try:
            card = add_flashcard(question, answer, topic)
            return ToolResult(success=True, data=f"Flashcard created (id={card.id})")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class CreateDocumentTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_document",
            description="Save a document or note to your knowledge base",
            parameters={
                "title": "document title",
                "content": "document content body",
                "tags": "optional comma-separated tags",
            },
        )

    async def execute(self, title: str, content: str, tags: str = "") -> ToolResult:
        from core.documents.manager import add_document
        try:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
            doc = add_document(title=title, content=content, tags=tag_list)
            return ToolResult(success=True, data=f"Document saved (id={doc.id})")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class SearchDocumentsTool(Tool):
    def __init__(self):
        super().__init__(
            name="search_documents",
            description="Search your saved documents and notes",
            parameters={
                "query": "the search query",
            },
        )

    async def execute(self, query: str) -> ToolResult:
        from core.documents.manager import search_documents, search_notes
        try:
            docs = search_documents(query, limit=5)
            notes = search_notes(query, limit=5)
            parts = []
            if docs:
                parts.append("Documents:")
                for d in docs:
                    parts.append(f"  [{d.id}] {d.title} — {d.content[:150]}...")
            if notes:
                parts.append("Notes:")
                for n in notes:
                    parts.append(f"  [{n.id}] {n.title} — {n.content[:150]}...")
            if not parts:
                return ToolResult(success=True, data="No matching documents or notes found.")
            return ToolResult(success=True, data="\n".join(parts))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class ListDocumentsTool(Tool):
    def __init__(self):
        super().__init__(
            name="list_documents",
            description="List all your saved documents",
            parameters={},
        )

    async def execute(self) -> ToolResult:
        from core.documents.manager import list_documents
        try:
            docs = list_documents()
            if not docs:
                return ToolResult(success=True, data="No documents yet.")
            lines = [f"[{d.id}] {d.title}" for d in docs]
            return ToolResult(success=True, data="\n".join(lines))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class GetDocumentTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_document",
            description="Get the full content of a document by its ID",
            parameters={
                "doc_id": "the document ID number",
            },
        )

    async def execute(self, doc_id: int) -> ToolResult:
        from core.documents.manager import get_document
        try:
            doc_id = int(doc_id)
            doc = get_document(doc_id)
            if not doc:
                return ToolResult(success=False, error=f"Document {doc_id} not found")
            return ToolResult(success=True, data=f"Title: {doc.title}\n\n{doc.content[:2000]}")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class GetCurrentTimeTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_current_time",
            description="Get the current date and time",
            parameters={},
        )

    async def execute(self) -> ToolResult:
        now = datetime.now()
        return ToolResult(success=True, data=now.strftime("%Y-%m-%d %H:%M:%S"))


class GenerateStudyPlanTool(Tool):
    def __init__(self):
        super().__init__(
            name="generate_study_plan",
            description="Create a study plan from documents for a given number of days",
            parameters={
                "topic": "the topic or subject to study",
                "document_ids": "comma-separated list of document IDs to study from",
                "duration_days": "number of days the plan should cover (default 7)",
            },
        )

    async def execute(self, topic: str, document_ids: str = "", duration_days: int = 7) -> ToolResult:
        from core.study.plans import generate_plan
        try:
            duration_days = int(duration_days)
            ids = [int(x.strip()) for x in document_ids.split(",") if x.strip()] if document_ids else []
            plan = await generate_plan(topic, ids, max(1, duration_days))
            return ToolResult(success=True, data=f"Study plan created: '{plan.title}' (id={plan.id}, {duration_days} days)")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class ListStudyPlansTool(Tool):
    def __init__(self):
        super().__init__(
            name="list_study_plans",
            description="List all your study plans",
            parameters={},
        )

    async def execute(self) -> ToolResult:
        from core.study.plans import list_plans
        try:
            plans = list_plans()
            if not plans:
                return ToolResult(success=True, data="No study plans yet.")
            lines = []
            for p in plans:
                lines.append(f"[{p.id}] {p.title} — {p.duration_days} days, {p.progress:.0f}% complete")
            return ToolResult(success=True, data="\n".join(lines))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class GetStudyPlanTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_study_plan",
            description="Get the full details and tasks for a study plan",
            parameters={
                "plan_id": "the study plan ID number",
            },
        )

    async def execute(self, plan_id: int) -> ToolResult:
        from core.study.plans import get_plan_with_tasks
        try:
            plan_id = int(plan_id)
            plan = get_plan_with_tasks(plan_id)
            if not plan:
                return ToolResult(success=False, error=f"Study plan {plan_id} not found")
            return ToolResult(success=True, data=plan)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


TOOL_REGISTRY: dict[str, Tool] = {
    "web_search": WebSearchTool(),
    "create_flashcard": CreateFlashcardTool(),
    "create_document": CreateDocumentTool(),
    "search_documents": SearchDocumentsTool(),
    "list_documents": ListDocumentsTool(),
    "get_document": GetDocumentTool(),
    "get_current_time": GetCurrentTimeTool(),
    "generate_study_plan": GenerateStudyPlanTool(),
    "list_study_plans": ListStudyPlansTool(),
    "get_study_plan": GetStudyPlanTool(),
}
