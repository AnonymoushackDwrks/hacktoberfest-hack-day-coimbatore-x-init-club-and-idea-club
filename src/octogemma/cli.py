"""Command Line Interface for OctoGemma."""

import asyncio
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn
from .agent import OctoGemmaAgent
from .config import settings
from .llm import OllamaClient

app = typer.Typer(
    name="octogemma",
    help="OctoGemma: Privacy-First Autonomous Coding & Self-Healing Agent powered by Google Gemma 4.",
    add_completion=False
)
console = Console()


def print_banner():
    banner = """[bold cyan]
   ____       _          ____                               
  / __ \\_____| |_ ___   / ____/___   ____ ___  ____ ___  ____ 
 / / / / ___/ __/ __ \\ / / __ / _ \\ / __ `__ \\/ __ `__ \\/ __ \\
/ /_/ / /__/ /_/ /_/ // /_/ //  __// / / / / / / / / / / /_/ /
\\____/\\___/\\__/\\____/ \\____/ \\___//_/ /_/ /_/_/ /_/ /_/\\__,_/ 
[/bold cyan]
[bold white]Privacy-First Autonomous Coding & Self-Healing Agent[/bold white]
[dim yellow]Powered by Google Gemma 4 • Built for Hacktoberfest Hack Day Coimbatore 2026[/dim yellow]
"""
    console.print(banner)


@app.command()
def models():
    """List all installed Ollama models and identify available Gemma 4 / coder models."""
    print_banner()
    client = OllamaClient()

    async def _run():
        with console.status("[bold green]Checking local Ollama daemon...[/bold green]"):
            health = await client.check_health()
            if not health:
                console.print("[bold red]Error:[/] Could not connect to Ollama at " + client.base_url)
                console.print("[dim]Make sure Ollama is running (`ollama serve`).[/dim]")
                return

            model_list = await client.list_models()

        if not model_list:
            console.print("[yellow]No models found in Ollama.[/yellow]")
            console.print("Run [bold cyan]octogemma pull gemma4:e4b[/bold cyan] to install Gemma 4.")
            return

        table = Table(title="Local Ollama Models", border_style="cyan")
        table.add_column("Model Name", style="bold white")
        table.add_column("Size", style="green")
        table.add_column("Modified", style="dim")
        table.add_column("Status", style="yellow")

        for m in model_list:
            name = m.get("name", "unknown")
            size_gb = round(m.get("size", 0) / (1024**3), 2)
            modified = m.get("modified_at", "")[:10]
            is_active = (name == settings.default_model or name.startswith("gemma4"))
            tag = "★ RECOMMENDED" if "gemma4" in name else ("ACTIVE" if is_active else "")
            table.add_row(name, f"{size_gb} GB", modified, tag)

        console.print(table)
        console.print("\nTo pull Gemma 4: [bold cyan]octogemma pull gemma4:e4b[/bold cyan]\n")

    asyncio.run(_run())


@app.command()
def pull(
    model: str = typer.Argument("gemma4:e4b", help="Model name to pull (e.g. gemma4:e4b, gemma4:12b)")
):
    """Pull an Ollama model with real-time download progress."""
    print_banner()
    client = OllamaClient()

    async def _run():
        console.print(f"[bold cyan]Initiating pull for model:[/] [bold yellow]{model}[/bold yellow]...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Pulling {model}", total=100)

            async for chunk in client.pull_model_stream(model):
                if chunk.get("status") == "error":
                    console.print(f"[bold red]Pull failed:[/] {chunk.get('error')}")
                    return

                status_msg = chunk.get("status", "")
                completed = chunk.get("completed", 0)
                total = chunk.get("total", 0)

                if total > 0:
                    progress.update(task, description=f"{status_msg}", completed=completed, total=total)
                else:
                    progress.update(task, description=f"{status_msg}")

        console.print(f"\n[bold green]✓ Successfully pulled model {model}![/bold green]\n")

    asyncio.run(_run())


@app.command()
def run(
    task: str = typer.Argument(..., help="The autonomous coding or bug-fixing task description"),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace path"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name (e.g. gemma4:e4b)"),
    max_steps: int = typer.Option(25, "--max-steps", "-s", help="Maximum agent steps")
):
    """Run OctoGemma autonomously to solve a coding objective in the given workspace."""
    print_banner()
    ws_path = Path(workspace).resolve()
    agent = OctoGemmaAgent(workspace=ws_path, model=model, max_steps=max_steps)

    async def _execute():
        async for event in agent.run(task):
            etype = event.get("type")

            if etype == "agent_started":
                console.print(Panel(
                    f"[bold white]Objective:[/] {event.get('instruction')}\n"
                    f"[bold cyan]Model:[/] {event.get('model')}\n"
                    f"[bold magenta]Workspace:[/] {event.get('workspace')}\n"
                    f"[bold yellow]Max Steps:[/] {event.get('max_steps')}",
                    title="[bold green]Autonomous Agent Initialized[/bold green]",
                    border_style="green"
                ))

            elif etype == "step_start":
                console.print(f"\n[bold blue]─── Step {event.get('step')} / {event.get('max_steps')} ───[/bold blue]")

            elif etype == "thought":
                console.print(Panel(
                    event.get("thought", ""),
                    title="[bold cyan]Agent Reasoning[/bold cyan]",
                    border_style="cyan"
                ))

            elif etype == "tool_call":
                tname = event.get("tool")
                targs = event.get("arguments")
                console.print(f"[bold yellow]▶ Tool Invocation:[/] [bold green]{tname}[/bold green]")
                if tname == "run_command":
                    console.print(f"  [dim]Executing command:[/] [bold]{targs.get('command')}[/bold]")
                elif tname in ("edit_file", "write_file", "read_file"):
                    console.print(f"  [dim]Target File:[/] [bold]{targs.get('path')}[/bold]")

            elif etype == "diff_updated":
                diff_text = event.get("diff", "")
                if diff_text:
                    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
                    console.print(Panel(syntax, title=f"[bold green]Patch: {event.get('path')}[/bold green]", border_style="green"))

            elif etype == "self_healing_triggered":
                console.print(Panel(
                    f"[bold red]Failure Detected during {event.get('tool')}:[/bold red]\n{event.get('reason')}\n"
                    f"[bold yellow]Self-Healing Activated (Attempt #{event.get('attempt')})[/bold yellow] - OctoGemma is diagnosing the error...",
                    title="[bold red]Self-Repair Loop Triggered[/bold red]",
                    border_style="red"
                ))

            elif etype == "tool_result":
                res = event.get("result", {})
                if event.get("tool") == "run_command":
                    stdout = res.get("stdout", "")
                    stderr = res.get("stderr", "")
                    code = res.get("exit_code")
                    color = "green" if code == 0 else "red"
                    console.print(f"  [bold {color}]Exit code:[/] {code}")
                    if stdout:
                        console.print(Panel(stdout[:1000], title="Stdout", border_style="dim"))
                    if stderr:
                        console.print(Panel(stderr[:1000], title="Stderr", border_style="red"))

            elif etype == "task_finished":
                console.print(Panel(
                    f"[bold green]✓ Task Completed Successfully in Step {event.get('step')}![/bold green]\n\n"
                    f"{event.get('summary')}",
                    title="[bold green]Mission Accomplished[/bold green]",
                    border_style="green"
                ))

            elif etype == "error":
                console.print(Panel(
                    f"[bold red]Error:[/] {event.get('message')}",
                    title="Agent Error",
                    border_style="red"
                ))

    asyncio.run(_execute())


@app.command()
def chat(
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace path"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name")
):
    """Start an interactive autonomous coding session."""
    print_banner()
    console.print("[bold green]Interactive Mode started. Type 'exit' or 'quit' to end session.[/bold green]\n")

    while True:
        try:
            task = console.input("[bold cyan]octogemma>[/bold cyan] ").strip()
            if not task:
                continue
            if task.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break
            run(task=task, workspace=workspace, model=model, max_steps=25)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session closed.[/dim]")
            break


@app.command()
def web(
    host: str = typer.Option(settings.web_host, "--host", "-h", help="Host address"),
    port: int = typer.Option(settings.web_port, "--port", "-p", help="Port number")
):
    """Launch the OctoGemma Web Studio UI."""
    print_banner()
    import uvicorn
    console.print(f"[bold green]Starting OctoGemma Web Studio at http://{host}:{port}[/bold green]")
    uvicorn.run("src.octogemma.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
