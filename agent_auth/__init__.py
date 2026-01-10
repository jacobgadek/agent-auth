"""AgentAuth - Identity and session management for AI Agents."""

from .identity import Agent
from .client import AgentAuthClient
from .vault import Vault

__version__ = "0.1.0"

__all__ = ["Agent", "AgentAuthClient", "Vault"]

# Optional LangChain integration
try:
    from .langchain import get_agentauth_tools, AuthenticatedRequestTool, GetSessionTool
    __all__.extend(["get_agentauth_tools", "AuthenticatedRequestTool", "GetSessionTool"])
except ImportError:
    # LangChain not installed
    pass
