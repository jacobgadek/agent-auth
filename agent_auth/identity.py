"""Agent identity management with Ed25519 signing."""

import json
import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from agent_auth.crypto import encrypt_data
from agent_auth.models import AgentIdentity
from agent_auth.vault import Vault, VaultError

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for agent operations."""
    pass


class AgentNotFoundError(AgentError):
    """Raised when agent is not found."""
    pass


class AgentScopeError(AgentError):
    """Raised when agent does not have required scope."""
    pass


class Agent:
    """Agent identity with UUID and Ed25519 keypair.
    
    Agents are used to authenticate and authorize access to sessions.
    Each agent has:
    - A unique UUID
    - A human-readable name
    - A list of scopes (domains they can access)
    - An Ed25519 keypair for signing operations
    
    Attributes:
        identity: The AgentIdentity model containing all agent data
        private_key: The Ed25519 private key (decrypted, in memory)
        public_key: The Ed25519 public key
    """
    
    def __init__(self, identity: AgentIdentity, private_key: Optional[Ed25519PrivateKey] = None):
        """Initialize agent from identity model.
        
        Args:
            identity: The AgentIdentity model
            private_key: Optional private key (if loading from vault)
        """
        self.identity = identity
        self.private_key: Optional[Ed25519PrivateKey] = private_key
        
        # Load public key from identity
        if identity.public_key:
            public_key_bytes = self._decode_key(identity.public_key)
            self.public_key_obj = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        else:
            self.public_key_obj = None
    
    @classmethod
    def create(cls, name: str, scopes: List[str], agents_dir: Optional[Path] = None) -> "Agent":
        """Create a new agent identity.
        
        Args:
            name: Human-readable agent name
            scopes: List of domains this agent can access
            agents_dir: Directory to store agent files (defaults to ~/.agent-auth/agents)
            
        Returns:
            New Agent instance
            
        Raises:
            AgentError: If agent with this name already exists
        """
        if agents_dir is None:
            agents_dir = Path.home() / ".agent-auth" / "agents"
        
        agents_dir = Path(agents_dir)
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        agent_file = agents_dir / f"{name}.json"
        if agent_file.exists():
            raise AgentError(f"Agent '{name}' already exists")
        
        # Generate Ed25519 keypair
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        
        # For now, store private key encrypted with a default password
        # In production, this should use vault password or user's keyring
        vault = Vault()
        if vault.is_initialized():
            try:
                # Try to use vault password (would need to be unlocked)
                # For simplicity, we'll store unencrypted for now
                # TODO: Add proper encryption using vault or keyring
                private_key_encrypted = None
            except Exception:
                private_key_encrypted = None
        else:
            private_key_encrypted = None
        
        # Create identity
        identity = AgentIdentity(
            name=name,
            scopes=scopes,
            public_key=cls._encode_key(public_key_bytes),
            private_key_encrypted=private_key_encrypted or cls._encode_key(private_key_bytes),
        )
        
        # Save to file
        with open(agent_file, "w") as f:
            json.dump(identity.model_dump(mode='json'), f, indent=2, default=str)
        
        logger.info(f"Created agent: {name} with scopes: {scopes}")
        
        return cls(identity, private_key)
    
    @classmethod
    def load(cls, name: str, agents_dir: Optional[Path] = None) -> "Agent":
        """Load an existing agent identity.
        
        Args:
            name: The agent name
            agents_dir: Directory where agent files are stored (defaults to ~/.agent-auth/agents)
            
        Returns:
            Agent instance
            
        Raises:
            AgentNotFoundError: If agent file does not exist
            AgentError: If agent file is corrupted
        """
        if agents_dir is None:
            agents_dir = Path.home() / ".agent-auth" / "agents"
        
        agents_dir = Path(agents_dir)
        agent_file = agents_dir / f"{name}.json"
        
        if not agent_file.exists():
            raise AgentNotFoundError(f"Agent '{name}' not found")
        
        try:
            with open(agent_file, "r") as f:
                data = json.load(f)
            
            identity = AgentIdentity(**data)
        except Exception as e:
            raise AgentError(f"Failed to load agent '{name}': {e}")
        
        # Decrypt/load private key
        private_key = None
        if identity.private_key_encrypted:
            try:
                # Decode private key
                private_key_bytes = cls._decode_key(identity.private_key_encrypted)
                private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            except Exception as e:
                logger.warning(f"Failed to load private key for agent '{name}': {e}")
                # Continue without private key (can still verify signatures)
        
        return cls(identity, private_key)
    
    @classmethod
    def list_agents(cls, agents_dir: Optional[Path] = None) -> List[str]:
        """List all registered agent names.
        
        Args:
            agents_dir: Directory where agent files are stored (defaults to ~/.agent-auth/agents)
            
        Returns:
            List of agent names
        """
        if agents_dir is None:
            agents_dir = Path.home() / ".agent-auth" / "agents"
        
        agents_dir = Path(agents_dir)
        if not agents_dir.exists():
            return []
        
        return [
            f.stem
            for f in agents_dir.glob("*.json")
            if f.is_file()
        ]
    
    def sign(self, message: bytes) -> bytes:
        """Sign a message with the agent's private key.
        
        Args:
            message: The message to sign
            
        Returns:
            Signature bytes
            
        Raises:
            AgentError: If private key is not available
        """
        if self.private_key is None:
            raise AgentError("Private key not available for signing")
        
        return self.private_key.sign(message)
    
    def verify(self, message: bytes, signature: bytes) -> bool:
        """Verify a signature against a message.
        
        Args:
            message: The original message
            signature: The signature to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        if self.public_key_obj is None:
            return False
        
        try:
            self.public_key_obj.verify(signature, message)
            return True
        except InvalidSignature:
            return False
    
    def has_scope(self, domain: str) -> bool:
        """Check if agent has scope for a domain.
        
        Args:
            domain: The domain to check
            
        Returns:
            True if agent has scope for domain, False otherwise
        """
        # Normalize domain
        domain = domain.strip().lower().replace('https://', '').replace('http://', '').split('/')[0]
        
        # Check exact match or parent domain match
        for scope in self.identity.scopes:
            scope = scope.strip().lower().replace('https://', '').replace('http://', '').split('/')[0]
            if scope == domain or domain.endswith(f".{scope}"):
                return True
        
        return False
    
    def check_scope(self, domain: str) -> None:
        """Check if agent has scope for a domain, raising exception if not.
        
        Args:
            domain: The domain to check
            
        Raises:
            AgentScopeError: If agent does not have required scope
        """
        if not self.has_scope(domain):
            raise AgentScopeError(
                f"Agent '{self.identity.name}' does not have scope for domain '{domain}'. "
                f"Required scopes: {self.identity.scopes}"
            )
    
    @staticmethod
    def _encode_key(key_bytes: bytes) -> str:
        """Encode key bytes to base64 string.
        
        Args:
            key_bytes: The key bytes
            
        Returns:
            Base64 encoded string
        """
        import base64
        return base64.urlsafe_b64encode(key_bytes).decode('utf-8')
    
    @staticmethod
    def _decode_key(encoded: str) -> bytes:
        """Decode base64 string to key bytes.
        
        Args:
            encoded: The base64 encoded string
            
        Returns:
            Key bytes
        """
        import base64
        return base64.urlsafe_b64decode(encoded.encode('utf-8'))
    
    def save(self, agents_dir: Optional[Path] = None) -> None:
        """Save agent identity to file.
        
        Args:
            agents_dir: Directory to save agent file (defaults to ~/.agent-auth/agents)
            
        Raises:
            AgentError: If save fails
        """
        if agents_dir is None:
            agents_dir = Path.home() / ".agent-auth" / "agents"
        
        agents_dir = Path(agents_dir)
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        agent_file = agents_dir / f"{self.identity.name}.json"
        
        # Update public key if needed
        if self.private_key:
            public_key_bytes = self.private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            self.identity.public_key = self._encode_key(public_key_bytes)
            
            # Update private key if needed
            private_key_bytes = self.private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            self.identity.private_key_encrypted = self._encode_key(private_key_bytes)
        
        try:
            with open(agent_file, "w") as f:
                json.dump(self.identity.model_dump(), f, indent=2)
        except Exception as e:
            raise AgentError(f"Failed to save agent: {e}")

