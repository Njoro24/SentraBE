"""
Immutable Audit Log
Append-only audit log with SHA-256 chain verification
"""

import sqlite3
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional
import os

# Audit log database path
AUDIT_LOG_DB = os.path.join(os.path.dirname(__file__), '..', 'audit_log.db')


def _get_connection():
    """Get SQLite connection"""
    conn = sqlite3.connect(AUDIT_LOG_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _init_database():
    """Initialize audit log database if it doesn't exist"""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            entry_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()


def _hash_payload(payload: Dict[str, Any]) -> str:
    """
    Compute SHA-256 hash of payload.
    
    Args:
        payload: Dictionary to hash
    
    Returns:
        Hex-encoded SHA-256 hash
    """
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(payload_json.encode()).hexdigest()


def _compute_entry_hash(timestamp: str, event_type: str, actor: str, 
                       payload_hash: str, previous_hash: str) -> str:
    """
    Compute SHA-256 hash of audit log entry.
    
    Args:
        timestamp: Entry timestamp
        event_type: Type of event
        actor: Actor performing the action
        payload_hash: Hash of the payload
        previous_hash: Hash of previous entry
    
    Returns:
        Hex-encoded SHA-256 hash
    """
    entry_data = f"{timestamp}{event_type}{actor}{payload_hash}{previous_hash}"
    return hashlib.sha256(entry_data.encode()).hexdigest()


def _get_last_entry_hash() -> str:
    """
    Get the hash of the last entry in the audit log.
    
    Returns:
        Hash of last entry or "GENESIS" if no entries exist
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row[0]
    return "GENESIS"


def write_log(event_type: str, actor: str, payload: Dict[str, Any]) -> int:
    """
    Write an entry to the audit log.
    
    Args:
        event_type: Type of event (e.g., 'TOKEN_ISSUED', 'SCORE_REQUEST')
        actor: Actor performing the action (e.g., user ID, service name)
        payload: Event payload as dictionary
    
    Returns:
        ID of the inserted entry
    """
    # Initialize database if needed
    _init_database()
    
    # Compute hashes
    timestamp = datetime.utcnow().isoformat()
    payload_hash = _hash_payload(payload)
    previous_hash = _get_last_entry_hash()
    entry_hash = _compute_entry_hash(timestamp, event_type, actor, payload_hash, previous_hash)
    
    # Insert entry
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO audit_log (timestamp, event_type, actor, payload_hash, previous_hash, entry_hash)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (timestamp, event_type, actor, payload_hash, previous_hash, entry_hash))
    
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return entry_id


def verify_chain() -> bool:
    """
    Verify the integrity of the audit log chain.
    
    Returns:
        True if chain is intact
    
    Raises:
        ValueError: If chain is broken or tampered
    """
    _init_database()
    
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, timestamp, event_type, actor, payload_hash, previous_hash, entry_hash
        FROM audit_log
        ORDER BY id ASC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return True
    
    # Verify first entry
    first_row = rows[0]
    if first_row['previous_hash'] != "GENESIS":
        raise ValueError(f"First entry has invalid previous_hash: {first_row['previous_hash']}")
    
    computed_hash = _compute_entry_hash(
        first_row['timestamp'],
        first_row['event_type'],
        first_row['actor'],
        first_row['payload_hash'],
        first_row['previous_hash']
    )
    
    if computed_hash != first_row['entry_hash']:
        raise ValueError(f"Entry {first_row['id']} has invalid entry_hash")
    
    # Verify remaining entries
    for i in range(1, len(rows)):
        row = rows[i]
        prev_row = rows[i - 1]
        
        # Check that previous_hash matches previous entry's entry_hash
        if row['previous_hash'] != prev_row['entry_hash']:
            raise ValueError(f"Entry {row['id']} has invalid previous_hash chain")
        
        # Recompute entry_hash
        computed_hash = _compute_entry_hash(
            row['timestamp'],
            row['event_type'],
            row['actor'],
            row['payload_hash'],
            row['previous_hash']
        )
        
        if computed_hash != row['entry_hash']:
            raise ValueError(f"Entry {row['id']} has invalid entry_hash")
    
    return True


def get_log_entries(limit: Optional[int] = None) -> list:
    """
    Retrieve audit log entries.
    
    Args:
        limit: Maximum number of entries to retrieve
    
    Returns:
        List of audit log entries
    """
    _init_database()
    
    conn = _get_connection()
    cursor = conn.cursor()
    
    if limit:
        cursor.execute('''
            SELECT id, timestamp, event_type, actor, payload_hash, previous_hash, entry_hash
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
        ''', (limit,))
    else:
        cursor.execute('''
            SELECT id, timestamp, event_type, actor, payload_hash, previous_hash, entry_hash
            FROM audit_log
            ORDER BY id ASC
        ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def clear_audit_log():
    """Clear the audit log (for testing purposes)"""
    if os.path.exists(AUDIT_LOG_DB):
        os.remove(AUDIT_LOG_DB)
