import json
import logging
import re
from typing import Optional

from core.agent.tools import TOOL_REGISTRY

logger = logging.getLogger("aqua.agent")

MAX_ITERATIONS = 6

SYSTEM_TEMPLATE = """You are Aqua, a sharp and efficient research & study assistant.

Be conversational, not academic. Use short paragraphs or bullet points.
Never write a huge wall of text unless the user asks for depth.
Briefly cite sources when you use web search or knowledge.

=== HOW TO USE TOOLS ===
When you need information or want to perform an action, respond with ONLY a valid JSON object on its own line:
{{"tool": "tool_name", "args": {{"arg1": "value1"}}}}

Examples:
- To search: {{"tool": "web_search", "args": {{"query": "Python programming", "max_results": 3}}}}
- To create a flashcard: {{"tool": "create_flashcard", "args": {{"question": "What is Python?", "answer": "A language", "topic": "programming"}}}}
- To get time: {{"tool": "get_current_time", "args": {{}}}}

After the tool result comes back, continue the conversation naturally. Use plain text for your final answer — no JSON.

=== IMPORTANT ===
Always use a tool when asked. Do NOT guess or make up information. If you don't have a tool for the task, say so.

Available tools:
{tool_descriptions}"""


def _build_tool_descriptions() -> str:
    lines = []
    for name, tool in TOOL_REGISTRY.items():
        params = tool.parameters
        if params:
            sig = ", ".join(f"{k}: {v}" for k, v in params.items())
            lines.append(f"  {name}({sig})")
        else:
            lines.append(f"  {name}()")
        lines.append(f"    {tool.description}")
    return "\n".join(lines)


def build_system_prompt(extra: Optional[str] = None) -> str:
    desc = _build_tool_descriptions()
    prompt = SYSTEM_TEMPLATE.format(tool_descriptions=desc)
    if extra:
        prompt += f"\n\n{extra}"
    return prompt


_TOOL_CALL_RE = re.compile(
    r'\{\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"args"\s*:\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*?\})\s*\}',
    re.DOTALL,
)


def _extract_tool_call(text: str) -> Optional[dict]:
    for match in _TOOL_CALL_RE.finditer(text):
        raw = match.group(0)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return None


def _serialize_conversation(turns: list[dict]) -> str:
    parts = []
    for t in turns:
        role = t["role"].capitalize()
        parts.append(f"{role}: {t['content']}")
    return "\n\n".join(parts)


async def run_agent(
    ai_router,
    message: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    provider_name: Optional[str] = None,
    session_id: str = "default",
) -> str:
    from core.router import TaskType

    system_prompt = system or build_system_prompt()
    turns: list[dict] = [{"role": "user", "content": message}]

    for iteration in range(MAX_ITERATIONS):
        prompt = _serialize_conversation(turns)

        result = await ai_router.run(
            TaskType.CONVERSATION,
            prompt,
            system=system_prompt,
            model=model,
            provider_name=provider_name,
        )

        response = result.text.strip()
        if not response:
            return "I received an empty response from the AI provider."

        call = _extract_tool_call(response)
        if call:
            tool_name = call.get("tool", "")
            args = call.get("args", {})

            turns.append({"role": "assistant", "content": f"Using tool: {tool_name}"})
            turns.append({"role": "tool", "content": json.dumps({"tool": tool_name, "args": args})})

            tool = TOOL_REGISTRY.get(tool_name)
            if tool is None:
                observation = f"Error: Unknown tool '{tool_name}'. Available: {', '.join(TOOL_REGISTRY)}"
            else:
                try:
                    tool_result = await tool.execute(**args)
                    observation = tool_result.to_string()
                except Exception as exc:
                    observation = f"Error executing {tool_name}: {exc}"

            turns.append({"role": "observation", "content": observation})
            continue

        return response

    return "I've reached the maximum number of steps. Please try a simpler request or be more specific."
