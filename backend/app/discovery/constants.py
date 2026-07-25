"""Shared constants for live discovery.

Kept dependency-free so the API request path does not import the ingestion
pipeline just to validate a module name.
"""

from __future__ import annotations

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

DEFAULT_MODULE = "hackathon"
ALLOWED_MODULES = frozenset({"hackathon", "ai_offer"})
