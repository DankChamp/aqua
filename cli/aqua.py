import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown

console = Console()
API_URL = os.environ.get("AQUA_API_URL", "http://localhost:8000")


def api(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{API_URL}{path}"
    headers = {"Content-Type": "application/json"}
    pw = os.environ.get("AQUA_WEB_PASSWORD") or None
    if pw:
        headers["Authorization"] = f"Bearer {pw}"
    with httpx.Client(timeout=120.0) as client:
        return client.request(method, url, headers=headers, **kwargs)


def cmd_ask(args):
    resp = api("POST", "/chat", json={
        "message": " ".join(args.query),
        "task_type": getattr(args, "task_type", "conversation"),
        "provider": getattr(args, "provider", None),
        "model": getattr(args, "model", None),
    })
    if resp.status_code == 503:
        console.print(f"[red]Error:[/red] {resp.json()['detail']}")
        return
    resp.raise_for_status()
    data = resp.json()
    console.print(Panel(data["reply"], title=f"[bold]{data['provider']}/{data['model']}[/bold]"))


def cmd_docs_list(args):
    resp = api("GET", "/documents", params={"tag": args.tag, "source": args.source, "limit": args.limit})
    docs = resp.json()
    if not docs:
        console.print("[yellow]No documents[/yellow]")
        return
    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Source")
    table.add_column("Tags")
    for d in docs:
        tags = ", ".join(d.get("tags", []))
        table.add_row(str(d["id"]), d["title"][:60], d.get("source", ""), tags)
    console.print(table)


def cmd_docs_add(args):
    resp = api("POST", "/documents", json={
        "title": args.title,
        "content": args.content or "",
        "authors": args.authors or "",
        "source": args.source or "manual",
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
    })
    resp.raise_for_status()
    doc = resp.json()
    console.print(f"[green]Document added:[/green] {doc['title']} (id={doc['id']})")


def cmd_docs_show(args):
    resp = api("GET", f"/documents/{args.id}")
    if resp.status_code == 404:
        console.print("[red]Not found[/red]")
        return
    doc = resp.json()
    tags = ", ".join(doc.get("tags", []))
    console.print(Panel(
        f"[bold]{doc['title']}[/bold]\nTags: {tags}\nSource: {doc.get('source', 'N/A')}\n\n{doc.get('content', '')[:2000]}",
        title=f"Document #{doc['id']}",
    ))


def cmd_docs_search(args):
    resp = api("GET", f"/documents/search/{args.query}")
    for d in resp.json()[:args.limit]:
        console.print(Panel(d.get("content", "")[:500] or "(no content)", title=f"[bold]{d['title']}[/bold] (id={d['id']})"))


def cmd_docs_delete(args):
    if not Confirm.ask(f"Delete document {args.id}?"):
        return
    resp = api("DELETE", f"/documents/{args.id}")
    console.print("[green]Deleted[/green]" if resp.ok else "[red]Not found[/red]")


def cmd_notes_list(args):
    params = {"limit": args.limit}
    if args.doc_id:
        params["document_id"] = args.doc_id
    resp = api("GET", "/notes", params=params)
    notes = resp.json()
    if not notes:
        console.print("[yellow]No notes[/yellow]")
        return
    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Preview")
    for n in notes:
        table.add_row(str(n["id"]), n.get("title", "") or "(untitled)", n.get("content", "")[:80])
    console.print(table)


def cmd_notes_add(args):
    resp = api("POST", "/notes", json={
        "content": args.content,
        "title": args.title or "",
        "document_id": args.doc_id,
    })
    resp.raise_for_status()
    note = resp.json()
    console.print(f"[green]Note added[/green] (id={note['id']})")


def cmd_notes_search(args):
    resp = api("GET", f"/notes/search/{args.query}")
    for n in resp.json()[:args.limit]:
        console.print(Panel(n.get("content", "")[:500], title=f"[bold]{n.get('title', 'Untitled')}[/bold] (id={n['id']})"))


def cmd_flashcards_list(args):
    params = {"limit": args.limit}
    if args.topic:
        params["topic"] = args.topic
    resp = api("GET", "/flashcards", params=params)
    cards = resp.json()
    if not cards:
        console.print("[yellow]No flashcards[/yellow]")
        return
    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Question")
    table.add_column("Topic")
    table.add_column("Difficulty")
    for c in cards:
        table.add_row(str(c["id"]), c["question"][:60], c.get("topic", ""), str(c.get("difficulty", 1)))
    console.print(table)


def cmd_flashcards_add(args):
    resp = api("POST", "/flashcards", json={
        "question": args.question,
        "answer": args.answer,
        "topic": args.topic or "",
        "difficulty": args.difficulty or 1,
    })
    resp.raise_for_status()
    card = resp.json()
    console.print(f"[green]Flashcard added[/green] (id={card['id']})")


def cmd_flashcards_review(args):
    resp = api("GET", "/flashcards", params={"topic": args.topic, "limit": 50})
    cards = resp.json()
    if not cards:
        console.print("[yellow]No cards to review[/yellow]")
        return
    for c in cards:
        console.print(Panel(c["question"], title=f"Flashcard #{c['id']}"))
        answer = Prompt.ask("[bold]Your answer[/bold]")
        console.print(f"[bold]Correct:[/bold] {c['answer']}")
        correct = Confirm.ask("Were you correct?")
        api("POST", f"/flashcards/{c['id']}/review", json={"correct": correct})
        console.print()


def cmd_profile_list(args):
    resp = api("GET", "/profile")
    entries = resp.json()
    if not entries:
        console.print("[yellow]No profile entries[/yellow]")
        return
    table = Table(show_header=True)
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    table.add_column("Category", style="dim")
    table.add_column("Updated")
    for e in entries:
        table.add_row(e["key"], e["value"][:60], e.get("category", ""), e.get("updated_at", "")[:10])
    console.print(table)


def cmd_profile_set(args):
    resp = api("POST", "/profile", json={"key": args.key, "value": args.value, "category": args.category or ""})
    if resp.ok:
        console.print(f"[green]Profile '{args.key}' saved[/green]")


def cmd_profile_remove(args):
    resp = api("DELETE", f"/profile/{args.key}")
    if resp.ok:
        console.print(f"[green]Profile '{args.key}' removed[/green]")
    else:
        console.print(f"[red]Key '{args.key}' not found[/red]")


def cmd_profile_prompt(args):
    if args.text:
        resp = api("PUT", "/profile/system-prompt", json={"text": args.text})
        if resp.ok:
            console.print("[green]System prompt saved[/green]")
    else:
        resp = api("GET", "/profile/system-prompt")
        data = resp.json()
        console.print(Panel(data.get("text", ""), title="System Prompt"))


def cmd_web_search(args):
    resp = api("POST", "/web/search", json={"query": " ".join(args.query), "max_results": args.limit})
    data = resp.json()
    results = data.get("results", [])
    if not results:
        console.print("[yellow]No results[/yellow]")
        return
    table = Table(show_header=True)
    table.add_column("Title")
    table.add_column("URL")
    for r in results:
        table.add_row(r["title"][:60], r["url"][:60])
    console.print(table)


def cmd_web_fetch(args):
    resp = api("POST", "/web/fetch", json={"url": args.url})
    data = resp.json()
    if data.get("error"):
        console.print(f"[red]{data['error']}[/red]")
        return
    console.print(f"[green]Imported:[/green] {data['title']} (id={data['id']})")
    if data.get("content_preview"):
        console.print(Panel(data["content_preview"], title="Preview"))


def cmd_web_research(args):
    topic = " ".join(args.topic)
    console.print(f"[yellow]Researching '{topic}'...[/yellow]")
    resp = api("POST", "/web/research", json={"topic": topic, "max_results": args.limit})
    data = resp.json()
    docs = data.get("documents", [])
    if not docs:
        console.print("[yellow]No documents imported[/yellow]")
        return
    table = Table(show_header=True)
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Source")
    for d in docs:
        table.add_row(str(d["id"]), d.get("search_title", d["title"])[:50], d.get("source_url", "")[:50])
    console.print(f"[green]Imported {len(docs)} document(s)[/green]")
    console.print(table)


def cmd_quiz_list(args):
    resp = api("GET", "/quizzes", params={"limit": args.limit})
    quizzes = resp.json()
    if not quizzes:
        console.print("[yellow]No quizzes[/yellow]")
        return
    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Topic")
    table.add_column("Score")
    for q in quizzes:
        score = f"{q.get('score', '?'):.0f}%" if q.get('score') is not None else "-"
        table.add_row(str(q["id"]), q["title"][:50], q.get("topic", ""), score)
    console.print(table)


def cmd_quiz_show(args):
    resp = api("GET", f"/quizzes/{args.id}")
    if resp.status_code == 404:
        console.print("[red]Quiz not found[/red]")
        return
    q = resp.json()
    console.print(f"[bold]{q['title']}[/bold] ({q.get('topic', 'no topic')})")
    if q.get("score") is not None:
        correct_count = sum(1 for qd in q.get("questions", []) if qd.get("is_correct"))
        console.print(f"Score: {q['score']:.0f}% ({correct_count}/{q.get('total', '?')})")
    for i, qd in enumerate(q.get("questions", []), 1):
        ua = qd.get("user_answer")
        icon = "[green]✓[/green]" if qd.get("is_correct") else "[red]✗[/red]" if ua else "[dim]—[/dim]"
        console.print(f"  {i}. {qd['question']}  {icon}")
        if ua:
            console.print(f"     Your answer: {ua}")
        console.print(f"     Correct: {qd['correct_answer']}")


def cmd_quiz_generate(args):
    resp = api("POST", "/quizzes/generate", json={
        "document_id": args.doc_id,
        "num_questions": args.count,
        "topic": args.topic or "",
    })
    if resp.status_code == 400:
        console.print(f"[red]{resp.json()['detail']}[/red]")
        return
    data = resp.json()
    console.print(f"[green]Quiz generated:[/green] {data['title']} (id={data['id']})")


def cmd_quiz_take(args):
    resp = api("GET", f"/quizzes/{args.id}")
    if resp.status_code == 404:
        console.print("[red]Quiz not found[/red]")
        return
    q = resp.json()
    console.print(f"\n[bold]{q['title']}[/bold]\n")
    for i, qd in enumerate(q.get("questions", []), 1):
        console.print(f"[bold]Q{i}:[/bold] {qd['question']}")
        if qd.get("options"):
            for j, opt in enumerate(qd["options"], 1):
                console.print(f"  {j}. {opt}")
        answer = Prompt.ask("Your answer")
        api("POST", f"/quizzes/{q['id']}/questions/{qd['id']}/answer", json={"answer": answer})
    resp = api("POST", f"/quizzes/{q['id']}/grade")
    result = resp.json()
    console.print(f"\n[bold]Score: {result['score']:.0f}% ({result['correct']}/{result['total']})[/bold]")


def cmd_search(args):
    resp = api("GET", f"/search?q={' '.join(args.query)}&limit={args.limit}")
    data = resp.json()
    if not data.get("documents") and not data.get("notes"):
        console.print("[yellow]No results[/yellow]")
        return
    for d in data.get("documents", []):
        console.print(Panel(d.get("content", "")[:300], title=f"[bold]{d['title']}[/bold] (doc #{d['id']})"))
    for n in data.get("notes", []):
        console.print(Panel(n.get("content", "")[:300], title=f"[bold]{n.get('title', 'Note')}[/bold] (note #{n['id']})"))


def cmd_serve(args):
    cmd = ["uvicorn", "main:app", "--host", args.host or "0.0.0.0", "--port", str(args.port or 8000)]
    if args.reload:
        cmd.append("--reload")
    os.chdir(Path(__file__).resolve().parent.parent)
    subprocess.run(cmd)


def cmd_init(args):
    from config import get_settings
    s = get_settings()
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    from core.deps import get_db
    get_db()
    console.print(f"[green]Aqua initialized[/green] (db: {s.db_path})")


def cmd_voice_start(args):
    cmd = [sys.executable, "aqua_voice.py"]
    wake_word = args.wake_word or None
    if wake_word:
        cmd.extend(["--wake-word", wake_word])
    if args.device:
        cmd.extend(["--device", args.device])
    if args.no_barge_in:
        cmd.append("--no-barge-in")
    if args.list_devices:
        cmd.append("--list-devices")
    log = open("voice.log", "a")
    subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                     cwd=Path(__file__).resolve().parent.parent)
    console.print("[green]Voice assistant started[/green]")


def cmd_voice_stop(args):
    subprocess.run(["pkill", "-f", "aqua_voice.py"])
    console.print("[red]Voice assistant stopped[/red]")


def main():
    parser = argparse.ArgumentParser(prog="aqua")
    sub = parser.add_subparsers(dest="command")

    p_ask = sub.add_parser("ask", help="Ask a question")
    p_ask.add_argument("query", nargs="+")
    p_ask.add_argument("--task-type", "-t", default="conversation")
    p_ask.add_argument("--provider", "-p")
    p_ask.add_argument("--model", "-m")

    p_docs = sub.add_parser("docs", help="Manage documents")
    docs_sub = p_docs.add_subparsers(dest="subcommand")
    p_dl = docs_sub.add_parser("list")
    p_dl.add_argument("--tag", "-t")
    p_dl.add_argument("--source", "-s")
    p_dl.add_argument("--limit", "-l", type=int, default=50)
    p_da = docs_sub.add_parser("add")
    p_da.add_argument("title")
    p_da.add_argument("--content", "-c")
    p_da.add_argument("--authors", "-a")
    p_da.add_argument("--source", "-s")
    p_da.add_argument("--tags", "-t")
    p_ds = docs_sub.add_parser("show")
    p_ds.add_argument("id", type=int)
    p_dsr = docs_sub.add_parser("search")
    p_dsr.add_argument("query")
    p_dsr.add_argument("--limit", "-l", type=int, default=20)
    p_dd = docs_sub.add_parser("delete")
    p_dd.add_argument("id", type=int)

    p_notes = sub.add_parser("notes", help="Manage notes")
    n_sub = p_notes.add_subparsers(dest="subcommand")
    n_l = n_sub.add_parser("list")
    n_l.add_argument("--doc-id", "-d", type=int)
    n_l.add_argument("--limit", "-l", type=int, default=50)
    n_a = n_sub.add_parser("add")
    n_a.add_argument("content")
    n_a.add_argument("--title", "-t")
    n_a.add_argument("--doc-id", "-d", type=int)
    n_s = n_sub.add_parser("search")
    n_s.add_argument("query")
    n_s.add_argument("--limit", "-l", type=int, default=20)

    p_fc = sub.add_parser("flashcards", help="Manage flashcards")
    fc_sub = p_fc.add_subparsers(dest="subcommand")
    fc_l = fc_sub.add_parser("list")
    fc_l.add_argument("--topic", "-t")
    fc_l.add_argument("--limit", "-l", type=int, default=50)
    fc_a = fc_sub.add_parser("add")
    fc_a.add_argument("question")
    fc_a.add_argument("answer")
    fc_a.add_argument("--topic", "-t")
    fc_a.add_argument("--difficulty", "-d", type=int, default=1)
    fc_r = fc_sub.add_parser("review")
    fc_r.add_argument("--topic", "-t")

    p_prof = sub.add_parser("profile", help="Manage your profile and system prompt")
    prof_sub = p_prof.add_subparsers(dest="subcommand")
    prof_l = prof_sub.add_parser("list")
    prof_s = prof_sub.add_parser("set")
    prof_s.add_argument("key")
    prof_s.add_argument("value")
    prof_s.add_argument("--category", "-c")
    prof_r = prof_sub.add_parser("remove")
    prof_r.add_argument("key")
    prof_p = prof_sub.add_parser("prompt")
    prof_p.add_argument("text", nargs="?", default=None)

    p_web = sub.add_parser("web", help="Search and fetch from the web")
    web_sub = p_web.add_subparsers(dest="subcommand")
    ws = web_sub.add_parser("search")
    ws.add_argument("query", nargs="+")
    ws.add_argument("--limit", "-l", type=int, default=5)
    wf = web_sub.add_parser("fetch")
    wf.add_argument("url")
    wr = web_sub.add_parser("research")
    wr.add_argument("topic", nargs="+")
    wr.add_argument("--limit", "-l", type=int, default=5)

    p_quiz = sub.add_parser("quiz", help="Manage and take quizzes")
    quiz_sub = p_quiz.add_subparsers(dest="subcommand")
    ql = quiz_sub.add_parser("list")
    ql.add_argument("--limit", "-l", type=int, default=20)
    qs = quiz_sub.add_parser("show")
    qs.add_argument("id", type=int)
    qg = quiz_sub.add_parser("generate")
    qg.add_argument("doc_id", type=int)
    qg.add_argument("--count", "-n", type=int, default=5)
    qg.add_argument("--topic", "-t")
    qt = quiz_sub.add_parser("take")
    qt.add_argument("id", type=int)

    p_search = sub.add_parser("search", help="Semantic search across documents and notes")
    p_search.add_argument("query", nargs="+")
    p_search.add_argument("--limit", "-l", type=int, default=10)

    p_voice = sub.add_parser("voice", help="Voice assistant")
    v_sub = p_voice.add_subparsers(dest="subcommand")
    vs = v_sub.add_parser("start")
    vs.add_argument("--wake-word")
    vs.add_argument("--device")
    vs.add_argument("--no-barge-in", action="store_true")
    vs.add_argument("--list-devices", action="store_true")
    v_stop = v_sub.add_parser("stop")

    p_serve = sub.add_parser("serve", help="Start the web server")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")

    p_init = sub.add_parser("init", help="Initialize database")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "ask":
        cmd_ask(args)
    elif args.command == "docs":
        {"list": cmd_docs_list, "add": cmd_docs_add, "show": cmd_docs_show, "search": cmd_docs_search, "delete": cmd_docs_delete}[args.subcommand](args)
    elif args.command == "notes":
        {"list": cmd_notes_list, "add": cmd_notes_add, "search": cmd_notes_search}[args.subcommand](args)
    elif args.command == "flashcards":
        {"list": cmd_flashcards_list, "add": cmd_flashcards_add, "review": cmd_flashcards_review}[args.subcommand](args)
    elif args.command == "profile":
        {"list": cmd_profile_list, "set": cmd_profile_set, "remove": cmd_profile_remove, "prompt": cmd_profile_prompt}[args.subcommand](args)
    elif args.command == "web":
        {"search": cmd_web_search, "fetch": cmd_web_fetch, "research": cmd_web_research}[args.subcommand](args)
    elif args.command == "quiz":
        {"list": cmd_quiz_list, "show": cmd_quiz_show, "generate": cmd_quiz_generate, "take": cmd_quiz_take}[args.subcommand](args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "voice":
        {"start": cmd_voice_start, "stop": cmd_voice_stop}[args.subcommand](args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "init":
        cmd_init(args)


if __name__ == "__main__":
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    main()
