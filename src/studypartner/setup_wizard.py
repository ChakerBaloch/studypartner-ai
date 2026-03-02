"""Interactive first-run setup wizard for StudyPartner."""

from __future__ import annotations


from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from studypartner.client.config import Config
from studypartner.client.database import init_db
from studypartner.shared.constants import DATA_DIR, SCREENSHOTS_DIR, LOGS_DIR

console = Console()


def run_wizard():
    """Run the interactive setup wizard."""
    console.print(Panel(
        "[bold green]🧠 StudyPartner AI — Setup Wizard[/bold green]\n\n"
        "This wizard will configure your local client and connect it\n"
        "to your Cloud Run backend. It takes about 2 minutes.",
        border_style="green",
    ))

    config = Config.load()

    # Step 1: Backend URL
    console.print("\n[bold]Step 1/4: Backend URL[/bold]")
    console.print(
        "[dim]If you haven't deployed the backend yet, run:[/dim]\n"
        "  [cyan]./deploy.sh[/cyan]\n"
        "[dim]or:[/dim]\n"
        "  [cyan]studypartner deploy[/cyan]"
    )

    backend_url = Prompt.ask(
        "Enter your Cloud Run backend URL",
        default=config.backend_url or "",
    )
    if backend_url:
        # Strip trailing slash
        config.backend_url = backend_url.rstrip("/")

    # Step 2: Verify backend connection
    console.print("\n[bold]Step 2/4: Verify Connection[/bold]")
    if config.backend_url:
        console.print(f"[dim]Testing connection to {config.backend_url}...[/dim]")
        try:
            import httpx
            response = httpx.get(f"{config.backend_url}/api/health", timeout=10)
            if response.status_code == 200:
                console.print("[green]✅ Backend is reachable![/green]")
            else:
                console.print(f"[yellow]⚠️  Backend returned status {response.status_code}[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not reach backend: {e}[/yellow]")
            if not Confirm.ask("Continue anyway?"):
                return
    else:
        console.print("[yellow]⚠️  No backend URL provided. You can set it later.[/yellow]")

    # Step 3: Preferences
    console.print("\n[bold]Step 3/4: Preferences[/bold]")

    config.default_pomodoro_minutes = int(Prompt.ask(
        "Default Pomodoro length (minutes)",
        default=str(config.default_pomodoro_minutes),
    ))

    config.enable_voice_coaching = Confirm.ask(
        "Enable voice coaching?",
        default=config.enable_voice_coaching,
    )

    # Step 4: macOS Permissions
    console.print("\n[bold]Step 4/4: macOS Permissions[/bold]")
    console.print(Panel(
        "StudyPartner needs these macOS permissions:\n\n"
        "  📸 [bold]Screen Recording[/bold] — to capture your screen\n"
        "     System Preferences → Privacy & Security → Screen Recording\n\n"
        "  🔔 [bold]Notifications[/bold] — to deliver coaching nudges\n"
        "     These will be requested automatically.\n\n"
        "  🎤 [bold]Microphone[/bold] (optional) — for voice coaching\n"
        "     System Preferences → Privacy & Security → Microphone",
        title="Required Permissions",
        border_style="yellow",
    ))

    console.print(
        "\n[dim]Please grant Screen Recording permission now if you haven't already.[/dim]"
    )
    Confirm.ask("Have you granted Screen Recording permission?", default=True)

    # Create local directories
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize database
    init_db()

    # Save config
    config.setup_complete = True
    config.save()

    console.print(Panel(
        "[bold green]✅ Setup complete![/bold green]\n\n"
        "Start your first study session:\n"
        "  [cyan]studypartner start[/cyan]\n\n"
        "Or start with a specific topic:\n"
        "  [cyan]studypartner start --topic \"Operating Systems\"[/cyan]",
        title="🎉 Ready!",
        border_style="green",
    ))
