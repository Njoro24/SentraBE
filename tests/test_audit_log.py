"""
Audit Log Tests
Tests for immutable append-only audit log with chain verification
"""

import pytest
import sys
import os
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from security.audit_log import (
    write_log, verify_chain, get_log_entries, clear_audit_log,
    _compute_entry_hash, _hash_payload, AUDIT_LOG_DB
)


class TestAuditLog:
    """Test audit log functionality"""
    
    def setup_method(self):
        """Clear audit log before each test"""
        clear_audit_log()
    
    def teardown_method(self):
        """Clear audit log after each test"""
        clear_audit_log()
    
    def test_write_ten_entries_and_verify_chain_passes(self):
        """Test that writing 10 entries and verifying chain passes"""
        # Write 10 entries
        for i in range(10):
            write_log(
                event_type=f"EVENT_{i}",
                actor=f"actor_{i}",
                payload={"index": i, "data": f"test_{i}"}
            )
        
        # Verify chain
        assert verify_chain() is True
        
        # Check entries were written
        entries = get_log_entries()
        assert len(entries) == 10
    
    def test_manually_update_entry_and_verify_chain_catches_tampering(self):
        """Test that manually updating an entry is caught by verify_chain"""
        # Write entries
        for i in range(5):
            write_log(
                event_type=f"EVENT_{i}",
                actor=f"actor_{i}",
                payload={"index": i}
            )
        
        # Tamper with an entry
        conn = sqlite3.connect(AUDIT_LOG_DB)
        cursor = conn.cursor()
        cursor.execute('UPDATE audit_log SET event_type = ? WHERE id = ?', ('TAMPERED', 2))
        conn.commit()
        conn.close()
        
        # Verify chain should fail
        with pytest.raises(ValueError):
            verify_chain()
    
    def test_fresh_log_with_one_entry_passes_verification(self):
        """Test that a fresh log with one entry passes verification"""
        write_log(
            event_type="FIRST_EVENT",
            actor="system",
            payload={"message": "genesis"}
        )
        
        assert verify_chain() is True
        
        entries = get_log_entries()
        assert len(entries) == 1
        assert entries[0]['event_type'] == "FIRST_EVENT"
        assert entries[0]['actor'] == "system"
        assert entries[0]['previous_hash'] == "GENESIS"
    
    def test_event_type_and_actor_correctly_stored_and_retrievable(self):
        """Test that event_type and actor are correctly stored and retrievable"""
        # Write entries with different types and actors
        write_log("TOKEN_ISSUED", "admin_user", {"token": "abc123"})
        write_log("SCORE_REQUEST", "client_app", {"transaction_id": "txn123"})
        write_log("TRANSACTION_STORED", "t24_adapter", {"account": "ACC123"})
        
        entries = get_log_entries()
        
        # Check first entry
        assert entries[0]['event_type'] == "TOKEN_ISSUED"
        assert entries[0]['actor'] == "admin_user"
        
        # Check second entry
        assert entries[1]['event_type'] == "SCORE_REQUEST"
        assert entries[1]['actor'] == "client_app"
        
        # Check third entry
        assert entries[2]['event_type'] == "TRANSACTION_STORED"
        assert entries[2]['actor'] == "t24_adapter"
    
    def test_chain_integrity_with_sequential_writes(self):
        """Test that chain integrity is maintained with sequential writes"""
        # Write entries
        ids = []
        for i in range(3):
            entry_id = write_log(
                event_type=f"EVENT_{i}",
                actor=f"actor_{i}",
                payload={"sequence": i}
            )
            ids.append(entry_id)
        
        # Verify chain
        assert verify_chain() is True
        
        # Get entries and check chain
        entries = get_log_entries()
        
        # First entry should have GENESIS as previous
        assert entries[0]['previous_hash'] == "GENESIS"
        
        # Second entry should reference first
        assert entries[1]['previous_hash'] == entries[0]['entry_hash']
        
        # Third entry should reference second
        assert entries[2]['previous_hash'] == entries[1]['entry_hash']
    
    def test_empty_log_passes_verification(self):
        """Test that an empty log passes verification"""
        assert verify_chain() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
