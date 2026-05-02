"""Shared mutable state set by the global callback and read by command functions."""

from __future__ import annotations


class _AppState:
    debug: bool = False


# Single instance shared across all modules.
state = _AppState()
