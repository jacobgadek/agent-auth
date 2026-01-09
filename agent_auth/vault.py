"""Encrypted vault for storing browser sessions."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from cryptography.fernet import InvalidToken

from agent_auth.crypto import (
    decrypt_data,
    encrypt_data,
    generate_salt,
    hash_password,
)
from agent_auth.models import Session

logger = logging.getLogger(__name__)


class VaultError(Exception):
    """Base exception for vault operations."""
    pass


class VaultNotInitializedError(VaultError):
    """Raised when vault is not initialized."""
    pass


class VaultAuthenticationError(VaultError):
    """Raised when vault authentication fails."""
    pass


class Vault:
    """Encrypted vault for storing browser sessions.
    
    The vault stores sessions in an encrypted SQLite database at
    ~/.agent-auth/vault.db. Sessions are encrypted using a master
    password via PBKDF2 key derivation.
    
    Attributes:
        vault_dir: Directory where vault database is stored
        db_path: Path to the SQLite database file
        config_path: Path to the vault configuration file
        password: The master password (stored in memory)
        salt: The salt used for encryption
    """
    
    def __init__(self, vault_dir: Optional[Path] = None):
        """Initialize vault with a directory path.
        
        Args:
            vault_dir: Custom vault directory. Defaults to ~/.agent-auth
        """
        if vault_dir is None:
            vault_dir = Path.home() / ".agent-auth"
        
        self.vault_dir = Path(vault_dir)
        self.db_path = self.vault_dir / "vault.db"
        self.config_path = self.vault_dir / "vault.json"
        self.password: Optional[str] = None
        self.salt: Optional[bytes] = None
        self._connection: Optional[sqlite3.Connection] = None
        
    def is_initialized(self) -> bool:
        """Check if the vault is initialized.
        
        Returns:
            True if vault is initialized, False otherwise
        """
        return self.db_path.exists() and self.config_path.exists()
    
    def initialize(self, password: str) -> None:
        """Initialize the vault with a master password.
        
        Args:
            password: The master password for encryption
            
        Raises:
            VaultError: If vault is already initialized
        """
        if self.is_initialized():
            raise VaultError("Vault is already initialized")
        
        # Create vault directory
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate salt for encryption
        self.salt = generate_salt()
        
        # Store configuration
        config = {
            "salt": self.salt.hex(),
            "password_hash": hash_password(password),
            "initialized_at": datetime.utcnow().isoformat(),
        }
        
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)
        
        # Create database schema
        self.password = password
        self._create_schema()
        
        logger.info(f"Vault initialized at {self.db_path}")
    
    def unlock(self, password: str) -> None:
        """Unlock the vault with a master password.
        
        Args:
            password: The master password
            
        Raises:
            VaultNotInitializedError: If vault is not initialized
            VaultAuthenticationError: If password is incorrect
        """
        if not self.is_initialized():
            raise VaultNotInitializedError("Vault is not initialized. Run 'agent-auth init' first.")
        
        # Load configuration
        with open(self.config_path, "r") as f:
            config = json.load(f)
        
        # Verify password
        expected_hash = hash_password(password)
        if config["password_hash"] != expected_hash:
            raise VaultAuthenticationError("Incorrect password")
        
        # Load salt and set password
        self.salt = bytes.fromhex(config["salt"])
        self.password = password
        
        # Test encryption/decryption to ensure password is correct
        try:
            test_data = b"test"
            encrypted = encrypt_data(test_data, self.password, self.salt)
            decrypt_data(encrypted, self.password, self.salt)
        except InvalidToken:
            raise VaultAuthenticationError("Incorrect password")
        
        logger.debug("Vault unlocked successfully")
    
    def _ensure_unlocked(self) -> None:
        """Ensure vault is unlocked.
        
        Raises:
            VaultNotInitializedError: If vault is not initialized
            VaultError: If vault is not unlocked
        """
        if not self.is_initialized():
            raise VaultNotInitializedError("Vault is not initialized")
        if self.password is None or self.salt is None:
            raise VaultError("Vault is not unlocked. Call unlock() first.")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection, creating if necessary.
        
        Returns:
            SQLite connection
            
        Raises:
            VaultError: If vault is not unlocked
        """
        self._ensure_unlocked()
        
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
        
        return self._connection
    
    def _create_schema(self) -> None:
        """Create database schema.
        
        Note: This method creates the connection directly without checking
        if the vault is initialized, since it's called during initialization
        when the database doesn't exist yet.
        """
        # Create connection directly (bypass _get_connection() which requires unlock check)
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                cookies_encrypted BLOB NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                UNIQUE(domain)
            )
        """)
        
        # Access logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS access_logs (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                domain TEXT NOT NULL,
                accessed_at TEXT NOT NULL
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_domain ON sessions(domain)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_agent_id ON access_logs(agent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_domain ON access_logs(domain)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_accessed_at ON access_logs(accessed_at)")
        
        conn.commit()
        conn.close()
    
    def store_session(
        self,
        domain: str,
        cookies: Dict,
        expires_at: datetime,
        session_id: Optional[UUID] = None,
    ) -> Session:
        """Store a session in the vault.
        
        Args:
            domain: The domain for this session
            cookies: Dictionary of cookie name-value pairs
            expires_at: When the session expires
            session_id: Optional UUID for the session (generated if not provided)
            
        Returns:
            The stored Session object
            
        Raises:
            VaultError: If vault is not unlocked or operation fails
        """
        self._ensure_unlocked()
        
        # Normalize domain
        domain = domain.strip().lower().replace('https://', '').replace('http://', '').split('/')[0]
        
        # Create session model
        from uuid import uuid4
        session = Session(
            id=session_id or uuid4(),
            domain=domain,
            cookies=cookies,
            expires_at=expires_at,
        )
        
        # Encrypt cookies
        cookies_json = json.dumps(cookies).encode('utf-8')
        encrypted_cookies = encrypt_data(cookies_json, self.password, self.salt)
        
        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO sessions
            (id, domain, cookies_encrypted, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(session.id),
            session.domain,
            encrypted_cookies,
            session.created_at.isoformat(),
            session.expires_at.isoformat(),
        ))
        
        conn.commit()
        
        logger.info(f"Stored session for domain: {domain}")
        return session
    
    def get_session(self, domain: str) -> Optional[Session]:
        """Retrieve a session from the vault.
        
        Args:
            domain: The domain to retrieve session for
            
        Returns:
            Session object if found, None otherwise
            
        Raises:
            VaultError: If vault is not unlocked or decryption fails
        """
        self._ensure_unlocked()
        
        # Normalize domain
        domain = domain.strip().lower().replace('https://', '').replace('http://', '').split('/')[0]
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, domain, cookies_encrypted, created_at, expires_at
            FROM sessions
            WHERE domain = ?
        """, (domain,))
        
        row = cursor.fetchone()
        if row is None:
            return None
        
        try:
            # Decrypt cookies
            encrypted_cookies = row["cookies_encrypted"]
            cookies_json = decrypt_data(encrypted_cookies, self.password, self.salt)
            cookies = json.loads(cookies_json.decode('utf-8'))
            
            # Build session object
            session = Session(
                id=UUID(row["id"]),
                domain=row["domain"],
                cookies=cookies,
                created_at=datetime.fromisoformat(row["created_at"]),
                expires_at=datetime.fromisoformat(row["expires_at"]),
            )
            
            return session
        except InvalidToken as e:
            raise VaultError(f"Failed to decrypt session: {e}")
        except json.JSONDecodeError as e:
            raise VaultError(f"Failed to parse session cookies: {e}")
    
    def list_sessions(self) -> List[Session]:
        """List all stored sessions.
        
        Returns:
            List of Session objects
            
        Raises:
            VaultError: If vault is not unlocked
        """
        self._ensure_unlocked()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, domain, cookies_encrypted, created_at, expires_at
            FROM sessions
            ORDER BY domain
        """)
        
        sessions = []
        for row in cursor.fetchall():
            try:
                # Decrypt cookies
                encrypted_cookies = row["cookies_encrypted"]
                cookies_json = decrypt_data(encrypted_cookies, self.password, self.salt)
                cookies = json.loads(cookies_json.decode('utf-8'))
                
                # Build session object
                session = Session(
                    id=UUID(row["id"]),
                    domain=row["domain"],
                    cookies=cookies,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]),
                )
                sessions.append(session)
            except (InvalidToken, json.JSONDecodeError) as e:
                logger.warning(f"Failed to decrypt session {row['domain']}: {e}")
                continue
        
        return sessions
    
    def delete_session(self, domain: str) -> bool:
        """Delete a session from the vault.
        
        Args:
            domain: The domain to delete session for
            
        Returns:
            True if session was deleted, False if not found
            
        Raises:
            VaultError: If vault is not unlocked
        """
        self._ensure_unlocked()
        
        # Normalize domain
        domain = domain.strip().lower().replace('https://', '').replace('http://', '').split('/')[0]
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM sessions WHERE domain = ?", (domain,))
        deleted = cursor.rowcount > 0
        conn.commit()
        
        if deleted:
            logger.info(f"Deleted session for domain: {domain}")
        
        return deleted
    
    def log_access(
        self,
        agent_id: UUID,
        agent_name: str,
        domain: str,
        accessed_at: Optional[datetime] = None,
    ) -> None:
        """Log a session access event.
        
        Args:
            agent_id: UUID of the agent
            agent_name: Name of the agent
            domain: Domain of the accessed session
            accessed_at: When access occurred (defaults to now)
            
        Raises:
            VaultError: If vault is not unlocked
        """
        self._ensure_unlocked()
        
        if accessed_at is None:
            accessed_at = datetime.utcnow()
        
        from uuid import uuid4
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO access_logs
            (id, agent_id, agent_name, domain, accessed_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(uuid4()),
            str(agent_id),
            agent_name,
            domain,
            accessed_at.isoformat(),
        ))
        
        conn.commit()
    
    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

