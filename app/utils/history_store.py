"""
VOLTERRA - History Store (Compatibility Layer)
==============================================
Re-exports canonical HistoryStore from storage.history_store.
"""

from storage.history_store import HistoryStore, history_store

__all__ = ["HistoryStore", "history_store"]
