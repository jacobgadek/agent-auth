"""Pydantic models for AgentAuth."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class Session(BaseModel):
    """Model representing a stored browser session.
    
    Attributes:
        id: Unique session identifier
        domain: The domain this session belongs to (e.g., "linkedin.com")
        cookies: Dictionary of cookie name-value pairs
        created_at: When the session was created
        expires_at: When the session expires
    """
    
    id: UUID = Field(default_factory=uuid4)
    domain: str
    cookies: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    
    @field_validator('domain')
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain format."""
        v = v.strip().lower()
        if not v:
            raise ValueError("Domain cannot be empty")
        # Remove protocol if present
        v = v.replace('https://', '').replace('http://', '').split('/')[0]
        return v
    
    @field_validator('cookies')
    @classmethod
    def validate_cookies(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cookies are a dictionary."""
        if not isinstance(v, dict):
            raise ValueError("Cookies must be a dictionary")
        return v
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class AgentIdentity(BaseModel):
    """Model representing an agent's identity.
    
    Attributes:
        id: Unique agent identifier (UUID)
        name: Human-readable agent name
        scopes: List of domains this agent has access to
        public_key: Ed25519 public key (base64 encoded)
        private_key_encrypted: Ed25519 private key (encrypted, base64 encoded)
        created_at: When the agent identity was created
    """
    
    id: UUID = Field(default_factory=uuid4)
    name: str
    scopes: List[str] = Field(default_factory=list)
    public_key: str  # Base64 encoded Ed25519 public key
    private_key_encrypted: Optional[str] = None  # Base64 encoded encrypted private key
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name."""
        v = v.strip()
        if not v:
            raise ValueError("Agent name cannot be empty")
        # Allow alphanumeric, hyphens, underscores
        if not all(c.isalnum() or c in ('-', '_') for c in v):
            raise ValueError("Agent name must contain only alphanumeric characters, hyphens, and underscores")
        return v
    
    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Validate and normalize scopes."""
        normalized = []
        for scope in v:
            scope = scope.strip().lower()
            # Remove protocol if present
            scope = scope.replace('https://', '').replace('http://', '').split('/')[0]
            if scope and scope not in normalized:
                normalized.append(scope)
        return normalized
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class SessionAccessLog(BaseModel):
    """Model for logging session access events.
    
    Attributes:
        id: Unique log entry identifier
        agent_id: UUID of the agent that accessed the session
        agent_name: Name of the agent
        domain: Domain of the accessed session
        accessed_at: When the access occurred
    """
    
    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    agent_name: str
    domain: str
    accessed_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }

