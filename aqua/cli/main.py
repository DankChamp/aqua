from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from aqua import __version__
from aqua.db import init_db
from aqua.documents.paper import add_document, list_documents, get_document, search_documents, delete_document
from aqua.documents.note import add_note, list_notes, search_notes, edit_note, delete_note as delete_note_db
from aqua.documents.parser import ingest_file
from aqua.study.flashcards import add_flashcard, list_flashcards, review_flashcard
from aqua.study.quiz import create_quiz, get_quiz, list_quizzes, submit_answer, grade_quiz
console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """aqua - personal AI assistant for research and studies"""
    pass


@cli.command()
def init():
    """Initialize the database and data directories"""
    from aqua.config import load_config
    config = load_config()
    Path(config["data_dir"]).mkdir(parents=True, exist_ok=True)
    Path(config["chroma_path"]).mkdir(parents=True, exist_ok=True)
    init_db()
    console.print("[green]aqua initialized successfully[/green]")


# ── Documents ──────────────────────────────────────────────

@cli.group()
def docs():
    """Manage research documents"""
    pass


@docs.command("add")
@click.argument("title")
@click.option("--content", "-c", default="", help="Document content")
@click.option("--authors", "-a", default="", help="Author(s)")
@click.option("--source", "-s", default="manual", help="Source type (manual, pdf, url, arxiv)")
@click.option("--file", "-f", "file_path", default="", help="File path to ingest")
@click.option("--tags", "-t", default="", help="Comma-separated tags")
@click.option("--summary", default="", help="Brief summary")
def add_doc_cmd(title, content, authors, source, file_path, tags, summary):
    """Add a new document"""
    if file_path:
        title, content, source = ingest_file(file_path)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    doc = add_document(
        title=title, content=content, authors=authors,
        source=source, file_path=file_path, summary=summary,
        tags=tag_list,
    )

    if source == "manual" and content:
        try:
            from aqua.rag import retriever as _r
            _r.index_document(doc.id, content)
        except ImportError:
            pass

    console.print(f"[green]Document added:[/green] {doc.title} (id={doc.id})")


@docs.command("list")
@click.option("--tag", "-t", default=None, help="Filter by tag")
@click.option("--source", "-s", default=None, help="Filter by source")
@click.option("--limit", "-l", default=20, help="Max results")
def list_docs_cmd(tag, source, limit):
    """List all documents"""
    docs = list_documents(tag=tag, source=source, limit=limit)
    if not docs:
        console.print("[yellow]No documents found[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Source")
    table.add_column("Tags")
    table.add_column("Date")

    for d in docs:
        tag_str = ", ".join(t.name for t in d.tags) if d.tags else ""
        table.add_row(str(d.id), d.title[:60], d.source, tag_str, d.created_at.strftime("%Y-%m-%d"))

    console.print(table)


@docs.command("show")
@click.argument("doc_id", type=int)
def show_doc_cmd(doc_id):
    """Show document details"""
    doc = get_document(doc_id)
    if not doc:
        console.print("[red]Document not found[/red]")
        return

    tag_str = ", ".join(t.name for t in doc.tags) if doc.tags else "none"
    info = Panel(
        f"[bold]{doc.title}[/bold]\n\n"
        f"[dim]ID:[/dim] {doc.id}  |  [dim]Source:[/dim] {doc.source}  |  [dim]Tags:[/dim] {tag_str}\n"
        f"[dim]Authors:[/dim] {doc.authors or 'N/A'}\n"
        f"[dim]Created:[/dim] {doc.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"[bold]Summary:[/bold]\n{doc.summary or 'No summary'}\n\n"
        f"[bold]Content:[/bold] ({len(doc.content)} chars)\n{doc.content[:2000] if doc.content else 'No content'}",
        title="Document",
    )
    console.print(info)


@docs.command("search")
@click.argument("query")
@click.option("--limit", "-l", default=20, help="Max results")
def search_docs_cmd(query, limit):
    """Search document content"""
    results = search_documents(query, limit=limit)
    if not results:
        console.print("[yellow]No matches found[/yellow]")
        return

    for r in results:
        snippet = ""
        if query.lower() in r.content.lower():
            idx = r.content.lower().index(query.lower())
            start = max(0, idx - 100)
            end = min(len(r.content), idx + len(query) + 100)
            snippet = "... " + r.content[start:end] + " ..."
        console.print(Panel(f"[bold]{r.title}[/bold] (id={r.id})\n\n{snippet or '(no content preview)'}"))


@docs.command("delete")
@click.argument("doc_id", type=int)
@click.confirmation_option(prompt="Delete this document?")
def delete_doc_cmd(doc_id):
    """Delete a document"""
    if delete_document(doc_id):
        try:
            from aqua.rag import retriever as _r
            _r.delete_document(doc_id)
        except ImportError:
            pass
        console.print("[green]Document deleted[/green]")
    else:
        console.print("[red]Document not found[/red]")


# ── Notes ──────────────────────────────────────────────────

@cli.group()
def notes():
    """Manage research notes"""
    pass


@notes.command("add")
@click.argument("content")
@click.option("--title", "-t", default="", help="Note title")
@click.option("--doc-id", "-d", "document_id", type=int, default=None, help="Link to document ID")
def add_note_cmd(content, title, document_id):
    """Add a new note"""
    note = add_note(content=content, title=title, document_id=document_id)
    console.print(f"[green]Note added[/green] (id={note.id})")


@notes.command("list")
@click.option("--doc-id", "-d", "document_id", type=int, default=None)
@click.option("--limit", "-l", default=20)
def list_notes_cmd(document_id, limit):
    """List notes"""
    notes = list_notes(document_id=document_id, limit=limit)
    if not notes:
        console.print("[yellow]No notes found[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Preview")
    table.add_column("Date")

    for n in notes:
        table.add_row(str(n.id), n.title or "(untitled)", n.content[:80], n.created_at.strftime("%Y-%m-%d"))

    console.print(table)


@notes.command("search")
@click.argument("query")
@click.option("--limit", "-l", default=20)
def search_notes_cmd(query, limit):
    """Search notes"""
    results = search_notes(query, limit=limit)
    if not results:
        console.print("[yellow]No matches found[/yellow]")
        return

    for r in results:
        console.print(Panel(f"[bold]{r.title or 'Untitled'}[/bold] (id={r.id})\n\n{r.content[:500]}"))


@notes.command("edit")
@click.argument("note_id", type=int)
@click.option("--content", "-c", required=True, help="New content")
@click.option("--title", "-t", help="New title")
def edit_note_cmd(note_id, content, title):
    """Edit a note"""
    note = edit_note(note_id, content, title=title)
    if note:
        console.print("[green]Note updated[/green]")
    else:
        console.print("[red]Note not found[/red]")


@notes.command("delete")
@click.argument("note_id", type=int)
@click.confirmation_option(prompt="Delete this note?")
def delete_note_cmd(note_id):
    """Delete a note"""
    if delete_note_db(note_id):
        console.print("[green]Note deleted[/green]")
    else:
        console.print("[red]Note not found[/red]")


# ── RAG / Ask ──────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.option("--doc-id", "-d", "document_id", type=int, default=None, help="Search within specific document")
@click.option("--n-results", "-n", default=5, help="Number of results")
def ask(query, document_id, n_results):
    """Ask a question against your knowledge base (RAG)"""
    try:
        from aqua.rag import retriever as _r
        results = _r.search(query, n_results=n_results, document_id=document_id)
    except Exception as e:
        console.print(f"[yellow]Embedding search not available: {e}[/yellow]")
        console.print("[yellow]Falling back to text search...[/yellow]")
        docs = search_documents(query)
        results = [{"content": d.content[:500], "score": 0, "metadata": {"document_id": d.id}, "id": str(d.id)} for d in docs[:n_results]]

    if not results:
        console.print("[yellow]No relevant results found[/yellow]")
        return

    console.print(f"\n[bold]Top {len(results)} results for:[/bold] {query}\n")
    for i, r in enumerate(results, 1):
        score = r.get("score", 0)
        doc_id = r.get("metadata", {}).get("document_id", "?")
        console.print(Panel(
            r["content"][:600],
            title=f"#{i} (doc_id={doc_id}, relevance={1-score:.2f})" if score else f"#{i} (doc_id={doc_id})",
        ))


# ── Flashcards ─────────────────────────────────────────────

@cli.group()
def flashcards():
    """Manage flashcards"""
    pass


@flashcards.command("add")
@click.argument("question")
@click.argument("answer")
@click.option("--topic", "-t", default="", help="Topic")
@click.option("--difficulty", "-d", default=1, type=int, help="Difficulty 1-5")
def add_fc_cmd(question, answer, topic, difficulty):
    """Add a flashcard"""
    card = add_flashcard(question, answer, topic=topic, difficulty=difficulty)
    console.print(f"[green]Flashcard added[/green] (id={card.id})")


@flashcards.command("list")
@click.option("--topic", "-t", default=None)
@click.option("--limit", "-l", default=50)
def list_fc_cmd(topic, limit):
    """List flashcards"""
    cards = list_flashcards(topic=topic, limit=limit)
    if not cards:
        console.print("[yellow]No flashcards found[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Question")
    table.add_column("Topic")
    table.add_column("Difficulty")
    table.add_column("Reviews")

    for c in cards:
        table.add_row(str(c.id), c.question[:60], c.topic or "-", str(c.difficulty), str(c.review_count))

    console.print(table)


@flashcards.command("review")
@click.option("--topic", "-t", default=None)
def review_fc_cmd(topic):
    """Review flashcards (spaced repetition)"""
    cards = list_flashcards(topic=topic)
    if not cards:
        console.print("[yellow]No flashcards to review[/yellow]")
        return

    for card in cards:
        console.print(Panel(f"[bold]Q:[/bold] {card.question}", title=f"Flashcard #{card.id}"))
        answer = Prompt.ask("[bold]Your answer[/bold]")
        console.print(f"[bold]Correct answer:[/bold] {card.answer}")
        correct = Confirm.ask("Were you correct?")
        review_flashcard(card.id, correct=correct)
        console.print()


# ── Quiz ───────────────────────────────────────────────────

@cli.group()
def quiz():
    """Create and take quizzes"""
    pass


@quiz.command("list")
def list_quiz_cmd():
    """List quizzes"""
    quizzes = list_quizzes()
    if not quizzes:
        console.print("[yellow]No quizzes found[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Topic")
    table.add_column("Score")
    table.add_column("Date")

    for q in quizzes:
        score_str = f"{q.score:.0f}%" if q.score is not None else "-"
        table.add_row(str(q.id), q.title, q.topic or "-", score_str, q.created_at.strftime("%Y-%m-%d"))

    console.print(table)


@quiz.command("create")
@click.argument("title")
@click.option("--topic", "-t", default="")
def create_quiz_cmd(title, topic):
    """Interactive quiz creation"""
    questions = []
    console.print("[bold]Creating quiz...[/bold] (type 'done' as question to finish)\n")

    while True:
        q = Prompt.ask("Question")
        if q.lower() == "done":
            break
        a = Prompt.ask("Answer")
        questions.append({"question": q, "correct_answer": a, "options": [a]})
        console.print("[dim]Question added[/dim]\n")

    if not questions:
        console.print("[yellow]No questions added[/yellow]")
        return

    quiz_obj = create_quiz(title, topic, questions)
    console.print(f"[green]Quiz created[/green] (id={quiz_obj.id}) with {len(questions)} questions")


@quiz.command("take")
@click.argument("quiz_id", type=int)
def take_quiz_cmd(quiz_id):
    """Take a quiz interactively"""
    q = get_quiz(quiz_id)
    if not q:
        console.print("[red]Quiz not found[/red]")
        return

    console.print(f"[bold]Quiz:[/bold] {q.title} ({len(q.questions)} questions)\n")

    for question in q.questions:
        console.print(f"[bold]Q:[/bold] {question.question}")
        answer = Prompt.ask("Your answer")
        submit_answer(question.id, answer)
        console.print()

    result = grade_quiz(quiz_id)
    if result:
        console.print(f"[bold]Result:[/bold] {result['correct']}/{result['total']} = {result['score']:.0f}%")


# ── Shell / Interactive ────────────────────────────────────

@cli.command()
def shell():
    """Launch an interactive aqua shell"""
    console.print("[bold blue]aqua shell[/bold blue] - type 'help' for commands, 'exit' to quit\n")

    while True:
        try:
            cmd = Prompt.ask("aqua")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye[/dim]")
            break

        if cmd in ("exit", "quit", "q"):
            break
        elif cmd == "help":
            console.print("""
[bold]Commands:[/bold]
  ask <query>         - Search your knowledge base
  docs                - List documents
  notes               - List notes
  flashcards          - List flashcards
  help                - Show this help
  exit                - Exit shell
""")
        elif cmd.startswith("ask "):
            query = cmd[4:]
            try:
                from aqua.rag import retriever as _r
                results = _r.search(query) if query else []
            except ImportError:
                results = []
            for r in results[:3]:
                console.print(Panel(r["content"][:400]))
        elif cmd == "docs":
            docs = list_documents(limit=10)
            for d in docs:
                console.print(f"  {d.id}: {d.title}")
        elif cmd == "notes":
            ns = list_notes(limit=10)
            for n in ns:
                console.print(f"  {n.id}: {n.content[:80]}")
        elif cmd == "flashcards":
            cards = list_flashcards(limit=10)
            for c in cards:
                console.print(f"  {c.id}: {c.question[:60]}")
        else:
            console.print(f"[red]Unknown command:[/red] {cmd}")


if __name__ == "__main__":
    cli()
