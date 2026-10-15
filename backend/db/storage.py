"""
Re-export module from app.db.storage to maintain backward compatibility
and prevent duplicate engine drift.
"""
from app.db.storage import LocalStorageEngine, storage

__all__ = ["LocalStorageEngine", "storage"]
