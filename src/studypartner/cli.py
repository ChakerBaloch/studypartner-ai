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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed debug logs"),
):
    """Start a study session. The AI tutor will observe your screen and coach you."""
    from studypartner.client.session import start_session

    start_session(topic=topic, verbose=verbose)


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


@app.command()
def logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow new log entries"),
):
    """View StudyPartner log files."""
    from studypartner.client.logging_config import get_log_path
    from studypartner.shared.constants import LOGS_DIR

    log_file = get_log_path()

    if not log_file.exists():
        console.print("[dim]No log file yet. Start a session first.[/dim]")
        console.print(f"[dim]Log directory: {LOGS_DIR}[/dim]")
        return

    console.print(f"[dim]📁 Log file: {log_file}[/dim]\n")

    if follow:
        import subprocess
        subprocess.run(["tail", "-f", str(log_file)])
    else:
        # Show last N lines
        content = log_file.read_text()
        log_lines = content.strip().split("\n")
        for line in log_lines[-lines:]:
            console.print(line)


@app.command()
def files():
    """Show where StudyPartner stores files on your computer."""
    from studypartner.shared.constants import DATA_DIR, DB_PATH, LOGS_DIR, SCREENSHOTS_DIR

    from rich.table import Table

    table = Table(title="📁 StudyPartner File Locations", border_style="blue")
    table.add_column("What", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Exists", style="green")

    locations = [
        ("Data directory", DATA_DIR),
        ("Database", DB_PATH),
        ("Screenshots", SCREENSHOTS_DIR),
        ("Log files", LOGS_DIR),
        ("Config", DATA_DIR / "config.json"),
        ("Learning profile", DATA_DIR / "learning_profile.json"),
    ]

    for name, path in locations:
        exists = "✅" if path.exists() else "—"
        table.add_row(name, str(path), exists)

    console.print(table)


if __name__ == "__main__":
    app()
