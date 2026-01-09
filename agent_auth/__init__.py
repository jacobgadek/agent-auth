"""AgentAuth - AI Agent session management SDK.

AgentAuth provides a secure way for AI Agent developers to manage browser
sessions without hardcoding credentials.

Example:
    ```python
    from agent_auth import Agent, AgentAuthClient

    # Load or create an agent
    agent = Agent.load("sales-bot")  # or Agent.create("sales-bot", scopes=["linkedin.com"])

    # Get authenticated client
    client = AgentAuthClient(agent)

    # Request session (agent must have linkedin.com in scopes)
    session = client.get_session("linkedin.com")

    # Use with requests or playwright
    import requests
    response = requests.get("https://linkedin.com/feed", cookies=session)
    ```
"""

__version__ = "0.1.0"

# Main public API
from agent_auth.client import (
    AgentAuthClient,
    AgentAuthClientError,
    SessionExpiredError,
    SessionNotFoundError,
)
from agent_auth.identity import (
    Agent,
    AgentError,
    AgentNotFoundError,
    AgentScopeError,
)
from agent_auth.models import AgentIdentity, Session, SessionAccessLog
from agent_auth.vault import (
    Vault,
    VaultAuthenticationError,
    VaultError,
    VaultNotInitializedError,
)

__all__ = [
    # Main classes
    "Agent",
    "AgentAuthClient",
    "Vault",
    # Models
    "AgentIdentity",
    "Session",
    "SessionAccessLog",
    # Exceptions
    "AgentError",
    "AgentNotFoundError",
    "AgentScopeError",
    "AgentAuthClientError",
    "SessionExpiredError",
    "SessionNotFoundError",
    "VaultError",
    "VaultNotInitializedError",
    "VaultAuthenticationError",
]

