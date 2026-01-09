"""CLI interface for AgentAuth using Typer and Rich."""

import json
import logging
from datetime import datetime, timedelta
from getpass import getpass
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich import print as rprint

from agent_auth.client import (
    AgentAuthClient,
    AgentAuthClientError,
    SessionExpiredError,
    SessionNotFoundError,
)
from agent_auth.identity import Agent, AgentError, AgentNotFoundError, AgentScopeError
from agent_auth.vault import (
    Vault,
    VaultAuthenticationError,
    VaultError,
    VaultNotInitializedError,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Typer app and Rich console
app = typer.Typer(
    name="agent-auth",
    help="AgentAuth - AI Agent session management SDK",
    add_completion=False,
)
console = Console()


def get_vault_password() -> str:
    """Prompt for vault password securely.
    
    Returns:
        The vault password
    """
    return getpass("Vault password: ")


@app.command()
def init():
    """Initialize the vault with a master password."""
    console.print("[bold blue]Initializing AgentAuth vault...[/bold blue]")
    
    vault = Vault()
    
    # Check if vault already exists
    if vault.is_initialized():
        console.print("[yellow]Vault already initialized[/yellow]")
        console.print(f"[dim]Vault location: {vault.db_path}[/dim]")
        raise typer.Exit(0)
    
    # Vault doesn't exist - create it
    password = getpass("Enter master password: ")
    password_confirm = getpass("Confirm master password: ")
    
    if password != password_confirm:
        console.print("[bold red]Passwords do not match![/bold red]")
        raise typer.Exit(1)
    
    if len(password) < 8:
        console.print("[bold red]Password must be at least 8 characters![/bold red]")
        raise typer.Exit(1)
    
    try:
        vault.initialize(password)
        console.print("[bold green]✓[/bold green] Vault initialized successfully!")
        console.print(f"[dim]Vault location: {vault.db_path}[/dim]")
    except VaultError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def add(domain: str):
    """Add a session for a domain."""
    console.print(f"[bold blue]Adding session for domain: {domain}[/bold blue]")
    
    vault = Vault()
    
    if not vault.is_initialized():
        console.print("[bold red]Vault is not initialized. Run 'agent-auth init' first.[/bold red]")
        raise typer.Exit(1)
    
    try:
        password = get_vault_password()
        vault.unlock(password)
    except VaultAuthenticationError:
        console.print("[bold red]Incorrect password![/bold red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error unlocking vault:[/bold red] {e}")
        raise typer.Exit(1)
    
    # Prompt for cookies JSON
    console.print("\n[bold]Enter cookies as JSON:[/bold]")
    console.print("[dim]Example: {\"session_id\": \"abc123\", \"auth_token\": \"xyz789\"}[/dim]")
    
    cookies_json = Prompt.ask("Cookies JSON")
    
    try:
        cookies = json.loads(cookies_json)
        if not isinstance(cookies, dict):
            raise ValueError("Cookies must be a JSON object (dictionary)")
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Invalid JSON:[/bold red] {e}")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)
    
    # Prompt for expiration
    days = Prompt.ask("Expiration (days from now)", default="30")
    try:
        days_int = int(days)
        expires_at = datetime.utcnow() + timedelta(days=days_int)
    except ValueError:
        console.print("[bold red]Invalid number of days![/bold red]")
        raise typer.Exit(1)
    
    try:
        session = vault.store_session(
            domain=domain,
            cookies=cookies,
            expires_at=expires_at,
        )
        console.print(f"[bold green]✓[/bold green] Session stored successfully!")
        console.print(f"[dim]Expires: {expires_at.isoformat()}[/dim]")
    except VaultError as e:
        console.print(f"[bold red]Error storing session:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def list_sessions():
    """List all stored sessions."""
    console.print("[bold blue]Stored Sessions[/bold blue]")
    
    vault = Vault()
    
    if not vault.is_initialized():
        console.print("[bold red]Vault is not initialized. Run 'agent-auth init' first.[/bold red]")
        raise typer.Exit(1)
    
    try:
        password = get_vault_password()
        vault.unlock(password)
    except VaultAuthenticationError:
        console.print("[bold red]Incorrect password![/bold red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error unlocking vault:[/bold red] {e}")
        raise typer.Exit(1)
    
    try:
        sessions = vault.list_sessions()
    except VaultError as e:
        console.print(f"[bold red]Error listing sessions:[/bold red] {e}")
        raise typer.Exit(1)
    
    if not sessions:
        console.print("[yellow]No sessions stored.[/yellow]")
        return
    
    # Create table
    table = Table(title="Stored Sessions")
    table.add_column("Domain", style="cyan")
    table.add_column("Expires", style="yellow")
    table.add_column("Created", style="dim")
    
    now = datetime.utcnow()
    for session in sessions:
        expires_style = "green" if session.expires_at > now else "red"
        expires_str = session.expires_at.isoformat()
        if session.expires_at < now:
            expires_str += " [red](EXPIRED)[/red]"
        
        table.add_row(
            session.domain,
            expires_str,
            session.created_at.isoformat(),
        )
    
    console.print(table)


@app.command()
def create_agent(
    name: str,
    scopes: Optional[str] = typer.Option(None, "--scopes", "-s", help="Comma-separated list of scopes"),
):
    """Create a new agent identity."""
    console.print(f"[bold blue]Creating agent: {name}[/bold blue]")
    
    # Parse scopes
    scope_list = []
    if scopes:
        scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
    
    if not scope_list:
        # Prompt for scopes interactively
        console.print("\n[bold]Enter scopes (domains this agent can access):[/bold]")
        console.print("[dim]Example: linkedin.com,gmail.com[/dim]")
        scopes_input = Prompt.ask("Scopes (comma-separated)", default="")
        if scopes_input:
            scope_list = [s.strip() for s in scopes_input.split(",") if s.strip()]
    
    if not scope_list:
        console.print("[yellow]No scopes provided. Agent will be created without scopes.[/yellow]")
        if not Confirm.ask("Continue?"):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()
    
    try:
        agent = Agent.create(name, scope_list)
        console.print(f"[bold green]✓[/bold green] Agent created successfully!")
        console.print(f"[dim]Agent ID: {agent.identity.id}[/dim]")
        console.print(f"[dim]Scopes: {', '.join(agent.identity.scopes) if agent.identity.scopes else '(none)'}[/dim]")
    except AgentError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command(name="agents")
def list_agents():
    """List all registered agents."""
    console.print("[bold blue]Registered Agents[/bold blue]")
    
    try:
        agent_names = Agent.list_agents()
    except Exception as e:
        console.print(f"[bold red]Error listing agents:[/bold red] {e}")
        raise typer.Exit(1)
    
    if not agent_names:
        console.print("[yellow]No agents registered.[/yellow]")
        return
    
    # Load and display agent details
    table = Table(title="Registered Agents")
    table.add_column("Name", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Scopes", style="yellow")
    table.add_column("Created", style="dim")
    
    for name in agent_names:
        try:
            agent = Agent.load(name)
            scopes_str = ", ".join(agent.identity.scopes) if agent.identity.scopes else "(none)"
            table.add_row(
                agent.identity.name,
                str(agent.identity.id)[:8] + "...",
                scopes_str,
                agent.identity.created_at.isoformat(),
            )
        except Exception as e:
            table.add_row(name, "[red]Error[/red]", str(e), "")
    
    console.print(table)


@app.command()
def test_session(
    agent_name: str,
    domain: str,
):
    """Test retrieving a session with an agent."""
    console.print(f"[bold blue]Testing session retrieval[/bold blue]")
    console.print(f"Agent: {agent_name}")
    console.print(f"Domain: {domain}\n")
    
    try:
        agent = Agent.load(agent_name)
    except AgentNotFoundError:
        console.print(f"[bold red]Agent '{agent_name}' not found![/bold red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error loading agent:[/bold red] {e}")
        raise typer.Exit(1)
    
    vault = Vault()
    
    if not vault.is_initialized():
        console.print("[bold red]Vault is not initialized. Run 'agent-auth init' first.[/bold red]")
        raise typer.Exit(1)
    
    password = get_vault_password()
    
    try:
        client = AgentAuthClient(agent)
        session = client.get_session(domain, password=password)
        
        console.print(f"[bold green]✓[/bold green] Session retrieved successfully!")
        console.print("\n[bold]Cookies:[/bold]")
        console.print(Panel(json.dumps(session, indent=2), title="Session Cookies"))
    except SessionNotFoundError as e:
        console.print(f"[bold red]Session not found:[/bold red] {e}")
        raise typer.Exit(1)
    except SessionExpiredError as e:
        console.print(f"[bold red]Session expired:[/bold red] {e}")
        raise typer.Exit(1)
    except AgentScopeError as e:
        console.print(f"[bold red]Scope error:[/bold red] {e}")
        raise typer.Exit(1)
    except AgentAuthClientError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


def main():
    """Main entry point for CLI."""
    app()


# Typer app can also be called directly
if __name__ == "__main__":
    main()

