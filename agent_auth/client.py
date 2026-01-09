"""Main client interface for AgentAuth SDK."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from agent_auth.identity import Agent, AgentScopeError
from agent_auth.models import Session
from agent_auth.vault import Vault, VaultAuthenticationError, VaultError, VaultNotInitializedError

logger = logging.getLogger(__name__)


class AgentAuthClientError(Exception):
    """Base exception for AgentAuthClient operations."""
    pass


class SessionNotFoundError(AgentAuthClientError):
    """Raised when a session is not found."""
    pass


class SessionExpiredError(AgentAuthClientError):
    """Raised when a session has expired."""
    pass


class AgentAuthClient:
    """Main client interface for accessing authenticated sessions.
    
    Developers use this client to retrieve browser sessions for their agents.
    The client:
    - Requires an Agent identity to request sessions
    - Verifies agent has scope for requested domain
    - Logs all session access
    - Handles session expiration
    
    Attributes:
        agent: The Agent identity
        vault: The Vault instance (optional, created if not provided)
    """
    
    def __init__(self, agent: Agent, vault: Optional[Vault] = None):
        """Initialize AgentAuthClient with an agent identity.
        
        Args:
            agent: The Agent identity that will access sessions
            vault: Optional Vault instance (creates new one if not provided)
            
        Raises:
            AgentAuthClientError: If agent is invalid
        """
        if agent is None:
            raise AgentAuthClientError("Agent is required")
        
        self.agent = agent
        self.vault = vault or Vault()
        
        logger.debug(f"Initialized AgentAuthClient for agent: {agent.identity.name}")
    
    def get_session(
        self,
        domain: str,
        password: Optional[str] = None,
        auto_unlock: bool = True,
    ) -> Dict:
        """Get a session for a domain.
        
        This method:
        1. Verifies the agent has scope for the domain
        2. Unlocks the vault if needed (if password provided or auto_unlock enabled)
        3. Retrieves the session from the vault
        4. Checks if session is expired
        5. Logs the access
        6. Returns the cookies dictionary
        
        Args:
            domain: The domain to get session for
            password: Optional vault password (if vault needs unlocking)
            auto_unlock: If True and vault not unlocked, will prompt for password
                        (CLI only - in library mode, password must be provided)
            
        Returns:
            Dictionary of cookie name-value pairs
            
        Raises:
            AgentScopeError: If agent does not have scope for domain
            VaultNotInitializedError: If vault is not initialized
            VaultAuthenticationError: If vault password is incorrect
            SessionNotFoundError: If session not found for domain
            SessionExpiredError: If session has expired
            AgentAuthClientError: For other errors
        """
        # Normalize domain
        domain = domain.strip().lower().replace('https://', '').replace('http://', '').split('/')[0]
        
        # Verify agent has scope
        self.agent.check_scope(domain)
        
        # Ensure vault is unlocked
        if not self.vault.is_initialized():
            raise VaultNotInitializedError(
                "Vault is not initialized. Run 'agent-auth init' first."
            )
        
        # Try to unlock vault if needed
        # Note: In library mode, password should be provided explicitly
        # In CLI mode, getpass can be used (handled by CLI)
        try:
            # Check if vault is already unlocked (password/salt set)
            if self.vault.password is None or self.vault.salt is None:
                if password is None:
                    if not auto_unlock:
                        raise VaultAuthenticationError(
                            "Vault is locked. Provide password to unlock."
                        )
                    # In library mode without auto_unlock, we can't prompt
                    # This would be handled by CLI layer
                    raise VaultAuthenticationError(
                        "Vault is locked. Please provide password or use CLI."
                    )
                self.vault.unlock(password)
        except VaultAuthenticationError:
            raise
        except Exception as e:
            raise AgentAuthClientError(f"Failed to unlock vault: {e}")
        
        # Get session from vault
        try:
            session = self.vault.get_session(domain)
        except VaultError as e:
            raise AgentAuthClientError(f"Failed to retrieve session: {e}")
        
        if session is None:
            raise SessionNotFoundError(
                f"No session found for domain '{domain}'. "
                f"Add a session with 'agent-auth add {domain}'"
            )
        
        # Check if session is expired
        if session.expires_at < datetime.utcnow():
            raise SessionExpiredError(
                f"Session for domain '{domain}' expired on {session.expires_at.isoformat()}"
            )
        
        # Log access
        try:
            self.vault.log_access(
                agent_id=self.agent.identity.id,
                agent_name=self.agent.identity.name,
                domain=domain,
                accessed_at=datetime.utcnow(),
            )
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(f"Failed to log access: {e}")
        
        logger.info(
            f"Agent '{self.agent.identity.name}' accessed session for domain '{domain}'"
        )
        
        return session.cookies
    
    def list_sessions(self, password: Optional[str] = None) -> list[Session]:
        """List all available sessions.
        
        Note: This lists all sessions in the vault, not just ones
        the agent has scope for.
        
        Args:
            password: Optional vault password (if vault needs unlocking)
            
        Returns:
            List of Session objects
            
        Raises:
            VaultNotInitializedError: If vault is not initialized
            VaultAuthenticationError: If vault password is incorrect
            AgentAuthClientError: For other errors
        """
        # Ensure vault is initialized
        if not self.vault.is_initialized():
            raise VaultNotInitializedError(
                "Vault is not initialized. Run 'agent-auth init' first."
            )
        
        # Unlock vault if needed
        if self.vault.password is None or self.vault.salt is None:
            if password is None:
                raise VaultAuthenticationError(
                    "Vault is locked. Provide password to unlock."
                )
            self.vault.unlock(password)
        
        try:
            return self.vault.list_sessions()
        except VaultError as e:
            raise AgentAuthClientError(f"Failed to list sessions: {e}")
    
    def close(self) -> None:
        """Close the client and release resources."""
        if self.vault:
            self.vault.close()

