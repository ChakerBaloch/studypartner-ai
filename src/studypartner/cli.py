"""StudyPartner CLI — Main entry point."""

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="studypartner",
    help="🧠 AI study tutor that watches your screen and coaches you in real-time.",
    add_completion=False,
)
console = Console()


@app.command()
def start(
    topic: str = typer.Option(None, "--topic", "-t", help="Topic you're studying"),
):
    """Start a study session. The AI tutor will observe your screen and coach you."""
    from studypartner.client.session import start_session

    console.print(
        Panel(
            "[bold green]StudyPartner AI[/bold green]\n"
            "Starting study session...\n"
            f"Topic: {topic or 'Auto-detect from screen'}",
            title="🧠 Study Session",
            border_style="green",
        )
    )
    start_session(topic=topic)


@app.command()
def stop():
    """Stop the current study session and show summary."""
    from studypartner.client.session import stop_session

    stop_session()
    console.print("[yellow]Session ended.[/yellow]")


@app.command()
def status():
    """Show current session status."""
    from studypartner.client.session import get_status

    info = get_status()
    if info:
        console.print(Panel(info, title="📊 Session Status", border_style="blue"))
    else:
        console.print("[dim]No active session.[/dim]")


@app.command()
def setup():
    """Interactive first-run setup wizard."""
    from studypartner.setup_wizard import run_wizard

    run_wizard()


@app.command()
def deploy():
    """Deploy the Cloud Run backend to your GCP project."""
    import subprocess
    from pathlib import Path

    deploy_script = Path(__file__).parent.parent.parent / "deploy.sh"
    if not deploy_script.exists():
        console.print("[red]deploy.sh not found. Run from the project root.[/red]")
        raise typer.Exit(1)

    console.print("[bold blue]Deploying backend to Cloud Run...[/bold blue]")
    result = subprocess.run(["bash", str(deploy_script)], check=False)
    if result.returncode == 0:
        console.print("[bold green]✅ Backend deployed successfully![/bold green]")
    else:
        console.print("[red]❌ Deployment failed. Check the output above.[/red]")
        raise typer.Exit(1)


@app.command()
def history():
    """View past study sessions."""
    from studypartner.client.database import get_recent_sessions

    sessions = get_recent_sessions(limit=10)
    if not sessions:
        console.print("[dim]No sessions recorded yet.[/dim]")
        return

    from rich.table import Table

    table = Table(title="📚 Recent Study Sessions")
    table.add_column("Date", style="cyan")
    table.add_column("Topic", style="green")
    table.add_column("Duration", style="yellow")
    table.add_column("Focus", style="magenta")

    for s in sessions:
        table.add_row(s["date"], s["topic"], s["duration"], s["focus"])

    console.print(table)


@app.command()
def review():
    """Show topics due for spaced review."""
    from studypartner.client.scheduler import get_due_reviews

    reviews = get_due_reviews()
    if not reviews:
        console.print("[dim]No reviews due. Keep studying![/dim]")
        return

    for r in reviews:
        console.print(f"  📅 [bold]{r['topic']}[/bold] — overdue by {r['overdue_days']} day(s)")


@app.command()
def reset(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Wipe all local data (sessions, profile, screenshots)."""
    if not confirm:
        confirm = typer.confirm("⚠️  This will delete ALL StudyPartner data. Are you sure?")
    if confirm:
        from studypartner.client.database import reset_all_data

        reset_all_data()
        console.print("[green]All data wiped.[/green]")
    else:
        console.print("[dim]Cancelled.[/dim]")


if __name__ == "__main__":
    app()
