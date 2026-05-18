"""Pytest configuration: force mock mode so tests never hit the network."""

from __future__ import annotations

import os

# Set BEFORE the app imports its settings module.
os.environ.setdefault("LLM_MODE", "mock")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("AGENT_MAX_ITERATIONS", "6")
os.environ.setdefault("LOG_LEVEL", "WARNING")
