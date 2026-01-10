"""LangChain integration for AgentAuth.

Provides tools and utilities for LangChain agents to use authenticated sessions.
"""

from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from pydantic import Field

from .client import AgentAuthClient
from .identity import Agent


class AuthenticatedRequestTool(BaseTool):
    """A LangChain tool that makes authenticated HTTP requests using AgentAuth sessions."""
    
    name: str = "authenticated_request"
    description: str = (
        "Make an authenticated HTTP request to a website using stored session cookies. "
        "Use this when you need to access a site that requires login (e.g., LinkedIn, Gmail). "
        "Input should be a JSON string with 'url' and optionally 'method' (GET/POST)."
    )
    
    agent_name: str = Field(description="Name of the AgentAuth agent to use")
    vault_password: str = Field(description="Password to unlock the vault")
    _client: Optional[AgentAuthClient] = None
    
    def __init__(self, agent_name: str, vault_password: str, **kwargs):
        super().__init__(agent_name=agent_name, vault_password=vault_password, **kwargs)
        agent = Agent.load(agent_name)
        self._client = AgentAuthClient(agent)
        self.vault_password = vault_password
    
    def _run(self, query: str) -> str:
        """Execute the authenticated request."""
        import json
        import requests
        
        try:
            params = json.loads(query)
        except json.JSONDecodeError:
            # Assume it's just a URL
            params = {"url": query}
        
        url = params.get("url")
        method = params.get("method", "GET").upper()
        
        if not url:
            return "Error: No URL provided"
        
        # Extract domain from URL
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        try:
            cookies = self._client.get_session(domain, password=self.vault_password)
        except Exception as e:
            return f"Error getting session for {domain}: {str(e)}"
        
        try:
            if method == "GET":
                response = requests.get(url, cookies=cookies, timeout=30)
            elif method == "POST":
                data = params.get("data", {})
                response = requests.post(url, cookies=cookies, json=data, timeout=30)
            else:
                return f"Error: Unsupported method {method}"
            
            return f"Status: {response.status_code}\n\nContent (first 2000 chars):\n{response.text[:2000]}"
        except requests.RequestException as e:
            return f"Request error: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version - just calls sync for now."""
        return self._run(query)


class GetSessionTool(BaseTool):
    """A LangChain tool that retrieves session cookies for a domain."""
    
    name: str = "get_session_cookies"
    description: str = (
        "Get session cookies for a specific domain. "
        "Use this when you need cookies to make your own requests. "
        "Input should be the domain name (e.g., 'linkedin.com')."
    )
    
    agent_name: str = Field(description="Name of the AgentAuth agent to use")
    vault_password: str = Field(description="Password to unlock the vault")
    _client: Optional[AgentAuthClient] = None
    
    def __init__(self, agent_name: str, vault_password: str, **kwargs):
        super().__init__(agent_name=agent_name, vault_password=vault_password, **kwargs)
        agent = Agent.load(agent_name)
        self._client = AgentAuthClient(agent)
        self.vault_password = vault_password
    
    def _run(self, domain: str) -> str:
        """Get cookies for the domain."""
        import json
        
        domain = domain.strip()
        
        try:
            cookies = self._client.get_session(domain, password=self.vault_password)
            return json.dumps(cookies, indent=2)
        except Exception as e:
            return f"Error getting session for {domain}: {str(e)}"
    
    async def _arun(self, domain: str) -> str:
        """Async version - just calls sync for now."""
        return self._run(domain)


def get_agentauth_tools(agent_name: str, vault_password: str) -> list:
    """
    Get all AgentAuth tools for use with a LangChain agent.
    
    Args:
        agent_name: Name of the AgentAuth agent identity to use
        vault_password: Password to unlock the AgentAuth vault
        
    Returns:
        List of LangChain tools
        
    Example:
        from langchain.agents import initialize_agent, AgentType
        from langchain_openai import ChatOpenAI
        from agent_auth.langchain import get_agentauth_tools
        
        tools = get_agentauth_tools("my-agent", "vault-password")
        llm = ChatOpenAI(model="gpt-4")
        agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)
        agent.run("Get my LinkedIn notifications")
    """
    return [
        AuthenticatedRequestTool(agent_name=agent_name, vault_password=vault_password),
        GetSessionTool(agent_name=agent_name, vault_password=vault_password),
    ]
